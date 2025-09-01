# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


try:

    from VeraGridEngine.enumerations import *
    from VeraGridEngine.basic_structures import *
    from VeraGridEngine.Simulations import *
    from VeraGridEngine.IO import *
    from VeraGridEngine.Devices import *
    from VeraGridEngine.DataStructures import *
    from VeraGridEngine.Topology import *
    from VeraGridEngine.Compilers import *
    from VeraGridEngine.IO.file_handler import FileOpen, FileSave, FileSavingOptions
    from VeraGridEngine.IO.veragrid.remote import (gather_model_as_jsons_for_communication, RemoteInstruction,
                                                   SimulationTypes, send_json_data, get_certificate_path,
                                                   get_certificate)
    from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at, NumericalCircuit

    from VeraGridEngine.api import *

    PROPERLY_LOADED_API = True
except ModuleNotFoundError as e:
    print("Modules not found :/", e)
    PROPERLY_LOADED_API = False
except NameError as e:
    print("Name not found :/", e)
    PROPERLY_LOADED_API = False
