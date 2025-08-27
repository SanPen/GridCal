# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List, Dict, Union
from warnings import warn

from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.enumerations import DeviceType
from VeraGrid.Gui.Diagrams.SchematicWidget.Substation.bus_graphics import BusGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Fluid.fluid_node_graphics import FluidNodeGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Fluid.fluid_path_graphics import FluidPathGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.line_graphics import LineGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.winding_graphics import WindingGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.dc_line_graphics import DcLineGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.transformer2w_graphics import TransformerGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.hvdc_graphics import HvdcGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.vsc_graphics import VscGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.upfc_graphics import UpfcGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.series_reactance_graphics import SeriesReactanceGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.line_graphics_template import LineGraphicTemplateItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.transformer3w_graphics import Transformer3WGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Injections.generator_graphics import GeneratorGraphicItem
from VeraGrid.Gui.Diagrams.MapWidget.Branches.map_line_container import MapLineContainer
from VeraGrid.Gui.Diagrams.MapWidget.Substation.voltage_level_graphic_item import VoltageLevelGraphicItem
from VeraGrid.Gui.Diagrams.MapWidget.Branches.line_location_graphic_item import LineLocationGraphicItem
from VeraGrid.Gui.Diagrams.MapWidget.Substation.substation_graphic_item import SubstationGraphicItem
from VeraGrid.Gui.Diagrams.MapWidget.Branches.map_line_segment import MapLineSegment


ALL_BUS_BRACH_GRAPHICS = Union[
    BusGraphicItem,
    FluidNodeGraphicItem,
    FluidPathGraphicItem,
    LineGraphicItem,
    WindingGraphicItem,
    DcLineGraphicItem,
    TransformerGraphicItem,
    HvdcGraphicItem,
    VscGraphicItem,
    UpfcGraphicItem,
    SeriesReactanceGraphicItem,
    LineGraphicTemplateItem,
    Transformer3WGraphicItem,
    GeneratorGraphicItem,
]

ALL_MAP_GRAPHICS = Union[
    MapLineContainer,
    VoltageLevelGraphicItem,
    LineLocationGraphicItem,
    SubstationGraphicItem,
    MapLineSegment
]

ALL_GRAPHICS = Union[ALL_BUS_BRACH_GRAPHICS, ALL_MAP_GRAPHICS]


class GraphicsManager:
    """
    Class to handle the correspondance between graphics and database devices
    """

    def __init__(self) -> None:
        # this is a dictionary that groups by 2 levels:
        # first by DeviceType
        # second idtag -> GraphicItem
        self.graphic_dict: Dict[DeviceType, Dict[str, ALL_GRAPHICS]] = dict()

    def clear(self):
        """
        Clear all graphics references
        """
        self.graphic_dict.clear()

    def add_device(self, elm: ALL_DEV_TYPES, graphic: ALL_GRAPHICS) -> None:
        """
        Add the graphic of a device
        :param elm: Any database device
        :param graphic: Corresponding graphic
        """
        if graphic is not None:  # it makes no sense to add a None graphic

            elm_dict: Dict[str, ALL_GRAPHICS] = self.graphic_dict.get(elm.device_type, None)

            if elm_dict is None:
                self.graphic_dict[elm.device_type] = {elm.idtag: graphic}
            else:
                graphic_0 = elm_dict.get(elm.idtag, None)  # try to get the existing element
                if graphic_0 is None:
                    elm_dict[elm.idtag] = graphic
                else:
                    if graphic_0 != graphic:
                        warn(f"Replacing {graphic} with {graphic}, this could be a sign of an idtag bug")
                    elm_dict[elm.idtag] = graphic

        else:
            raise ValueError(f"Trying to set a None graphic object for {elm}")

    def delete_device(self, device: ALL_DEV_TYPES) -> Union[ALL_GRAPHICS, None]:
        """
        Delete device from the registry and return the object if it exists
        :param device: Any database device
        :return: Corresponding graphic or None
        """
        if device is not None:
            # check if the category exists ...
            elm_dict = self.graphic_dict.get(device.device_type, None)

            if elm_dict is not None:
                # the category does exist, delete_with_dialogue from it
                graphic = elm_dict.get(device.idtag, None)

                if graphic:
                    del elm_dict[device.idtag]
                    return graphic

            else:
                # not found so we're ok
                return None
        else:
            return None

    def query(self, elm: ALL_DEV_TYPES) -> Union[None, ALL_GRAPHICS]:
        """
        Query the graphic of a database element
        :param elm: Any database element
        :return: Corresponding graphic
        """
        if elm is None:
            return None

        else:
            elm_dict: Dict[str, ALL_GRAPHICS] = self.graphic_dict.get(elm.device_type, None)

            if elm_dict is None:
                return None
            else:
                return elm_dict.get(elm.idtag, None)

    def query_preferring_busbars(self, elm: ALL_DEV_TYPES) -> Union[None, ALL_GRAPHICS]:
        """
        Because some connectivity nodes are graphically substituted by BusBars, we need to do this
        :param elm: Any device
        :return: Any graphic element if found, None otherwise
        """
        return self.query(elm=elm)

    def get_device_type_list(self, device_type: DeviceType) -> List[ALL_GRAPHICS]:
        """
        Get the list of graphics of a device type
        :param device_type: DeviceType
        :return: List[ALL_GRAPHICS]
        """
        elm_dict: Dict[str, ALL_GRAPHICS] = self.graphic_dict.get(device_type, None)

        if elm_dict is None:
            return list()
        else:
            return [graphic for idtag, graphic in elm_dict.items()]

    def get_device_type_dict(self, device_type: DeviceType) -> Dict[str, ALL_GRAPHICS]:
        """
        Get the list of graphics of a device type
        :param device_type: DeviceType
        :return: Dict[str, ALL_GRAPHICS]
        """
        return self.graphic_dict.get(device_type, dict())
