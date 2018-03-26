#!/usr/bin/env bash
python3 setup.py sdist
twine upload dist/GridCal-1.57.tar.gz