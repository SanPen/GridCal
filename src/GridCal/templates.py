# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0


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
