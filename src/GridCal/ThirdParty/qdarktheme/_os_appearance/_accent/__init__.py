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
import platform


def _check_macos_supported_version():
    sys_ver = platform.mac_ver()[0]  # typically 10.14.2 or 12.3
    major = int(sys_ver.split(".")[0])
    if major < 10:
        return False
    if major >= 11:
        return True
    minor = int(sys_ver.split(".")[1])
    return minor >= 14


def _dummy_accent_detector() -> None:
    return None


def _select_accent_detector():
    if platform.system() == "Darwin":
        if _check_macos_supported_version():
            from GridCal.ThirdParty.qdarktheme._os_appearance._accent._mac_detect import get_mac_accent

            return get_mac_accent
        return _dummy_accent_detector
    return _dummy_accent_detector


accent = _select_accent_detector()
