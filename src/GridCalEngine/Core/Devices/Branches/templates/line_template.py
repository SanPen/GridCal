# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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


from GridCalEngine.Core.Devices.editable_device import DeviceType


class LineTemplate:

    def __init__(self, name='BranchTemplate', idtag=None):
        self.idtag = idtag

        self.name = name

        self.device_type = DeviceType.LineTypeDevice

        self.edit_headers = []
        self.units = []
        self.non_editable_indices = []
        self.edit_types = {}

    def __str__(self):
        return self.name

    def get_save_data(self):
        dta = list()
        for property in self.edit_headers:
            dta.append(getattr(self, property))