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
import os
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from enum import Enum
import zipfile
from xml.etree import cElementTree as ElementTree
from GridCalEngine.Devices import Bus, Generator, Load, Transformer2W, Line
from GridCalEngine.Devices.multi_circuit import MultiCircuit


class XmlDictConfig(dict):
    """
    Note: need to add a root into if no exising
    Example usage:
    >>> tree = ElementTree.parse('your_file.xml')
    >>> root = tree.getroot()
    >>> xmldict = XmlDictConfig(root)
    Or, if you want to use an XML string:
    >>> root = ElementTree.XML(xml_string)
    >>> xmldict = XmlDictConfig(root)
    And then use xmldict for what it is... a dict.
    """

    def __init__(self, parent_element, text_to_remove=''):
        """

        :param parent_element:
        :param text_to_remove:
        """
        dict.__init__(self)
        self.text_to_remove = text_to_remove

        if parent_element.items():
            self.update_shim(dict(parent_element.items()))

        for element in parent_element:

            tag = element.tag.replace(self.text_to_remove, '')

            if len(element):

                a_dict = XmlDictConfig(element, self.text_to_remove)

                self.update_shim({tag: a_dict})

            elif element.items():  # items() is especialy for attributes

                element_attrib = element.items()

                if element.text:
                    element_attrib.append((tag, element.text))  # add tag:text if there exist

                self.update_shim({tag: dict(element_attrib)})
            else:
                self.update_shim({tag: element.text})

    def update_shim(self, a_dict):
        """

        :param a_dict:
        :return:
        """
        for og_key in a_dict.keys():  # keys() includes tag and attributes

            key = og_key.replace(self.text_to_remove, '')

            if key in self:
                value = self.pop(key)
                if type(value) is not list:
                    list_of_dicts = list()
                    list_of_dicts.append(value)
                    list_of_dicts.append(a_dict[key])
                    self.update({key: list_of_dicts})
                else:
                    value.append(a_dict[key])
                    self.update({key: value})
            else:
                self.update({key: a_dict[key]})  # it was self.update(aDict)


class PlxBusMode(Enum):
    PQ = 1
    PV = 2
    REF = 3
    NONE = 4
    STO_DISPATCH = 5  # Storage dispatch, in practice it is the same as REF


class PlxElement:

    def __init__(self, name):
        """
        Generic element constructor
        :param name: Name of the element
        """
        self.name = name

    def __str__(self):
        return self.name


class PlxNode(PlxElement):

    def __init__(self, name='', zone='', region='', voltage=0, latitude=0, longitude=0):

        PlxElement.__init__(self, name=name)

        self.zone = zone

        self.region = region

        self.voltage = voltage

        self.latitude = latitude

        self.longitude = longitude

        self.load = 0.0

        self.load_prof = None

        self.generators = list()

        self.batteries = list()

        self.key = 0  # usually the PSS/e key...

        # get the PSS/e name if that'd be there (PSSNODE_NAME_KV)
        if '_' in self.name:
            self.key = self.name.split('_')[0]
            try:
                self.key = int(self.key)  # try to set it as an integer value
            except ValueError:
                pass


class PlxGenerator(PlxElement):

    def __init__(self, name='', category='', p_max=0, p_min=0, node=None):
        PlxElement.__init__(self, name=name)

        self.category = category

        self.p_max = p_max

        self.p_min = p_min

        self.node = None

        self.rating_factor_prof = None

        self.aux_fixed_prof = None

        self.must_run_units_prof = None


class PlexosBattery(PlxGenerator):

    def __init__(self, name='', category=''):
        """

        :param name:
        :param category:
        """
        PlxGenerator.__init__(self, name=name, category=category)


class PlxLine(PlxElement):

    def __init__(self, name='', units=1, node_from=None, node_to=None, r=0.0, x=0.0, rate_max=0.0, rate_min=0.0):
        """

        :param name:
        :param units: number of active units (if 0, then the line is not active)
        :param node_from:
        :param node_to:
        :param r:
        :param x:
        :param rate_max:
        :param rate_min:
        """
        PlxElement.__init__(self, name=name)

        self.units = units

        self.node_from = node_from

        self.node_to = node_to

        self.r = r

        self.x = x

        self.rate_max = rate_max

        self.rate_min = rate_min

        self.coordinates = list()

        self.rate_max_prof = None

        self.rate_min_prof = None

    def get_key(self, sep='-'):
        """
        Split the name in the plexos way to get the new key
        """
        vals = self.name.split('_')
        return vals[0] + sep + vals[3] + sep + vals[6]

    def get_highest_voltage(self):
        """
        Return the highest voltage at which this line is connected
        :return:
        """
        return max(self.node_from.voltage, self.node_to.voltage)

    def delete_zero_coordinates(self):
        """

        :return:
        """
        # delete coordinates with zeros
        for k in range(len(self.coordinates) - 1, -1, -1):
            a, b = self.coordinates[k]
            if a == 0.0 or b == 0.0:
                self.coordinates.pop(k)

    def get_coordinates(self):
        """
        Get polyline of coordinates
        :return:
        """
        if len(self.coordinates) >= 2:
            locations = self.coordinates
        else:
            locations = [[self.node_from.latitude, self.node_from.longitude],
                         [self.node_to.latitude, self.node_to.longitude]]

        # delete coordinates with zeros
        for k in range(len(locations) - 1, -1, -1):
            a, b = locations[k]
            if (a + b) <= 0:
                locations.pop(k)

        return locations


class PlxTransformer(PlxLine):

    def __init__(self, name=''):
        PlxLine.__init__(self, name=name)


class PlxZone(PlxElement):

    def __init__(self, name=''):
        PlxElement.__init__(self, name=name)


class PlxRegion(PlxElement):

    def __init__(self, name=''):
        PlxElement.__init__(self, name=name)


class PlxModel:

    def __init__(self, fname, load_profiles=True, text_func=None, prog_func=None):
        """
        Plexos model
        :param fname: plexos file name (either .zip or .xml)
        :param load_profiles: load profiles associated
        :param text_func: function pointer to print text
        :param prog_func: function pointer to show the progress
        """

        # name of the project file
        self.file_name = fname
        self.load_profiles = load_profiles
        self.text_func = text_func
        self.prog_func = prog_func

        # directory of this project
        self.directory = os.path.dirname(self.file_name)

        # name of this instance
        self.name = ''

        # dictionary of nodes
        self.nodes = dict()

        # dictionary of generators
        self.generators = dict()

        # dictionary of batteries
        self.batteries = dict()

        # dictionary of lines
        self.lines = dict()

        # dictionary of transformers
        self.transformers = dict()

        # dictionary of lines and transformers all together
        self.branches = dict()

        # dictionary of zones
        self.zones = dict()

        # dictionary of regions
        self.regions = dict()

        # dictionary of transformers od/or lines. dict['line']['line name']
        self.branches_by_type = dict()

        # dictionary of data profiles. The profiles are loaded on the fly
        self.data_profiles = dict()

        # load the project file
        self.load_project_file(fname=self.file_name)

    def load_project_file(self, fname):
        """
        Load a PLEXOS project file
        :param fname: name of the plexos project file (*.zip, *.xml, *.xlsx)
        """
        # split the file name path into name and extension
        filename, file_extension = os.path.splitext(fname)

        # parse the file information
        if file_extension == '.xlsx':
            objects2, memberships2, data = self.parse_excel(fname=self.file_name)
            zip_file_pointer = None

        elif file_extension == '.xml':
            objects2, memberships2, data = self.parse_xml(fname=self.file_name)
            zip_file_pointer = None

        elif file_extension == '.zip':
            objects2, memberships2, data, zip_file_pointer = self.parse_zip(fname=self.file_name)

        else:
            raise Exception('File type not supported: ' + fname)

        # convert the xml data into objects for this class
        self.parse_data(objects=objects2,
                        memberships=memberships2,
                        properties=data,
                        zip_file_pointer=zip_file_pointer)

        # close the zip file
        if zip_file_pointer is not None:
            zip_file_pointer.close()

    def load_profile(self, path, zip_file_pointer=None):
        """
        Attempt loading the profile
        :param path: relative or absolute path
        :param zip_file_pointer: pointer to open zip file is the file ins inside a zip file
        :return: DataFrame
        """
        if zip_file_pointer is not None:
            # create a buffer to read the file
            path2 = path.replace('\\', '/')
            final_path = zip_file_pointer.open(path2)
            df = pd.read_csv(final_path)
            return df

        else:
            if ':' in path:
                final_path = path
            else:
                final_path = os.path.join(self.directory, path)

            if os.path.exists(final_path):
                df = pd.read_csv(final_path)
                return df
            else:
                print(final_path, 'not found :(')
                return None

    def load_profile_if_necessary(self, key, path, zip_file_pointer=None):
        """
        Load a profile is necessary
        :param key: object property type
        :param path: relative or absolute path where to find the file
        :param zip_file_pointer: pointer to open zip file is the file ins inside a zip file
        :return: Nothing
        """

        if key not in self.data_profiles.keys():

            df = self.load_profile(path=path, zip_file_pointer=zip_file_pointer)

            if df is not None:
                self.data_profiles[key] = df
                return df
            else:
                # the profile does not exist
                return False
        else:
            # the profile exists
            return self.data_profiles[key]

    def parse_zip(self, fname):
        """
        Parse zip file with the plexos xml and the profiles utilized
        :param fname: zip file name
        :return: Nothing
        """
        # open the zip file
        zip_file_pointer = zipfile.ZipFile(fname)

        # search for the xml file
        names = zip_file_pointer.namelist()
        xml_file_name = None
        for name in names:
            if name.endswith('.xml'):
                xml_file_name = name
                break

        if xml_file_name is not None:
            # parse the xml and read the data profiles
            objects2, memberships2, data = self.parse_xml(xml_file_name, zip_file_pointer=zip_file_pointer)

        else:
            raise Exception('No xml file was found in the zip file', fname)

        return objects2, memberships2, data, zip_file_pointer

    @staticmethod
    def parse_excel(fname):
        """
        Parse excel export of the plexos file
        :param fname: complete path to the file
        """
        excel = pd.ExcelFile(fname)

        print('Reading objects...')
        objects = excel.parse(sheet_name='Objects')

        print('Reading Memberships...')
        memberships = excel.parse(sheet_name='Memberships')

        print('Reading Properties...')
        properties = excel.parse(sheet_name='Properties')
        properties.rename(columns={'filename': 'path'})
        excel.close()

        # file_dict = {row['child_object']: row['filename'] for i, row in properties.iterrows()}

        return objects, memberships, properties

    def parse_xml(self, fname, zip_file_pointer=None):
        """
        Parse PLEXOS file
        :param fname: xml PLEXOS file name
        :param zip_file_pointer: pointer to a zip file, if not none, the file will be read from within a zip file
        """
        if self.text_func is None:
            print('Parsing plexos xml', fname, '...')
        else:
            self.text_func('Parsing plexos xml ' + fname)

        # read xml tree from file or from zip-file pointer
        if zip_file_pointer is not None:
            file_pointer = zip_file_pointer.open(fname)
            xtree = ElementTree.parse(file_pointer)
        else:
            xtree = ElementTree.parse(fname)

        # get xml root node
        root = xtree.getroot()

        # text to remove: {http://tempuri.org/MasterDataSet.xsd}
        # this is a very annoying text that is present in all the xml nodes
        text_to_remove = root.tag[root.tag.find("{"):root.tag.find("}") + 1]

        # pass the XML file to a dictionary
        xmldict = XmlDictConfig(root, text_to_remove=text_to_remove)

        # pass the dictionaries to Pandas DataFrames
        classes = pd.DataFrame(xmldict['t_class'])
        category = pd.DataFrame(xmldict['t_category'])
        collections = pd.DataFrame(xmldict['t_collection'])

        '''
        objects 
        class	GUID	name	category
        '''
        objects = pd.DataFrame(xmldict['t_object'])
        objects2 = objects.copy()
        objects2['class_id'] = objects2['class_id'].map(classes.set_index('class_id')['name'])
        objects2['category_id'] = objects2['category_id'].map(category.set_index('category_id')['name'])
        objects2.rename(columns={'class_id': 'class', 'category_id': 'category'}, inplace=True)

        '''
        Membership
        parent_class	child_class	   collection	parent_object	child_object
        '''
        memberships = pd.DataFrame(xmldict['t_membership'])

        memberships2 = memberships.copy()
        memberships2['parent_class_id'] = memberships2['parent_class_id'].map(classes.set_index('class_id')['name'])
        memberships2['child_class_id'] = memberships2['child_class_id'].map(classes.set_index('class_id')['name'])
        memberships2['parent_object_id'] = memberships2['parent_object_id'].map(objects.set_index('object_id')['name'])
        memberships2['child_object_id'] = memberships2['child_object_id'].map(objects.set_index('object_id')['name'])
        memberships2['collection_id'] = memberships2['collection_id'].map(
            collections.set_index('collection_id')['name'])
        memberships2.rename(columns={'parent_class_id': 'parent_class',
                                     'child_class_id': 'child_class',
                                     'parent_object_id': 'parent_object',
                                     'child_object_id': 'child_object',
                                     'collection_id': 'collection'}, inplace=True)

        '''
        Properties
        parent_class	child_class	collection	parent_object	child_object	property	band_id	value	units	
        date_from	date_to	pattern	action	expression	filename	scenario	memo	period_type_id
        '''
        attribute = pd.DataFrame(xmldict['t_attribute'])
        attribute_data = pd.DataFrame(xmldict['t_attribute_data'])
        # attributes = pd.merge(attribute, attribute_data, on='attribute_id')

        data = pd.DataFrame(xmldict['t_data'])
        tag = pd.DataFrame(xmldict['t_tag'])
        text = pd.DataFrame(xmldict['t_text'])
        text.rename(columns={'value': 'path'}, inplace=True)

        properties = pd.DataFrame(xmldict['t_property'])

        data = pd.merge(data, memberships2, on='membership_id')
        data = pd.merge(data, text, on='data_id', how='left')
        data = pd.merge(data, tag, on='data_id', how='left')
        data['property_id'] = data['property_id'].map(properties.set_index('property_id')['name'])
        data['object_id'] = data['object_id'].map(objects.set_index('object_id')['name'])
        data.rename(columns={'property_id': 'property', 'object_id': 'filename'}, inplace=True)

        return objects2, memberships2, data

    def parse_data(self, objects, memberships, properties, zip_file_pointer=None):
        """
        Pass the loaded DataFrames to model objects
        :param objects: Objects DataFrame
        :param memberships: Memberships DataFrame
        :param properties: Properties DataFrame
        :param zip_file_pointer: zip file pointer. If not None the data will be read from a zip file
        :return: Nothing
        """
        # create the objects
        if self.text_func is None:
            print('Reading plexos xml file...', end='')
        else:
            self.text_func('Reading plexos xml file... ')

        for i, row in objects.iterrows():

            if row['class'] == 'Generator':
                elm = PlxGenerator(name=row['name'], category=row['category'])
                self.generators[elm.name] = elm

            elif row['class'] == 'Node':
                elm = PlxNode(name=row['name'], zone=row['category'])
                self.nodes[elm.name] = elm

            elif row['class'] == 'Line':
                elm = PlxLine(name=row['name'])
                self.lines[elm.name] = elm
                self.branches[elm.name] = elm

            elif row['class'] == 'Transformer':
                elm = PlxTransformer(name=row['name'])
                self.transformers[elm.name] = elm
                self.branches[elm.name] = elm

            elif row['class'] == 'Zone':
                elm = PlxZone(name=row['name'])
                self.zones[elm.name] = elm

            elif row['class'] == 'Region':
                elm = PlxRegion(name=row['name'])
                self.regions[elm.name] = elm

        # store the Branches by type
        self.branches_by_type['Line'] = self.lines
        self.branches_by_type['Transformer'] = self.transformers

        # parse the memberships (node of the elements, region of the nodes, etc...)
        for i, row in memberships.iterrows():
            cls = row['parent_class']
            name = row['parent_object']
            member = row['child_object']

            if cls in ['Line', 'Transformer']:
                if row['collection'] == 'Node From':
                    self.branches_by_type[cls][name].node_from = self.nodes[member]
                elif row['collection'] == 'Node To':
                    self.branches_by_type[cls][name].node_to = self.nodes[member]

            elif cls == 'Node':
                if row['collection'] == 'Region':
                    self.nodes[name].region = self.regions[member]
                elif row['collection'] == 'Zone':
                    self.nodes[name].zone = self.zones[member]

            elif cls == 'Generator':
                if row['collection'] == 'Schema':
                    self.generators[name].node = self.nodes[member]
                    self.nodes[member].generators.append(self.generators[name])

        # make dictionary of file objects -> file paths
        files_info = properties[properties['child_class'] == 'Data File']
        file_dict = {row['child_object']: row['path'] for i, row in files_info.iterrows()}

        # parse the properties of the objects

        if self.text_func is not None:  # show progress
            self.text_func('Parsing properties')

        used_profiles = set()
        for i, row in properties.iterrows():
            cls = row['child_class']
            name = row['child_object']
            prop = row['property']
            file_obj = row['filename']

            if isinstance(file_obj, float):
                if np.isnan(file_obj):
                    file_obj = None

            if cls == 'Node':

                if prop == 'Voltage':
                    self.nodes[name].voltage = float(row['value'])

                elif prop == 'Fixed Load':
                    self.nodes[name].load = float(row['value'])

                    if file_obj is not None:
                        self.nodes[name].load_prof = file_obj
                        used_profiles.add(file_obj)

            elif cls in ['Line', 'Transformer']:

                if prop == 'Units':
                    self.branches_by_type[cls][name].units = float(row['value'])

                elif prop == 'Resistance':
                    self.branches_by_type[cls][name].R = float(row['value'])

                elif prop == 'Reactance':
                    self.branches_by_type[cls][name].X = float(row['value'])

                elif prop == 'Max Flow':
                    self.branches_by_type[cls][name].rate_max = float(row['value'])

                    if file_obj is not None:
                        self.branches_by_type[cls][name].rate_max_prof = file_obj
                        used_profiles.add(file_obj)

                elif prop == 'Min Flow':
                    self.branches_by_type[cls][name].rate_min = float(row['value'])

                    if file_obj is not None:
                        self.branches_by_type[cls][name].rate_min_prof = file_obj
                        used_profiles.add(file_obj)

            elif cls == 'Generator':

                if prop == 'Max Capacity':
                    self.generators[name].p_max = float(row['value'])

                elif prop == 'Min Stable Level':
                    self.generators[name].p_min = float(row['value'])

                elif prop == 'Rating Factor':
                    if file_obj is not None:
                        self.generators[name].rating_factor_prof = file_obj
                        used_profiles.add(file_obj)

                elif prop == 'Aux Fixed':
                    if file_obj is not None:
                        self.generators[name].rating_factor_prof = file_obj
                        used_profiles.add(file_obj)

                elif prop == 'Must-Run Units':
                    if file_obj is not None:
                        self.generators[name].rating_factor_prof = file_obj
                        used_profiles.add(file_obj)

            if self.prog_func is not None:
                self.prog_func(i + 1 / properties.shape[0] * 100)

        # load the profiles that are used
        if self.load_profiles:
            if self.text_func is not None:
                self.text_func('Loading input profiles')

            for i, file_obj in enumerate(used_profiles):
                self.load_profile_if_necessary(key=file_obj,
                                               path=file_dict[file_obj],
                                               zip_file_pointer=zip_file_pointer)
                # show progress
                if self.prog_func is not None:
                    self.prog_func(i + 1 / len(used_profiles) * 100)
        else:
            if self.text_func is not None:
                self.text_func('Skipping input profiles')

    def get_buses_dictionary(self):
        """
        Get dictionary relating the bus name to the latitude, longitude, voltage and name
        >>> bus_dict[name]
        >>> latitude, longitude, voltage, name
        :return: dictionary
        """
        return {b.name: (b.latitude, b.longitude, b.voltage, b.name) for b in self.nodes.values()}

    def get_all_branches_dictionary(self):
        """
        Returns a dictionary with all the Branches by the name
        :return: dictionary name -> object
        """
        z = self.lines.copy()  # start with x's keys and values
        z.update(self.transformers)
        return z

    def get_branch_ratings(self, n=None):
        """
        Get DataFrame with the dynamic branch ratings
        :param n: number of time steps to extrapolate the profile
        :return: DataFrame
        """

        """
        plexos index
        M1-D1-P1
        M4-D1-P1

        M1-3
        M4-5
        M6-8
        M9-10
        M11-12
        """

        # merge the max rating profiles for each of the Branches with profiles
        df = None
        for name, branch in self.get_all_branches_dictionary().items():

            if branch.rate_max_prof is not None:
                profile = self.data_profiles[branch.rate_max_prof].set_index('Pattern')
                new_df = profile[[name]]
                if df is None:
                    df = new_df
                else:
                    df = pd.concat([df, new_df], axis=1, sort=False)

        if n is None:
            return df

        # generate dates from the stupid plexos index
        for i, val in enumerate(df.index.values):
            m = val.replace('M', '').split('-')[0]
            df.index.values[i] = datetime(2000, int(m), 1)

        # generate new index according to the number of elements n
        new_index = [datetime(2000, 1, 1) + timedelta(hours=i) for i in range(n)]

        # forward fill...
        df2 = df.reindex(new_index).ffill()

        return df2


def get_st_generation_sent_out(plexos_results_folder):
    """
    Get the generation auxiliary use from a PLEXOS results folder
    :param plexos_results_folder: PLEXOS results folder
    :return: pandas DataFrame with the generation dispatch
    """
    fname = os.path.join(plexos_results_folder, 'Interval', 'ST Generator.Generation Sent Out.csv')

    df = pd.read_csv(fname, index_col='DATETIME')
    df = pd.read_csv(fname, index_col='DATETIME')

    return df


def get_st_node_load(plexos_results_folder, parse_dates=False):
    """
    Get the node load use from a PLEXOS results folder
    :param plexos_results_folder: PLEXOS results folder
    :param parse_dates: Parse the dates?
    :return: pandas DataFrame with the node load
    """
    fname = os.path.join(plexos_results_folder, 'Interval', 'ST Node.Load.csv')

    if parse_dates:
        df = pd.read_csv(fname, index_col='DATETIME', parse_dates=True, dayfirst=True)
    else:
        df = pd.read_csv(fname, index_col='DATETIME')

    return df


def plx_to_gridcal(mdl: PlxModel, plexos_results_folder, time_indices=None, text_func=None, prog_func=None):
    """
    Reads plexos model with results and creates a GridCal model
    :param mdl: Plexos model instance
    :param plexos_results_folder: plexos results folder
    :param time_indices: time indices to sample
    :param text_func:
    :param prog_func:
    :return: MultiCircuit instance
    """
    gen_df = get_st_generation_sent_out(plexos_results_folder=plexos_results_folder)
    load_df = get_st_node_load(plexos_results_folder=plexos_results_folder)
    rating_df = mdl.get_branch_ratings(n=load_df.shape[0])

    circuit = MultiCircuit()
    circuit.name = 'Grid from PLEXOS model'
    circuit.comments = 'Grid from PLEXOS model'
    # keep the time profile

    if 'DATETIME' in gen_df.columns.values:
        t = pd.to_datetime(gen_df['DATETIME']).values
    else:
        t = gen_df.index.values

    if time_indices is not None:
        circuit.time_profile = t[time_indices]
    else:
        circuit.time_profile = t

    n_total = len(mdl.nodes) + len(mdl.generators) + len(mdl.branches)
    nn = 0

    # add the buses and the loads (in plexos there is only one load per bus)
    bus_dict = dict()
    for name, elm in mdl.nodes.items():
        bus = Bus(name=name, Vnom=elm.voltage,
                  latitude=elm.longitude,
                  longitude=-elm.latitude,
                  area=elm.region.name,
                  zone=elm.zone.name)

        # add the bus to the buses dictionary
        bus_dict[name] = bus

        # add the bus to the circuit
        bus.ensure_profiles_exist(circuit.time_profile)
        circuit.add_bus(bus)

        # add the load and its profile if it is not zero
        if name in load_df.columns.values:
            if time_indices is not None:
                load_profile = load_df[name].values[time_indices]
            else:
                load_profile = load_df[name].values

            if (load_profile != 0).any():
                load = Load(name='Load@' + name,
                            P=elm.load,
                            Q=elm.load * 0.8, )
                load.P_prof = load_profile
                load.Q_prof = load_profile * 0.8
                load.ensure_profiles_exist(circuit.time_profile)
                circuit.add_load(bus, load)

        if text_func is not None:
            text_func("Creating GridCal model: Buses")

        if prog_func is not None:
            prog_func((nn / n_total) * 100)
        nn += 1

    # add the generators
    for name, elm in mdl.generators.items():
        if name in gen_df.columns.values:

            if time_indices is not None:
                gen_profile = gen_df[name].values[time_indices]
            else:
                gen_profile = gen_df[name].values

            gen = Generator(name=name,
                            Pmin=elm.p_min,
                            Pmax=elm.p_max)
            gen.P_prof = gen_profile
            bus = bus_dict[elm.node.name]
            gen.ensure_profiles_exist(circuit.time_profile)
            circuit.add_generator(bus, gen)

        if text_func is not None:
            text_func("Creating GridCal model: Buses")

        if prog_func is not None:
            prog_func((nn / n_total) * 100)
        nn += 1

    # add the lines
    for name, elm in mdl.lines.items():
        bus_f = bus_dict[elm.node_from.name]
        bus_t = bus_dict[elm.node_to.name]

        if name in rating_df.columns.values:
            profile = rating_df[name].values
            rating = profile.max()
        else:
            profile = None
            rating = elm.rate_max

        br = Line(bus_from=bus_f,
                  bus_to=bus_t,
                  name=name,
                  active=elm.units,
                  r=elm.R,
                  x=elm.X,
                  rate=rating)
        br.rate_prof = profile
        br.ensure_profiles_exist(circuit.time_profile)
        circuit.add_line(br)

        if text_func is not None:
            text_func("Creating GridCal model: Buses")

        if prog_func is not None:
            prog_func(nn / n_total * 100)
        nn += 1

    # add the transformers
    for name, elm in mdl.transformers.items():
        bus_f = bus_dict[elm.node_from.name]
        bus_t = bus_dict[elm.node_to.name]

        if name in rating_df.columns.values:
            profile = rating_df[name].values
            rating = profile.max()
        else:
            profile = None
            rating = elm.rate_max

        br = Transformer2W(bus_from=bus_f,
                           bus_to=bus_t,
                           name=name,
                           active=elm.units,
                           r=elm.R,
                           x=elm.X,
                           rate=rating)
        br.rate_prof = profile
        br.ensure_profiles_exist(circuit.time_profile)
        circuit.add_transformer2w(br)

        if text_func is not None:
            text_func("Creating GridCal model: Buses")

        if prog_func is not None:
            prog_func(nn / n_total * 100)
        nn += 1

    return circuit
