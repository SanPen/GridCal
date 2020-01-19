#!python
#cython: language_level=3

from distutils.core import setup
from distutils.extension import Extension
from Cython.Build import cythonize
from Cython.Distutils import build_ext
import numpy
from sys import platform
import os

try:
    blas_path = numpy.distutils.system_info.get_info('blas')['library_dirs'][0]
except:
    if "library_dirs" in numpy.__config__.blas_mkl_info:
        blas_path = numpy.__config__.blas_mkl_info["library_dirs"][0]
    elif "library_dirs" in numpy.__config__.blas_opt_info:
        blas_path = numpy.__config__.blas_opt_info["library_dirs"][0]
    else:
        raise ValueError("Could not locate BLAS library.")


if platform[:3] == "win":
    if os.path.exists(os.path.join(blas_path, "mkl_rt.lib")):
        blas_file = "mkl_rt.lib"
    elif os.path.exists(os.path.join(blas_path, "mkl_rt.dll")):
        blas_file = "mkl_rt.dll"
    else:
        import re
        blas_file = [f for f in os.listdir(blas_path) if bool(re.search("blas", f))]
        if len(blas_file) == 0:
            raise ValueError("Could not locate BLAS library.")
        blas_file = blas_file[0]

elif platform[:3] == "dar":
    blas_file = "libblas.dylib"
else:
    blas_file = "libblas.so"


## https://stackoverflow.com/questions/724664/python-distutils-how-to-get-a-compiler-that-is-going-to-be-used
class build_ext_subclass( build_ext ):
    def build_extensions(self):
        compiler = self.compiler.compiler_type
        if compiler == 'msvc': # visual studio
            for e in self.extensions:
                e.extra_link_args += [os.path.join(blas_path, blas_file)]
        else: # gcc
            for e in self.extensions:
                e.extra_link_args += ["-L"+blas_path, "-l:"+blas_file]
        build_ext.build_extensions(self)


extensions = [Extension("matmul_package.matmul",
                             sources=["matmul.pyx"],
                             include_dirs=[numpy.get_include()],
                             extra_link_args=[])]

extensions = cythonize(extensions, compiler_directives={'language_level' : "3"}) # or "2" or "3str"

setup(
    name  = "matmul",
    packages = ["matmul_package"],
    cmdclass = {'build_ext': build_ext_subclass},
    ext_modules = extensions
    )