# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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

from PySide2 import QtWidgets, QtGui

from GridCal.Engine.Core.multi_circuit import MultiCircuit, DeviceType
from GridCal.Engine.Simulations.ContingencyAnalysis.contingency_plan import ContingencyPlan, generate_automatic_contingency_plan


def get_contingency_planner_model(grid: MultiCircuit, plan: ContingencyPlan):

    model = QtGui.QStandardItemModel()
    model.setHorizontalHeaderLabels(['id', 'name', 'type'])

    branches = grid.get_branches_wo_hvdc()
    hvdc = grid.hvdc_lines

    # populate data
    for contingency in plan.contingencies:
        parent1 = QtGui.QStandardItem(contingency.name)

        for k in contingency.branch_indices:
            children = [QtGui.QStandardItem(str(branches[k].idtag)),
                        QtGui.QStandardItem(str(branches[k].name)),
                        QtGui.QStandardItem(str(branches[k].device_type.value))]
            for chld in children:
                chld.setEditable(False)

            parent1.appendRow(children)

        parent1.setEditable(False)
        model.appendRow(parent1)

    return model
