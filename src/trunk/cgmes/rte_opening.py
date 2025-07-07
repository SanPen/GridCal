import os
import GridCalEngine as gce
from GridCalEngine.IO.file_handler import FileSavingOptions, FileOpenOptions, FileSave

# fname = os.path.join("..", "..", "tests", "data", "grids", "CGMES_2_4_15", "IEEE 118 Bus v2.zip")
fname = "C:/Users/raiya/PycharmProjects/RTE_Short_Circuits/RTE_grid_04_07_2025.xml"
# logger = gce.Logger()
# data_parser = gce.CgmesDataParser()
# data_parser.load_files(files=[fname])
# cgmes_circuit = gce.CgmesCircuit(cgmes_version=data_parser.cgmes_version,
#                                  cgmes_map_areas_like_raw=False, logger=logger)
# cgmes_circuit.parse_files(data_parser=data_parser)
#
# for ac_line_segment in cgmes_circuit.cgmes_assets.ACLineSegment_list:
#     print(ac_line_segment.name)
#
# # print the logs
# logger.print()


#########################################################################################################
# print("Processing raw file ...")
# logger = gce.Logger()
# # CGMES model import to MultiCircuit
# fileOpenOptions = FileOpenOptions(cgmes_map_areas_like_raw=True)
#
# circuit = gce.FileOpen(file_name=fname, options=fileOpenOptions).open()
# nc_1 = gce.compile_numerical_circuit_at(circuit)
#
# print("Done")

#########################################################################################################
# Try opening normally
grid = gce.open_file(filename=fname)

print("Parsed")

