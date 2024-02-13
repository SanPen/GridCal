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
import numpy as np
import json


def parse_config_df(df, data=None):
    if data is None:
        data = dict()

    if 'baseMVA' in df.index:
        data["baseMVA"] = float(df.at['name', 'Value'])
    else:
        data["baseMVA"] = 100

    if 'version' in df.index:
        data["version"] = float(df.at['version', 'Value'])

    if 'name' in df.index:
        data["name"] = df.at['name', 'Value']
    elif 'Name' in df.index:
        data["name"] = df.at['Name', 'Value']
    else:
        data["name"] = 'Grid'

    if 'Comments' in df.index:
        data["Comments"] = df.at['Comments', 'Value']
    else:
        data["Comments"] = ''

    if 'ModelVersion' in df.index:
        data["ModelVersion"] = df.at['ModelVersion', 'Value']
    else:
        data["ModelVersion"] = 1

    if 'UserName' in df.index:
        data["UserName"] = df.at['UserName', 'Value']
    else:
        pass

    return data


class CustomJSONizer(json.JSONEncoder):
    def default(self, obj):
        # this solves the error:
        # TypeError: Object of type bool_ is not JSON serializable
        return super().encode(bool(obj)) if isinstance(obj, np.bool_) else super().default(obj)
