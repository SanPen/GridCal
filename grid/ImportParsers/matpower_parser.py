import pandas as pd
import numpy as np
import os

def find_between( s, first, last ):
    try:
        start = s.index( first ) + len( first )
        end = s.index( last, start )
        return s[start:end]
    except ValueError:
        return ""


def parse_matpower_file(filename, export=False):
    """
    Converts a matpower file to gridcal basic dictionary
    @param filename:
    @return:
    """
    f = open(filename)
    lines = f.readlines()
    f.close()

    keyword = ''


    version = 0
    baseMVA = 0

    strings = dict()
    structures = dict()

    structures_names = ['bus', 'gen', 'branch', 'gencost', 'bus_name']

    bus = list()
    gen = list()
    branch = list()
    gencost = list()
    bus_name = list()

    for line in lines:

        if line[0] == '%':
            pass
        else:
            dotsplit = line.split('.')

            if len(dotsplit) == 2:
                equalsplit = dotsplit[1].strip().split('=')

    #            print("keyword = |", keyword, "|")
                if len(equalsplit) == 2:
                    data = equalsplit[1].replace(";", "").replace("'", "")
                    keyword = equalsplit[0].strip()
                    if keyword == 'version':
                        version = float(data)

                    elif keyword == 'baseMVA':
                        baseMVA = float(data)

            if keyword in structures_names:

                # clean the comments from line: find % and remove from there on

                try:
                    idx = line.index('%')
                    line = line[0:idx-1]
                except:
                    pass

                if keyword in strings.keys():
                    strings[keyword] += line
                else:
                    strings[keyword] = line
            else:
                pass


    # clean strings
    for key in strings.keys():
        string = strings[key]
        if string.find('[') > -1:
            strings[key] = find_between(string, '[', ']').replace('\n', '')
        elif string.find('{') > -1:
            strings[key] = find_between(string, '{', '}').replace('\n', '')

        structures[key] = strings[key].split(';')

    # split the rows
    for key in structures.keys():
        table = structures[key]
        table2 = list()

        for line in table:
            if len(line.strip()) > 0:

                lne = line.split('\t')[1:]

                # for the bus names...
                if len(lne) == 1:
                    lne = lne[0].split()[:-1]
                    if len(lne) == 2:
                        lne = lne[0][1:] + '_' + lne[1]
                    else:
                        lne = lne[0][1:]
                # remove the empty elements from lne
                for i in range(len(lne)-1, -1, -1):
                    if lne[i] == '':
                        lne.pop(i)
                table2.append(lne)

        structures[key] = table2

    bus = np.array(structures['bus'], dtype=np.float)
    branch = np.array(structures['branch'], dtype=np.float)
    gen = np.array(structures['gen'], dtype=np.float)

    if 'gencost' in structures.keys():
        gencost = np.array(structures['gencost'], dtype=np.float)

    # refactor indices: Pass to zero indexing
    bus_dict = dict()
    i = 0
    BIDX = 0
    for bus_i in bus[:, BIDX]:
        bus_dict[bus_i] = i
        bus[i, BIDX] = i
        i += 1

    # replace buses in Branch and gen
    BF = 0
    BT = 1
    rows, cols = np.shape(branch)
    for r in range(rows):
        branch[r, BF] = bus_dict[branch[r, BF]]
        branch[r, BT] = bus_dict[branch[r, BT]]

    rows, cols = np.shape(gen)
    for r in range(rows):
        gen[r, BIDX] = bus_dict[gen[r, BIDX]]

    # Save
    if export:
        gen_headers = ["bus",
                       "Pg",
                       "Qg",
                       "Qmax",
                       "Qmin",
                       "Vg",
                       "mBase",
                       "status",
                       "Pmax",
                       "Pmin",
                       "Pc1",
                       "Pc2",
                       "Qc1min",
                       "Qc1max",
                       "Qc2min",
                       "Qc2max",
                       "ramp_agc",
                       "ramp_10",
                       "ramp_30",
                       "ramp_q",
                       "apf",
                       "MU_PMAX",
                       "MU_PMIN",
                       "MU_QMAX",
                       "MU_QMIN"]

        bus_headers = ["bus_i",
                       "type",
                       "Pd",
                       "Qd",
                       "Gs",
                       "Bs",
                       "area",
                       "Vm",
                       "Va",
                       "baseKV",
                       "zone",
                       "Vmax",
                       "Vmin",
                       "LaM_P",
                       "LaM_Q",
                       "Mu_Vmax",
                       "Mu_Vmin",
                       "Bus_X",
                       "Bus_Y",
                       "Collapsed"]

        branch_headers = ["fbus",  # 0
                          "tbus",
                          "r",
                          "x",
                          "b",
                          "rateA",
                          "rateB",
                          "rateC",
                          "ratio",
                          "angle",  # 9
                          "status",
                          "angmin",
                          "angmax",
                          "Pf",
                          "Qf",
                          "Pt",
                          "Qt",
                          "Mu_Sf",
                          "Mu_St",
                          "Mu_AngMin",  # 19
                          "Mu_AngMax",
                          "Current",
                          "Loading",
                          "Losses",
                          "Original_index"]

        name, file_extension = os.path.splitext(filename)
        writer = pd.ExcelWriter(name+'.xls', engine='xlsxwriter')

        # write conf
        dta = np.zeros((2, 2), dtype=np.object)
        dta[0, 0] = "Property"
        dta[0, 1] = "Value"

        dta[1, 0] = "baseMVA"
        dta[1, 1] = baseMVA
        df = pd.DataFrame(data=dta)
        df.to_excel(writer, index=False, header=False, sheet_name='Conf')

        # write buses
        rows, cols = np.shape(bus)
        df = pd.DataFrame(data=bus, columns=bus_headers[0:cols])
        df.to_excel(writer, index=False, header=True, sheet_name='Bus')

        # write gen
        rows, cols = np.shape(gen)
        df = pd.DataFrame(data=gen, columns=gen_headers[0:cols])
        df.to_excel(writer, index=False, header=True, sheet_name='Gen')

        # write branch
        rows, cols = np.shape(branch)
        df = pd.DataFrame(data=branch, columns=branch_headers[0:cols])
        df.to_excel(writer, index=False, header=True, sheet_name='Branch')

        writer.save()

    structures['bus'] = bus
    structures['gen'] = gen
    structures['branch'] = branch
    structures['baseMVA'] = baseMVA
    structures['version'] = version

    return structures