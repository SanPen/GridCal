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
from GridCalEngine.Devices.Parents.editable_device import EditableDevice
from GridCalEngine.enumerations import DeviceType


class OptionsTemplate(EditableDevice):
    """
    Options template
    """

    def __init__(self, name: str):
        """

        :param name:
        """
        EditableDevice.__init__(self, name=name,
                                idtag=None,
                                code="",
                                device_type=DeviceType.SimulationOptionsDevice,
                                comment="")

    # def register(self,
    #              key: str,
    #              tpe: GCPROP_TYPES,
    #              units: str = "",
    #              definition: str = "",
    #              display: bool = True,
    #              editable: bool = True,
    #              old_names: List[str] = None):
    #     """
    #     Register property
    #     The property must exist, and if provided, the profile_name property must exist too
    #     :param key: key (this is the displayed name)
    #     :param units: string with the declared units
    #     :param tpe: type of the attribute [Type[int], Type[bool], Type[float], Type[str], DeviceType, Type[BuildStatus]]
    #     :param definition: Definition of the property
    #     :param display: display this property?
    #     :param editable: is this editable?
    #     :param old_names: List of old names
    #     """
    #     assert (hasattr(self, key))  # the property must exist, this avoids bugs when registering
    #
    #     prop = GCProp(prop_name=key,
    #                   units=units,
    #                   tpe=tpe,
    #                   definition=definition,
    #                   profile_name="",
    #                   display=display,
    #                   editable=editable,
    #                   old_names=old_names)
    #
    #     if key in self.registered_properties.keys():
    #         raise Exception(f"Option property {key} already registered!")
    #
    #     self.registered_properties[key] = prop
    #
    #     self.property_list.append(prop)

    # def to_dict(self) -> Dict:
    #     """
    #
    #     :return:
    #     """
    #     data = dict()
    #
    #     for gc_prop in self.property_list:
    #
    #         # get the property value
    #         val = getattr(self, gc_prop.name)
    #
    #         if isinstance(val, list):
    #             val2 = list()
    #
    #             for e in val:
    #                 if isinstance(e, (float, bool, str, int)):
    #                     val2.append(e)
    #                 elif hasattr(e, 'idtag'):
    #                     # it is a GridCal device
    #                     val2.append(e.idtag)
    #
    #         elif isinstance(val, (float, bool, str, int)):
    #             val2 = val
    #
    #         elif hasattr(val, 'idtag'):
    #             val2 = val.to_dict()
    #
    #         else:
    #             val2 = val
    #
    #         data[gc_prop.name] = val2
    #
    #     return data
