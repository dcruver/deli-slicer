// deli's binding to PrusaSlicer's libslic3r. The surface is deliberately narrow:
// one call that loads a model, transforms it, slices it and writes the G-code,
// one that measures a model, one that hands its triangles to a viewer, one that sorts
// the settings of an INI file into printer, process and filament, and one that lists
// the settings of each of those kinds.

#include <algorithm>
#include <array>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>

#include <boost/property_tree/ini_parser.hpp>
#include <boost/property_tree/ptree.hpp>

#include <nanobind/nanobind.h>
#include <nanobind/stl/array.h>
#include <nanobind/stl/map.h>
#include <nanobind/stl/pair.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/tuple.h>
#include <nanobind/stl/vector.h>

#include "libslic3r/libslic3r.h"
#include "libslic3r/BuildVolume.hpp"
#include "libslic3r/ClipperUtils.hpp"
#include "libslic3r/Config.hpp"
#include "libslic3r/FileReader.hpp"
#include "libslic3r/Model.hpp"
#include "libslic3r/MultipleBeds.hpp"
#include "libslic3r/Preset.hpp"
#include "libslic3r/Print.hpp"
#include "libslic3r/PrintConfig.hpp"
#include <arrange-wrapper/Arrange.hpp>
#include <arrange-wrapper/ModelArrange.hpp>

namespace nb = nanobind;
using namespace nb::literals;
using namespace Slic3r;

namespace {

struct SliceResult
{
    std::string              gcode_path;
    double                   print_time;
    double                   filament_mm;
    double                   filament_g;
    std::vector<std::string> warnings;
};

// The settings in `ini` as given, with names from older PrusaSlicer versions updated.
// PrusaSlicer treats a setting it does not know as an obsolete one and silently drops it.
// A misspelt setting must not be ignored, so the keys are checked one by one here: unknown
// ones are collected in `unknown`, or are an error when the caller does not ask for them.
DynamicPrintConfig parse_config(const std::string &ini, std::vector<std::string> *unknown = nullptr)
{
    boost::property_tree::ptree tree;
    std::istringstream          stream(ini);
    try {
        boost::property_tree::read_ini(stream, tree);
    } catch (const boost::property_tree::ini_parser_error &err) {
        throw std::invalid_argument("config is not valid INI: " + err.message() + " (line " +
                                    std::to_string(err.line()) + ")");
    }

    DynamicPrintConfig        config;
    ConfigSubstitutionContext substitutions(ForwardCompatibilitySubstitutionRule::Disable);
    std::vector<std::string>  dropped;
    for (const auto &entry : tree) {
        // handle_legacy() renames settings from older versions and clears the key of
        // anything that is not a setting any more, or never was.
        t_config_option_key key   = entry.first;
        std::string         value = entry.second.get_value<std::string>();
        PrintConfigDef::handle_legacy(key, value);
        if (key.empty()) {
            dropped.push_back(entry.first);
            continue;
        }
        try {
            config.set_deserialize(key, value, substitutions);
        } catch (const std::exception &err) {
            throw std::invalid_argument("bad value for setting " + entry.first + ": " + err.what());
        }
    }
    if (unknown)
        *unknown = dropped;
    else if (!dropped.empty()) {
        std::string names;
        for (const std::string &name : dropped)
            names += (names.empty() ? "" : ", ") + name;
        throw std::invalid_argument("unknown or obsolete settings: " + names);
    }

    config.handle_legacy_composite();
    return config;
}

// A configuration PrusaSlicer can slice with: normalised, validated, and with every
// setting that was left out filled in with PrusaSlicer's default.
DynamicPrintConfig complete_config(DynamicPrintConfig config)
{
    config.normalize_fdm();
    config.option<ConfigOptionEnum<PrinterTechnology>>("printer_technology", true)->value = ptFFF;

    FullPrintConfig full;
    full.apply(config, true);
    config.apply(full, true);

    if (std::string err = config.validate(); !err.empty())
        throw std::invalid_argument("invalid configuration: " + err);
    return config;
}

// A part of a print: a model file, per-axis scale factors, angles in degrees about X, Y
// and Z (applied in that order after scaling), and how many copies to print.
using Part = std::tuple<std::string, std::array<double, 3>, std::array<double, 3>, int>;

// The model in a file, scaled by per-axis factors and then turned about X, Y and Z, in
// that order, by angles in degrees; every object of it is then dropped onto the bed.
Model load_transformed(const std::string &model_path, const std::array<double, 3> &scale,
                       const std::array<double, 3> &rotate, int count = 1)
{
    Model model = FileReader::load_model(model_path);
    for (ModelObject *object : model.objects) {
        object->scale(Vec3d(scale[0], scale[1], scale[2]));
        object->rotate(Geometry::deg2rad(rotate[0]), X);
        object->rotate(Geometry::deg2rad(rotate[1]), Y);
        object->rotate(Geometry::deg2rad(rotate[2]), Z);
        for (int copy = 1; copy < count; ++copy)
            object->add_instance(*object->instances.front());
        object->ensure_on_bed();
    }
    return model;
}

// Whether every copy of every object stands within the bed's outline. PrusaSlicer's own
// test uses the outline's convex hull, which cannot see a cut-out corner, so this one
// clips each footprint against the outline itself.
bool on_the_bed(const Model &model, const Points &bed)
{
    const Polygons outline{Polygon(bed)};
    for (const ModelObject *object : model.objects)
        for (size_t i = 0; i < object->instances.size(); ++i) {
            const BoundingBoxf3 box = object->instance_bounding_box(i);
            const BoundingBox footprint(Point::new_scale(box.min.x(), box.min.y()), Point::new_scale(box.max.x(), box.max.y()));
            if (!diff_ex(Polygons{footprint.polygon()}, outline).empty())
                return false;
        }
    return true;
}

// All the parts of a print in one model, each transformed, then arranged on the bed as
// PrusaSlicer's command line would: spread out with the process's spacing, and a single
// object centred. The bed may be any polygon, so a printer's unusable corner can be cut
// out of its bed_shape and the parts keep clear of it.
Model load_arranged(const std::vector<Part> &parts, const DynamicPrintConfig &config)
{
    Model model;
    for (const auto &[path, scale, rotate, count] : parts) {
        Model one = load_transformed(path, scale, rotate, count);
        for (const ModelObject *object : one.objects)
            model.add_object(*object);
    }
    arr2::ArrangeSettings arrange;
    arrange.set_distance_from_objects(min_object_distance(config));
    const Points bed = get_bed_shape(config);

    // On a rectangle PrusaSlicer centres what it arranges; on any other polygon it packs
    // towards an edge. So arrange on the bed's rectangle first, and only when something
    // then lands outside the real outline (in a cut-out corner) arrange on the outline.
    arrange_objects(model, arr2::ArrangeBed{arr2::RectangleBed{BoundingBox(bed), Vec2crd{0, 0}}}, arrange);
    if (!on_the_bed(model, bed)) {
        arrange_objects(model, arr2::to_arrange_bed(bed, Vec2crd{0, 0}), arrange);
        if (!on_the_bed(model, bed))
            throw std::runtime_error("the parts do not fit on the bed, keeping clear of the part of it that cannot be printed on");
    }
    return model;
}

SliceResult slice(const std::vector<Part> &parts, const std::string &config_ini, const std::string &output_path)
{
    nb::gil_scoped_release release;

    DynamicPrintConfig config = complete_config(parse_config(config_ini));
    Model              model  = load_arranged(parts, config);

    Print print;
    print.set_status_silent();
    for (ModelObject *object : model.objects)
        print.auto_assign_extruders(object);

    const Pointfs bed_shape = config.option<ConfigOptionPoints>("bed_shape")->values;
    s_multiple_beds.update_build_volume(BoundingBoxf(bed_shape));
    model.update_print_volume_state(BuildVolume(bed_shape, config.opt_float("max_print_height")));
    MultipleBedsUtils::with_single_bed_model_fff(model, 0, [&]() { print.apply(model, config); });

    SliceResult result;
    if (std::string err = print.validate(&result.warnings); !err.empty())
        throw std::runtime_error(err);
    if (print.empty())
        throw std::runtime_error("nothing to print: the object is not fully inside the print volume");

    print.process();
    result.gcode_path = print.export_gcode(output_path, nullptr, nullptr);

    const PrintStatistics &stats = print.print_statistics();
    result.print_time  = stats.normal_print_time_seconds;
    result.filament_mm = stats.total_used_filament;
    result.filament_g  = stats.total_weight;
    return result;
}

// Extent of the model in a file along X, Y and Z, in millimetres, once scaled and turned.
std::array<double, 3> model_size(const std::string &model_path, std::array<double, 3> scale, std::array<double, 3> rotate)
{
    nb::gil_scoped_release release;

    const Model model = load_transformed(model_path, scale, rotate);
    const Vec3d size  = model.bounding_box_exact().size();
    return {size.x(), size.y(), size.z()};
}

// The triangles of every part, every copy, placed on the bed exactly as `slice` places
// them. Vertices are float32 x, y, z; triangles are three uint32 vertex indices each.
std::pair<nb::bytes, nb::bytes> mesh(const std::vector<Part> &parts, const std::string &config_ini)
{
    std::vector<float>    vertices;
    std::vector<uint32_t> triangles;
    {
        nb::gil_scoped_release release;

        const DynamicPrintConfig config = complete_config(parse_config(config_ini));
        const Model              model  = load_arranged(parts, config);
        for (const ModelObject *object : model.objects) {
            const TriangleMesh m    = object->mesh();
            const uint32_t     base = uint32_t(vertices.size() / 3);
            for (const Vec3f &v : m.its.vertices)
                vertices.insert(vertices.end(), {v.x(), v.y(), v.z()});
            for (const Vec3i &t : m.its.indices)
                triangles.insert(triangles.end(), {base + uint32_t(t(0)), base + uint32_t(t(1)), base + uint32_t(t(2))});
        }
    }
    return {nb::bytes(reinterpret_cast<const char *>(vertices.data()), vertices.size() * sizeof(float)),
            nb::bytes(reinterpret_cast<const char *>(triangles.data()), triangles.size() * sizeof(uint32_t))};
}

using Settings = std::map<std::string, std::string>;

// Sort the settings of an INI file by the kind of preset PrusaSlicer keeps them in.
// Returns the groups and the names of settings this engine does not know.
std::pair<std::map<std::string, Settings>, std::vector<std::string>> split_config(const std::string &ini)
{
    std::vector<std::string> unknown;
    const DynamicPrintConfig config = parse_config(ini, &unknown);
    complete_config(config); // throws when the values do not make a valid configuration

    // Each kind's settings, and the setting PrusaSlicer keeps that preset's name in.
    const std::tuple<const char *, const std::vector<std::string> &, const char *> kinds[] = {
        {"printer", Preset::printer_options(), "printer_settings_id"},
        {"process", Preset::print_options(), "print_settings_id"},
        {"filament", Preset::filament_options(), "filament_settings_id"},
    };
    std::map<std::string, Settings> groups;
    for (const auto &[kind, keys, name_key] : kinds) {
        for (const std::string &key : keys)
            if (config.has(key))
                groups[kind][key] = config.opt_serialize(key);
        if (!groups[kind].empty() && config.has(name_key))
            groups[kind][name_key] = config.opt_serialize(name_key);
    }
    return {groups, unknown};
}

// PrusaSlicer's default for one setting, as it writes it.
std::string setting_default(const std::string &key)
{
    const FullPrintConfig full;
    if (!full.has(key))
        throw std::invalid_argument("no setting named " + key);
    return full.opt_serialize(key);
}

// Every setting PrusaSlicer keeps in a printer, a process and a filament preset.
std::map<std::string, std::vector<std::string>> setting_names()
{
    return {
        {"printer", Preset::printer_options()},
        {"process", Preset::print_options()},
        {"filament", Preset::filament_options()},
    };
}

} // namespace

NB_MODULE(_engine, m)
{
    m.doc() = "In-process slicing with PrusaSlicer's libslic3r.";
    m.attr("SLIC3R_VERSION") = SLIC3R_VERSION;
    // Bumped whenever a call's signature changes, so that Python run against an older
    // build of this module (an editable install after a C++ change) says so plainly.
    m.attr("API_VERSION") = 3;

    nb::class_<SliceResult>(m, "SliceResult")
        .def_ro("gcode_path", &SliceResult::gcode_path, "Path the G-code was written to.")
        .def_ro("print_time", &SliceResult::print_time, "Estimated print time in seconds.")
        .def_ro("filament_mm", &SliceResult::filament_mm, "Filament used, in millimetres.")
        .def_ro("filament_g", &SliceResult::filament_g, "Filament used, in grams.")
        .def_ro("warnings", &SliceResult::warnings, "Warnings PrusaSlicer raised while validating the print.");

    m.def("slice", &slice, "parts"_a, "config"_a, "output"_a,
          "Slice the parts of a print and write G-code to `output`.\n\n"
          "Each part is (model file, scale, rotate, count): per-axis scale factors, degrees about\n"
          "X, Y and Z applied in that order after scaling, and the number of copies. The parts are\n"
          "dropped onto the bed and arranged on it. `config` is PrusaSlicer INI text; settings it\n"
          "leaves out take PrusaSlicer's defaults.");

    m.def("model_size", &model_size, "model"_a, nb::kw_only(),
          "scale"_a = std::array<double, 3>{1., 1., 1.}, "rotate"_a = std::array<double, 3>{0., 0., 0.},
          "Extent of the model in a file along X, Y and Z, in millimetres, after `scale` and\n"
          "`rotate` are applied as `slice` applies them.\n\n"
          "Raises RuntimeError when the file cannot be read as a model.");

    m.def("mesh", &mesh, "parts"_a, "config"_a,
          "The triangles of every part and copy, placed on the bed as `slice` places them: a pair\n"
          "of bytes, float32 vertex coordinates and uint32 triangle vertex indices.");

    m.def("split_config", &split_config, "config"_a,
          "Sort the settings in PrusaSlicer INI text into 'printer', 'process' and 'filament'.\n\n"
          "Returns the groups, each a dict of setting name to value, and a list of the settings\n"
          "this version of PrusaSlicer does not know. Bad values raise ValueError.");

    m.def("setting_default", &setting_default, "key"_a, "PrusaSlicer's default for a setting, as it writes it.");

    m.def("setting_names", &setting_names,
          "The names of the settings PrusaSlicer keeps in a 'printer', a 'process' and a 'filament'.");
}
