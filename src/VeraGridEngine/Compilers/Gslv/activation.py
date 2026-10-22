# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import Tuple
import os.path
import shutil
import packaging.version as pkg
import warnings
from pathlib import Path
from VeraGridEngine.enumerations import (
    TapModuleControl,
    TapPhaseControl,
    BusMode,
    ShuntConnectionType,
    WindingType,
    WindingsConnection,
    HvdcControlType,
    ContingencyMethod,
    ContingencyOperationTypes,
    BuildStatus,
    BranchGroupTypes,
    ConverterControlType,
    GeneratorControlMode,
    BatteryDispatchMode,
    RemedialActionPropertyEnum,
)
GSLV_MINIMUM_VERSION: str = "1.0.0"
GSLV_RECOMMENDED_VERSION: str = GSLV_MINIMUM_VERSION
GSLV_VERSION: str = ''
GSLV_AVAILABLE: bool = False
GSLV_UNAVAILABLE_REASON: str = ""

# pygslv exports its statically linked HiGHS symbols globally; if it loads before
# highspy, the highspy solver resolves against pygslv's HiGHS and segfaults mid-solve.
# Loading highspy first pins the correct symbols. Missing highspy is fine: the except
# below only shields the import order, nothing else uses this module reference.
# try:
#     import highspy as _highspy_loaded_before_pygslv
# except ImportError:
#     _highspy_loaded_before_pygslv = None

try:
    import pygslv as pg
    # Optional pygslv is not necessarily upgraded with VeraGrid; an old licensed version
    # can still lack required enums (for example BatteryDispatchMode in 0.9.4).
    # Check the minimum before activation or touching those symbols so GUI startup survives.
    GSLV_VERSION = pg.get_version()
    if pkg.parse(GSLV_VERSION) < pkg.parse(GSLV_MINIMUM_VERSION):
        GSLV_UNAVAILABLE_REASON = (
            f"installed pygslv {GSLV_VERSION}; this VeraGrid requires pygslv >= {GSLV_MINIMUM_VERSION}. "
            "Upgrade pygslv in this Python environment and restart VeraGrid"
        )
    else:
        # The wrapper owns license discovery; only licensed, complete APIs are usable.
        pg.search_license_and_activate(verbose=False)
        if pg.isLicensed():
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

            generator_control_mode_dict = {
                GeneratorControlMode.Q: pg.GeneratorControlMode.Q,
                GeneratorControlMode.V: pg.GeneratorControlMode.V,
                GeneratorControlMode.QVDroop: pg.GeneratorControlMode.QVDroop,
            }

            battery_dispatch_mode_dict: dict[BatteryDispatchMode, pg.BatteryDispatchMode] = {
                BatteryDispatchMode.Grid: pg.BatteryDispatchMode.Grid,
                BatteryDispatchMode.PlantChargeGridDischarge: pg.BatteryDispatchMode.PlantChargeGridDischarge,
                BatteryDispatchMode.PlantChargeAndDisCharge: pg.BatteryDispatchMode.PlantChargeAndDisCharge,
            }

            remedial_action_property_dict: dict[RemedialActionPropertyEnum, pg.RemedialActionPropertyEnum] = {
                RemedialActionPropertyEnum.Vmin: pg.RemedialActionPropertyEnum.Vmin,
                RemedialActionPropertyEnum.Vmax: pg.RemedialActionPropertyEnum.Vmax,
                RemedialActionPropertyEnum.Loading: pg.RemedialActionPropertyEnum.Loading,
                RemedialActionPropertyEnum.ContingencyLoading: pg.RemedialActionPropertyEnum.ContingencyLoading,
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
                ContingencyMethod.Linear: pg.ContingencyMethod.PTDF,
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
                ConverterControlType.Pdc_angle_droop: pg.ConverterControlType.P_dc_angle_droop,
                ConverterControlType.Pdc_droop: pg.ConverterControlType.P_dc_droop,
                ConverterControlType.Q_droop: pg.ConverterControlType.Q_droop,
                ConverterControlType.P_droop: pg.ConverterControlType.P_droop,
                ConverterControlType.Imax: pg.ConverterControlType.Imax,
                ConverterControlType.Fault1: pg.ConverterControlType.Fault1,
                ConverterControlType.Fault2: pg.ConverterControlType.Fault2,
            }

            bus_type_dict = {
                BusMode.PQ_tpe.value: pg.BusMode.PQ,
                BusMode.PV_tpe.value: pg.BusMode.PV,
                BusMode.Slack_tpe.value: pg.BusMode.Slack,
                BusMode.P_tpe.value: pg.BusMode.P,
                BusMode.PQV_tpe.value: pg.BusMode.PQV,
            }

            shunt_connection_type_dict = {
                ShuntConnectionType.GroundedStar: pg.ShuntConnectionType.GroundedStar,
                ShuntConnectionType.FloatingStar: pg.ShuntConnectionType.FloatingStar,
                ShuntConnectionType.NeutralStar: pg.ShuntConnectionType.NeutralStar,
                ShuntConnectionType.Delta: pg.ShuntConnectionType.Delta,
            }

            winding_type_dict = {
                WindingType.GroundedStar: pg.WindingType.GroundedStar,
                WindingType.NeutralStar: pg.WindingType.NeutralStar,
                WindingType.Delta: pg.WindingType.Delta,
                WindingType.GroundedZigZag: pg.WindingType.ZigZag,
                WindingType.FloatingZigZag: pg.WindingType.ZigZag,
                WindingType.NeutralZigZag: pg.WindingType.ZigZag,
            }

            windings_connection_dict = {
                WindingsConnection.GG: pg.WindingsConnection.GG,
                WindingsConnection.GS: pg.WindingsConnection.GS,
                WindingsConnection.GD: pg.WindingsConnection.GD,
                WindingsConnection.SS: pg.WindingsConnection.SS,
                WindingsConnection.SD: pg.WindingsConnection.SD,
                WindingsConnection.DD: pg.WindingsConnection.DD,
            }
            GSLV_AVAILABLE = True
        else:
            GSLV_UNAVAILABLE_REASON = "pygslv has no valid license"

except ModuleNotFoundError as error:
    if error.name == "pygslv":
        GSLV_UNAVAILABLE_REASON = "pygslv is not installed"
    else:
        GSLV_UNAVAILABLE_REASON = f"pygslv dependency could not be imported: {error}"
except (ImportError, AttributeError, OSError, RuntimeError, pkg.InvalidVersion) as error:
    GSLV_UNAVAILABLE_REASON = f"pygslv {GSLV_VERSION or 'unknown version'} could not initialize: {error}"

if not GSLV_AVAILABLE:
    # Clear partially built mappings as well as the module to prevent accidental dispatch.
    pg = None
    build_status_dict = dict()
    tap_module_control_mode_dict = dict()
    tap_phase_control_mode_dict = dict()
    generator_control_mode_dict = dict()
    battery_dispatch_mode_dict = dict()
    remedial_action_property_dict = dict()
    hvdc_control_mode_dict = dict()
    group_type_dict = dict()
    contingency_ops_type_dict = dict()
    contingency_method_dict = dict()
    converter_control_type_dict = dict()
    bus_type_dict = dict()
    shunt_connection_type_dict = dict()
    winding_type_dict = dict()
    windings_connection_dict = dict()

    if GSLV_UNAVAILABLE_REASON != "pygslv is not installed":
        warnings.warn(f"GSLV disabled: {GSLV_UNAVAILABLE_REASON}", stacklevel=2)
    else:
        pass
else:
    pass


def install_gslv_license(fname: str) -> Tuple[bool, str]:
    """
    Copy one GSLV license file into VeraGrid's managed folder.

    :param fname: Source license file path.
    :return: Success flag and status message.
    """

    if os.path.exists(fname):
        # The license must live inside VeraGrid's managed folder so the wrapper
        # can discover it consistently on later runs.
        folder: str = os.path.join(str(Path.home()), '.VeraGrid')
        if os.path.exists(folder):
            pass
        else:
            os.makedirs(folder)

        name = os.path.basename(fname)
        dst = os.path.join(folder, name)
        shutil.copyfile(fname, dst)
        return True, "License installed!"
    else:
        return False, "The file does not exists :("
