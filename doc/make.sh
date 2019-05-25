#!/usr/bin/env bash

#sphinx-build -b html -E . _build/html
sphinx-build -b html . build/html
#sphinx-build -b latex -E . _build/latex
#pdflatex -interaction=nonstopmode _build/latex