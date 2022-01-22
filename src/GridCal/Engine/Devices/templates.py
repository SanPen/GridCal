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

import os
import pandas as pd
from GridCal.Engine.Devices.line import SequenceLineType
from GridCal.Engine.Devices.transformer import TransformerType
from GridCal.Engine.Devices.wire import Wire


def get_transformer_catalogue():

    path = os.path.dirname(os.path.abspath(__file__))
    fname = os.path.join(path, '..', '..', 'data', 'transformers.csv')

    if os.path.exists(fname):
        df = pd.read_csv(fname)

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
    else:
        return list()


def get_cables_catalogue():

    path = os.path.dirname(os.path.abspath(__file__))
    fname = os.path.join(path, '..', '..', 'data', 'cables.csv')

    if os.path.exists(fname):
        df = pd.read_csv(fname)

        lst = list()
        for i, item in df.iterrows():
            """
            Name,
            Rated voltage [kV],
            Rated current [kA],
            Nominal Frequency,
            R [Ohm/km AC,20°C],
            X [Ohm/km],
            L [Ohm/km],
            R0 (AC) [Ohm/km],
            X0  [Ohm/km]
            L0 [mH/km]
            """
            tpe = SequenceLineType(name=item['Name'],
                                   rating=item['Rated current [kA]'],
                                   R=item['R [Ohm/km AC@20°C]'],
                                   X=item['X [Ohm/km]'],
                                   G=0.0,
                                   B=0.0,
                                   R0=item['R0 (AC) [Ohm/km]'],
                                   X0=item['X0  [Ohm/km]'],
                                   G0=0.0,
                                   B0=0.0)

            lst.append(tpe)

        return lst
    else:
        return list()


def get_wires_catalogue():

    path = os.path.dirname(os.path.abspath(__file__))
    fname = os.path.join(path, '..', '..', 'data', 'wires.csv')

    if os.path.exists(fname):
        df = pd.read_csv(fname)

        lst = list()
        for i, item in df.iterrows():

            '''
            Size,Stranding,Material,Diameter [cm],GMR [m],R [Ohm/km],Rating [kA]
            '''
            name = str(item['Stranding']) + '_' + str(item['Material']) + '_' + str(item['Diameter [cm]'])
            tpe = Wire(name=name,
                       gmr=item['GMR [m]'],
                       r=item['R [Ohm/km]'],
                       x=0.0,
                       max_current=item['Rating [kA]'])
            lst.append(tpe)

        return lst
    else:
        return list()


if __name__ == '__main__':
    tr = get_transformer_catalogue()
    cab = get_cables_catalogue()
    wi = get_wires_catalogue()
    print()
