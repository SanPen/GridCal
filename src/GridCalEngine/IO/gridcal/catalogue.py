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
        tpe = TransformerType(hv_nominal_voltage=item['HV (kV)'],
                              lv_nominal_voltage=item['LV (kV)'],
                              nominal_power=item['Rate (MVA)'],
                              copper_losses=item['Copper losses (kW)'],
                              iron_losses=item['No load losses (kW)'],
                              no_load_current=item['No load current (%)'],
                              short_circuit_voltage=item['V short circuit (%)'],
                              gr_hv1=0.5,
                              gx_hv1=0.5,
                              name=item['Name'])
        lst.append(tpe)

    return lst


def parse_cable_types(df: pd.DataFrame) -> List[UndergroundLineType]:
    """

    :param df:
    :return:
    """
    lst = list()
    for i, item in df.iterrows():
        tpe = UndergroundLineType(name=item['Name'],
                                  Imax=item['Rated current [kA]'],
                                  Vnom=item['Rated voltage [kV]'],
                                  R=item['R [Ohm/km AC@20°C]'],
                                  X=item['X [Ohm/km]'],
                                  B=0.0,
                                  R0=item['R0 (AC) [Ohm/km]'],
                                  X0=item['X0  [Ohm/km]'],
                                  B0=0.0)
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
                   stranding=item['Stranding'],
                   material=item['Material'],
                   diameter=item['Diameter [cm]'],
                   gmr=item['GMR [m]'],
                   r=item['R [Ohm/km]'],
                   x=0.0,
                   max_current=item['Rating [kA]'])
        lst.append(tpe)

    return lst


def parse_sequence_line_types(df: pd.DataFrame) -> List[SequenceLineType]:
    """

    :param df:
    :return:
    """
    lst = list()
    for i, item in df.iterrows():
        tpe = SequenceLineType(name=item['Name'],
                               Vnom=item['Vnom (kV)'],
                               Imax=item['Imax (kA)'],
                               R=item['r (ohm/km)'],
                               X=item['x (ohm/km)'],
                               B=item['b (uS/km)'],
                               R0=item['r0 (ohm/km)'],
                               X0=item['x0 (ohm/km)'],
                               B0=item['b0 (uS/km)'])
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
