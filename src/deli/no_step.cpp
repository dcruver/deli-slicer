// deli is built without STEP files, which need OpenCASCADE (see CMakeLists.txt). On macOS
// libslic3r calls the wrapper's loader directly rather than loading it at run time, so
// this stands in for it and says so.

#include <optional>
#include <stdexcept>
#include <utility>

#include "occt_wrapper/OCCTWrapper.hpp"

extern "C" bool load_step_internal(const char *, Slic3r::OCCTResult *, std::optional<std::pair<double, double>>)
{
    throw std::runtime_error("this build of deli cannot read STEP files; export the model as STL or 3MF");
}
