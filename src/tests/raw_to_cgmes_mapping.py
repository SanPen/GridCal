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
import numpy as np
import GridCal.Engine as gce
import GridCal.api as gca

from GridCal.Engine.IO.raw.raw_parser_writer import read_raw
from GridCal.Engine.IO.cim.cgmes_2_4_15.devices.topological_node import TopologicalNode
from GridCal.Engine.IO.cim.cgmes_2_4_15.cgmes_circuit import CgmesCircuit


this_dir = os.path.dirname(os.path.realpath(__file__))

# load the RAW file
psse_circuit = read_raw(filename=os.path.join(this_dir, 'data', 'grids', 'RAW', '202101181105_mod_def.raw'))

# create the CGMES circuit and load the boundary set
cgmes_circuit = CgmesCircuit()
cgmes_circuit.parse_files(files=[os.path.join(this_dir, 'data', 'grids', 'CGMES_2_4_15', 'ENTSOe_boundary_set.zip')])
base_voltages_dict = cgmes_circuit.get_boundary_voltages_dict()


# Buses
for b1 in psse_circuit.buses:

    cgmes_bus = TopologicalNode(rdfid=b1.get_rdfid())
    cgmes_bus.name = b1.NAME
    cgmes_bus.BaseVoltage = base_voltages_dict.get(b1.BASKV, None)

    cgmes_circuit.add(cgmes_bus)

print()
