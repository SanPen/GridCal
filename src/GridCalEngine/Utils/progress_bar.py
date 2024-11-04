# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import sys


def print_progress_bar(iteration: int, total: int, length=40, txt=""):
    """
    Simple text progress bar
    :param iteration: current iteration (1 based)
    :param total: total progress
    :param length: length of the bar in characters
    :param txt: text to print at the end of the progress bar
    """
    if iteration > total:
        iteration = total

    percent = (iteration / total)
    arrow = '=' * int(length * percent) + '>'
    spaces = ' ' * (length - len(arrow))
    sys.stdout.write(f'\r[{arrow}{spaces}] {percent:.1%} {txt}')
    sys.stdout.flush()
