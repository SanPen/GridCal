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

def print_power_flow_results(power_flow):
    print('\t|V|:', abs(power_flow.results.voltage))
    print('\t|Sf|:', abs(power_flow.results.Sf))
    print('\t|loading|:', abs(power_flow.results.loading) * 100)
    print('\terr:', power_flow.results.error)
    print('\tConv:', power_flow.results.converged)
