// deli's binding to PrusaSlicer's libslic3r. The surface is deliberately narrow:
// one call that loads a model, transforms it, slices it and writes the G-code,
// one that measures a model, one that hands its triangles to a viewer, one that reads
// the extrusions back out of a G-code file for the viewer, one that sorts the settings
// of an INI file into printer, process and filament, and one that lists the settings
// of each of those kinds.

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <limits>
#include <map>
#include <memory>
#include <optional>
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
#include <nanobind/stl/optional.h>
#include <nanobind/stl/pair.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/tuple.h>
#include <nanobind/stl/vector.h>

#include "libslic3r/libslic3r.h"
#include "libslic3r/BuildVolume.hpp"
#include "libslic3r/ClipperUtils.hpp"
#include "libslic3r/Config.hpp"
#include "libslic3r/CustomGCode.hpp"
#include "libslic3r/ExtrusionRole.hpp"
#include "libslic3r/FileReader.hpp"
#include "libslic3r/GCode/GCodeProcessor.hpp"
#include "libslic3r/GCode/ThumbnailData.hpp"
#include "libslic3r/Layer.hpp"
#include "libslic3r/Model.hpp"
#include "libslic3r/MultipleBeds.hpp"
#include "libslic3r/Preset.hpp"
#include "libslic3r/Print.hpp"
#include "libslic3r/PrintConfig.hpp"
#include <arrange-wrapper/Arrange.hpp>
#include <arrange-wrapper/ModelArrange.hpp>
#include <arrange-wrapper/SceneBuilder.hpp>

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
    std::vector<std::pair<int, double>> pauses; // the layer each pause comes after, and how high the print is by then
    int                      layers;     // as the G-code counts them: see layer_tops
    double                   height;     // of the top of the last one, in mm
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
// and Z (applied in that order after scaling), how many copies to print, where on the bed
// its middle is to be (x and y in millimetres; left out, it is arranged), and how far its
// underside is above the bed (negative: sunk into it, and what is below is not printed).
using Part = std::tuple<std::string, std::array<double, 3>, std::array<double, 3>, int, std::optional<std::array<double, 2>>, double>;

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
bool on_the_bed(const ModelObjectPtrs &objects, const Points &bed)
{
    const Polygons outline{Polygon(bed)};
    for (const ModelObject *object : objects)
        for (size_t i = 0; i < object->instances.size(); ++i) {
            const BoundingBoxf3 box = object->instance_bounding_box(i);
            const BoundingBox footprint(Point::new_scale(box.min.x(), box.min.y()), Point::new_scale(box.max.x(), box.max.y()));
            if (!diff_ex(Polygons{footprint.polygon()}, outline).empty())
                return false;
        }
    return true;
}

// Which copies PrusaSlicer's arrange places: those of the parts that were not given a place
// of their own. The others stay where they are, and what is arranged keeps clear of them.
struct Unplaced : arr2::SelectionMask
{
    std::vector<std::vector<bool>> copies; // per object, per copy

    std::vector<bool> selected_objects() const override
    {
        std::vector<bool> objects;
        for (const std::vector<bool> &object : copies)
            objects.push_back(std::find(object.begin(), object.end(), true) != object.end());
        return objects;
    }
    std::vector<bool> selected_instances(int object) const override { return object < int(copies.size()) ? copies[object] : std::vector<bool>{}; }
    bool              is_wipe_tower_selected(int) const override { return false; }
};

// All the parts of a print in one model, each transformed, then arranged on the bed as
// PrusaSlicer's command line would: spread out with the process's spacing, and a single
// object centred. A part that was given a place stays there, and the others are arranged
// around it. The bed may be any polygon, so a printer's unusable corner can be cut out of
// its bed_shape and the parts keep clear of it.
Model load_arranged(const std::vector<Part> &parts, const DynamicPrintConfig &config, std::vector<size_t> *objects_per_part = nullptr)
{
    const Points bed = get_bed_shape(config);
    Model        model;
    Unplaced     unplaced;
    bool         any_unplaced = false;
    for (const auto &[path, scale, rotate, count, place, height] : parts) {
        if (place && count > 1)
            throw std::runtime_error(path + " has a place of its own on the bed, which a part with copies cannot have");
        Model one = load_transformed(path, scale, rotate, count);
        // A file is moved as a whole, so that its objects stay as they are to each other.
        Vec3d shift(0, 0, height);
        if (place) {
            const Vec3d middle = one.bounding_box_exact().center();
            shift += Vec3d((*place)[0] - middle.x(), (*place)[1] - middle.y(), 0);
        }
        for (ModelObject *object : one.objects)
            for (ModelInstance *copy : object->instances)
                copy->set_offset(copy->get_offset() + shift);
        if (place && !on_the_bed(one.objects, bed))
            throw std::runtime_error(path + " is not on the bed where it has been moved to");
        for (const ModelObject *object : one.objects) {
            model.add_object(*object);
            unplaced.copies.emplace_back(object->instances.size(), !place);
        }
        if (objects_per_part)
            objects_per_part->push_back(one.objects.size());
        any_unplaced |= !place;
    }
    if (!any_unplaced)
        return model;

    arr2::ArrangeSettings settings;
    settings.set_distance_from_objects(min_object_distance(config));
    const auto arrange_on = [&](const arr2::ArrangeBed &on) {
        arr2::arrange(arr2::SceneBuilder{}.set_bed(on).set_arrange_settings(settings).set_model(model).set_selection(&unplaced));
    };

    // On a rectangle PrusaSlicer centres what it arranges; on any other polygon it packs
    // towards an edge. So arrange on the bed's rectangle first, and only when something
    // then lands outside the real outline (in a cut-out corner) arrange on the outline.
    arrange_on(arr2::ArrangeBed{arr2::RectangleBed{BoundingBox(bed), Vec2crd{0, 0}}});
    if (!on_the_bed(model.objects, bed)) {
        arrange_on(arr2::to_arrange_bed(bed, Vec2crd{0, 0}));
        if (!on_the_bed(model.objects, bed))
            throw std::runtime_error("the parts do not fit on the bed, keeping clear of the part of it that cannot be printed on");
    }
    return model;
}

// A picture of the parts for the printer's screen. libslic3r leaves thumbnails to
// PrusaSlicer's OpenGL window, so this draws one itself: the parts as they stand on the
// bed, seen from the front right and above as `deli view` first shows them, in the
// viewer's orange, on a transparent background. Rows run bottom to top, which is what
// PrusaSlicer's image encoders expect.
ThumbnailData render_thumbnail(const Model &model, unsigned width, unsigned height)
{
    constexpr int   samples   = 4;               // per pixel, each way, to smooth the edges
    constexpr float colour[3] = {242, 140, 40};
    const int       w = int(width) * samples, h = int(height) * samples;
    const Vec3f     toward = Vec3f(0.9f, -1.1f, 0.8f).normalized(); // from the parts to the eye
    const Vec3f     right  = Vec3f::UnitZ().cross(toward).normalized();
    const Vec3f     up     = toward.cross(right);
    const Vec3f     light  = Vec3f(0.4f, -0.7f, 1.f).normalized();
    const auto      seen   = [&](const Vec3f &v) { return Vec3f(v.dot(right), v.dot(up), v.dot(toward)); };

    std::vector<TriangleMesh> meshes;
    for (const ModelObject *object : model.objects)
        meshes.push_back(object->mesh());

    // Fit what is seen into the picture, with a margin.
    constexpr float far = std::numeric_limits<float>::max();
    Vec2f           lo(far, far), hi(-far, -far);
    for (const TriangleMesh &mesh : meshes)
        for (const Vec3f &v : mesh.its.vertices) {
            const Vec2f at = seen(v).head<2>();
            lo = lo.cwiseMin(at);
            hi = hi.cwiseMax(at);
        }
    const float zoom  = 0.9f * std::min(w / std::max(hi.x() - lo.x(), 1e-3f), h / std::max(hi.y() - lo.y(), 1e-3f));
    const Vec2f shift = Vec2f(w, h) / 2 - zoom * (lo + hi) / 2;

    // Each sample keeps the nearest triangle over it and how brightly that one is lit.
    const auto         edge = [](const Vec3f &a, const Vec3f &b, float x, float y) { return (b.x() - a.x()) * (y - a.y()) - (b.y() - a.y()) * (x - a.x()); };
    std::vector<float> depth(size_t(w) * h, -far), shade(size_t(w) * h, 0.f);
    for (const TriangleMesh &mesh : meshes)
        for (const Vec3i &triangle : mesh.its.indices) {
            const Vec3f &a = mesh.its.vertices[triangle(0)], &b = mesh.its.vertices[triangle(1)], &c = mesh.its.vertices[triangle(2)];
            Vec3f        p[3] = {seen(a), seen(b), seen(c)};
            for (Vec3f &point : p)
                point.head<2>() = zoom * point.head<2>() + shift;
            const float area = edge(p[0], p[1], p[2].x(), p[2].y());
            if (std::abs(area) < 1e-6f)
                continue;
            Vec3f normal = (b - a).cross(c - a).normalized();
            if (normal.dot(toward) < 0) // lit the same whichever way the triangle is wound
                normal = -normal;
            const float lit = 0.35f + 0.65f * std::max(0.f, normal.dot(light));

            const int x0 = std::max(0, int(std::floor(std::min({p[0].x(), p[1].x(), p[2].x()}))));
            const int x1 = std::min(w - 1, int(std::ceil(std::max({p[0].x(), p[1].x(), p[2].x()}))));
            const int y0 = std::max(0, int(std::floor(std::min({p[0].y(), p[1].y(), p[2].y()}))));
            const int y1 = std::min(h - 1, int(std::ceil(std::max({p[0].y(), p[1].y(), p[2].y()}))));
            for (int y = y0; y <= y1; ++y)
                for (int x = x0; x <= x1; ++x) {
                    const float u = edge(p[1], p[2], x + 0.5f, y + 0.5f) / area, v = edge(p[2], p[0], x + 0.5f, y + 0.5f) / area;
                    if (u < 0 || v < 0 || u + v > 1)
                        continue;
                    const float  z  = u * p[0].z() + v * p[1].z() + (1 - u - v) * p[2].z();
                    const size_t at = size_t(y) * w + x;
                    if (z > depth[at]) {
                        depth[at] = z;
                        shade[at] = lit;
                    }
                }
        }

    ThumbnailData picture;
    picture.set(width, height);
    for (unsigned y = 0; y < height; ++y)
        for (unsigned x = 0; x < width; ++x) {
            float sum     = 0;
            int   covered = 0;
            for (int sy = 0; sy < samples; ++sy)
                for (int sx = 0; sx < samples; ++sx) {
                    const size_t at = size_t(y * samples + sy) * w + x * samples + sx;
                    if (depth[at] > -far) {
                        sum += shade[at];
                        ++covered;
                    }
                }
            unsigned char *pixel = &picture.pixels[4 * (size_t(y) * width + x)];
            for (int k = 0; k < 3; ++k)
                pixel[k] = covered ? static_cast<unsigned char>(colour[k] * sum / covered) : 0;
            pixel[3] = static_cast<unsigned char>(255 * covered / (samples * samples));
        }
    return picture;
}

// The heights the print's layers reach, lowest first: one for every height at which a
// layer of a part or of its supports is laid, which is how the G-code counts its layers.
std::vector<double> layer_tops(const Print &print)
{
    std::vector<double> tops;
    for (const PrintObject *object : print.objects()) {
        for (const Layer *layer : object->layers())
            tops.push_back(layer->print_z);
        for (const SupportLayer *layer : object->support_layers())
            tops.push_back(layer->print_z);
    }
    std::sort(tops.begin(), tops.end());
    tops.erase(std::unique(tops.begin(), tops.end(), [](double a, double b) { return b - a < EPSILON; }), tops.end());
    return tops;
}

SliceResult slice(const std::vector<Part> &parts, const std::string &config_ini, const std::string &output_path, std::vector<int> pauses)
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
    const std::vector<double> tops = layer_tops(print);
    result.layers = int(tops.size());
    result.height = tops.empty() ? 0. : tops.back();
    if (!pauses.empty()) {
        // PrusaSlicer keeps pauses by height and writes each before the first layer at or
        // above it. The heights are only known now, so the pauses go into the model here and
        // the print is told again; that redoes the last steps only, not the slicing.
        if (config.opt_bool("complete_objects"))
            throw std::runtime_error("a print cannot pause at a layer when its parts are printed one after another (complete_objects)");
        std::sort(pauses.begin(), pauses.end());
        CustomGCode::Info &custom = model.custom_gcode_per_print_z();
        custom.mode = CustomGCode::SingleExtruder;
        for (int layer : pauses) {
            if (layer < 1 || size_t(layer) >= tops.size())
                throw std::runtime_error("the print cannot pause after layer " + std::to_string(layer) + ": it has " +
                                         std::to_string(tops.size()) + " layers, and a pause comes between two of them");
            custom.gcodes.push_back({tops[layer], CustomGCode::PausePrint, 1, "", ""});
            result.pauses.emplace_back(layer, tops[layer - 1]);
        }
        MultipleBedsUtils::with_single_bed_model_fff(model, 0, [&]() { print.apply(model, config); });
        print.process();
    }
    // Asked for once per size in the printer's `thumbnails` setting, and not at all without it.
    const ThumbnailsGeneratorCallback thumbnails = [&model](const ThumbnailsParams &params) {
        ThumbnailsList pictures;
        for (const Vec2d &size : params.sizes)
            pictures.push_back(render_thumbnail(model, unsigned(size.x()), unsigned(size.y())));
        return pictures;
    };
    result.gcode_path = print.export_gcode(output_path, nullptr, thumbnails);

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
std::tuple<nb::bytes, nb::bytes, std::vector<std::pair<size_t, size_t>>> mesh(const std::vector<Part> &parts, const std::string &config_ini)
{
    std::vector<float>    vertices;
    std::vector<uint32_t> triangles;
    std::vector<std::pair<size_t, size_t>> per_part;  // vertices and triangles, each part's after the one before
    {
        nb::gil_scoped_release release;

        const DynamicPrintConfig config = complete_config(parse_config(config_ini));
        std::vector<size_t>      objects_per_part;
        const Model              model  = load_arranged(parts, config, &objects_per_part);
        size_t object_id = 0;
        for (const size_t objects : objects_per_part) {
            const size_t first_vertex = vertices.size() / 3, first_triangle = triangles.size() / 3;
            for (const size_t end = object_id + objects; object_id < end; ++object_id) {
                const TriangleMesh m    = model.objects[object_id]->mesh();
                const uint32_t     base = uint32_t(vertices.size() / 3);
                for (const Vec3f &v : m.its.vertices)
                    vertices.insert(vertices.end(), {v.x(), v.y(), v.z()});
                for (const Vec3i &t : m.its.indices)
                    triangles.insert(triangles.end(), {base + uint32_t(t(0)), base + uint32_t(t(1)), base + uint32_t(t(2))});
            }
            per_part.emplace_back(vertices.size() / 3 - first_vertex, triangles.size() / 3 - first_triangle);
        }
    }
    return {nb::bytes(reinterpret_cast<const char *>(vertices.data()), vertices.size() * sizeof(float)),
            nb::bytes(reinterpret_cast<const char *>(triangles.data()), triangles.size() * sizeof(uint32_t)),
            per_part};
}

// The arcs (G2, G3) in a G-code file by line number, counted from 1 as the reader's
// `gcode_id` is: the end's x and y where the line gives them, the centre's offset from the
// start, and whether the arc goes clockwise.
struct Arc { std::optional<float> x, y; float i = 0.f, j = 0.f; bool clockwise = false; };
static std::map<unsigned int, Arc> arcs(const std::string &gcode_path)
{
    std::map<unsigned int, Arc> found;
    std::ifstream file(gcode_path);
    std::string text;
    for (unsigned int line = 1; std::getline(file, text); ++line) {
        if (text.size() < 3 || text[0] != 'G' || (text[1] != '2' && text[1] != '3') || text[2] != ' ')
            continue;
        Arc arc;
        arc.clockwise = text[1] == '2';
        std::istringstream words(text.substr(3, text.find(';') == std::string::npos ? std::string::npos : text.find(';') - 3));
        for (std::string word; words >> word;) {
            if (word.size() < 2)
                continue;
            const float value = std::strtof(word.c_str() + 1, nullptr);
            switch (word[0]) {
            case 'X': arc.x = value; break;
            case 'Y': arc.y = value; break;
            case 'I': arc.i = value; break;
            case 'J': arc.j = value; break;
            }
        }
        found.emplace(line, arc);
    }
    return found;
}

// How long an arc from `from` is, along the circle.
static float arc_length(const Arc &arc, const Vec3f &from)
{
    const float cx = from.x() + arc.i, cy = from.y() + arc.j;
    const float ex = arc.x.value_or(from.x()), ey = arc.y.value_or(from.y());
    const float start = std::atan2(from.y() - cy, from.x() - cx), end = std::atan2(ey - cy, ex - cx);
    float sweep = arc.clockwise ? start - end : end - start;
    if (sweep <= 1e-6f)
        sweep += float(2. * M_PI);
    return std::hypot(arc.i, arc.j) * sweep;
}

// The extrusions and the travel moves in a G-code file, in the order they are made, as
// PrusaSlicer's own G-code reader finds them: for each, float32 x, y, z of its start and of
// its end, its width and its height (0 for a travel move); float32 speed (mm/s, as the
// G-code asks, within the machine's limits) and flow (mm³/s; 0 for a travel move); a uint32
// layer, counted from 0; and a uint8 index into `extrusion_roles`, whose last name is the
// one for travel. The z is the nozzle's, so the top of the extruded line.
// Then the time the reader estimates, acceleration included, in seconds: per name in
// `extrusion_roles` and one more for every other move (retracting, waiting, a lone z move),
// and per layer. Together they make the estimated printing time.
using Toolpaths = std::tuple<nb::bytes, nb::bytes, nb::bytes, nb::bytes, std::vector<float>, std::vector<float>>;
Toolpaths toolpaths(const std::string &gcode_path)
{
    std::vector<float>    segments, rates;
    std::vector<uint32_t> layers;
    std::vector<uint8_t>  roles;
    const size_t travel_role = size_t(GCodeExtrusionRole::Count), other_role = travel_role + 1;
    std::vector<float> role_times(other_role + 1, 0.f), layer_times;
    {
        nb::gil_scoped_release release;

        GCodeProcessor processor;
        processor.process_file(gcode_path);
        const GCodeProcessorResult &result = processor.get_result();
        // The extrusions of the G-code line being read: where they start, their filament
        // (mm3) and length, and the speed the line asks for.
        unsigned int line = std::numeric_limits<unsigned int>::max();
        size_t line_start = 0;
        float line_volume = 0.f, line_length = 0.f, line_speed = 0.f;
        std::optional<float> line_arc;  // an arc's length along the circle
        const std::map<unsigned int, Arc> arc_lines = arcs(gcode_path);
        const std::vector<GCodeProcessorResult::MoveVertex> &moves = result.moves;
        for (size_t i = 0; i < moves.size(); ++i) {
            const GCodeProcessorResult::MoveVertex &move = moves[i];
            const float time = move.time[size_t(PrintEstimatedStatistics::ETimeMode::Normal)];
            const bool travel = move.type == EMoveType::Travel || move.type == EMoveType::Wipe;
            role_times[move.type == EMoveType::Extrude ? size_t(move.extrusion_role) : travel ? travel_role : other_role] += time;
            if (layer_times.size() <= move.layer_id)
                layer_times.resize(move.layer_id + 1, 0.f);
            layer_times[move.layer_id] += time;

            if (i == 0 || (move.type != EMoveType::Extrude && move.type != EMoveType::Travel))
                continue;
            const Vec3f &from = moves[i - 1].position, &to = move.position;
            if (from == to)
                continue;
            const bool extrudes = move.type == EMoveType::Extrude;
            segments.insert(segments.end(), {from.x(), from.y(), from.z(), to.x(), to.y(), to.z(), extrudes ? move.width : 0.f, extrudes ? move.height : 0.f});
            rates.insert(rates.end(), {move.feedrate, extrudes ? move.volumetric_rate() : 0.f});
            layers.push_back(move.layer_id);
            roles.push_back(extrudes ? uint8_t(move.extrusion_role) : uint8_t(travel_role));
            // A line's speed and flow are the G-code's, not the reader's per piece. The
            // reader cuts an arc (G2/G3) into chords with equal shares of its filament,
            // and for its own preview adds a vertex where a move stops accelerating or
            // starts slowing down, with speed and flow blended from the move before
            // (zero time, before the move it splits): read piece by piece, a small arc of
            // solid infill shows 29.7 mm3/s where the G-code has 21. The chords of a small
            // arc are shorter than the arc, so its length is the G-code's.
            if (!extrudes) {
                line = std::numeric_limits<unsigned int>::max();
                continue;
            }
            const size_t piece = roles.size() - 1;
            if (move.gcode_id != line) {
                line = move.gcode_id;
                line_start = piece;
                line_volume = line_length = line_speed = 0.f;
                const auto arc = arc_lines.find(line);
                line_arc = arc == arc_lines.end() ? std::nullopt : std::optional<float>(arc_length(arc->second, from));
            }
            line_length += (to - from).norm();
            if (time > 0.f) {  // not one of the preview's vertices
                const float diameter = result.filament_diameters[std::min<size_t>(move.extruder_id, result.filament_diameters.size() - 1)];
                line_volume += move.delta_extruder * float(M_PI) * diameter * diameter / 4.f;
                line_speed = move.feedrate;
            }
            if (line_volume > 0.f)
                for (size_t j = line_start; j <= piece; ++j)
                    rates[2 * j] = line_speed, rates[2 * j + 1] = line_speed * line_volume / line_arc.value_or(line_length);
        }
    }
    return {nb::bytes(reinterpret_cast<const char *>(segments.data()), segments.size() * sizeof(float)),
            nb::bytes(reinterpret_cast<const char *>(rates.data()), rates.size() * sizeof(float)),
            nb::bytes(reinterpret_cast<const char *>(layers.data()), layers.size() * sizeof(uint32_t)),
            nb::bytes(reinterpret_cast<const char *>(roles.data()), roles.size()),
            role_times, layer_times};
}

// PrusaSlicer's names for what an extrusion is for, in the order `toolpaths` numbers them,
// and after them the name `toolpaths` gives a move that extrudes nothing.
std::vector<std::string> extrusion_roles()
{
    std::vector<std::string> names;
    for (uint8_t role = 0; role < uint8_t(GCodeExtrusionRole::Count); ++role)
        names.push_back(gcode_extrusion_role_to_string(GCodeExtrusionRole(role)));
    names.push_back("Travel");
    return names;
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
    m.attr("API_VERSION") = 8;

    nb::class_<SliceResult>(m, "SliceResult")
        .def_ro("gcode_path", &SliceResult::gcode_path, "Path the G-code was written to.")
        .def_ro("print_time", &SliceResult::print_time, "Estimated print time in seconds.")
        .def_ro("filament_mm", &SliceResult::filament_mm, "Filament used, in millimetres.")
        .def_ro("filament_g", &SliceResult::filament_g, "Filament used, in grams.")
        .def_ro("warnings", &SliceResult::warnings, "Warnings PrusaSlicer raised while validating the print.")
        .def_ro("pauses", &SliceResult::pauses, "For each pause, the layer it comes after and the height of the print by then, in mm.")
        .def_ro("layers", &SliceResult::layers, "How many layers the print has, as the G-code's layer changes count them.")
        .def_ro("height", &SliceResult::height, "Height of the top of the last layer, in mm.");

    m.def("slice", &slice, "parts"_a, "config"_a, "output"_a, "pauses"_a = std::vector<int>{},
          "Slice the parts of a print and write G-code to `output`.\n\n"
          "Each part is (model file, scale, rotate, count, place, height): per-axis scale factors,\n"
          "degrees about X, Y and Z applied in that order after scaling, the number of copies, the\n"
          "x and y of its middle on the bed or None to have it arranged, and how far its underside\n"
          "is above the bed (negative sinks it). The parts are dropped onto the bed and those\n"
          "without a place are arranged on it. `config` is PrusaSlicer INI text; settings it\n"
          "leaves out take PrusaSlicer's defaults. A picture of the parts is written into the\n"
          "G-code for each size in the `thumbnails` setting. `pauses` are layers, counted from 1\n"
          "as the G-code's layer changes count them, after which the printer's pause G-code\n"
          "(`pause_print_gcode`) is written.");

    m.def("model_size", &model_size, "model"_a, nb::kw_only(),
          "scale"_a = std::array<double, 3>{1., 1., 1.}, "rotate"_a = std::array<double, 3>{0., 0., 0.},
          "Extent of the model in a file along X, Y and Z, in millimetres, after `scale` and\n"
          "`rotate` are applied as `slice` applies them.\n\n"
          "Raises RuntimeError when the file cannot be read as a model.");

    m.def("mesh", &mesh, "parts"_a, "config"_a,
          "The triangles of every part and copy, placed on the bed as `slice` places them: bytes\n"
          "of float32 vertex coordinates, bytes of uint32 triangle vertex indices, and per part, in\n"
          "the order given, how many of the vertices and triangles are its, each part's after\n"
          "the one before.");

    m.def("toolpaths", &toolpaths, "gcode"_a,
          "The extrusions and travel moves in a G-code file, in order, and the time they take.\n"
          "Four bytes objects, per move: eight float32 (start x, y, z, end x, y, z, width, height;\n"
          "the last two 0 for travel); two float32 (speed in mm/s, flow in mm3/s, 0 for travel);\n"
          "one uint32 layer counted from 0; one uint8 index into `extrusion_roles()`. Then two\n"
          "lists of seconds, acceleration included: per name in `extrusion_roles()` and one more\n"
          "for every other move (retracts, waits), and per layer.\n\n"
          "Raises RuntimeError when the file cannot be read.");

    m.def("extrusion_roles", &extrusion_roles,
          "PrusaSlicer's names for what an extrusion is for, in the order `toolpaths` numbers them,\n"
          "followed by 'Travel' for the moves that extrude nothing.");

    m.def("split_config", &split_config, "config"_a,
          "Sort the settings in PrusaSlicer INI text into 'printer', 'process' and 'filament'.\n\n"
          "Returns the groups, each a dict of setting name to value, and a list of the settings\n"
          "this version of PrusaSlicer does not know. Bad values raise ValueError.");

    m.def("setting_default", &setting_default, "key"_a, "PrusaSlicer's default for a setting, as it writes it.");

    m.def("setting_names", &setting_names,
          "The names of the settings PrusaSlicer keeps in a 'printer', a 'process' and a 'filament'.");
}
