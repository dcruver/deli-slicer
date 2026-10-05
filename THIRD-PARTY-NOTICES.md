# Third-party notices

deli is licensed under the GNU Affero General Public License, version 3 only
(AGPL-3.0-only); see `LICENSE`.

deli's wheels contain the software below. The engine, `deli._engine`, has
PrusaSlicer's `libslic3r` and the libraries it needs compiled and linked into
it statically; the viewer's JavaScript is shipped as plain files. Each
component keeps its own licence. Their texts are in `licenses/`; where a
component has no licence file of its own, the file there holds the licence
notice from its source and says so.

| Component | Version | Licence (SPDX id) | Upstream URL | Licence file |
|---|---|---|---|---|
| PrusaSlicer (libslic3r, slic3r-arrange, libseqarrange, sla-time-estimates) | 2.9.6 | AGPL-3.0-or-later | https://github.com/prusa3d/PrusaSlicer | `LICENSE` |
| localesutils (part of PrusaSlicer) | 2.9.6 | AGPL-3.0-or-later | https://github.com/prusa3d/PrusaSlicer | `LICENSE` |
| ADMesh (bundled in PrusaSlicer) | as bundled in PrusaSlicer 2.9.6 | GPL-2.0-or-later | https://github.com/admesh/admesh | `licenses/admesh.txt` |
| Clipper (bundled in PrusaSlicer, with its Int128 excerpt) | 6.4.2 | BSL-1.0 | http://www.angusj.com/delphi/clipper.php | `licenses/clipper.txt` |
| GLU libtess (bundled in PrusaSlicer) | mesa/glu 0bf42e4 | SGI-B-2.0 | https://gitlab.freedesktop.org/mesa/glu | `licenses/glu-libtess.txt` |
| QOI (bundled in PrusaSlicer) | 6c0831f | MIT | https://github.com/phoboslab/qoi | `licenses/qoi.txt` |
| semver.c (bundled in PrusaSlicer) | 0.2.0 | MIT | https://github.com/h2non/semver.c | `licenses/semver.txt` |
| miniz (bundled in PrusaSlicer, modified) | 2.1.0 | MIT | https://github.com/richgel999/miniz | `licenses/miniz.txt` |
| prusa_fdm_mixer (bundled in PrusaSlicer) | as bundled in PrusaSlicer 2.9.6 | MIT | https://github.com/prusa3d/PrusaSlicer | `licenses/prusa_fdm_mixer.txt` |
| Anti-Grain Geometry (bundled in PrusaSlicer) | 2.4 | BSD-3-Clause OR LicenseRef-AGG-Public-License | https://agg.sourceforge.net/antigrain.com/ | `licenses/agg.txt` |
| ankerl::unordered_dense (bundled in PrusaSlicer) | 3.1.1 | MIT | https://github.com/martinus/unordered_dense | `licenses/ankerl-unordered-dense.txt` |
| fast_float (bundled in PrusaSlicer) | 2.0.0 | MIT | https://github.com/fastfloat/fast_float | `licenses/fast_float.txt` |
| libigl (bundled in PrusaSlicer) | as bundled in PrusaSlicer 2.9.6 | MPL-2.0 | https://libigl.github.io | `licenses/libigl.txt` |
| libnest2d (bundled in PrusaSlicer) | as bundled in PrusaSlicer 2.9.6 | LGPL-3.0-only | https://github.com/tamasmeszaros/libnest2d | `licenses/libnest2d.txt` |
| tcb::span (bundled in PrusaSlicer) | 836dc6a | BSL-1.0 | https://github.com/tcbrindle/span | `licenses/tcbspan.txt` |
| Boost (atomic, chrono, container, context, coroutine, date_time, exception, filesystem, iostreams, locale, log, nowide, random, thread; and headers) | 1.83.0 | BSL-1.0 | https://www.boost.org | `licenses/boost.txt` |
| CGAL | 5.6.2 | GPL-3.0-or-later AND LGPL-3.0-or-later AND BSL-1.0 | https://www.cgal.org | `licenses/cgal.txt` |
| GMP (libgmp, libgmpxx) | 6.2.1 | LGPL-3.0-or-later OR GPL-2.0-or-later | https://gmplib.org | `licenses/gmp.txt` |
| MPFR | 4.2.1 | LGPL-3.0-or-later | https://www.mpfr.org | `licenses/mpfr.txt` |
| NLopt | 2.5.0 | LGPL-2.1-or-later AND MIT AND BSD-3-Clause | https://github.com/stevengj/nlopt | `licenses/nlopt.txt` |
| oneTBB (tbb, tbbmalloc) | 2021.5.0 | Apache-2.0 AND BSD-3-Clause | https://github.com/oneapi-src/oneTBB | `licenses/tbb.txt` |
| OpenVDB (Prusa fork 339ee88) | 8.2.0 | MPL-2.0 | https://www.openvdb.org | `licenses/openvdb.txt` |
| OpenEXR (Half library only) | 2.5.5 | BSD-3-Clause | https://github.com/AcademySoftwareFoundation/openexr | `licenses/openexr.txt` |
| c-blosc (with its bundled LZ4, Snappy, Zstd) | 1.17.0 (8724c06) | BSD-3-Clause AND BSD-2-Clause AND MIT AND (BSD-3-Clause OR GPL-2.0-only) | https://github.com/Blosc/c-blosc | `licenses/blosc.txt` |
| Z3 | 4.15.1 | MIT | https://github.com/Z3Prover/z3 | `licenses/z3.txt` |
| Qhull | 8.1-alpha3 | Qhull | http://www.qhull.org | `licenses/qhull.txt` |
| Expat | 2.4.3 | MIT | https://libexpat.github.io | `licenses/expat.txt` |
| libjpeg-turbo | 3.0.1 | IJG AND BSD-3-Clause AND Zlib | https://libjpeg-turbo.org | `licenses/libjpeg-turbo.txt` |
| libpng | 1.6.43 (Linux wheels); 1.6.35 (macOS wheels) | libpng-2.0 (1.6.43); Libpng (1.6.35) | http://www.libpng.org/pub/png/libpng.html | `licenses/libpng.txt` |
| zlib | 1.3.1 | Zlib | https://zlib.net | `licenses/zlib.txt` |
| LibBGCode | 0.3.0 (6f4ad7c) | AGPL-3.0-or-later | https://github.com/prusa3d/libbgcode | `licenses/libbgcode.txt` |
| heatshrink | 0.4.1 | ISC | https://github.com/atomicobject/heatshrink | `licenses/heatshrink.txt` |
| Eigen (header-only) | 3.3.7 | MPL-2.0 (a few files LGPL-2.1-or-later, BSD-3-Clause) | https://eigen.tuxfamily.org | `licenses/eigen.txt` |
| cereal (header-only) | 1.3.0 | BSD-3-Clause | https://github.com/USCiLab/cereal | `licenses/cereal.txt` |
| nlohmann/json (header-only) | 3.12.0 | MIT | https://github.com/nlohmann/json | `licenses/nlohmann-json.txt` |
| NanoSVG (header-only) | fltk/nanosvg abcd277 | Zlib | https://github.com/fltk/nanosvg | `licenses/nanosvg.txt` |
| nanobind (with its bundled tsl::robin_map) | 3.1.0 | BSD-3-Clause AND MIT | https://github.com/wjakob/nanobind | `licenses/nanobind.txt` |
| three.js and OrbitControls (viewer, plain files) | r170 | MIT | https://threejs.org | `licenses/threejs.txt` |

The printer, process and filament profiles in `profiles/` are converted from
OrcaSlicer's presets. OrcaSlicer is licensed under the AGPL-3.0
(https://github.com/SoftFever/OrcaSlicer); its text is the one in `LICENSE`.

NLopt includes Ladislav Luksan's optimisation routines, which ask that this
notice be cited: Subroutines PLIP, PSEN, Copyright Jan Vlcek, 2007. The
remaining subroutines, Copyright Ladislav Luksan, 2007. Licensed under the
GNU LGPL 2.1 or later. Available at
http://www.cs.cas.cz/~luksan/subroutines.html. Used by permission.

## LGPL libraries

GMP, MPFR, NLopt, libnest2d and parts of CGAL (and, if any of its
LGPL-licensed files are used, Eigen) are under the GNU Lesser General Public
License. They are linked statically into `deli._engine`. deli is itself
licensed under the AGPL, and its complete corresponding source, including the
build scripts, is available from its repository, so a recipient can modify
these libraries, rebuild the engine against them, and relink it.
