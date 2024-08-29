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
from typing import Dict, List
import GridCalEngine.api as gce


def test_load_and_run_pf() -> None:
    """

    :return:
    """
    base_folder = os.path.join("data", "grids", "CGMES_2_4_15", "TestConfigurations_packageCASv2.0")

    logger = gce.Logger()

    packs = [
        {"BD": os.path.join(base_folder, 'FullGrid', 'CGMES_v2.4.15_FullGridTestConfiguration_BD_v1.zip'),
         "Files": [os.path.join(base_folder, 'FullGrid', 'CGMES_v2.4.15_FullGridTestConfiguration_BB_BE_v1.zip'),
                   os.path.join(base_folder, 'FullGrid', 'CGMES_v2.4.15_FullGridTestConfiguration_BB_BE_v2.zip'),
                   os.path.join(base_folder, 'FullGrid', 'CGMES_v2.4.15_FullGridTestConfiguration_NB_BE_v3.zip'),
                   os.path.join(base_folder, 'FullGrid', 'CGMES_v2.4.15_FullGridTestConfiguration_NB_BE_v4.zip'),
                   ]
         },

        {"BD": os.path.join(base_folder, 'MicroGrid', 'BaseCase_BC',
                            'CGMES_v2.4.15_MicroGridTestConfiguration_BD_v2.zip'),
         "Files": [
             os.path.join(base_folder, 'MicroGrid', 'BaseCase_BC',
                          'CGMES_v2.4.15_MicroGridTestConfiguration_BC_Assembled_v2.zip'),
             os.path.join(base_folder, 'MicroGrid', 'BaseCase_BC',
                          'CGMES_v2.4.15_MicroGridTestConfiguration_BC_BE_v2.zip'),
             os.path.join(base_folder, 'MicroGrid', 'BaseCase_BC',
                          'CGMES_v2.4.15_MicroGridTestConfiguration_BC_NL_v2.zip'),
         ]
         },

        {"BD": os.path.join(base_folder, 'MicroGrid', 'Type1_T1', 'CGMES_v2.4.15_MicroGridTestConfiguration_BD_v2.zip'),
         "Files": [
             os.path.join(base_folder, 'MicroGrid', 'Type1_T1',
                          'CGMES_v2.4.15_MicroGridTestConfiguration_T1_Assembled_Complete_v2.zip'),
             os.path.join(base_folder, 'MicroGrid', 'Type1_T1',
                          'CGMES_v2.4.15_MicroGridTestConfiguration_T1_BE_Complete_v2.zip'),
             os.path.join(base_folder, 'MicroGrid', 'Type1_T1',
                          'CGMES_v2.4.15_MicroGridTestConfiguration_T1_NL_Complete_v2.zip'),
             # os.path.join(base_folder, 'MicroGrid', 'Type1_T1', 'T1_BE_Difference_v2.zip'),
             # os.path.join(base_folder, 'MicroGrid', 'Type1_T1', 'T1_NL_Difference_v2.zip'),
         ]
         },

        {"BD": os.path.join(base_folder, 'MicroGrid', 'Type2_T2', 'CGMES_v2.4.15_MicroGridTestConfiguration_BD_v2.zip'),
         "Files": [
             os.path.join(base_folder, 'MicroGrid', 'Type2_T2',
                          'CGMES_v2.4.15_MicroGridTestConfiguration_T2_Assembled_Complete_v2.zip'),
             os.path.join(base_folder, 'MicroGrid', 'Type2_T2',
                          'CGMES_v2.4.15_MicroGridTestConfiguration_T2_BE_Complete_v2.zip'),
             os.path.join(base_folder, 'MicroGrid', 'Type2_T2',
                          'CGMES_v2.4.15_MicroGridTestConfiguration_T2_NL_Complete_v2.zip'),
             # os.path.join(base_folder, 'MicroGrid', 'Type2_T2', 'T2_BE_Difference_v2.zip'),
             # os.path.join(base_folder, 'MicroGrid', 'Type2_T2', 'T2_NL_Difference_v2.zip'),
         ]
         },

        {"BD": os.path.join(base_folder, 'MicroGrid', 'Type3_T3', 'CGMES_v2.4.15_MicroGridTestConfiguration_BD_v2.zip'),
         "Files": [
             os.path.join(base_folder, 'MicroGrid', 'Type3_T3',
                          'CGMES_v2.4.15_MicroGridTestConfiguration_T3_Assembled_Complete_v2.zip'),
             os.path.join(base_folder, 'MicroGrid', 'Type3_T3',
                          'CGMES_v2.4.15_MicroGridTestConfiguration_T3_BE_Complete_v2.zip'),
             os.path.join(base_folder, 'MicroGrid', 'Type3_T3',
                          'CGMES_v2.4.15_MicroGridTestConfiguration_T3_NL_Complete_v2.zip'),
             # os.path.join(base_folder, 'MicroGrid', 'Type3_T3', 'T3_BE_Difference_v2.zip'),
             # os.path.join(base_folder, 'MicroGrid', 'Type3_T3', 'T3_NL_Difference_v2.zip'),
         ]
         },

        {"BD": os.path.join(base_folder, 'MicroGrid', 'Type4_T4', 'CGMES_v2.4.15_MicroGridTestConfiguration_BD_v2.zip'),
         "Files": [
             os.path.join(base_folder, 'MicroGrid', 'Type4_T4',
                          'CGMES_v2.4.15_MicroGridTestConfiguration_T4_Assembled_BB_Complete_v2.zip'),
             os.path.join(base_folder, 'MicroGrid', 'Type4_T4',
                          'CGMES_v2.4.15_MicroGridTestConfiguration_T4_Assembled_NB_Complete_v2.zip'),
             os.path.join(base_folder, 'MicroGrid', 'Type4_T4',
                          'CGMES_v2.4.15_MicroGridTestConfiguration_T4_BE_BB_Complete_v2.zip'),
             os.path.join(base_folder, 'MicroGrid', 'Type4_T4',
                          'CGMES_v2.4.15_MicroGridTestConfiguration_T4_BE_NB_Complete_v2.zip'),
             os.path.join(base_folder, 'MicroGrid', 'Type4_T4',
                          'CGMES_v2.4.15_MicroGridTestConfiguration_T4_NL_BB_Complete_v2.zip'),
             os.path.join(base_folder, 'MicroGrid', 'Type4_T4',
                          'CGMES_v2.4.15_MicroGridTestConfiguration_T4_NL_NB_Complete_v2.zip'),
             # os.path.join(base_folder, 'MicroGrid', 'Type4_T4', 'T4_BE_BB_Difference_v2.zip'),
             # os.path.join(base_folder, 'MicroGrid', 'Type4_T4', 'T4_BE_NB_Difference_v2.zip'),
             # os.path.join(base_folder, 'MicroGrid', 'Type4_T4', 'T4_NL_BB_Difference_v2.zip'),
             # os.path.join(base_folder, 'MicroGrid', 'Type4_T4', 'T4_NL_NB_Difference_v2.zip'),
         ]
         },

        {"BD": "",
         "Files": [
             os.path.join(base_folder, 'MicroGrid', 'Type5_EDD',
                          'CGMES_v2.4.15_MicroGridTestConfiguration-T5_BD_v1.zip'),
             os.path.join(base_folder, 'MicroGrid', 'Type5_EDD',
                          'CGMES_v2.4.15_MicroGridTestConfiguration-T5_BE_v1.zip'),
         ]
         },

        {"BD": os.path.join(base_folder, 'MiniGrid', 'BusBranch',
                            'CGMES_v2.4.15_MiniGridTestConfiguration_Boundary_v3.zip'),
         "Files": [
             os.path.join(base_folder, 'MiniGrid', 'BusBranch',
                          'CGMES_v2.4.15_MiniGridTestConfiguration_BaseCase_v3.zip'),
             os.path.join(base_folder, 'MiniGrid', 'BusBranch',
                          'CGMES_v2.4.15_MiniGridTestConfiguration_T1_Complete_v3.zip'),
             os.path.join(base_folder, 'MiniGrid', 'BusBranch',
                          'CGMES_v2.4.15_MiniGridTestConfiguration_T2_Complete_v3.zip'),
         ]
         },

        {"BD": os.path.join(base_folder, 'MiniGrid', 'NodeBreaker',
                            'CGMES_v2.4.15_MiniGridTestConfiguration_Boundary_v3.zip'),
         "Files": [
             os.path.join(base_folder, 'MiniGrid', 'NodeBreaker',
                          'CGMES_v2.4.15_MiniGridTestConfiguration_BaseCase_Complete_v3.zip'),
             os.path.join(base_folder, 'MiniGrid', 'NodeBreaker',
                          'CGMES_v2.4.15_MiniGridTestConfiguration_T1_Complete_v3.zip'),
             os.path.join(base_folder, 'MiniGrid', 'NodeBreaker',
                          'CGMES_v2.4.15_MiniGridTestConfiguration_T2_Complete_v3.zip'),
         ]
         },

        {"BD": "",
         "Files": [
             os.path.join(base_folder, 'RealGrid', 'CGMES_v2.4.15_RealGridTestConfiguration_v2.zip'),
         ]
         },

        {"BD": os.path.join(base_folder, 'SmallGrid', 'BusBranch',
                            'CGMES_v2.4.15_SmallGridTestConfiguration_Boundary_v3.0.0.zip'),
         "Files": [
             os.path.join(base_folder, 'SmallGrid', 'BusBranch',
                          'CGMES_v2.4.15_SmallGridTestConfiguration_BaseCase_Complete_v3.0.0.zip'),
             os.path.join(base_folder, 'SmallGrid', 'BusBranch',
                          'CGMES_v2.4.15_SmallGridTestConfiguration_HVDC_Complete_v3.0.0.zip'),
             os.path.join(base_folder, 'SmallGrid', 'BusBranch',
                          'CGMES_v2.4.15_SmallGridTestConfiguration_ReducedNetwork_Complete_v3.0.0.zip'),
         ]
         },

        {"BD": os.path.join(base_folder, 'SmallGrid', 'NodeBreaker',
                            'CGMES_v2.4.15_SmallGridTestConfiguration_Boundary_v3.0.0.zip'),
         "Files": [
             os.path.join(base_folder, 'SmallGrid', 'NodeBreaker',
                          'CGMES_v2.4.15_SmallGridTestConfiguration_BaseCase_Complete_v3.0.0.zip'),
             os.path.join(base_folder, 'SmallGrid', 'NodeBreaker',
                          'CGMES_v2.4.15_SmallGridTestConfiguration_HVDC_Complete_v3.0.0.zip'),
             os.path.join(base_folder, 'SmallGrid', 'NodeBreaker',
                          'CGMES_v2.4.15_SmallGridTestConfiguration_ReducedNetwork_Complete_v3.0.0.zip'),
         ]
         },

        {"BD": "",
         "Files": [
             os.path.join(base_folder, 'PST_PTChLin_PTE1_PSEI.zip'),
             os.path.join(base_folder, 'PST_PTChLin_PTE2_PSEI.zip'),
             os.path.join(base_folder, 'PST_PTChTab_PTE2_PSEI.zip'),
             os.path.join(base_folder, 'TransformerLineTest.zip')
         ]
         },

    ]

    n = 0
    failures = 0
    for data in packs:
        bd = data['BD']
        files = data['Files']

        for fname in files:
            if bd is "":
                lst = [fname]
            else:
                lst = [bd, fname]

            # print("*" * 200)
            # print("Loading ", bd, fname)

            n += 1

            try:
                grid = gce.open_file(filename=lst)
            except Exception as e:
                logger.add_error(msg="Failed loading - " + str(e), device=os.path.basename(fname))
                grid = None
                failures += 1

            if grid is not None:
                try:
                    gce.power_flow(grid)
                except Exception as e:
                    logger.add_error(msg="Failed PF - " + str(e), device=os.path.basename(fname))
                    failures += 1

            # print("*" * 200)

    if logger.has_logs():
        logger.print()
        print(f"Failed {failures} out of {n}, {failures/n*100:.2f}%")

    assert not logger.has_logs()
