#!/usr/bin/env bash
pyuic5 -x gui.ui -o gui.py
pyrcc5 icons.qrc -o icons_rc.py
