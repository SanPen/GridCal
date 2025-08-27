# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import os.path
import warnings
from VeraGridEngine.IO.file_system import get_create_veragrid_folder
from VeraGridEngine import TapModuleControl, TapPhaseControl, BusMode
from VeraGridEngine.enumerations import (HvdcControlType, SolverType, TimeGrouping,
                                         ZonalGrouping, MIPSolvers, ContingencyMethod, ContingencyOperationTypes,
                                         BuildStatus, BranchGroupTypes, ConverterControlType)
GSLV_RECOMMENDED_VERSION = "0.4.1"
GSLV_VERSION = ''
GSLV_AVAILABLE = False
try:
    import pygslv as pg
    pg.activate(os.path.join(get_create_veragrid_folder(), "license.gslv"), verbose=False)

    # activate
    if not pg.isLicensed():
        # license not found
        GSLV_AVAILABLE = False
    else:
        # already activated
        GSLV_AVAILABLE = True
        GSLV_VERSION = pg.get_version()

    if GSLV_AVAILABLE:
        if GSLV_VERSION < GSLV_RECOMMENDED_VERSION:
            warnings.warn(f"Recommended version for GSLV is {GSLV_RECOMMENDED_VERSION} "
                          f"instead of {GSLV_VERSION}")

    build_status_dict = {
        BuildStatus.Planned: pg.BuildStatus.Planned,
        BuildStatus.Commissioned: pg.BuildStatus.Commissioned,
        BuildStatus.Candidate: pg.BuildStatus.Candidate,
        BuildStatus.Decommissioned: pg.BuildStatus.Decommissioned,
        BuildStatus.PlannedDecommission: pg.BuildStatus.PlannedDecommission,
    }

    tap_module_control_mode_dict = {
        TapModuleControl.fixed: pg.TapModuleControl.fixed,
        TapModuleControl.Qf: pg.TapModuleControl.Qf,
        TapModuleControl.Qt: pg.TapModuleControl.Qt,
        TapModuleControl.Vm: pg.TapModuleControl.Vm,
    }

    tap_phase_control_mode_dict = {
        TapPhaseControl.fixed: pg.TapPhaseControl.fixed,
        TapPhaseControl.Pf: pg.TapPhaseControl.Pf,
        TapPhaseControl.Pt: pg.TapPhaseControl.Pt,
    }

    hvdc_control_mode_dict = {
        HvdcControlType.type_0_free: pg.HvdcControlType.type_0_free,
        HvdcControlType.type_1_Pset: pg.HvdcControlType.type_1_Pset,
    }

    group_type_dict = {
        BranchGroupTypes.GenericGroup: pg.BranchGroupTypes.GenericGroup,
        BranchGroupTypes.TransformerGroup: pg.BranchGroupTypes.TransformerGroup,
        BranchGroupTypes.LineSegmentsGroup: pg.BranchGroupTypes.LineSegmentsGroup,
    }

    contingency_ops_type_dict = {
        ContingencyOperationTypes.Active: pg.ContingencyOperationTypes.Active,
        ContingencyOperationTypes.PowerPercentage: pg.ContingencyOperationTypes.PowerPercentage,
    }

    contingency_method_dict = {
        ContingencyMethod.PTDF: pg.ContingencyMethod.PTDF,
        ContingencyMethod.PowerFlow: pg.ContingencyMethod.PowerFlow,
        ContingencyMethod.HELM: pg.ContingencyMethod.HELM,
    }

    converter_control_type_dict = {
        ConverterControlType.Vm_dc: pg.ConverterControlType.Vm_dc,
        ConverterControlType.Vm_ac: pg.ConverterControlType.Vm_ac,
        ConverterControlType.Va_ac: pg.ConverterControlType.Va_ac,
        ConverterControlType.Qac: pg.ConverterControlType.Q_ac,
        ConverterControlType.Pdc: pg.ConverterControlType.P_dc,
        ConverterControlType.Pac: pg.ConverterControlType.P_ac,
    }

    bus_type_dict = {
        BusMode.PQ_tpe.value: pg.BusMode.PQ,
        BusMode.PV_tpe.value: pg.BusMode.PV,
        BusMode.Slack_tpe.value: pg.BusMode.Slack,
        BusMode.P_tpe.value: pg.BusMode.P,
        BusMode.PQV_tpe.value: pg.BusMode.PQV,
    }

except ImportError as e:
    pg = None
    GSLV_AVAILABLE = False
    GSLV_VERSION = ''

    build_status_dict = dict()
    tap_module_control_mode_dict = dict()
    tap_phase_control_mode_dict = dict()
    hvdc_control_mode_dict = dict()
    group_type_dict = dict()
    contingency_ops_type_dict = dict()
    contingency_method_dict = dict()
    converter_control_type_dict = dict()
    bus_type_dict = dict()
