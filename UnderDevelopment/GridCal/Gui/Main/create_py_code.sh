#!/usr/bin/env bash
pyuic5 -x MainWindow.ui -o MainWindow.py
pyrcc5 icons.qrc -o icons_rc.py
