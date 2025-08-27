# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import os
from sphinx.cmd.build import build_main

# Replace 'path/to/your/source' and 'path/to/your/build' with your actual paths
# source_dir = os.path.join('.', 'rst_source')
build_dir = './build'
confdir = '.'
# doctreedir = os.path.abspath('../src/VeraGrid')
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
