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

from numpy import intc, double
from enum import Enum

# define the indices
BUS_S           = 0    # bus number (1 to 29997)
STORAGE_TYPE    = 1    # Storage type
PS              = 2    # Pd, real power demand (MW)
QS              = 3    # Qd, reactive power demand (MVAr)
P_MAX_CHARGE    = 4    # Maximum power allowed when changing (negative in the general reference) (MW)
P_MAX_DISCHARGE = 5    # Maximum power allowed when dischanging (positive in the general reference) (MW)
S_CAPACITY      = 6    # Storage capacity (MWh)
SoC_0           = 7    # Storage initial considered state of charge (0~1)
STO_STATUS      = 8    # Storage status (0: off, 1: on)
VM_S            = 9    # Storage voltage set point

storage_format_array = [intc,
                        intc,
                        double,
                        double,
                        double,
                        double,
                        double,
                        double,
                        intc,
                        double
                        ]

storage_headers = ["bus_s",
                   "storage_type",
                   "Ps",
                   "Qs",
                   "P_max_charge",
                   "P_max_discharge",
                   "Capacity",
                   "SoC_0",
                   "Status",
                   "VM"]


class StorageDispatchMode(Enum):
    no_dispatch = 0,
    dispatch_vd = 1,
    dispatch_pv = 2
