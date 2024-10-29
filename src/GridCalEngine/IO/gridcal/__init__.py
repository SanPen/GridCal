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

from GridCalEngine.IO.gridcal.json_parser import save_json_file_v3, parse_json_data_v3
from GridCalEngine.IO.gridcal.excel_interface import interpret_excel_v3, interprete_excel_v2
from GridCalEngine.IO.gridcal.results_export import export_drivers, export_results
from GridCalEngine.IO.gridcal.remote import (gather_model_as_jsons_for_communication, RemoteInstruction,
                                             SimulationTypes, send_json_data, get_certificate_path, get_certificate)