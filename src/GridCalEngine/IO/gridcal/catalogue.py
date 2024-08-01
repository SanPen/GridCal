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


def save_catalogue(fname: str, grid: MultiCircuit):
    """

    :param fname:
    :param grid:
    :return:
    """
    with pd.ExcelWriter(fname) as writer:
        df = get_transformers_catalogue_df(grid)
        df.to_excel(writer, sheet_name="transformer_types", index=False)


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

    return data, logger
