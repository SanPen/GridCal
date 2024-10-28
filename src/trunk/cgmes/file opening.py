import os
from GridCalEngine.IO.cim.cgmes.cgmes_data_parser import CgmesDataParser
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from GridCalEngine.basic_structures import Logger

fname = os.path.join("..", "..", "tests", "data", "grids", "CGMES_2_4_15", "IEEE 118 Bus v2.zip")

logger = Logger()
data_parser = CgmesDataParser()
data_parser.load_files(files=[fname])
cgmes_circuit = CgmesCircuit(cgmes_version=data_parser.cgmes_version,
                             cgmes_map_areas_like_raw=False, logger=logger)
cgmes_circuit.parse_files(data_parser=data_parser)

for ac_line_segment in cgmes_circuit.cgmes_assets.ACLineSegment_list:
    print(ac_line_segment.name)

# print the logs
logger.print()
