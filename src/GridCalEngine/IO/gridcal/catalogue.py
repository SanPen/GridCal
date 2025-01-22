# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import List, Tuple
import pandas as pd
from GridCalEngine.Devices.Branches.transformer_type import TransformerType
from GridCalEngine.Devices.Branches.sequence_line_type import SequenceLineType
from GridCalEngine.Devices.Branches.underground_line_type import UndergroundLineType
from GridCalEngine.Devices.Branches.wire import Wire
from GridCalEngine.Devices.assets import Assets
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.basic_structures import Logger


def get_transformers_catalogue_df(grid: MultiCircuit):
    """

    :param grid:
    :return:
    """
    data = list()

    for elm in grid.transformer_types:
        data.append({
            'Name': elm.name,
            'HV (kV)': elm.HV,
            'LV (kV)': elm.LV,
            'Rate (MVA)': elm.Sn,
            'Copper losses (kW)': elm.Pcu,
            'No load losses (kW)': elm.Pfe,
            'No load current (%)': elm.I0,
            'V short circuit (%)': elm.Vsc
        })

    return pd.DataFrame(data)


def get_cables_catalogue_df(grid: MultiCircuit):
    """

    :param grid:
    :return:
    """
    data = list()

    for elm in grid.underground_cable_types:
        data.append({
            'Name': elm.name,
            'Rated current [kA]': elm.Imax,
            'Rated voltage [kV]': elm.Vnom,
            'R [Ohm/km AC@20°C]': elm.R,
            'B [uS/km]': elm.B,
            'X [Ohm/km]': elm.X,
            'R0 (AC) [Ohm/km]': elm.R0,
            'X0  [Ohm/km]': elm.X0
        })

    return pd.DataFrame(data)


def get_wires_catalogue_df(grid: MultiCircuit):
    """

    :param grid:
    :return:
    """
    data = list()

    for elm in grid.wire_types:
        data.append({
            'Name': elm.name,
            'Stranding': elm.stranding,
            'Material': elm.material,
            'Diameter [cm]': elm.diameter,
            'GMR [m]': elm.GMR,
            'R [Ohm/km]': elm.R,
            'Rating [kA]': elm.max_current
        })
    return pd.DataFrame(data)


def get_sequence_lines_catalogue_df(grid: MultiCircuit):
    """

    :param grid:
    :return:
    """
    data = list()

    for elm in grid.sequence_line_types:
        data.append({
            'Name': elm.name,
            'Vnom (kV)': elm.Vnom,
            'Imax (kA)': elm.Imax,
            'r (ohm/km)': elm.R,
            'x (ohm/km)': elm.X,
            'b (uS/km)': elm.B,
            'r0 (ohm/km)': elm.R0,
            'x0 (ohm/km)': elm.X0,
            'b0 (uS/km)': elm.B0
        })

    return pd.DataFrame(data)


def parse_transformer_types(df: pd.DataFrame) -> List[TransformerType]:
    """

    :param df:
    :return:
    """
    lst = list()
    for i, item in df.iterrows():
        tpe = TransformerType(hv_nominal_voltage=item.get('HV (kV)',0.0),
                              lv_nominal_voltage=item.get('LV (kV)',0.0),
                              nominal_power=item.get('Rate (MVA)',0.001),
                              copper_losses=item.get('Copper losses (kW)',0.0),
                              iron_losses=item.get('No load losses (kW)',0.0),
                              no_load_current=item.get('No load current (%)',0.0),
                              short_circuit_voltage=item.get('V short circuit (%)',0.0),
                              gr_hv1=item.get("gr_hv1",0.5),
                              gx_hv1=item.get("gx_hv1",0.5),
                              name=item.get('Name',"TransformerType_{}".format(i)))
        lst.append(tpe)

    return lst


def parse_cable_types(df: pd.DataFrame) -> List[UndergroundLineType]:
    """

    :param df:
    :return:
    """
    lst = list()
    for i, item in df.iterrows():
        tpe = UndergroundLineType(name=item.get('Name',"UndergroundLine_{}".format(i)),
                                  Imax=item.get('Rated current [kA]',1.0),
                                  Vnom=item.get('Rated voltage [kV]',1.0),
                                  R=item.get('R [Ohm/km AC@20°C]',0.0),
                                  X=item.get('X [Ohm/km]',0.0),
                                  B=item.get('B [uS/km]', 0.0),
                                  R0=item.get('R0 (AC) [Ohm/km]',0.0),
                                  X0=item.get('X0  [Ohm/km]',0.0),
                                  B0=item.get('B0 [uS/km]',0.0))
        lst.append(tpe)

    return lst


def parse_wire_types(df: pd.DataFrame) -> List[Wire]:
    """

    :param df:
    :return:
    """
    lst = list()
    for i, item in df.iterrows():
        tpe = Wire(name=str(item['Stranding']) + '_' + str(item['Material']) + '_' + str(item['Diameter [cm]']),
                   stranding=item.get('Stranding',""),
                   material=item.get('Material',""),
                   diameter=item.get('Diameter [cm]',0.0),
                   gmr=item.get('GMR [m]',0.01),
                   r=item.get('R [Ohm/km]',0.01),
                   x=item.get("X [Ohm/km]",0.0),
                   max_current=item.get('Rating [kA]',1.0))
        lst.append(tpe)

    return lst


def parse_sequence_line_types(df: pd.DataFrame) -> List[SequenceLineType]:
    """

    :param df:
    :return:
    """
    lst = list()
    for i, item in df.iterrows():
        tpe = SequenceLineType(name=item.get('Name','SequenceLine_{}'.format(i)),
                               Vnom=item.get('Vnom (kV)',1),
                               Imax=item.get('Imax (kA)',1),
                               R=item.get('r (ohm/km)',0),
                               X=item.get('x (ohm/km)',0),
                               B=item.get('b (uS/km)',0),
                               R0=item.get('r0 (ohm/km)',0),
                               X0=item.get('x0 (ohm/km)',0),
                               B0=item.get('b0 (uS/km)',0))
        lst.append(tpe)

    return lst


def save_catalogue(fname: str, grid: MultiCircuit):
    """

    :param fname:
    :param grid:
    :return:
    """
    with pd.ExcelWriter(fname) as writer:
        df_transformers = get_transformers_catalogue_df(grid)
        df_transformers.to_excel(writer, sheet_name="transformer_types", index=False)
        df_cables = get_cables_catalogue_df(grid)
        df_cables.to_excel(writer, sheet_name="cable_types", index=False)
        df_wires = get_wires_catalogue_df(grid)
        df_wires.to_excel(writer, sheet_name="wire_types", index=False)
        df_sequence_lines = get_sequence_lines_catalogue_df(grid)
        df_sequence_lines.to_excel(writer, sheet_name="sequence_line_types", index=False)


def load_catalogue(fname: str) -> Tuple[Assets, Logger]:
    """

    :param fname:
    :return:
    """
    data = Assets()
    logger = Logger()
    with pd.ExcelFile(fname) as f:
        if "transformer_types" in f.sheet_names:
            df = pd.read_excel(f, sheet_name="transformer_types", index_col=None)
            devices = parse_transformer_types(df)
            data.set_elements_list_by_type(device_type=DeviceType.TransformerTypeDevice,
                                           devices=devices,
                                           logger=logger)
        if "cable_types" in f.sheet_names:
            df = pd.read_excel(f, sheet_name="cable_types", index_col=None)
            devices = parse_cable_types(df)
            data.set_elements_list_by_type(device_type=DeviceType.UnderGroundLineDevice,
                                           devices=devices,
                                           logger=logger)
        if "wire_types" in f.sheet_names:
            df = pd.read_excel(f, sheet_name="wire_types", index_col=None)
            devices = parse_wire_types(df)
            data.set_elements_list_by_type(device_type=DeviceType.WireDevice,
                                           devices=devices,
                                           logger=logger)
        if "sequence_line_types" in f.sheet_names:
            df = pd.read_excel(f, sheet_name="sequence_line_types", index_col=None)
            devices = parse_sequence_line_types(df)
            data.set_elements_list_by_type(device_type=DeviceType.SequenceLineDevice,
                                           devices=devices,
                                           logger=logger)

    return data, logger
