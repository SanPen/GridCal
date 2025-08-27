# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
import os
from typing import List

from VeraGridEngine.IO.cim.cgmes.cgmes_data_parser import CgmesDataParser
from VeraGridEngine.IO.cim.db.base_db import BaseDb
from VeraGridEngine.IO.cim.db.file_system import get_create_roseta_db_folder
from VeraGridEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from VeraGridEngine.enumerations import CGMESVersions


class CgmesLookUpDb(BaseDb):
    """
    CgmesLookUpDb
    """

    def __init__(self, new_db=False):
        """

        :param new_db: By default, load from the disk
        """
        here = os.path.dirname(os.path.abspath(__file__))
        BaseDb.__init__(self,
                        db_folder=os.path.join(get_create_roseta_db_folder(), 'CgmesLookUp'),
                        db_extension='.zip',
                        new_db=new_db,
                        init_files=[os.path.join(here, '..', 'data', 'ENTSOe_boundary_set.zip')])

        self.circuit: CgmesCircuit | None = None
        print('loading CGMES boundary set...', end='')
        self.read_db_file(file_name=self.get_last_file_path())
        print('ok')

    def read_db_file(self, file_name):
        """
        Read CGMES database file
        :param file_name:
        :return:
        """
        pth = os.path.join(self.db_folder, file_name)
        data_parser = CgmesDataParser()
        data_parser.load_files(files=[pth])
        self.circuit: CgmesCircuit = CgmesCircuit(cgmes_version=CGMESVersions.v2_4_15)
        self.circuit.parse_files(data_parser=data_parser, delete_unused=False, detect_circular_references=False)

    def get_structures_names(self) -> List[str]:
        """

        :return:
        """
        classes = [prop.property_name for prop in self.circuit.get_class_properties()]
        classes.sort()

        return classes
