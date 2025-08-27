# MIT License
#
# Copyright (c) 2021-2022 Yunosuke Ohsugi
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""PyQtDarkTheme - A flat dark theme for PySide and PyQt.

- Repository: https://github.com/5yutan5/PyQtDarkTheme
- Documentation: https://pyqtdarktheme.readthedocs.io


License Information
===================

Material design icons
---------------------

All svg files in PyQtDarkTheme is from Material design icons(which uses an Apache 2.0 license).

- Author: Google
- Site: https://fonts.google.com/icons
- Source: https://github.com/google/material-design-icons
- License: Apache License Version 2.0 | https://www.apache.org/licenses/LICENSE-2.0.txt

Modifications made to each files to change the icon color and angle and delete svg namespace.

The current Material design icons license summary can be viewed at:
https://github.com/google/material-design-icons/blob/master/LICENSE


QDarkStyleSheet(Source code)
----------------------------

Qt stylesheets are originally fork of QDarkStyleSheet(MIT License).

- Author: Colin Duquesnoy
- Site: https://github.com/ColinDuquesnoy/QDarkStyleSheet
- Source: https://github.com/ColinDuquesnoy/QDarkStyleSheet
- License: MIT License | https://opensource.org/licenses/MIT

Modifications made to a file to change the style.

The current QDarkStyleSheet license summary can be viewed at:
https://github.com/ColinDuquesnoy/QDarkStyleSheet/blob/master/LICENSE.rst

"""
# Version of PyQtDarkTheme
__version__ = "2.1.0"

from VeraGrid.ThirdParty.qdarktheme._main import enable_hi_dpi, setup_theme, stop_sync
from VeraGrid.ThirdParty.qdarktheme._style_loader import clear_cache, get_themes, load_palette, load_stylesheet
