from setuptools import setup, Extension

_sunfish_core = Extension(
    "_sunfish_core",
    sources=["csrc/_sunfish_core.c"],
    include_dirs=["csrc"],
    extra_compile_args=["-O3", "-DNDEBUG"],
)

setup(
    name="sunfish-core",
    version="1.0.0",
    ext_modules=[_sunfish_core],
)
