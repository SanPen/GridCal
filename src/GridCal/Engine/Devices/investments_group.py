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


from GridCal.Engine.Devices.editable_device import EditableDevice, DeviceType, GCProp


class InvestmentsGroup(EditableDevice):
    """
    The Contingency object is the container of all the

    Arguments:

        **name** (str, "Contingency"): Name of the contingency

        **type** (float, 10.0): Nominal voltage in kV

        **loads** (list, list()): List of contingency elements

    """

    def __init__(self, idtag=None,  name="ContingencyGroup", category=''):
        """
        Contingency group
        :param idtag: Unique identifier
        :param name: contingency group name
        :param category: tag to category the group
        """

        EditableDevice.__init__(
            self,
            idtag=idtag,
            name=name,
            active=True,
            device_type=DeviceType.InvestmentsGroupDevice,
            editable_headers={
                'idtag': GCProp('', str, 'Unique ID'),
                'name': GCProp('', str, 'Name of the contingency group'),
                'category': GCProp('', str, 'Some tag to category the contingency group'),
            },
            non_editable_attributes=['idtag'],
            properties_with_profile=dict()
        )

        # Contingency type
        self.category = category

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, val: str):
        self._name = val
        if self.graphic_obj is not None:
            self.graphic_obj.set_label(self._name)

    def get_properties_dict(self):
        """
        Get json dictionary
        :return:
        """

        return {
            'id': self.idtag,
            'name': self.name,
            'category': self.category,
        }
