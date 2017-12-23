#!/usr/bin/env bash
pyrcc5 icons.qrc -o icons_rc.py
pyuic5 -x MainWindow.ui -o MainWindow.py

