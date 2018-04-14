#!/usr/bin/env bash
python3 setup.py sdist
twine upload dist/GridCal-2.24.tar.gz