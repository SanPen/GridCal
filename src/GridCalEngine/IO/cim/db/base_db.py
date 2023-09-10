import os
import json
import shutil
from typing import List


class BaseDb:

    def __init__(self, db_folder: str, db_extension: str, new_db=False, init_files: List[str] = ()):
        """
        BaseDb constructor
        :param db_folder: folder of this DB
        :param db_extension: Extension of the DB files (i.e. .xlsx)
        :param init_files: List of file paths to copy
        """

        self.config_file_name = "db_config.json"

        self.last_file_opened = ''

        self.list_of_db_files = list()

        self.db_folder = db_folder

        self.db_extension = db_extension

        if not new_db:

            # open the config file
            self.open_config()

            # if the DB folder does not exist, create it
            if not os.path.exists(self.db_folder):
                os.makedirs(self.db_folder)

            # copy any missing file
            any_file_copied = False
            for src in init_files:
                name = os.path.basename(src)
                dst = os.path.join(self.db_folder, name)

                if os.path.exists(src) and not os.path.exists(dst):
                    shutil.copyfile(src, dst)
                    any_file_copied = True

            # refresh the list of available files
            self.refresh()

            # if any file was copied, set the last file to the first available file
            if any_file_copied:
                self.last_file_opened = self.list_of_db_files[0]
                self.save_config()

    def refresh(self):
        # get the list of files
        self.list_of_db_files = self.get_list_of_db_files()

    def get_last_file_path(self):
        return os.path.join(self.db_folder, self.last_file_opened)

    def save_config(self):
        """
        Save configuration file
        :return:
        """
        data = {"last_file_opened": self.last_file_opened}
        file_path = os.path.join(self.db_folder, self.config_file_name)
        with open(file_path, "w") as f:
            f.write(json.dumps(data, indent=4, sort_keys=True))

    def open_config(self):
        """
        Save configuration file
        :return:
        """
        file_path = os.path.join(self.db_folder, self.config_file_name)

        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                data = json.load(f)
                self.last_file_opened = data['last_file_opened']

    def get_list_of_db_files(self):
        """
        Get list of db files
        :return:
        """
        return [x for x in os.listdir(self.db_folder) if x.endswith(self.db_extension)]

    def read_db_file(self, file_name):
        pass

    def get_structures_names(self) -> List[str]:
        return []

