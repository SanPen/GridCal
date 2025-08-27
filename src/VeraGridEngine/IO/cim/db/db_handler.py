# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import json
from VeraGridEngine.IO.cim.db.file_system import get_create_roseta_db_folder
from VeraGridEngine.IO.cim.db.psse_lookup_db import PSSeLookUpDb
from VeraGridEngine.IO.cim.db.cgmes_lookup_db import CgmesLookUpDb


class DbHandler:

    def __init__(self, new_db=False):

        # get / create DB folder
        self.db_folder = get_create_roseta_db_folder()

        self.psse_lookup_db: PSSeLookUpDb = PSSeLookUpDb(new_db=new_db)

        self.cgmes_lookup_db: CgmesLookUpDb = CgmesLookUpDb(new_db=new_db)


