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

import os
import pandas as pd
from GridCalEngine.Devices.Branches.line import SequenceLineType, UndergroundLineType
from GridCalEngine.Devices.Branches.transformer import TransformerType
from GridCalEngine.Devices.Branches.wire import Wire
from GridCalEngine.IO.gridcal.catalogue import parse_transformer_types, parse_cable_types, parse_wire_types, parse_sequence_line_types


def get_transformer_catalogue():
    """

    :return:
    """
    here = os.path.dirname(os.path.abspath(__file__))
    fname = os.path.join(here, 'data', 'transformers.csv')

    if os.path.exists(fname):
        df = pd.read_csv(fname)

        return parse_transformer_types(df)
    else:
        return list()


def get_cables_catalogue():
    """

    :return:
    """
    here = os.path.dirname(os.path.abspath(__file__))
    fname = os.path.join(here, 'data', 'cables.csv')

    if os.path.exists(fname):
        df = pd.read_csv(fname)

        return parse_cable_types(df)
    else:
        return list()


def get_wires_catalogue():
    """

    :return:
    """
    here = os.path.dirname(os.path.abspath(__file__))
    fname = os.path.join(here, 'data', 'wires.csv')

    if os.path.exists(fname):
        df = pd.read_csv(fname)

        return parse_wire_types(df)
    else:
        return list()


def get_sequence_lines_catalogue():
    """

    :return:
    """
    here = os.path.dirname(os.path.abspath(__file__))
    fname = os.path.join(here, 'data', 'sequence_lines.csv')

    if os.path.exists(fname):
        df = pd.read_csv(fname)

        return parse_sequence_line_types(df)
    else:
        return list()
