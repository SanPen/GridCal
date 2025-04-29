# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import sys
from PySide6 import QtWidgets
from GridCal.Gui.GridMerge.grid_merge import GridMergeDialogue
import GridCalEngine.api as gce


folder = "C:/Users/eRoots1/Desktop/M-project/Model"

original = gce.open_file(filename=os.path.join(folder, "Database_T4.gridcal"))  # we use this for diff

grid1 = gce.open_file(filename=os.path.join(folder, "Database_T5.gridcal"))  # we modify this one in place

# calculate the difference of the modified grid with the original
ok_diff, diff_logger, diff = grid1.differentiate_circuits(base_grid=original)

print()


app = QtWidgets.QApplication(sys.argv)
window = GridMergeDialogue(original, diff)

# window.resize(int(1.61 * 700.0), int(600.0))  # golden ratio
window.show()
app.exec()



