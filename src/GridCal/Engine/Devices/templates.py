# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

import os
import pandas as pd
from GridCal.Engine.Devices.line import LineTemplate
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

if __name__ == '__main__':
    get_transformer_catalogue()