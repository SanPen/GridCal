# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pathlib import Path

import pytest

from VeraGridEngine.IO.fmu.config import ExportConfig as CoSimulationExportConfig
from VeraGridEngine.IO.fmu.config import ExportConfig as ModelExchangeExportConfig
from VeraGridEngine.enumerations import FmiVersion


def test_co_simulation_export_defaults_to_canonical_fmi_two(tmp_path: Path) -> None:
    """Verify the existing Co-Simulation path preserves its FMI 2 default.

    :param tmp_path: Isolated output directory provided by pytest.
    :return: None.
    """

    config: CoSimulationExportConfig = CoSimulationExportConfig(
        model_name="CoSimulation",
        output_path=tmp_path / "co-simulation.fmu",
        compile_binary=False,
        )
    assert config.fmi_version is FmiVersion.FMI_2_0


def test_model_exchange_export_defaults_to_canonical_fmi_two(tmp_path: Path) -> None:
    """Verify the existing Model Exchange path preserves its FMI 2 default.

    :param tmp_path: Isolated output directory provided by pytest.
    :return: None.
    """

    config: ModelExchangeExportConfig = ModelExchangeExportConfig(
        model_name="ModelExchange",
        output_path=tmp_path / "model-exchange.fmu",
        compile_binary=False,
    )

    assert config.fmi_version is FmiVersion.FMI_2_0


def test_export_configs_accept_the_canonical_fmi_two_text(tmp_path: Path) -> None:
    """Verify textual configuration resolves to the shared enum identity.

    :param tmp_path: Isolated output directory provided by pytest.
    :return: None.
    """

    co_simulation_config: CoSimulationExportConfig = CoSimulationExportConfig(
        model_name="CoSimulation",
        output_path=tmp_path / "co-simulation.fmu",
        compile_binary=False,
        fmi_version="2.0",
    )
    model_exchange_config: ModelExchangeExportConfig = ModelExchangeExportConfig(
        model_name="ModelExchange",
        output_path=tmp_path / "model-exchange.fmu",
        compile_binary=False,
        fmi_version="2.0",
    )

    assert co_simulation_config.fmi_version is FmiVersion.FMI_2_0
    assert model_exchange_config.fmi_version is FmiVersion.FMI_2_0
