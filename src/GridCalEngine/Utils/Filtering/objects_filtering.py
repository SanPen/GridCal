# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import numpy as np
from typing import Union, List
from GridCalEngine.Utils.Filtering.filtering import Filter
from GridCalEngine.Core.Devices.types import ALL_DEV_TYPES


def single_objects_filter(objects: List[ALL_DEV_TYPES], f: Filter):
    """
    Filter objects by the given filter
    :param objects:
    :param f:
    :return:
    """
    mask = np.zeros(len(objects), dtype=bool)

    return mask