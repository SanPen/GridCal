# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

import chardet


class PSSeParser:

    def __init__(self, file_name):
        """
        Parse PSSe file
        Args:
            file_name: file name or path
        """
        self.parsers = dict()
        self.versions = [33, 32, 30]

        self.pss_grid = self.parse_psse(file_name)

        self.circuit = self.pss_grid.get_circuit()

    def parse_psse(self, file_name):
        """
        Parser implemented according to:
            - POM section 5.2.1 (v.33)
            - POM section 5.2.1 (v.32)

        Args:
            file_name:

        Returns:

        """
        print('Parsing ', file_name)

        # make a guess of the file encoding
        detection = chardet.detect(open(file_name, "rb").read())

        # open the text file into a variable
        with open(file_name, 'r', encoding=detection['encoding']) as my_file:
            txt = my_file.read()

        # split the text file into sections
        sections = txt.split(' /')

        # header -> new grid
        grid = PSSeGrid(interpret_line(sections[0]))

        if grid.REV not in self.versions:
            raise Exception('The PSSe version is not compatible. Compatible versions are:', self.versions)
        else:
            version = grid.REV

        meta_data = list()
        # declare contents:
        # section_idx, objects_list, expected_data_length, ObjectT, lines per objects

        # SEQUENCE ORDER:
        # 0:  Case Identification Data
        # 1:  Bus Data
        # 2:  Load Data
        # 3:  Fixed Bus Shunt Data
        # 4:  Generator Data
        # 5:  Non-Transformer Branch Data
        # 6:  Transformer Data
        # 7:  Area Interchange Data
        # 8:  Two-Terminal DC Transmission Line Data
        # 9:  Voltage Source Converter (VSC) DC Transmission Line Data
        # 10: Transformer Impedance Correction Tables
        # 11: Multi-Terminal DC Transmission Line Data
        # 12: Multi-Section Line Grouping Data
        # 13: Zone Data
        # 14: Interarea Transfer Data
        # 15: Owner Data
        # 16: FACTS Device Data
        # 17: Switched Shunt Data
        # 18: GNE Device Data
        # 19: Induction Machine Data
        # 20: Q Record

        meta_data.append([1, grid.buses, PSSeBus, 1])
        meta_data.append([2, grid.loads, PSSeLoad, 1])
        meta_data.append([3, grid.shunts, PSSeShunt, 1])
        meta_data.append([4, grid.generators, PSSeGenerator, 1])
        meta_data.append([5, grid.branches, PSSeBranch, 1])
        meta_data.append([6, grid.transformers, PSSeTransformer, 4])

        for section_idx, objects_list, ObjectT, lines_per_object in meta_data:

            # split the section lines by object declaration: '\n  ' delimits each object start.
            lines = sections[section_idx].split('\n  ')

            # this removes the useless header
            lines.pop(0)

            # iterate ove the object's lines
            for line in lines:
                # pick the line that matches the object and split it by line returns \n
                object_lines = line.split('\n')

                # interpret each line of the object and store into data
                # data is a vector of vectors with data definitions
                # for the buses, branches, loads etc. data contains 1 vector,
                # for the transformers data contains 4 vectors
                data = [interpret_line(object_lines[k]) for k in range(lines_per_object)]

                # pass the data to the according object to assign it to the matching variables
                objects_list.append(ObjectT(data, version))

        return grid
