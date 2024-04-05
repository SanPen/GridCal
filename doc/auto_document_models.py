import os
from typing import Dict
import pandas as pd
from pytablewriter import RstSimpleTableWriter
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from GridCalEngine.IO.raw.devices.psse_circuit import PsseCircuit
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.IO.gridcal.pack_unpack import get_objects_dictionary


def get_cgmes_data_frames():
    """

    :return:
    """
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
    """

    :return:
    """
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
    """

    :return:
    """
    info = dict()

    obj_dict = get_objects_dictionary()

    circuit = MultiCircuit()
    d = circuit.objects_with_profiles.copy()
    categories = {elm.device_type.value: cat for cat, elms in d.items() for elm in elms}
    for obj_type_name, obj in obj_dict.items():

        class_name = obj.device_type.value

        data = list()
        for prop_name, prop in obj.registered_properties.items():
            data.append(prop.get_dict())

        info[class_name] = pd.DataFrame(data=data)

    return info


def get_gridcal_data_frames_per_category():
    """

    :return:
    """
    info = dict()

    obj_dict = get_objects_dictionary()

    circuit = MultiCircuit()
    d = circuit.objects_with_profiles.copy()
    categories = {elm.device_type.value: cat for cat, elms in d.items() for elm in elms}

    for obj_type_name, obj in obj_dict.items():

        class_name = obj.device_type.value
        category = categories.get(class_name, None)

        if category is not None:
            data = list()
            for prop_name, prop in obj.registered_properties.items():
                data.append(prop.get_dict())

            df = pd.DataFrame(data=data)

            category_dict = info.get(category, None)

            if category_dict:
                category_dict[class_name] = df
            else:
                info[category] = {class_name: df}

    return info


def write_dataframes_to_excel(data_frames: Dict[str, pd.DataFrame], filename):
    """

    :param data_frames:
    :param filename:
    :return:
    """
    with pd.ExcelWriter(filename) as w:
        for key, df in data_frames.items():
            df.to_excel(w, sheet_name=key)


def write_dataframes_to_excel_one_sheet(data_frames: Dict[str, pd.DataFrame], filename):
    """

    :param data_frames:
    :param filename:
    :return:
    """
    df_all = pd.DataFrame()
    for key, df in data_frames.items():
        # df['class'] = key
        df.insert(0, 'class', key)
        df_all = pd.concat([df_all, df], axis=0)

    with pd.ExcelWriter(filename) as w:
        df_all.to_excel(w, sheet_name='ALL_CLASSES')


def write_dataframes_to_rst(data_frames: Dict[str, pd.DataFrame], filename, tilte):
    """

    :param data_frames:
    :param filename:
    :param tilte:
    :return:
    """
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


def write_dataframes_to_latex(data_frames: Dict[str, Dict[str, pd.DataFrame]], folder="data_model",
                              cols_to_delete=['max_chars', 'comment', 'mandatory']):
    """

    :param data_frames:
    :param filename:
    :param tilte:
    :return:
    """

    if not os.path.exists(folder):
        os.makedirs(folder)

    def fix(val):
        return str(val).replace("_", "\_").replace("%", "\%")

    with open(os.path.join(folder, 'data_models.tex'), 'w') as wp:

        for cat_name, dataframes_dict in data_frames.items():

            cat_fname = "data_model_" + cat_name.replace(" & ", "_").lower()
            fname = os.path.join(folder, f'{cat_fname}.tex')

            wp.write("\\input{" + folder + "/" + cat_fname + "}\n")

            with open(fname, 'w') as w:

                w.write("\section{" + cat_name.replace("&", "and") + "}\n")

                for key, df in dataframes_dict.items():

                    w.write("\n\\textbf{" + str(key) + "}\n\n")

                    if len(cols_to_delete):
                        df = df.drop(columns=cols_to_delete)

                    hdr = [fix(col) for col in df.columns.tolist()]
                    idx = [fix(col) for col in df.index.tolist()]
                    data = df.values.copy()
                    for i in range(data.shape[0]):
                        for j in range(data.shape[1]):
                            data[i, j] = fix(data[i, j])

                    frmt = "|".join(["X" for h in hdr])
                    text = "\\begin{fullwidth}\n"
                    text += "\\small\n"
                    text += "\\begin{longtable}{|X|X|X|X|}\n"
                    text += "\\caption{" + str(key) + "}\n"
                    text += "\\toprule\n"
                    text += " & ".join(hdr) + "\\\\ \n"
                    text += "\\midrule\n"

                    nrows = data.shape[0]
                    for i in range(nrows):
                        text += " & ".join(data[i, :])
                        text += "\\\\ \n"
                        # if i < (nrows - 1):
                        #     text += "\\\\ \n"
                        # else:
                        #     text += "\n"
                    text += "\\bottomrule\n"
                    text += "\end{longtable}\n"
                    text += "\end{fullwidth}\n"

                    w.write(text + "\n")
                    w.write("\n\n")


def write_dataframes_to_rst2(w, data_frames: Dict[str, pd.DataFrame], tilte):
    """

    :param w:
    :param data_frames:
    :param tilte:
    :return:
    """
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
    """

    :param filename:
    :return:
    """
    with open(filename, 'w') as w:
        w.write("Data Models\n")
        w.write("==========================\n\n")

        cgmes_info = get_cgmes_data_frames()
        psse_info = get_psse_data_frames()
        gridcal_info = get_gridcal_data_frames()

        write_dataframes_to_rst2(w, cgmes_info, "CGMES")
        write_dataframes_to_rst2(w, psse_info, "PSSE")
        write_dataframes_to_rst2(w, gridcal_info, "GridCal")


if __name__ == '__main__':
    cgmes_info = get_cgmes_data_frames()
    psse_info = get_psse_data_frames()
    gridcal_info = get_gridcal_data_frames()
    gridcal_info_cat = get_gridcal_data_frames_per_category()

    # write_dataframes_to_excel_one_sheet(cgmes_info,
    #                           'cgmes_classes_all_in_one_sheet.xlsx')
    # write_dataframes_to_excel_one_sheet(psse_info,
    #                           'psse_classes_all_in_one_sheet.xlsx')
    write_dataframes_to_excel_one_sheet(gridcal_info,
                              'roseta_classes_all_in_one_sheet.xlsx')

    # write_dataframes_to_rst(cgmes_info, 'cgmes_clases.rst', "CGMES")
    # write_dataframes_to_rst(psse_info, 'psse_clases.rst', "PSSE")
    # write_dataframes_to_rst(roseta_info, 'roseta_clases.rst', "Roseta")
    # write_dataframes_to_latex(gridcal_info_cat)

    # write_models_to_rst(os.path.join('rst_source', 'other_data_models.rst'))

    print("done")
