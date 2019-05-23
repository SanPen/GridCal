
import os
import binascii


def main(fname):

    with open(fname, "rb") as binary_file:
        # Read the whole file at once
        bindata = binary_file.read()
        hexdata = binascii.hexlify(bindata)
        hexlist = map(''.join, zip(hexdata[::2], hexdata[1::2]))

        print(hexlist)

    print()


if __name__ == '__main__':

    path = 'C:\\Users\\A487516\\Dropbox\\C - Project Development\\' \
           'C1 - Information Collection\\01_Phase I (CESI)\\02_Data by Source\\' \
           'CESI\\PSSE Models\\Input information for model development'
    file = '2018 PEAK CASE FILE Ver3.sav'

    file_name = os.path.join(path, file)

    result = main(file_name)
