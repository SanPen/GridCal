# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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
from Tutorials.defining_a_grid_from_scratch_with_profiles import main as main_with_profiles
from Tutorials.defining_a_grid_from_scratch_without_profiles import main as main_without_profiles


def test_define_grid_from_scratch_without_profiles():
    main_without_profiles()


def test_define_grid_from_scratch_with_profiles():
    main_with_profiles()
