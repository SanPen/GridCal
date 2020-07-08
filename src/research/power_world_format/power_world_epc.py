import chardet
import csv
import pandas as pd
import re
from typing import List, AnyStr, Dict


def special_split(string, delimiter=' ', quotechar='"'):
    """
    Split the line
    :param string:
    :param delimiter:
    :param quotechar:
    :return:
    """
    # remove ':'
    # string = string.replace(':', '')
    # merge the delimiters
    string = delimiter.join(string.split())

    # list of elements
    lst = list(csv.reader([string], delimiter=delimiter, quotechar=quotechar))[0]

    # remove '' items
    lst = [x for x in lst if x.strip() != '']

    return lst


def read_EPC_format(file_name):
    # make a guess of the file encoding
    detection = chardet.detect(open(file_name, "rb").read())

    # open the text file into a variable
    txt = ''
    with open(file_name, 'r', encoding=detection['encoding']) as my_file:
        for line in my_file:
            if line[0] != '@':
                txt += line

    txt = txt.replace('/\n', ' ')

    # split the text file into sections
    sections = txt.split('\n')

    sections_dict = dict()

    current_section = ''
    current_lines = list()
    for i, sec in enumerate(sections):

        if 'end' not in sec:
            if '[' in sec and ']' in sec:  # new line

                # store previous
                df = pd.DataFrame(current_lines[1:])
                sections_dict[current_section] = (current_lines[0], df)

                # declare new
                values = sec.split('[')
                current_section = values[0].strip()
                values2 = sec.split(']')
                header = values2[1].strip()
                current_lines = [special_split(header)]
            else:
                if current_section == '':
                    current_lines.append(sec.strip())
                else:
                    current_lines.append(special_split(sec.strip()))

    return sections, sections_dict


if __name__ == '__main__':

    fname = '/home/santi/Descargas/ACTIVSg2000/ACTIVSg2000/ACTIVSg2000.EPC'

    sec_, sec_dict = read_EPC_format(file_name=fname)

    print()
