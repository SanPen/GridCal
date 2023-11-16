import os
from sphinx.cmd.build import build_main

# Replace 'path/to/your/source' and 'path/to/your/build' with your actual paths
# source_dir = os.path.join('.', 'rst_source')
build_dir = './build'
confdir = '.'
# doctreedir = os.path.abspath('../src/GridCal')
builder = 'html'

# Call the build_main function
status = build_main(
    [
        '-b', builder,  # Specify the builder
        '-d', os.path.join(build_dir, builder, 'doctrees'),  # Directory for doctrees (you can change this)
        confdir,  # Path to your Sphinx project's conf.py
        os.path.join(build_dir, builder),  # Output directory for generated documentation
    ]
)

# Check the status of the build
if status != 0:
    print(f"Documentation build failed with status code {status}")
else:
    print("Documentation build successful")
