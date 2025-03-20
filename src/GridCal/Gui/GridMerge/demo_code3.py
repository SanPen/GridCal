# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import sys
from PySide6 import QtWidgets
from GridCal.Gui.GridMerge.grid_diff import GridDiffDialogue
import GridCalEngine.api as gce


folder = "/home/santi/Documentos/Git/GitHub/GridCal/src/tests/data"

original = gce.open_file(filename=os.path.join(folder, "grids", "IEEE57.gridcal"))  # we use this for diff

grid1 = gce.open_file(filename=os.path.join(folder, "grids", "IEEE57.gridcal"))  # we modify this one in place

# add stuff
lynn_original = gce.open_file(filename=os.path.join(folder, "grids", "lynn5node.gridcal"))
lynn_original.delete_profiles()

# add elements one by one
for elm in lynn_original.items():
    grid1.add_element(obj=elm)

# calculate the difference of the modified grid with the original
ok_diff, diff_logger, diff = grid1.differentiate_circuits(base_grid=original)

# the calculated difference should be equal to the grid we added
ok_compare, comp_logger = diff.compare_circuits(grid2=lynn_original, skip_internals=True)

print()


app = QtWidgets.QApplication(sys.argv)
window = GridDiffDialogue(original)
window._diff = diff
window.build_tree()

# window.resize(int(1.61 * 700.0), int(600.0))  # golden ratio
window.show()
sys.exit(app.exec())