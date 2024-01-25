import os
from typing import Dict
import pandas as pd
# from pytablewriter import RstSimpleTableWriter
from GridCalEngine.IO.cim.cgmes_2_4_15.cgmes_circuit import CgmesCircuit
from GridCalEngine.IO.raw.devices.psse_circuit import PsseCircuit
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.IO.gridcal.pack_unpack import get_objects_dictionary


def get_cgmes_data_frames():
    info = dict()
    circuit = CgmesCircuit()

    for class_name, class_type in circuit.class_dict.items():

        cls = class_type("", class_name)

        data = list()
        for property_name, cim_property in cls.declared_properties.items():
            data.append(cim_property.get_dict())

        info[class_name] = pd.DataFrame(data=data)

    return info


def get_psse_data_frames():
    info = dict()

    circuit = PsseCircuit()

    for prop in circuit.get_properties():

        if prop.class_type not in [str, bool, int, float]:

            cls = prop.class_type
            class_name = str(cls).split('.')[-1].split(' ')[0].replace("'>", "")
            data = list()
            obj = cls()
            for cls_prop in obj.get_properties():
                data.append(cls_prop.get_dict())

            info[class_name] = pd.DataFrame(data=data)

    return info


def get_gridcal_data_frames():

    info = dict()

    obj_dict = get_objects_dictionary()

    circuit = MultiCircuit()

    for obj_type_name, obj in obj_dict.items():

        class_name = obj.device_type.value

        data = list()
        for prop_name, prop in obj.editable_headers.items():

            data.append(prop.get_dict())

        info[class_name] = pd.DataFrame(data=data)

    return info


def write_dataframes_to_excel(data_frames: Dict[str, pd.DataFrame], filename):

    df_all = pd.DataFrame()
    for key, df in data_frames.items():
        # df['class'] = key
        df.insert(0, 'class', key)
        df_all = pd.concat([df_all, df], axis=0)

    with pd.ExcelWriter(filename) as w:
        df_all.to_excel(w, sheet_name='ALL_CLASSES')


def write_dataframes_to_rst(data_frames: Dict[str, pd.DataFrame], filename, tilte):


    m = 10

    names = list(data_frames.keys())
    names.sort()

    with open(filename, 'w') as w:

        w.write("Models\n")
        w.write("=============\n\n")

        w.write(tilte + "\n")
        w.write("-" * (len(tilte) * m) + "\n\n")

        for key in names:
            df = data_frames[key]

            if df.shape[0] > 0:
                writer = RstSimpleTableWriter(dataframe=df)
                s = writer.dumps()
            else:
                s = "No table info."

            w.write(key + "\n")
            w.write("^" * (len(tilte) * m) + "\n\n")
            w.write(s)
            w.write("\n\n")


def write_dataframes_to_rst2(w, data_frames: Dict[str, pd.DataFrame], tilte):

    m = 10

    names = list(data_frames.keys())
    names.sort()

    w.write(tilte + "\n")
    w.write("-" * (len(tilte) * m) + "\n\n")

    for key in names:
        df = data_frames[key]

        if df.shape[0] > 0:
            writer = RstSimpleTableWriter(dataframe=df)
            s = writer.dumps()
        else:
            s = "No table info."

        w.write(key + "\n")
        w.write("^" * (len(tilte) * m) + "\n\n")
        w.write(s)
        w.write("\n\n")


def write_models_to_rst(filename):
    with open(filename, 'w') as w:

        w.write("Data Models\n")
        w.write("==========================\n\n")

        cgmes_info = get_cgmes_data_frames()
        psse_info = get_psse_data_frames()
        gridcal_info = get_gridcal_data_frames()

        write_dataframes_to_rst2(w, cgmes_info,  "CGMES")
        write_dataframes_to_rst2(w, psse_info, "PSSE")
        write_dataframes_to_rst2(w, gridcal_info, "GridCal")


if __name__ == '__main__':
    cgmes_info = get_cgmes_data_frames()
    psse_info = get_psse_data_frames()
    roseta_info = get_gridcal_data_frames()

    write_dataframes_to_excel(cgmes_info,
                              'cgmes_classes_all_in_one_sheet.xlsx')
    write_dataframes_to_excel(psse_info,
                              'psse_classes_all_in_one_sheet.xlsx')
    write_dataframes_to_excel(roseta_info,
                              'roseta_classes_all_in_one_sheet.xlsx')

    # write_dataframes_to_rst(cgmes_info, 'cgmes_clases.rst', "CGMES")
    # write_dataframes_to_rst(psse_info, 'psse_clases.rst', "PSSE")
    # write_dataframes_to_rst(roseta_info, 'roseta_clases.rst', "Roseta")

    # write_models_to_rst(os.path.join('rst_source', 'other_data_models.rst'))

    print("done")

