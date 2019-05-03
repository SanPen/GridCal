import os
from subprocess import call

# path to source
this_path = os.path.dirname(os.path.abspath(__file__))
packagedir = os.path.join(this_path, '..', '..', 'UnderDevelopment', 'GridCal')
outputdir = os.path.join(this_path)

# Command you should run
# sphinx-apidoc [options] -o outputdir packagedir [pathnames]

call(["sphinx-apidoc", "-o", outputdir, packagedir])
call([os.path.join('..', 'make.bat'), 'html'])
call([os.path.join('..', 'make.bat'), 'latex'])
