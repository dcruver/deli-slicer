// deli's binding to PrusaSlicer's libslic3r. The surface is deliberately narrow:
// one call that loads a model, transforms it, slices it and writes the G-code,
// one that measures a model, one that sorts the settings of an INI file into printer,
// process and filament, and one that lists the settings of each of those kinds.

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
#include <nanobind/stl/vector.h>

#include "libslic3r/libslic3r.h"
#include "libslic3r/BuildVolume.hpp"
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

// The model in a file, scaled by per-axis factors and then turned about X, Y and Z, in
// that order, by angles in degrees; every object of it is then dropped onto the bed.
Model load_transformed(const std::string &model_path, const std::array<double, 3> &scale,
                       const std::array<double, 3> &rotate)
{
    Model model = FileReader::load_model(model_path);
    for (ModelObject *object : model.objects) {
        object->scale(Vec3d(scale[0], scale[1], scale[2]));
        object->rotate(Geometry::deg2rad(rotate[0]), X);
        object->rotate(Geometry::deg2rad(rotate[1]), Y);
        object->rotate(Geometry::deg2rad(rotate[2]), Z);
        object->ensure_on_bed();
    }
    return model;
}

SliceResult slice(const std::string &model_path, const std::string &config_ini, const std::string &output_path,
                  std::array<double, 3> scale, std::array<double, 3> rotate)
{
    nb::gil_scoped_release release;

    DynamicPrintConfig config = complete_config(parse_config(config_ini));
    Model              model  = load_transformed(model_path, scale, rotate);

    // Same placement as PrusaSlicer's command line: arranged on the bed, which centres a single object.
    arr2::ArrangeSettings arrange;
    arrange.set_distance_from_objects(min_object_distance(config));
    arrange_objects(model, arr2::to_arrange_bed(get_bed_shape(config), Vec2crd{0, 0}), arrange);

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

    nb::class_<SliceResult>(m, "SliceResult")
        .def_ro("gcode_path", &SliceResult::gcode_path, "Path the G-code was written to.")
        .def_ro("print_time", &SliceResult::print_time, "Estimated print time in seconds.")
        .def_ro("filament_mm", &SliceResult::filament_mm, "Filament used, in millimetres.")
        .def_ro("filament_g", &SliceResult::filament_g, "Filament used, in grams.")
        .def_ro("warnings", &SliceResult::warnings, "Warnings PrusaSlicer raised while validating the print.");

    m.def("slice", &slice, "model"_a, "config"_a, "output"_a, nb::kw_only(),
          "scale"_a = std::array<double, 3>{1., 1., 1.}, "rotate"_a = std::array<double, 3>{0., 0., 0.},
          "Slice one model file and write G-code to `output`.\n\n"
          "`config` is PrusaSlicer INI text; settings it leaves out take PrusaSlicer's defaults.\n"
          "`scale` holds per-axis factors and `rotate` degrees about X, Y and Z, applied in that\n"
          "order after scaling. The object is then dropped onto the bed and centred.");

    m.def("model_size", &model_size, "model"_a, nb::kw_only(),
          "scale"_a = std::array<double, 3>{1., 1., 1.}, "rotate"_a = std::array<double, 3>{0., 0., 0.},
          "Extent of the model in a file along X, Y and Z, in millimetres, after `scale` and\n"
          "`rotate` are applied as `slice` applies them.\n\n"
          "Raises RuntimeError when the file cannot be read as a model.");

    m.def("split_config", &split_config, "config"_a,
          "Sort the settings in PrusaSlicer INI text into 'printer', 'process' and 'filament'.\n\n"
          "Returns the groups, each a dict of setting name to value, and a list of the settings\n"
          "this version of PrusaSlicer does not know. Bad values raise ValueError.");

    m.def("setting_names", &setting_names,
          "The names of the settings PrusaSlicer keeps in a 'printer', a 'process' and a 'filament'.");
}
