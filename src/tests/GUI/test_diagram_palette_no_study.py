"""Palette changes before a study is selected must use design colouring."""

from types import SimpleNamespace
from unittest.mock import Mock

from VeraGrid.Gui.Main.SubClasses.Model.diagrams import DiagramsMain


def test_grid_colour_without_selected_study_uses_design_colouring():
    palette = object()
    diagram = object()
    owner = SimpleNamespace(
        ui=SimpleNamespace(
            branch_width_based_on_flow_checkBox=Mock(isChecked=Mock(return_value=True)),
            min_branch_size_spinBox=Mock(value=Mock(return_value=2)),
            max_branch_size_spinBox=Mock(value=Mock(return_value=5)),
            min_node_size_spinBox=Mock(value=Mock(return_value=3)),
            max_node_size_spinBox=Mock(value=Mock(return_value=6)),
            palette_comboBox=Mock(currentData=Mock(return_value=palette)),
        ),
        default_colouring=Mock(),
    )
    DiagramsMain.grid_colour_function(owner, diagram_widget=diagram, current_study=None, t_idx=None)
    owner.default_colouring.assert_called_once_with(
        t_idx=None,
        diagram_widget=diagram,
        cmap=palette,
        use_flow_based_width=True,
        min_branch_width=2,
        max_branch_width=5,
        min_bus_width=3,
        max_bus_width=6,
    )
