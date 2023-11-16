import os
import pandas as pd

from GridCalEngine.IO.cim.db.base_db import BaseDb
from GridCalEngine.IO.cim.db.file_system import get_create_roseta_db_folder
from GridCalEngine.IO.raw.devices.psse_circuit import PsseCircuit


class PSSeLookUpDb(BaseDb):

    def __init__(self, new_db=False):
        """

        :param new_db: By default load from the disk
        """
        here = os.path.dirname(os.path.abspath(__file__))
        BaseDb.__init__(self,
                        db_folder=os.path.join(get_create_roseta_db_folder(), 'PSSeLookUp'),
                        db_extension='.xlsx',
                        new_db=new_db,
                        init_files=[os.path.join(here, '..', 'data', 'main_psse_lookup.xlsx')])

        self.areas: pd.DataFrame = pd.DataFrame(columns=['psse_id', 'rdfid'])
        self.zones: pd.DataFrame = pd.DataFrame(columns=['psse_id', 'rdfid'])
        self.buses: pd.DataFrame = pd.DataFrame(columns=['psse_id', 'rdfid'])
        self.loads: pd.DataFrame = pd.DataFrame(columns=['psse_id', 'rdfid'])
        self.generators: pd.DataFrame = pd.DataFrame(columns=['psse_id', 'rdfid'])
        self.induction_machines: pd.DataFrame = pd.DataFrame(columns=['psse_id', 'rdfid'])
        self.switched_shunts: pd.DataFrame = pd.DataFrame(columns=['psse_id', 'rdfid'])
        self.fixed_shunts: pd.DataFrame = pd.DataFrame(columns=['psse_id', 'rdfid'])
        self.branches: pd.DataFrame = pd.DataFrame(columns=['psse_id', 'rdfid'])
        self.transformers: pd.DataFrame = pd.DataFrame(columns=['psse_id', 'rdfid'])
        self.facts: pd.DataFrame = pd.DataFrame(columns=['psse_id', 'rdfid'])
        self.two_terminal_dc_lines: pd.DataFrame = pd.DataFrame(columns=['psse_id', 'rdfid'])
        self.vsc_dc_lines: pd.DataFrame = pd.DataFrame(columns=['psse_id', 'rdfid'])

        self.__dataframes_index = {"areas": None,
                                   "zones": None,
                                   "buses": None,
                                   "loads": None,
                                   "generators": None,
                                   "induction_machines": None,
                                   "switched_shunts": None,
                                   "fixed_shunts": None,
                                   "branches": None,
                                   "transformers": None,
                                   "facts": None,
                                   "two_terminal_dc_lines": None,
                                   "vsc_dc_lines": None}

    def read_db_file(self, file_name):
        """
        This function reads the DB from an excel file
        :param file_name: name of the file (not the path)
        """
        file_path = os.path.join(self.db_folder, file_name)
        with pd.ExcelFile(file_path) as f:
            for sheet_name in f.sheet_names:
                if hasattr(self, sheet_name):
                    df = pd.read_excel(f, sheet_name=sheet_name, index_col=None)
                    setattr(self, sheet_name, df)

        self.last_file_opened = file_name
        self.save_config()

    def write_db_file(self, file_name):
        """
        Write DB to excel
        :param file_name: name of the file (not the path)
        """
        file_path = os.path.join(self.db_folder, file_name)
        with pd.ExcelWriter(file_path) as f:
            for key in self.get_structures_names():
                df = getattr(self, key)
                df.to_excel(f, sheet_name=key, index=False)

        self.last_file_opened = file_name
        self.save_config()
        self.refresh()

    def get_df(self, name) -> pd.DataFrame:

        # get the appropriate dataframe
        return getattr(self, name)

    def get_available_table_names(self):
        """
        Get a list of the available tables
        :return:
        """
        return list(self.__dataframes_index.keys())

    @staticmethod
    def get_from_psse_lookup(df: pd.DataFrame):
        """
        Get a dictionary with the PSSe id as key and the RDFID as value
        :param df: lookup DataFrame
        :return:
        """
        # get the appropriate dataframe
        return {row['psse_id']: row['rdfid'] for i, row in df.iterrows()}

    def get_structures_names(self):
        return list(self.__dataframes_index.keys())


def create_PSSeLookUpDb(circuit: PsseCircuit) -> PSSeLookUpDb:
    db = PSSeLookUpDb(new_db=True)

    db_structs = db.get_structures_names()

    all_ids = set()

    for prop in circuit.get_properties():

        if prop.class_type not in [str, bool, int, float]:
            if prop.property_name in db_structs:
                data = list()
                for obj in getattr(circuit, prop.property_name):
                    psse_id = obj.get_id()
                    cgmes_id = obj.get_uuid5()
                    data.append([psse_id, cgmes_id])

                    # check
                    if cgmes_id in all_ids:
                        print(cgmes_id, 'for ', prop.property_name, ' at ', psse_id, ' collides :(')
                    else:
                        all_ids.add(cgmes_id)

                df = pd.DataFrame(columns=['psse_id', 'rdfid'], data=data)
                setattr(db, prop.property_name, df)

    return db
