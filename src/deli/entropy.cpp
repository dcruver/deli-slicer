// std::random_device::entropy() calls _M_getentropy(), which libstdc++ only has from
// GLIBCXX_3.4.25, newer than a manylinux_2_28 wheel may depend on. The link wraps it
// (see CMakeLists.txt) so that it lands here. Zero is what libstdc++ itself answers for
// sources it cannot vouch for; fuzzy skin, its one caller, then seeds from the thread id.

extern "C" double __wrap__ZNKSt13random_device13_M_getentropyEv(const void *) noexcept
{
    return 0.0;
}
