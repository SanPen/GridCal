from __future__ import annotations

from pathlib import Path

import numpy as np

import VeraGridEngine.api as vg
from VeraGridEngine.enumerations import ResultTypes
from VeraGrid.Session.session import SimulationSession
from VeraGridEngine.IO.veragrid.zip_interface import get_session_tree
from VeraGridEngine.IO.veragrid.zip_interface import load_session_driver_objects
from VeraGridEngine.Simulations.InvestmentsEvaluation.investments_evaluation_driver import (
    InvestmentsEvaluationDriver,
)
from VeraGridEngine.Simulations.InvestmentsEvaluation.investments_evaluation_options import (
    InvestmentsEvaluationOptions,
)
from VeraGridEngine.Simulations.InvestmentsEvaluation.investments_evaluation_results import (
    InvestmentsEvaluationResults,
)


def test_investments_results_session_save_load_roundtrip(tmp_path: Path) -> None:
    """
    Save one investments-results session to disk and load it back.

    The regression target is scalar results metadata such as ``max_eval`` and
    plot indices. Those fields used to be skipped by the generic parquet save
    path, which made the saved session appear incomplete.

    :param tmp_path: Temporary pytest path.
    :return: None.
    """
    grid: vg.MultiCircuit = vg.MultiCircuit(name="save-load-investments")
    driver: InvestmentsEvaluationDriver = InvestmentsEvaluationDriver(
        grid=grid,
        options=InvestmentsEvaluationOptions(max_eval=3),
        problem=None,
    )
    driver.results = InvestmentsEvaluationResults(
        f_names=np.array(["capex", "losses"], dtype=str),
        x_names=np.array(["group_0"], dtype=str),
        max_eval=3,
        plot_x_idx=0,
        plot_y_idx=1,
    )
    driver.results.x = np.array([[0.0], [1.0], [1.0]], dtype=float)
    driver.results.f = np.array([[10.0, 5.0], [8.0, 4.0], [7.0, 3.5]], dtype=float)
    driver.results.f_best = np.array([1.0], dtype=float)
    driver.results.sorting_indices = np.array([2, 1, 0], dtype=int)

    file_name: Path = tmp_path / "investments_results_roundtrip.veragrid"
    vg.save_file(grid=grid, filename=str(file_name), drivers_to_save=[driver.get_save_data()])

    session_tree = get_session_tree(str(file_name))
    assert driver.name in session_tree
    assert driver.tpe.value in session_tree[driver.name]
    stored_names = session_tree[driver.name][driver.tpe.value]
    assert "max_eval.parquet" in stored_names
    assert "plot_x_idx.parquet" in stored_names
    assert "plot_y_idx.parquet" in stored_names
    assert "x.parquet" in stored_names
    assert "f.parquet" in stored_names

    session_data = load_session_driver_objects(
        file_name_zip=str(file_name),
        session_name=driver.name,
        study_name=driver.tpe.value,
    )

    session = SimulationSession()
    logger = session.register_driver_from_disk_data(
        grid=grid,
        study_name=driver.tpe.value,
        data_dict=session_data,
    )
    assert len(logger.entries) == 0

    loaded_driver, loaded_results = session.investments_evaluation
    assert loaded_driver is not None
    assert loaded_results is not None
    assert isinstance(loaded_results.max_eval, int)
    assert isinstance(loaded_results.plot_x_idx, int)
    assert isinstance(loaded_results.plot_y_idx, int)
    assert loaded_results.max_eval == 3
    assert loaded_results.plot_x_idx == 0
    assert loaded_results.plot_y_idx == 1
    assert np.array_equal(loaded_results.f_names, driver.results.f_names)
    assert np.array_equal(loaded_results.x_names, driver.results.x_names)
    assert np.array_equal(loaded_results.x, driver.results.x)
    assert np.array_equal(loaded_results.f, driver.results.f)
    assert np.array_equal(loaded_results.f_best, driver.results.f_best)
    assert np.array_equal(loaded_results.sorting_indices, driver.results.sorting_indices)

    # Imported scalar metadata must also work when constructing plot tables.
    iterations = loaded_results.mdl(ResultTypes.InvestmentsIterationsPlot)
    assert np.array_equal(iterations.data_c[:, 0], np.arange(3))
