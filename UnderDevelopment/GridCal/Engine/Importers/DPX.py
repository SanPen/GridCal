import pandas as pd
import numpy as np


class DPXbase:

    def __init__(self, tpe='', data=list(), columns=list()):

        self.tpe = tpe
        self.cols = columns
        self.data = data

    def add_row(self, data_row):

        self.data.append(data_row)

    def get_data_frame(self):

        return pd.DataFrame(data=self.data, columns=self.cols)

    def copy(self):

        return DPXbase(self.data, self.cols)

# """
# PT Posto de transformação de distribuição
# PTC Posto de transformação de cliente
# TT Transformador de tensão
# """
#
# # PT and PTC
# # EQ: equipment code
# # SNOM: nominal power in p.u. (on base 100 MVA)
# # COST: cost in €
# PT  = DPXbase(data=[], columns=['EQ', 'SNOM', 'COST'])
# PTC = DPXbase(data=[], columns=['EQ', 'SNOM', 'COST'])
#
# # TT
# # EQ; equipment code
# # DESC: Description
# # VNOM: Nominal voltage of the primary in kV
# # TAP100: tap value at 1.00 pu (bool)
# # TAP105: tap value at 1.05 pu (bool)
# # TAP110: tap value at 1.10 pu (bool)
# # Vnompw: nominal voltage of the protection winding
# # RBPW: Potência de precisão do enrolamento de protecção (VA)
# # CLASSPW: Classe de precisão do enrolamento de protecção
# # ODW: Existência de enrolamento para ligação em triângulo aberto
# # VNOMDW; Tensão nominal do enrolamento de triângulo aberto (existe apenas se ODW = 1)
# # RBDW: Potência de precisão do enrolamento de triângulo aberto (existe apenas se ODW = 1) in VA
# # CLASSDW: Classe de precisão do enrolamento de triângulo aberto (existe apenas se ODW = 1)
# # COST; cost in €
# TT = DPXbase(data=[], columns=['EQ', 'DESC', 'VNOM',
#                                'TAP100', 'TAP105', 'TAP110',
#                                'Vnompw', 'RBPW', 'CLASSPW', 'ODW',
#                                'VNOMDW', 'RBDW', 'CLASSDW', 'COST'])
#
# # CAP: Capacitor
# # EQ; equipment code
# # DESC: Description
# # VNOM: Nominal voltage of the primary in kV
# # REAC: reactance in pu on SBASE = 100 MVA
# CAP = DPXbase(data=[], columns=['EQ', 'DESC', 'VNOM', 'REAC'])
#
# # IND: Inductor
# # EQ; equipment code
# # DESC: Description
# # VNOM: Nominal voltage of the primary in kV
# # REAC: reactance in pu on SBASE = 100 MVA
# IND = DPXbase(data=[], columns=['EQ', 'DESC', 'VNOM', 'REAC'])
#
#
# structures_dict['PT'] = PT
# structures_dict['PTC'] = PTC
# structures_dict['TT'] = TT
# structures_dict['CAP'] = CAP
# structures_dict['IND'] = IND


def load_dpx(file_name):
    """
    Read DPX file
    :param file_name: file name
    :return: MultiCircuit
    """

    logger = list()

    structures_dict = dict()

    current_block = None

    # parse the data into the structures
    with open(file_name) as f:
        for line in f:

            if ':' in line and ',' not in line:
                # block separators
                vals = line.split(':')
                current_block = vals[0]

            else:
                # Data

                values = line.split(',')

                if len(values) > 1:

                    # check the if the block has been created
                    if current_block not in structures_dict.keys():
                        structures_dict[current_block] = dict()

                    # parse the data
                    if current_block in ['CatalogNode', 'CatalogBranch', '']:
                        # blocks with header marker

                        marker = values[0]
                        data = [val.strip().replace("'", "") for val in values[1:]]
                        if marker not in structures_dict[current_block].keys():
                            structures_dict[current_block][marker] = DPXbase(tpe=marker)

                        # add the data
                        structures_dict[current_block][marker].add_row(data)

                    elif current_block in ['CatalogUGen', 'Parameters']:
                        # blocks without header marker
                        pass

                    elif current_block in ['Areas', 'Sites']:
                        # blocks without header marker
                        pass

                    elif current_block in ['Nodes', 'Branches']:
                        # blocks without header marker
                        pass

                    elif current_block in ['DrawObjs', 'Panels']:
                        # blocks without header marker
                        pass

                    else:
                        logger.append('Block ' + current_block + ' unknown')

                else:
                    logger.append('Unrecognized line: ' + line)

    return structures_dict, logger


if __name__ == '__main__':

    fname = 'example.dpx'

    parsed_data, logger = load_dpx(file_name=fname)

    pass