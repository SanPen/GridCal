#!/usr/bin/env bash
python3 setup.py sdist
twine upload dist/GridCal-2.26.tar.gz