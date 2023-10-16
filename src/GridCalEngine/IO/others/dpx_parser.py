# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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
from typing import Tuple, Any, Union

import chardet

import numpy as np
import pandas as pd

from GridCalEngine.Core import MultiCircuit
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
import GridCalEngine.Core.Devices as dev

pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 1000)

__headers__ = dict()

########################################################################################################################
# CatalogBranch block
__headers__['CatalogBranch'] = dict()

__headers__['CatalogBranch']['CAP'] = ['CLASS', 'EQ', 'DESC', 'VNOM', 'REAC']

__headers__['CatalogBranch']['DISJ'] = ['CLASS', 'EQ', 'DESC', 'VNOM', 'RAT', 'FRATSH', 'FRATME', 'RATOFF', 'RATON',
                                        'RATONA', 'TOP', 'ISOLT']

__headers__['CatalogBranch']['FUS'] = ['CLASS', 'EQ', 'DESC', 'VNOM', 'RAT', 'FRATSH', 'FRATME', 'RATOFF', 'RATON',
                                       'FUS_IN', 'FUS_INF', 'FUS_IF', 'FUS_I5S', 'FUS_I01S', 'FUS_001S']

__headers__['CatalogBranch']['IND'] = ['CLASS', 'EQ', 'DESC', 'VNOM', 'REAC']

__headers__['CatalogBranch']['INTR'] = ['CLASS', 'EQ', 'DESC', 'VNOM', 'RAT', 'FRATSH', 'FRATME', 'RATOFF', 'RATON']

__headers__['CatalogBranch']['LINE'] = ['CLASS', 'EQ', 'DESC', 'VNOM', 'TYPE', 'SEC', 'SECIP', 'SECN', 'RATTYP',
                                        'RATSUM', 'RATWIN', 'FRATSH', 'FRATME', 'FRAT1S', 'R', 'RIP', 'RN',
                                        'K', 'X', 'B', 'R0', 'X0', 'B0', 'COST']

__headers__['CatalogBranch']['SECC'] = ['CLASS', 'EQ', 'DESC', 'VNOM', 'RAT', 'FRATSH', 'FRATME', 'RATOFF', 'RATON']

__headers__['CatalogBranch']['TI'] = ['CLASS', 'EQ', 'DESC', 'VNOM',
                                      'TOR']  # fuck the rest, having variable number of properties is bad design

__headers__['CatalogBranch']['XFORM1'] = ['CLASS', 'EQ', 'DESC', 'VNOM1', 'VNOM2', 'VNOM3',
                                          'SNOMTYP1', 'SNOMSUM1', 'SNOMWIN1', 'NATAP1', 'MAX1', 'MIN1', 'RD1', 'XD1',
                                          'RH1', 'XH1',
                                          'SNOMTYP2', 'SNOMSUM2', 'SNOMWIN2', 'NATAP2', 'MAX2', 'MIN2', 'RD2', 'XD2',
                                          'RH2', 'XH2', 'RDC', 'XDC', 'RHC', 'XHC',
                                          'SNOMTYP3', 'SNOMSUM3', 'SNOMWIN3', 'NATAP3', 'MAX3', 'MIN3', 'RD3', 'XD3',
                                          'RH3', 'XH3', 'G', 'B', 'G0', 'B0', 'POC', 'IOC', 'USC12', 'PSC12',
                                          'USC13', 'PSC13', 'USC23', 'PSC23', 'P1P2', 'P1P3', 'P2P3', 'FAB', 'MOD',
                                          'PYEAR', 'TYPE']

__headers__['CatalogBranch']['XFORM2'] = ['CLASS', 'EQ', 'DESC', 'VNOM1', 'VNOM2', 'VNOM3',
                                          'SNOMTYP1', 'SNOMSUM1', 'SNOMWIN1', 'NATAP1', 'MAX1', 'MIN1', 'RD1', 'XD1',
                                          'RH1', 'XH1',
                                          'SNOMTYP2', 'SNOMSUM2', 'SNOMWIN2', 'NATAP2', 'MAX2', 'MIN2', 'RD2', 'XD2',
                                          'RH2', 'XH2', 'RDC', 'XDC', 'RHC', 'XHC',
                                          'SNOMTYP3', 'SNOMSUM3', 'SNOMWIN3', 'NATAP3', 'MAX3', 'MIN3', 'RD3', 'XD3',
                                          'RH3', 'XH3', 'G', 'B', 'G0', 'B0', 'POC', 'IOC', 'USC12', 'PSC12',
                                          'USC13', 'PSC13', 'USC23', 'PSC23', 'P1P2', 'P1P3', 'P2P3', 'FAB', 'MOD',
                                          'PYEAR', 'TYPE']

__headers__['CatalogBranch']['XFORM3'] = ['CLASS', 'EQ', 'DESC', 'VNOM1', 'VNOM2', 'VNOM3',
                                          'SNOMTYP1', 'SNOMSUM1', 'SNOMWIN1', 'NATAP1', 'MAX1', 'MIN1', 'RD1', 'XD1',
                                          'RH1', 'XH1',
                                          'SNOMTYP2', 'SNOMSUM2', 'SNOMWIN2', 'NATAP2', 'MAX2', 'MIN2', 'RD2', 'XD2',
                                          'RH2', 'XH2', 'RDC', 'XDC', 'RHC', 'XHC',
                                          'SNOMTYP3', 'SNOMSUM3', 'SNOMWIN3', 'NATAP3', 'MAX3', 'MIN3', 'RD3', 'XD3',
                                          'RH3', 'XH3', 'G', 'B', 'G0', 'B0', 'POC', 'IOC', 'USC12', 'PSC12',
                                          'USC13', 'PSC13', 'USC23', 'PSC23', 'P1P2', 'P1P3', 'P2P3', 'FAB', 'MOD',
                                          'PYEAR', 'TYPE']

__headers__['CatalogBranch']['ZN'] = ['CLASS', 'EQ', 'DESC', 'VNOM', 'RZN', 'RXN', 'COST']

########################################################################################################################
# nodes block
__headers__['Nodes'] = dict()

# Airline support post
__headers__['Nodes']['APOIO'] = ['CLASS', 'ID', 'NAME', 'VBASE', 'GX', 'GY', 'SX', 'SY', 'EXIST']

# Cabinet (only for low voltage)
__headers__['Nodes']['ARM'] = ['CLASS', 'ID', 'NAME', 'VBASE', 'GX', 'GY', 'SX', 'SY', 'EXIST', 'YEAR']

# Connection
__headers__['Nodes']['CX'] = ['CLASS', 'ID', 'NAME', 'VBASE', 'GX', 'GY', 'SX', 'SY', 'EXIST']

# Neutral connection
__headers__['Nodes']['CXN'] = ['CLASS', 'ID', 'NAME', 'VBASE', 'GX', 'GY', 'SX', 'SY', 'EXIST']

# Network Equivalent
__headers__['Nodes']['EQUIV'] = ['CLASS', 'ID', 'NAME', 'VBASE', 'GX', 'GY', 'SX', 'SY', 'VMIN', 'VMAX', 'ZONE',
                                 'SEPNET', 'AUTOUP', 'P', 'Q', 'ELAST', 'SIMUL', 'HTYP', 'HARM5', 'HARM7', 'HARM11',
                                 'HARM13', 'NOGRW', 'RS', 'XS', 'R1', 'X1', 'R2', 'X2', 'RH', 'XH', 'COM']

# Generator
__headers__['Nodes']['GEN'] = ['CLASS', 'ID', 'NAME', 'VBASE', 'GX', 'GY', 'SX', 'SY', 'EXIST', 'MODEL', 'VMIN', 'VMAX',
                               'V', 'ENAB', 'P', 'Q', 'QMIN', 'QMAX', 'ELAST', 'HTYP', 'HARM5', 'HARM7', 'HARM11',
                               'HARM13', 'VNOM', 'RAT', 'TGEN', 'COST', 'YEAR']

# Charging (only for low voltage)
__headers__['Nodes']['LOAD'] = ['CLASS', 'ID', 'NAME', 'VBASE', 'GX', 'GY', 'SX', 'SY', 'EXIST', 'VMIN', 'VMAX',
                                'NCMPLAN']  # fill to fit...

# Transformation station
__headers__['Nodes']['PT'] = ['CLASS', 'ID', 'NAME', 'VBASE', 'GX', 'GY', 'SX', 'SY', 'EXIST', 'VMIN', 'VMAX', 'ZONE',
                              'ENAB', 'P', 'Q', 'ELAST', 'SIMUL', 'HTYP', 'HARM5', 'HARM7', 'HARM11', 'HARM13', 'NOGRW',
                              'EQEXIST', 'EQPOSS1', 'MCOST1', 'ICOST1', 'EQPOSS2', 'MCOST2', 'ICOST2', 'EQPOSS3',
                              'MCOST3',
                              'ICOST3', 'NCLI', 'EQTYPE', 'YEAR', 'COM', 'INFOCOM', 'ID_AUX']

# Customer transformation office
__headers__['Nodes']['PTC'] = ['CLASS', 'ID', 'NAME', 'VBASE', 'GX', 'GY', 'SX', 'SY', 'EXIST', 'VMIN', 'VMAX', 'ZONE',
                               'ENAB', 'P', 'Q', 'ELAST', 'SIMUL', 'HTYP', 'HARM5', 'HARM7', 'HARM11', 'HARM13',
                               'NOGRW',
                               'EQEXIST', 'EQPOSS1', 'MCOST1', 'ICOST1', 'EQPOSS2', 'MCOST2', 'ICOST2', 'EQPOSS3',
                               'MCOST3',
                               'ICOST3', 'NCLI', 'EQTYPE', 'YEAR', 'COM', 'INFOCOM', 'ID_AUX']

# Reference node
__headers__['Nodes']['REF'] = ['CLASS', 'ID', 'NAME', 'VBASE', 'GX', 'GY', 'SX', 'SY', 'VREF', 'RAT',
                               'COST', 'TGEN', 'YEAR']

# Voltage Transformer
__headers__['Nodes']['TT'] = ['CLASS', 'ID', 'NAME', 'VBASE', 'GX', 'GY', 'SX', 'SY', 'EXIST', 'VMIN', 'VMAX',
                              'DISABLE', 'HARM5', 'HARM7', 'HARM11', 'HARM13', 'EQEXIST', 'TAP', 'YEAR', 'ID_AUX']

########################################################################################################################
# Branches block
__headers__['Branches'] = dict()

# Condenser series or shunt
__headers__['Branches']['CAP'] = ['CLASS', 'ID', 'NAME', 'ID1', 'ID2', 'EXIST', 'STAT', 'PERM', 'EQ', 'YEAR']

# Breaker
__headers__['Branches']['DISJ'] = ['CLASS', 'ID', 'NAME', 'ID1', 'ID2', 'EXIST', 'STAT', 'PERM', 'FAILRT', 'TISOL',
                                   'TRECONF', 'TREPAIR', 'EQ', 'YEAR', 'CONTROL']

# Estimator
__headers__['Branches']['ESTIM'] = ['CLASS', 'ID', 'NAME', 'ID1', 'ID2', 'INDEP', 'I', 'SIMULT']

# Fuse
__headers__['Branches']['FUS'] = ['CLASS', 'ID', 'NAME', 'ID1', 'ID2', 'EXIST', 'STAT', 'PERM', 'FAILRT', 'TISOL',
                                  'TRECONF', 'TREPAIR', 'EQ', 'YEAR']

# Inductance series or shunt
__headers__['Branches']['IND'] = ['CLASS', 'ID', 'NAME', 'ID1', 'ID2', 'EXIST', 'STAT', 'PERM', 'EQ', 'YEAR']

# Switch
__headers__['Branches']['INTR'] = ['CLASS', 'ID', 'NAME', 'ID1', 'ID2', 'EXIST', 'STAT', 'PERM', 'FAILRT', 'TISOL',
                                   'TRECONF', 'TREPAIR', 'EQ', 'YEAR', 'DRIVE', 'CONTROL']

# Lines, cables and bars
# fill until it fits or truncate the data
__headers__['Branches']['LINE'] = ['CLASS', 'ID', 'NAME', 'ID1', 'ID2', 'EXIST', 'COLOR', 'GEOLEN', 'LEN', 'STAT',
                                   'PERM', 'FAILRT', 'TISOL', 'TRECONF', 'TREPAIR', 'RERAT', 'EQEXIST', 'NPOSS',
                                   'CHOOSEQ', 'INSRTCOST', 'EQPOSS1', 'MATCOST1', 'EQPOSS2', 'MATCOST2', 'EQPOSS3',
                                   'MATCOST3', 'NCOOG', 'GX1', 'GY1', 'GX2', 'GY2']

# Disconnector
__headers__['Branches']['SECC'] = ['CLASS', 'ID', 'NAME', 'ID1', 'ID2', 'EXIST', 'STAT', 'PERM', 'FAILRT', 'TISOL',
                                   'TRECONF', 'TREPAIR', 'EQ', 'YEAR', 'DRIVE', 'CONTROL']

# Intensity Transformer
__headers__['Branches']['TI'] = ['CLASS', 'ID', 'NAME', 'ID1', 'ID2', 'INDEP', 'I', 'SIMULT', 'EXIST', 'STAT', 'PERM',
                                 'FAILRT', 'TISOL', 'TRECONF', 'TREPAIR', 'EQ', 'TAP1', 'TAP2', 'YEAR']

# Self-transformer
__headers__['Branches']['XFORM1'] = ['CLASS', 'ID', 'NAME', 'ID1', 'ID2', 'ID3', 'ID1N', 'ID2N', 'ID3N', 'EXIST',
                                     'STAT', 'FAILRT', 'TISOL', 'TRECONF', 'TREPAIR', 'RERAT', 'CON1', 'RE1', 'XE1',
                                     'CON2', 'RE2', 'XE2', 'CON3', 'RE3', 'XE3', 'LOSS', 'TPERM', 'SETVSEL', 'SETV',
                                     'EQ', 'TAP1', 'TAP2', 'TAP3', 'YEAR', 'NUM']

# 2-winding transformer
__headers__['Branches']['XFORM2'] = ['CLASS', 'ID', 'NAME', 'ID1', 'ID2', 'ID3', 'ID1N', 'ID2N', 'ID3N', 'EXIST',
                                     'STAT', 'FAILRT', 'TISOL', 'TRECONF', 'TREPAIR', 'RERAT', 'CON1', 'RE1', 'XE1',
                                     'CON2', 'RE2', 'XE2', 'CON3', 'RE3', 'XE3', 'LOSS', 'TPERM', 'SETVSEL', 'SETV',
                                     'EQ', 'TAP1', 'TAP2', 'TAP3', 'YEAR', 'NUM']

# 3-winding transformer
__headers__['Branches']['XFORM3'] = ['CLASS', 'ID', 'NAME', 'ID1', 'ID2', 'ID3', 'ID1N', 'ID2N', 'ID3N', 'EXIST',
                                     'STAT', 'FAILRT', 'TISOL', 'TRECONF', 'TREPAIR', 'RERAT', 'CON1', 'RE1', 'XE1',
                                     'CON2', 'RE2', 'XE2', 'CON3', 'RE3', 'XE3', 'LOSS', 'TPERM', 'SETVSEL', 'SETV',
                                     'EQ', 'TAP1', 'TAP2', 'TAP3', 'YEAR', 'NUM']

# Neutral impedance
__headers__['Branches']['ZN'] = ['CLASS', 'ID', 'NAME', 'ID1', 'ID2', 'EXIST', 'STAT', 'PERM', 'FAILRT', 'TISOL',
                                 'TRECONF', 'TREPAIR', 'EQ', 'YEAR']


def reformat(val):
    """
    Pick string and give it format
    :param val: string value
    :return: int, float or string
    """
    try:
        x = int(val)
    except:
        try:
            x = float(val)
        except:
            x = val
    return x


def read_dpx_data(file_name):
    """
    Read the DPX file into a structured dictionary
    :param file_name:
    :return:
    """
    logger = Logger()

    structures_dict = dict()

    current_block = None

    # make a guess of the file encoding
    detection = chardet.detect(open(file_name, "rb").read())

    # parse the data into the structures
    with open(file_name, 'r', encoding=detection['encoding']) as f:
        for line in f:

            if ':' in line and ',' not in line:
                # block separators
                vals = line.split(':')
                current_block = vals[0]

            else:
                # Data

                values = line.replace(",", "").split('\t')

                if len(values) > 1:

                    if current_block in ['CatalogNode', 'CatalogBranch', 'Areas', 'Sites', 'Nodes',
                                         'Branches']:  # blocks with further categorization

                        # check the if the block has been created
                        if current_block not in structures_dict.keys():
                            structures_dict[current_block] = dict()

                        marker = values[0]
                        data = [reformat(val.strip().replace("'", "")) for val in values[1:]]
                        if marker not in structures_dict[current_block].keys():
                            # structures_dict[current_block][marker] = DPXbase(tpe=marker)
                            structures_dict[current_block][marker] = list()

                        # add the data
                        structures_dict[current_block][marker].append(data)

                    elif current_block in ['CatalogUGen', 'Parameters']:  # blocks without further categorization

                        # check the if the block has been created
                        if current_block not in structures_dict.keys():
                            structures_dict[current_block] = list()

                        # correct the values
                        data = [reformat(val.strip().replace("'", "")) for val in values]

                        # insert the data
                        structures_dict[current_block].append(data)

                    else:
                        # append an entry to the logger
                        logger.add_warning('Unknown block', current_block)

                else:
                    logger.add_warning('Unrecognized line', line)

    return structures_dict, logger


def repack(data_structures, logger=Logger(), verbose=False):
    """
    Pack the values as DataFrames with headers where available
    :param data_structures: Raw data structures
    :param logger: logger (inherited)
    :param verbose: print extra stuff
    :return:
    """
    for current_block in data_structures.keys():

        # parse the data
        if current_block in ['CatalogNode']:
            # blocks with header marker
            pass

        elif current_block in ['CatalogUGen', 'Parameters']:
            # blocks without header marker
            pass

        elif current_block in ['Areas', 'Sites']:
            # blocks without header marker
            pass

        elif current_block in ['Nodes', 'Branches', 'CatalogBranch']:  # blocks without header marker

            # repack the data with headers
            for tpe in data_structures[current_block].keys():
                hdr = __headers__[current_block][tpe][1:]
                data = data_structures[current_block][tpe]
                try:
                    data = np.array(data)[:, :len(hdr)]  # truncate to the length of hdr
                except:
                    # each line does have different lengths (shitty format...)

                    data2 = list()

                    # determine the maximum length
                    lmax = 0
                    for i in range(len(data)):
                        l = len(data[i])
                        if l > lmax:
                            lmax = l

                    # format all to have Lmax length
                    for i in range(len(data)):
                        line = data[i]
                        l = len(line)
                        d = lmax - l
                        fill = [0] * d
                        data2.append(line + fill)

                    data = np.array(data2)[:, :len(hdr)]

                # extend the data
                if data.shape[1] < len(hdr):
                    d = len(hdr) - data.shape[1]
                    data = np.c_[data, np.zeros((data.shape[0], d))]

                df = pd.DataFrame(data=data, columns=hdr)
                data_structures[current_block][tpe] = df

                if verbose:
                    print('\n', current_block, ' -> ', tpe)
                    print(df)

        elif current_block in ['DrawObjs', 'Panels']:
            # blocks without header marker
            pass

        else:
            logger.add_warning('Unknown block', current_block)

    return data_structures, logger


def load_dpx(file_name, contraction_factor=1000) -> tuple[Union[MultiCircuit, Any], Union[Logger, Any]]:
    """
    Read DPX file
    :param file_name: file name
    :param contraction_factor: contraction factor
    :return: MultiCircuit
    """

    circuit = MultiCircuit()

    Sbase = 100
    circuit.Sbase = Sbase

    SQRT3 = np.sqrt(3)

    # read the raw data into a structured dictionary
    print('Reading file...')
    structures_dict, logger = read_dpx_data(file_name=file_name)

    # format the read data
    print('Packing data...')
    data_structures, logger = repack(data_structures=structures_dict, logger=logger)

    buses_id_dict = dict()
    #  create nodes
    for tpe in data_structures['Nodes']:
        # Airline support post
        # __headers__['Nodes']['APOIO'] = ['CLASS', 'ID', 'NAME', 'VBASE', 'GX', 'GY', 'SX', 'SY', 'EXIST']
        # __headers__['Nodes']['ARM'] = ['CLASS', 'ID', 'NAME', 'VBASE', 'GX', 'GY', 'SX', 'SY', 'EXIST', 'YEAR']
        # __headers__['Nodes']['CX'] = ['CLASS', 'ID', 'NAME', 'VBASE', 'GX', 'GY', 'SX', 'SY', 'EXIST']
        # __headers__['Nodes']['CXN'] = ['CLASS', 'ID', 'NAME', 'VBASE', 'GX', 'GY', 'SX', 'SY', 'EXIST']
        # __headers__['Nodes']['LOAD'] = ['CLASS', 'ID', 'NAME', 'VBASE', 'GX', 'GY', 'SX', 'SY', 'EXIST', 'VMIN', 'VMAX', 'NCMPLAN']  # fill to fit...
        if tpe in ['APOIO', 'ARM', 'CX', 'CXN', 'LOAD']:
            df = data_structures['Nodes'][tpe]

            for i in range(df.shape[0]):
                name = 'B' + str(len(circuit.buses) + 1) + '_' + str(df['NAME'].values[i])
                Vnom = float(df['VBASE'].values[i])
                x = float(df['GX'].values[i]) / contraction_factor
                y = float(df['GY'].values[i]) / contraction_factor
                id_ = df['ID'].values[i]
                bus = dev.Bus(name=name, vnom=Vnom, xpos=x, ypos=y, height=40, width=60)

                circuit.add_bus(bus)
                buses_id_dict[id_] = bus

        # Network Equivalent
        # __headers__['Nodes']['EQUIV'] = ['CLASS', 'ID', 'NAME', 'VBASE', 'GX', 'GY', 'SX', 'SY', 'VMIN', 'VMAX', 'ZONE',
        #                                  'SEPNET', 'AUTOUP', 'P', 'Q', 'ELAST', 'SIMUL', 'HTYP', 'HARM5', 'HARM7',
        #                                  'HARM11',
        #                                  'HARM13', 'NOGRW', 'RS', 'XS', 'R1', 'X1', 'R2', 'X2', 'RH', 'XH', 'COM']
        elif tpe == 'EQUIV':
            df = data_structures['Nodes'][tpe]

            for i in range(df.shape[0]):
                name = 'B' + str(len(circuit.buses) + 1) + '_' + str(df['NAME'].values[i])
                Vnom = float(df['VBASE'].values[i])
                x = float(df['GX'].values[i]) / contraction_factor
                y = float(df['GY'].values[i]) / contraction_factor
                id_ = df['ID'].values[i]
                bus = dev.Bus(name=name, vnom=Vnom, xpos=x, ypos=y, height=40, width=60, is_slack=True)
                circuit.add_bus(bus)
                buses_id_dict[id_] = bus

                name = 'LD' + str(len(circuit.buses)) + '_' + str(df['NAME'].values[i])
                p = float(df['P'].values[i]) * Sbase
                q = float(df['Q'].values[i]) * Sbase
                load = dev.Load(name=name, P=p, Q=q)

                circuit.add_load(bus, load)

        # Generator
        # __headers__['Nodes']['GEN'] = ['CLASS', 'ID', 'NAME', 'VBASE', 'GX', 'GY', 'SX', 'SY', 'EXIST', 'MODEL', 'VMIN',
        #                                'VMAX',
        #                                'V', 'ENAB', 'P', 'Q', 'QMIN', 'QMAX', 'ELAST', 'HTYP', 'HARM5', 'HARM7',
        #                                'HARM11',
        #                                'HARM13', 'VNOM', 'RAT', 'TGEN', 'COST', 'YEAR']
        elif tpe == 'GEN':
            df = data_structures['Nodes'][tpe]

            for i in range(df.shape[0]):
                name = 'B' + str(len(circuit.buses) + 1) + '_' + str(df['NAME'].values[i])
                Vnom = float(df['VBASE'].values[i])
                x = float(df['GX'].values[i]) / contraction_factor
                y = float(df['GY'].values[i]) / contraction_factor
                id_ = df['ID'].values[i]
                bus = dev.Bus(name=name, vnom=Vnom, xpos=x, ypos=y, height=40, width=60)
                circuit.add_bus(bus)
                buses_id_dict[id_] = bus

                mode = int(df['MODEL'].values[i])

                if mode == 1:
                    name = 'GEN' + str(len(circuit.buses)) + '_' + str(df['NAME'].values[i])
                    p = float(df['P'].values[i]) * Sbase
                    q = float(df['Q'].values[i]) * Sbase
                    v = float(df['V'].values[i])  # p.u.
                    gen = dev.Generator(name=name, P=p, vset=v)

                    circuit.add_generator(bus, gen)
                else:
                    name = 'GENSTAT' + str(len(circuit.buses)) + '_' + str(df['NAME'].values[i])
                    p = float(df['P'].values[i]) * Sbase
                    q = float(df['Q'].values[i]) * Sbase
                    gen = dev.StaticGenerator(name=name, P=p, Q=q)
                    circuit.add_static_generator(bus, gen)

        # Transformation station
        # __headers__['Nodes']['PT'] = ['CLASS', 'ID', 'NAME', 'VBASE', 'GX', 'GY', 'SX', 'SY', 'EXIST', 'VMIN', 'VMAX',
        #                               'ZONE',
        #                               'ENAB', 'P', 'Q', 'ELAST', 'SIMUL', 'HTYP', 'HARM5', 'HARM7', 'HARM11', 'HARM13',
        #                               'NOGRW',
        #                               'EQEXIST', 'EQPOSS1', 'MCOST1', 'ICOST1', 'EQPOSS2', 'MCOST2', 'ICOST2',
        #                               'EQPOSS3', 'MCOST3',
        #                               'ICOST3', 'NCLI', 'EQTYPE', 'YEAR', 'COM', 'INFOCOM', 'ID_AUX']
        elif tpe in ['PT', 'PTC']:

            df = data_structures['Nodes'][tpe]

            for i in range(df.shape[0]):
                name = 'B' + str(len(circuit.buses) + 1) + '_' + str(df['NAME'].values[i])
                Vnom = float(df['VBASE'].values[i])
                x = float(df['GX'].values[i]) / contraction_factor
                y = float(df['GY'].values[i]) / contraction_factor
                id_ = df['ID'].values[i]
                bus = dev.Bus(name=name, vnom=Vnom, xpos=x, ypos=y, height=40, width=60)

                name = 'LD' + str(len(circuit.buses) + 1) + '_' + str(df['NAME'].values[i])
                p = float(df['P'].values[i]) * Sbase
                q = float(df['Q'].values[i]) * Sbase
                load = dev.Load(name=name, P=p, Q=q)

                circuit.add_bus(bus)
                circuit.add_load(bus, load)
                buses_id_dict[id_] = bus

        # Reference node
        # __headers__['Nodes']['REF'] = ['CLASS', 'ID', 'NAME', 'VBASE', 'GX', 'GY', 'SX', 'SY', 'VREF', 'RAT',
        #                                'COST', 'TGEN', 'YEAR']
        elif tpe == 'REF':
            df = data_structures['Nodes'][tpe]

            for i in range(df.shape[0]):
                name = 'B' + str(len(circuit.buses) + 1) + '_' + str(df['NAME'].values[i])
                Vnom = float(df['VBASE'].values[i])
                x = float(df['GX'].values[i]) / contraction_factor
                y = float(df['GY'].values[i]) / contraction_factor
                id_ = df['ID'].values[i]
                bus = dev.Bus(name=name, vnom=Vnom, xpos=x, ypos=y, height=40, width=60, is_slack=True)

                circuit.add_bus(bus)
                buses_id_dict[id_] = bus

        # Voltage Transformer
        # __headers__['Nodes']['TT'] = ['CLASS', 'ID', 'NAME', 'VBASE', 'GX', 'GY', 'SX', 'SY', 'EXIST', 'VMIN', 'VMAX',
        #                               'DISABLE', 'HARM5', 'HARM7', 'HARM11', 'HARM13', 'EQEXIST', 'TAP', 'YEAR',
        #                               'ID_AUX']
        elif tpe == 'TT':
            df = data_structures['Nodes'][tpe]

            for i in range(df.shape[0]):
                name = 'B' + str(len(circuit.buses) + 1) + '_' + str(df['NAME'].values[i])
                Vnom = float(df['VBASE'].values[i])
                x = float(df['GX'].values[i]) / contraction_factor
                y = float(df['GY'].values[i]) / contraction_factor
                id_ = df['ID'].values[i]
                bus = dev.Bus(name=name, vnom=Vnom, xpos=x, ypos=y, height=40, width=60)

                circuit.add_bus(bus)
                buses_id_dict[id_] = bus

        else:
            logger.add_error('Not recognised under Nodes', tpe)

    # create Branches
    for tpe in data_structures['Branches']:

        # Condenser series or shunt
        # __headers__['Branches']['CAP'] = ['CLASS', 'ID', 'NAME', 'ID1', 'ID2', 'EXIST', 'STAT', 'PERM', 'EQ', 'YEAR']
        if tpe in ['CAP', 'IND']:

            df = data_structures['Branches'][tpe]

            for i in range(df.shape[0]):
                name = df['NAME'].values[i]
                id1 = df['ID1'].values[i]
                id2 = df['ID2'].values[i]
                b1 = buses_id_dict[id1]
                b2 = buses_id_dict[id2]

                # get equipment reference in the catalogue
                eq_id = df['EQ'].values[i]
                df_cat = data_structures['CatalogBranch'][tpe]
                cat_elm = df_cat[df_cat['EQ'] == eq_id]

                try:
                    x = float(cat_elm['REAC'].values[0]) * Sbase
                except:
                    x = 1e-20

                br = dev.Branch(bus_from=b1, bus_to=b2, name=name, x=x, branch_type=dev.BranchType.Branch)
                circuit.add_branch(br)

        # Estimator
        # __headers__['Branches']['ESTIM'] = ['CLASS', 'ID', 'NAME', 'ID1', 'ID2', 'INDEP', 'I', 'SIMULT']
        if tpe in ['ESTIM']:
            df = data_structures['Branches'][tpe]

            for i in range(df.shape[0]):
                name = df['NAME'].values[i]
                id1 = df['ID1'].values[i]
                id2 = df['ID2'].values[i]
                b1 = buses_id_dict[id1]
                b2 = buses_id_dict[id2]
                br = dev.Branch(bus_from=b1, bus_to=b2, name=name, branch_type=dev.BranchType.Branch)
                circuit.add_branch(br)

        # Breaker
        # __headers__['Branches']['DISJ'] = ['CLASS', 'ID', 'NAME', 'ID1', 'ID2', 'EXIST', 'STAT', 'PERM', 'FAILRT',
        #                                    'TISOL', 'TRECONF', 'TREPAIR', 'EQ', 'YEAR', 'CONTROL']

        # Fuse
        # __headers__['Branches']['FUS'] = ['CLASS', 'ID', 'NAME', 'ID1', 'ID2', 'EXIST', 'STAT', 'PERM', 'FAILRT',
        #                                   'TISOL','TRECONF', 'TREPAIR', 'EQ', 'YEAR']

        # Switch
        # __headers__['Branches']['INTR'] = ['CLASS', 'ID', 'NAME', 'ID1', 'ID2', 'EXIST', 'STAT', 'PERM', 'FAILRT',
        #                                    'TISOL', 'TRECONF', 'TREPAIR', 'EQ', 'YEAR', 'DRIVE', 'CONTROL']

        # Disconnector
        # __headers__['Branches']['SECC'] = ['CLASS', 'ID', 'NAME', 'ID1', 'ID2', 'EXIST', 'STAT', 'PERM', 'FAILRT',
        #                                    'TISOL', 'TRECONF', 'TREPAIR', 'EQ', 'YEAR', 'DRIVE', 'CONTROL']
        if tpe in ['DISJ', 'FUS', 'INTR', 'SECC']:
            df = data_structures['Branches'][tpe]

            for i in range(df.shape[0]):
                name = df['NAME'].values[i]
                id1 = df['ID1'].values[i]
                id2 = df['ID2'].values[i]
                state = bool(int(df['STAT'].values[i]))
                b1 = buses_id_dict[id1]
                b2 = buses_id_dict[id2]
                br = dev.Branch(bus_from=b1, bus_to=b2, name=name, active=state, branch_type=dev.BranchType.Switch)
                circuit.add_branch(br)

        # Lines, cables and bars
        # fill until it fits or truncate the data
        # __headers__['Branches']['LINE'] = ['CLASS', 'ID', 'NAME', 'ID1', 'ID2', 'EXIST', 'COLOR', 'GEOLEN', 'LEN',
        #                                    'STAT',
        #                                    'PERM', 'FAILRT', 'TISOL', 'TRECONF', 'TREPAIR', 'RERAT', 'EQEXIST', 'NPOSS',
        #                                    'CHOOSEQ', 'INSRTCOST', 'EQPOSS1', 'MATCOST1', 'EQPOSS2', 'MATCOST2',
        #                                    'EQPOSS3',
        #                                    'MATCOST3', 'NCOOG', 'GX1', 'GY1', 'GX2', 'GY2']
        if tpe in ['LINE']:
            df = data_structures['Branches'][tpe]

            for i in range(df.shape[0]):
                name = df['NAME'].values[i]
                id1 = df['ID1'].values[i]
                id2 = df['ID2'].values[i]
                b1 = buses_id_dict[id1]
                b2 = buses_id_dict[id2]

                length = float(df['LEN'].values[i])

                # get equipment reference in the catalogue
                eq_id = df['EQEXIST'].values[i]
                df_cat = data_structures['CatalogBranch'][tpe]
                cat_elm = df_cat[df_cat['EQ'] == eq_id]

                try:
                    r = float(cat_elm['R'].values[0]) * length / 1000
                except:
                    r = 1e-20
                try:
                    x = float(cat_elm['X'].values[0]) * length / 1000
                except:
                    x = 1e-20
                try:
                    b = float(cat_elm['B'].values[0]) * length / 1000
                except:
                    b = 1e-20

                Imax = float(cat_elm['RATTYP'].values[0]) / 1000.0  # pass from A to kA
                Vnom = float(cat_elm['VNOM'].values[0])  # kV
                Smax = Imax * Vnom * SQRT3  # MVA
                # correct for zero values which are problematic
                r = r if r > 0.0 else 1e-20
                x = x if x > 0.0 else 1e-20
                b = b if b > 0.0 else 1e-20

                br = dev.Branch(bus_from=b1, bus_to=b2, name=name, r=r, x=x, b=b, rate=Smax, length=length,
                                branch_type=dev.BranchType.Line)
                circuit.add_branch(br)

        # Intensity Transformer
        # __headers__['Branches']['TI'] = ['CLASS', 'ID', 'NAME', 'ID1', 'ID2', 'INDEP', 'I', 'SIMULT', 'EXIST', 'STAT',
        #                                  'PERM', 'FAILRT', 'TISOL', 'TRECONF', 'TREPAIR', 'EQ', 'TAP1', 'TAP2', 'YEAR']
        if tpe in ['TI']:
            df = data_structures['Branches'][tpe]

            for i in range(df.shape[0]):
                name = df['NAME'].values[i]
                id1 = df['ID1'].values[i]
                id2 = df['ID2'].values[i]
                b1 = buses_id_dict[id1]
                b2 = buses_id_dict[id2]

                # get equipment reference in the catalogue
                eq_id = df['EQ'].values[i]
                df_cat = data_structures['CatalogBranch'][tpe]
                cat_elm = df_cat[df_cat['EQ'] == eq_id]

                br = dev.Branch(bus_from=b1, bus_to=b2, name=name, branch_type=dev.BranchType.Transformer)
                circuit.add_branch(br)

        # Self-transformer
        # __headers__['Branches']['XFORM1'] = ['CLASS', 'ID', 'NAME', 'ID1', 'ID2', 'ID3', 'ID1N', 'ID2N', 'ID3N',
        #                                      'EXIST',
        #                                      'STAT', 'FAILRT', 'TISOL', 'TRECONF', 'TREPAIR', 'RERAT', 'CON1', 'RE1',
        #                                      'XE1',
        #                                      'CON2', 'RE2', 'XE2', 'CON3', 'RE3', 'XE3', 'LOSS', 'TPERM', 'SETVSEL',
        #                                      'SETV',
        #                                      'EQ', 'TAP1', 'TAP2', 'TAP3', 'YEAR', 'NUM']
        if tpe in ['XFORM1', 'XFORM2']:
            df = data_structures['Branches'][tpe]

            for i in range(df.shape[0]):
                name = df['NAME'].values[i]
                id1 = df['ID1'].values[i]
                id2 = df['ID2'].values[i]
                b1 = buses_id_dict[id1]
                b2 = buses_id_dict[id2]

                # get equipment reference in the catalogue
                # eq_id = df['EQ'].values[i]
                eq_id = df['XE3'].values[i]  # to correct the bad data formatting these file has...
                df_cat = data_structures['CatalogBranch'][tpe]
                cat_elm = df_cat[df_cat['EQ'] == eq_id]

                if cat_elm.shape[0] > 0:
                    r1 = float(cat_elm['RD1'].values[0])
                    r2 = float(cat_elm['RD2'].values[0])
                    x1 = float(cat_elm['XD1'].values[0])
                    x2 = float(cat_elm['XD2'].values[0])

                    s1 = float(cat_elm['SNOMTYP1'].values[0]) / 1000.0  # from kVA to MVA
                    s2 = float(cat_elm['SNOMTYP2'].values[0]) / 1000.0  # from kVA to MVA

                    r = r1 + r2
                    x = x1 + x2
                    s = s1 + s2

                    r = r if r > 0.0 else 1e-20
                    x = x if x > 0.0 else 1e-20
                    s = s if s > 0.0 else 1e-20
                else:
                    r = 1e-20
                    x = 1e-20
                    s = 1e-20
                    logger.add_error('Not found.', tpe + ':' + eq_id)

                br = dev.Branch(bus_from=b1, bus_to=b2, name=name, r=r, x=x, rate=s,
                                branch_type=dev.BranchType.Transformer)
                circuit.add_branch(br)

        # 3-winding transformer
        # __headers__['Branches']['XFORM3'] = ['CLASS', 'ID', 'NAME', 'ID1', 'ID2', 'ID3', 'ID1N', 'ID2N', 'ID3N',
        #                                      'EXIST',
        #                                      'STAT', 'FAILRT', 'TISOL', 'TRECONF', 'TREPAIR', 'RERAT', 'CON1', 'RE1',
        #                                      'XE1',
        #                                      'CON2', 'RE2', 'XE2', 'CON3', 'RE3', 'XE3', 'LOSS', 'TPERM', 'SETVSEL',
        #                                      'SETV',
        #                                      'EQ', 'TAP1', 'TAP2', 'TAP3', 'YEAR', 'NUM']
        if tpe in ['XFORM3']:
            df = data_structures['Branches'][tpe]

            for i in range(df.shape[0]):
                name = df['NAME'].values[i]
                id1 = df['ID1'].values[i]
                id2 = df['ID2'].values[i]
                id3 = df['ID3'].values[i]
                b1 = buses_id_dict[id1]
                b2 = buses_id_dict[id2]
                b3 = buses_id_dict[id3]

                # get equipment reference in the catalogue
                eq_id = df['EQ'].values[i]
                df_cat = data_structures['CatalogBranch'][tpe]
                cat_elm = df_cat[df_cat['EQ'] == eq_id]

                r1 = float(cat_elm['RD1'].values[0])
                r2 = float(cat_elm['RD2'].values[0])
                r3 = float(cat_elm['RD3'].values[0])
                x1 = float(cat_elm['XD1'].values[0])
                x2 = float(cat_elm['XD2'].values[0])
                x3 = float(cat_elm['XD3'].values[0])

                s1 = float(cat_elm['SNOMTYP1'].values[0]) / 1000.0  # from kVA to MVA
                s2 = float(cat_elm['SNOMTYP2'].values[0]) / 1000.0  # from kVA to MVA
                s3 = float(cat_elm['SNOMTYP3'].values[0]) / 1000.0  # from kVA to MVA

                r12 = r1 + r2
                x12 = x1 + x2
                s12 = s1 + s2

                r13 = r1 + r3
                x13 = x1 + x3
                s13 = s1 + s3

                r23 = r2 + r3
                x23 = x2 + x3
                s23 = s2 + s3

                r12 = r12 if r12 > 0.0 else 1e-20
                x12 = x12 if x12 > 0.0 else 1e-20
                s12 = s12 if s12 > 0.0 else 1e-20

                r13 = r13 if r13 > 0.0 else 1e-20
                x13 = x13 if x13 > 0.0 else 1e-20
                s13 = s13 if s13 > 0.0 else 1e-20

                r23 = r23 if r23 > 0.0 else 1e-20
                x23 = x23 if x23 > 0.0 else 1e-20
                s23 = s23 if s23 > 0.0 else 1e-20

                br = dev.Branch(bus_from=b1, bus_to=b2, name=name, r=r12, x=x12, rate=s12,
                                branch_type=dev.BranchType.Transformer)
                circuit.add_branch(br)

                br = dev.Branch(bus_from=b1, bus_to=b3, name=name, r=r13, x=x13, rate=s13,
                                branch_type=dev.BranchType.Transformer)
                circuit.add_branch(br)

                br = dev.Branch(bus_from=b2, bus_to=b3, name=name, r=r23, x=x23, rate=s23,
                                branch_type=dev.BranchType.Transformer)
                circuit.add_branch(br)

        # Neutral impedance
        # __headers__['Branches']['ZN'] = ['CLASS', 'ID', 'NAME', 'ID1', 'ID2', 'EXIST', 'STAT', 'PERM', 'FAILRT',
        #                                  'TISOL','TRECONF', 'TREPAIR', 'EQ', 'YEAR']
        if tpe in ['ZN']:
            df = data_structures['Branches'][tpe]

            for i in range(df.shape[0]):
                name = df['NAME'].values[i]
                id1 = df['ID1'].values[i]
                id2 = df['ID2'].values[i]
                b1 = buses_id_dict[id1]
                b2 = buses_id_dict[id2]
                br = dev.Branch(bus_from=b1, bus_to=b2, name=name, branch_type=dev.BranchType.Branch)
                circuit.add_branch(br)

    # return the circuit and the logs
    return circuit, logger
