
import os
import json
from GridCalEngine.IO.cim.db.file_system import get_create_roseta_db_folder
from GridCalEngine.IO.cim.db.psse_lookup_db import PSSeLookUpDb
from GridCalEngine.IO.cim.db.cgmes_lookup_db import CgmesLookUpDb


class DbHandler:

    def __init__(self, new_db=False):

        # get / create DB folder
        self.db_folder = get_create_roseta_db_folder()

        self.psse_lookup_db: PSSeLookUpDb = PSSeLookUpDb(new_db=new_db)

        self.cgmes_lookup_db: CgmesLookUpDb = CgmesLookUpDb(new_db=new_db)


