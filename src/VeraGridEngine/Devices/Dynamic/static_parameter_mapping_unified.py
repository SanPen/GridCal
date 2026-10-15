# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Unified API-object parameter initialization mapping.

This module contains the static-device to problem-parameter assignment layer
shared by EMT and RMS problem builders. The contract is intentionally narrow:

* Entries in ``Block.api_obj_mapping`` map ``ParamPowerFlowReferenceType``
  keys to variables declared by the same block. ``Block.parameters`` declares
  immutable values, ``Block.event_dict`` declares continuous event-capable
  values and ``Block.mode_dict`` declares retained discrete values. The mapping
  only selects the initial value source; it does not select the runtime role.
* A successfully resolved API-object mapping is authoritative for
  initialization. A concrete declaration in ``parameters`` or ``event_dict``
  is only a fallback when no mapping is resolved. ``Const(None)`` declares
  that the device-backed source is required.
* Scheduled events may replace the initialized value of an ``event_dict``
  target after initialization. They never change the precedence used to build
  the initial problem.
* Only values that come from the static grid device, or from static network
  bases such as ``Sbase`` and ``fBase``, are assigned here.
* ``Block.parameters``, ``Block.event_dict`` and ``Block.mode_dict`` are never
  written by this module. Resolved values are stored in the problem-side
  mapping consumed by both RMS and EMT assembly.

The unified mapper combines two strategies:

* automatic direct mapping for schema-declared ``dyn_ref`` properties whose
  semantics are true direct static-to-problem assignments;
* explicit device-family mapping for grid-base quantities, derived electrical
  quantities, matrix contracts and historical aliases whose meaning depends on
  the target dynamic model contract.

The problem parser should call ``assign_static_api_object_mapping_for_device``
for each device model root. The function recursively visits all blocks, and the
dynamic model template chooses which static values it consumes by exposing only
the desired enum keys in each owner block's ``api_obj_mapping``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple, TYPE_CHECKING, Union

import numpy as np

from VeraGridEngine.Devices.Branches.overhead_line_type import OverheadLineType
from VeraGridEngine.Devices import MultiCircuit
from VeraGridEngine.Devices.Branches.dc_line import DcLine
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Templates.Emt.line_matrix_conversion import build_physical_line_matrices_from_stored_admittances
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import (
    ConverterControlType,
    DeviceType,
    DynamicSimulationMode,
    ExternalGridMode,
    ParamPowerFlowReferenceType,
    ShuntConnectionType,
    ShuntControlMode,
    WindingType,
)
from VeraGridEngine.Devices.Parents.editable_device import GCProp

if TYPE_CHECKING:
    import VeraGridEngine.Devices as dev
    from VeraGridEngine.Devices.types import ALL_DEV_TYPES


class StaticParameterMappingDiagnostics:
    """Attach one simulation domain to driver-owned mapping diagnostics.

    This lightweight context never owns log entries. It only forwards mapping
    warnings to the logger created by the RMS or EMT driver and supplies the
    correct simulation-domain label. A ``None`` logger keeps direct low-level
    mapper use functional without manufacturing a problem-local logger.

    :param logger: Driver-owned logger, or ``None`` for silent low-level use.
    :param simulation_mode: Dynamic simulation domain requesting the mapping.
    """

    __slots__ = (
        "_logger",
        "_simulation_mode",
    )

    def __init__(
            self,
            logger: Logger | None,
            simulation_mode: DynamicSimulationMode,
    ) -> None:
        self._logger: Logger | None = logger
        self._simulation_mode: DynamicSimulationMode = simulation_mode

    def add_warning(
            self,
            message: str,
            device_name: str,
            value: str,
            expected_value: str,
            device_property: str,
    ) -> None:
        """Forward one mapping warning with the correct RMS or EMT label.

        :param message: Human-readable mapping diagnostic.
        :param device_name: Static device associated with the dynamic model.
        :param value: Actual mapping state that caused the warning.
        :param expected_value: Expected mapping contract.
        :param device_property: Dynamic-model property involved in the warning.
        :return: None.
        """
        if self._logger is None:
            # Silent utility calls still execute the complete numerical mapping;
            # only the unavailable diagnostic sink is omitted.
            pass
        else:
            self._logger.add_warning(
                msg=message,
                device=device_name,
                value=value,
                expected_value=expected_value,
                device_class=self._simulation_mode.value,
                device_property=device_property,
            )

    def add_info(
            self,
            message: str,
            device_name: str,
            value: str,
            expected_value: str,
            device_property: str,
    ) -> None:
        """Forward one mapping information entry with its simulation label.

        Information entries expose intentional source precedence without
        turning a valid mapping contract into a warning.

        :param message: Human-readable mapping diagnostic.
        :param device_name: Static device associated with the dynamic model.
        :param value: Resolved mapping and overridden declaration.
        :param expected_value: Documented source-precedence contract.
        :param device_property: Dynamic-model property involved in the entry.
        :return: None.
        """
        if self._logger is None:
            # Silent utility calls keep the same numerical result while
            # omitting diagnostics that have no driver-owned destination.
            pass
        else:
            self._logger.add_info(
                msg=message,
                device=device_name,
                value=value,
                expected_value=expected_value,
                device_class=self._simulation_mode.value,
                device_property=device_property,
            )

    def get_logger(self) -> Logger | None:
        """Return the driver-owned logger without transferring ownership.

        Device helpers that already implement their own diagnostics can use
        the same driver logger while the mapping context remains responsible
        only for adding the RMS or EMT domain to mapping-specific warnings.

        :return: Driver-owned logger, or ``None`` for silent utility use.
        """
        if self._logger is None:
            return None
        else:
            return self._logger


StaticParameterMappingDiagnosticSink = Logger | StaticParameterMappingDiagnostics


class StaticParameterMappingCandidate:
    """Store the final value proposed by one API reference for one UID.

    :param parameter: Symbolic target associated with the candidate.
    :param source_key: API-object reference that produced the value.
    :param value: Latest value resolved for the source reference.
    :param block_name: Owner block used in diagnostics.
    """

    __slots__ = (
        "parameter",
        "source_key",
        "value",
        "block_name",
    )

    def __init__(
            self,
            parameter: Var,
            source_key: ParamPowerFlowReferenceType,
            value: Const,
            block_name: str,
    ) -> None:
        self.parameter: Var = parameter
        self.source_key: ParamPowerFlowReferenceType = source_key
        self.value: Const = value
        self.block_name: str = block_name


class StaticParameterMappingValues(dict[Var, Const]):
    """Track resolved values and their API reference during one assembly.

    The numerical mapping remains a normal ``dict`` for all existing device
    helpers. The additional source index is problem-local and is never written
    to a dynamic model or serialized file.

    :param initial_values: Existing problem-side values without source metadata.
    """

    __slots__ = ("_candidates",)

    def __init__(self, initial_values: Dict[Var, Const]) -> None:
        super().__init__(initial_values)
        self._candidates: Dict[
            Tuple[int, ParamPowerFlowReferenceType],
            StaticParameterMappingCandidate,
        ] = dict()

    def record_candidate(
            self,
            parameter: Var,
            source_key: ParamPowerFlowReferenceType,
            value: Const,
            block_name: str,
    ) -> None:
        """Record the latest layered value for one UID and API reference.

        Repeated assignments from one reference replace only that reference's
        intermediate candidate. Values from different references remain
        separate until all generic and device-specific layers are complete.

        :param parameter: Symbolic parameter receiving the candidate.
        :param source_key: API-object reference producing the value.
        :param value: Latest value resolved by that reference.
        :param block_name: Owner block used in conflict diagnostics.
        :return: None.
        """
        candidate_id: Tuple[int, ParamPowerFlowReferenceType] = (parameter.uid, source_key)
        self._candidates[candidate_id] = StaticParameterMappingCandidate(
            parameter=parameter,
            source_key=source_key,
            value=value,
            block_name=block_name,
        )

    def finalize_candidates(
            self,
            logger: StaticParameterMappingDiagnosticSink | None,
            device_name: str,
    ) -> None:
        """Select final UID values and report incompatible API references.

        The first semantic source for a UID remains authoritative when final
        candidates disagree. A single warning is emitted after all layered
        assignments have completed, so intermediate generic values never
        create false conflicts.

        :param logger: Optional driver logger or simulation-aware context.
        :param device_name: Static device name used in diagnostics.
        :return: None.
        """
        selected_candidates_by_uid: Dict[int, StaticParameterMappingCandidate] = dict()
        reported_conflicts: Set[int] = set()
        candidate_id: Tuple[int, ParamPowerFlowReferenceType]
        candidate: StaticParameterMappingCandidate

        for candidate_id, candidate in self._candidates.items():
            parameter_uid: int = candidate_id[0]
            selected_candidate: StaticParameterMappingCandidate | None = selected_candidates_by_uid.get(
                parameter_uid,
                None,
            )

            if selected_candidate is None:
                selected_candidates_by_uid[parameter_uid] = candidate
            elif selected_candidate.value.value == candidate.value.value:
                # Different references with the same final value are
                # idempotent and preserve the first target identity.
                pass
            elif parameter_uid in reported_conflicts:
                # One contextual warning per UID is sufficient even if more
                # than two semantic sources disagree.
                pass
            else:
                add_static_mapping_warning(
                    logger=logger,
                    device_name=device_name,
                    message="Conflicting API-object initial values target the same symbolic parameter; later value skipped.",
                    value=(
                        f"uid={parameter_uid}; "
                        + f"kept={selected_candidate.block_name}:{selected_candidate.source_key}:"
                        + f"{selected_candidate.value.value}; "
                        + f"skipped={candidate.block_name}:{candidate.source_key}:{candidate.value.value}"
                    ),
                    expected_value="Every mapping source for one symbolic UID must resolve to the same initial value.",
                    device_property="model template api_obj_mapping",
                )
                reported_conflicts.add(parameter_uid)

        # Replace intermediate last-write values with the selected final value
        # for each symbolic identity before RMS or EMT consumes the mapping.
        final_candidate: StaticParameterMappingCandidate
        for final_candidate in selected_candidates_by_uid.values():
            self[final_candidate.parameter] = final_candidate.value

# devices_static_params_mapping: Dict[DeviceType, List[ParamPowerFlowReferenceType]] = {
#     DeviceType.LoadDevice: [
#         ParamPowerFlowReferenceType.device_active,
#         ParamPowerFlowReferenceType.injection_connection_type,
#         ParamPowerFlowReferenceType.Pl0,
#         ParamPowerFlowReferenceType.Ql0,
#         ParamPowerFlowReferenceType.Pl0_A,
#         ParamPowerFlowReferenceType.Pl0_B,
#         ParamPowerFlowReferenceType.Pl0_C,
#         ParamPowerFlowReferenceType.Ql0_A,
#         ParamPowerFlowReferenceType.Ql0_B,
#         ParamPowerFlowReferenceType.Ql0_C,
#         ParamPowerFlowReferenceType.load_g_pu,
#         ParamPowerFlowReferenceType.load_b_pu,
#         ParamPowerFlowReferenceType.load_ga_pu,
#         ParamPowerFlowReferenceType.load_gb_pu,
#         ParamPowerFlowReferenceType.load_gc_pu,
#         ParamPowerFlowReferenceType.load_ba_pu,
#         ParamPowerFlowReferenceType.load_bb_pu,
#         ParamPowerFlowReferenceType.load_bc_pu,
#         ParamPowerFlowReferenceType.load_ir_pu,
#         ParamPowerFlowReferenceType.load_ii_pu,
#         ParamPowerFlowReferenceType.load_ira_pu,
#         ParamPowerFlowReferenceType.load_irb_pu,
#         ParamPowerFlowReferenceType.load_irc_pu,
#         ParamPowerFlowReferenceType.load_iia_pu,
#         ParamPowerFlowReferenceType.load_iib_pu,
#         ParamPowerFlowReferenceType.load_iic_pu,
#         ParamPowerFlowReferenceType.load_contract_power_pu,
#         ParamPowerFlowReferenceType.Pl0,
#         ParamPowerFlowReferenceType.g,
#         ParamPowerFlowReferenceType.Pl0_A,
#         ParamPowerFlowReferenceType.Pl0_B,
#         ParamPowerFlowReferenceType.Pl0_C,
#         ParamPowerFlowReferenceType.Ql0_A,
#         ParamPowerFlowReferenceType.Ql0_B,
#         ParamPowerFlowReferenceType.Ql0_C,
#         ParamPowerFlowReferenceType.omega_base,
#     ],
#     DeviceType.StaticGeneratorDevice: [
#         ParamPowerFlowReferenceType.device_active,
#         ParamPowerFlowReferenceType.injection_connection_type,
#         ParamPowerFlowReferenceType.Pl0,
#         ParamPowerFlowReferenceType.Ql0,
#         ParamPowerFlowReferenceType.Pl0_A,
#         ParamPowerFlowReferenceType.Pl0_B,
#         ParamPowerFlowReferenceType.Pl0_C,
#         ParamPowerFlowReferenceType.Ql0_A,
#         ParamPowerFlowReferenceType.Ql0_B,
#         ParamPowerFlowReferenceType.Ql0_C,
#         ParamPowerFlowReferenceType.Pl0_A,
#         ParamPowerFlowReferenceType.Pl0_B,
#         ParamPowerFlowReferenceType.Pl0_C,
#         ParamPowerFlowReferenceType.Ql0_A,
#         ParamPowerFlowReferenceType.Ql0_B,
#         ParamPowerFlowReferenceType.Ql0_C,
#         ParamPowerFlowReferenceType.omega_base,
#         ParamPowerFlowReferenceType.static_generator_snom_mva,
#     ],
#     DeviceType.ExternalGridDevice: [
#         ParamPowerFlowReferenceType.device_active,
#         ParamPowerFlowReferenceType.injection_connection_type,
#         ParamPowerFlowReferenceType.Pl0,
#         ParamPowerFlowReferenceType.Pl0_A,
#         ParamPowerFlowReferenceType.Pl0_B,
#         ParamPowerFlowReferenceType.Pl0_C,
#         ParamPowerFlowReferenceType.Ql0_A,
#         ParamPowerFlowReferenceType.Ql0_B,
#         ParamPowerFlowReferenceType.Ql0_C,
#         ParamPowerFlowReferenceType.omega_base,
#         ParamPowerFlowReferenceType.Ql0,
#         ParamPowerFlowReferenceType.external_grid_vm_pu,
#         ParamPowerFlowReferenceType.external_grid_va_rad,
#         ParamPowerFlowReferenceType.external_grid_mode_code,
#     ],
#     DeviceType.ShuntDevice: [
#         ParamPowerFlowReferenceType.device_active,
#         ParamPowerFlowReferenceType.injection_connection_type,
#         ParamPowerFlowReferenceType.shunt_g_pu,
#         ParamPowerFlowReferenceType.shunt_b_pu,
#         ParamPowerFlowReferenceType.shunt_g0_pu,
#         ParamPowerFlowReferenceType.shunt_b0_pu,
#         ParamPowerFlowReferenceType.shunt_ga_pu,
#         ParamPowerFlowReferenceType.shunt_gb_pu,
#         ParamPowerFlowReferenceType.shunt_gc_pu,
#         ParamPowerFlowReferenceType.shunt_ba_pu,
#         ParamPowerFlowReferenceType.shunt_bb_pu,
#         ParamPowerFlowReferenceType.shunt_bc_pu,
#     ],
#     DeviceType.ControllableShuntDevice: [
#         ParamPowerFlowReferenceType.device_active,
#         ParamPowerFlowReferenceType.injection_connection_type,
#         ParamPowerFlowReferenceType.shunt_g_pu,
#         ParamPowerFlowReferenceType.shunt_b_pu,
#         ParamPowerFlowReferenceType.shunt_g0_pu,
#         ParamPowerFlowReferenceType.shunt_b0_pu,
#         ParamPowerFlowReferenceType.shunt_ga_pu,
#         ParamPowerFlowReferenceType.shunt_gb_pu,
#         ParamPowerFlowReferenceType.shunt_gc_pu,
#         ParamPowerFlowReferenceType.shunt_ba_pu,
#         ParamPowerFlowReferenceType.shunt_bb_pu,
#         ParamPowerFlowReferenceType.shunt_bc_pu,
#         ParamPowerFlowReferenceType.controllable_shunt_step,
#         ParamPowerFlowReferenceType.controllable_shunt_vset_pu,
#         ParamPowerFlowReferenceType.controllable_shunt_vmin_pu,
#         ParamPowerFlowReferenceType.controllable_shunt_vmax_pu,
#         ParamPowerFlowReferenceType.controllable_shunt_gmin_pu,
#         ParamPowerFlowReferenceType.controllable_shunt_gmax_pu,
#         ParamPowerFlowReferenceType.controllable_shunt_bmin_pu,
#         ParamPowerFlowReferenceType.controllable_shunt_bmax_pu,
#         ParamPowerFlowReferenceType.controllable_shunt_control_mode_code,
#     ],
#     DeviceType.CurrentInjectionDevice: [
#         ParamPowerFlowReferenceType.device_active,
#         ParamPowerFlowReferenceType.injection_connection_type,
#         ParamPowerFlowReferenceType.current_injection_ir_pu,
#         ParamPowerFlowReferenceType.current_injection_ii_pu,
#         ParamPowerFlowReferenceType.current_injection_ira_pu,
#         ParamPowerFlowReferenceType.current_injection_irb_pu,
#         ParamPowerFlowReferenceType.current_injection_irc_pu,
#         ParamPowerFlowReferenceType.current_injection_iia_pu,
#         ParamPowerFlowReferenceType.current_injection_iib_pu,
#         ParamPowerFlowReferenceType.current_injection_iic_pu,
#     ],
#     DeviceType.GeneratorDevice: [
#         ParamPowerFlowReferenceType.device_active,
#         ParamPowerFlowReferenceType.injection_connection_type,
#         ParamPowerFlowReferenceType.omega_base,
#         ParamPowerFlowReferenceType.ws,
#         ParamPowerFlowReferenceType.R1,
#         ParamPowerFlowReferenceType.X1,
#         ParamPowerFlowReferenceType.X0,
#         ParamPowerFlowReferenceType.generator_p_pu,
#         ParamPowerFlowReferenceType.generator_q_pu,
#         ParamPowerFlowReferenceType.Pmin,
#         ParamPowerFlowReferenceType.Pmax,
#         ParamPowerFlowReferenceType.generator_qmin_pu,
#         ParamPowerFlowReferenceType.generator_qmax_pu,
#         ParamPowerFlowReferenceType.generator_power_factor,
#         ParamPowerFlowReferenceType.generator_vset_pu,
#         ParamPowerFlowReferenceType.generator_snom_mva,
#         ParamPowerFlowReferenceType.generator_r0_pu,
#         ParamPowerFlowReferenceType.generator_r2_pu,
#         ParamPowerFlowReferenceType.generator_x2_pu,
#         ParamPowerFlowReferenceType.generator_control_mode,
#         ParamPowerFlowReferenceType.generator_enabled_dispatch,
#         ParamPowerFlowReferenceType.generator_must_run,
#         ParamPowerFlowReferenceType.generator_use_reactive_power_curve,
#         ParamPowerFlowReferenceType.generator_device_sbase_mva,
#         ParamPowerFlowReferenceType.freq,
#     ],
#     DeviceType.BatteryDevice: [
#         ParamPowerFlowReferenceType.device_active,
#         ParamPowerFlowReferenceType.injection_connection_type,
#         ParamPowerFlowReferenceType.omega_base,
#         ParamPowerFlowReferenceType.ws,
#         ParamPowerFlowReferenceType.R1,
#         ParamPowerFlowReferenceType.X1,
#         ParamPowerFlowReferenceType.X0,
#         ParamPowerFlowReferenceType.generator_p_pu,
#         ParamPowerFlowReferenceType.generator_q_pu,
#         ParamPowerFlowReferenceType.Pmin,
#         ParamPowerFlowReferenceType.Pmax,
#         ParamPowerFlowReferenceType.generator_qmin_pu,
#         ParamPowerFlowReferenceType.generator_qmax_pu,
#         ParamPowerFlowReferenceType.generator_power_factor,
#         ParamPowerFlowReferenceType.generator_vset_pu,
#         ParamPowerFlowReferenceType.generator_snom_mva,
#         ParamPowerFlowReferenceType.generator_r0_pu,
#         ParamPowerFlowReferenceType.generator_r2_pu,
#         ParamPowerFlowReferenceType.generator_x2_pu,
#         ParamPowerFlowReferenceType.generator_control_mode,
#         ParamPowerFlowReferenceType.generator_enabled_dispatch,
#         ParamPowerFlowReferenceType.generator_must_run,
#         ParamPowerFlowReferenceType.generator_use_reactive_power_curve,
#         ParamPowerFlowReferenceType.generator_device_sbase_mva,
#         ParamPowerFlowReferenceType.freq,
#         ParamPowerFlowReferenceType.battery_enom_mwh,
#         ParamPowerFlowReferenceType.battery_soc_0_pu,
#         ParamPowerFlowReferenceType.battery_max_soc_pu,
#         ParamPowerFlowReferenceType.battery_min_soc_pu,
#         ParamPowerFlowReferenceType.battery_charge_efficiency_pu,
#         ParamPowerFlowReferenceType.battery_discharge_efficiency_pu,
#         ParamPowerFlowReferenceType.battery_charge_per_cycle_pu,
#         ParamPowerFlowReferenceType.battery_discharge_per_cycle_pu,
#     ],
#     DeviceType.VscDevice: [
#         ParamPowerFlowReferenceType.device_active,
#         ParamPowerFlowReferenceType.branch_rate_mva,
#         ParamPowerFlowReferenceType.branch_temp_base_deg_c,
#         ParamPowerFlowReferenceType.branch_temp_oper_deg_c,
#         ParamPowerFlowReferenceType.branch_alpha_per_deg_c,
#         ParamPowerFlowReferenceType.Sbase,
#         ParamPowerFlowReferenceType.omega_base,
#         ParamPowerFlowReferenceType.converter_control_mode_1,
#         ParamPowerFlowReferenceType.converter_control_mode_2,
#         ParamPowerFlowReferenceType.converter_control_target_1,
#         ParamPowerFlowReferenceType.converter_control_target_2,
#         ParamPowerFlowReferenceType.alpha1,
#         ParamPowerFlowReferenceType.alpha2,
#         ParamPowerFlowReferenceType.alpha3,
#         ParamPowerFlowReferenceType.vsc_kdp_pu,
#         ParamPowerFlowReferenceType.vsc_min_ac_voltage_pu,
#     ],
#     DeviceType.DCLineDevice: [
#         ParamPowerFlowReferenceType.device_active,
#         ParamPowerFlowReferenceType.branch_rate_mva,
#         ParamPowerFlowReferenceType.branch_temp_base_deg_c,
#         ParamPowerFlowReferenceType.branch_temp_oper_deg_c,
#         ParamPowerFlowReferenceType.branch_alpha_per_deg_c,
#         ParamPowerFlowReferenceType.g,
#         ParamPowerFlowReferenceType.b,
#         ParamPowerFlowReferenceType.bsh,
#         ParamPowerFlowReferenceType.dc_line_r_pu,
#         ParamPowerFlowReferenceType.dc_line_length_km,
#     ],
#     DeviceType.Transformer2WDevice: [
#         ParamPowerFlowReferenceType.device_active,
#         ParamPowerFlowReferenceType.branch_rate_mva,
#         ParamPowerFlowReferenceType.branch_temp_base_deg_c,
#         ParamPowerFlowReferenceType.branch_temp_oper_deg_c,
#         ParamPowerFlowReferenceType.branch_alpha_per_deg_c,
#         ParamPowerFlowReferenceType.omega_base,
#         ParamPowerFlowReferenceType.transformer_rated_power_mva,
#         ParamPowerFlowReferenceType.transformer_winding1_rated_voltage_ll_kv,
#         ParamPowerFlowReferenceType.transformer_winding2_rated_voltage_ll_kv,
#         ParamPowerFlowReferenceType.transformer_connection_clock,
#         ParamPowerFlowReferenceType.transformer_open_circuit_current_pct,
#         ParamPowerFlowReferenceType.transformer_open_circuit_loss_kw,
#         ParamPowerFlowReferenceType.transformer_short_circuit_voltage_pct,
#         ParamPowerFlowReferenceType.transformer_short_circuit_resistance_pct,
#         ParamPowerFlowReferenceType.transformer_short_circuit_loss_kw,
#         ParamPowerFlowReferenceType.tap_module,
#         ParamPowerFlowReferenceType.transformer_nominal_voltage_ratio,
#         ParamPowerFlowReferenceType.transformer_total_voltage_ratio,
#         ParamPowerFlowReferenceType.transformer_tap_ratio,
#         ParamPowerFlowReferenceType.transformer_winding1_resistance_pu,
#         ParamPowerFlowReferenceType.transformer_winding2_resistance_pu,
#         ParamPowerFlowReferenceType.transformer_winding1_inductance_pu_s,
#         ParamPowerFlowReferenceType.transformer_winding2_inductance_pu_s,
#         ParamPowerFlowReferenceType.transformer_mutual_inductance_pu_s,
#         ParamPowerFlowReferenceType.transformer_magnetizing_conductance_pu,
#     ],
#     DeviceType.WindingDevice: [
#         ParamPowerFlowReferenceType.device_active,
#         ParamPowerFlowReferenceType.branch_rate_mva,
#         ParamPowerFlowReferenceType.branch_temp_base_deg_c,
#         ParamPowerFlowReferenceType.branch_temp_oper_deg_c,
#         ParamPowerFlowReferenceType.branch_alpha_per_deg_c,
#         ParamPowerFlowReferenceType.omega_base,
#         ParamPowerFlowReferenceType.transformer_rated_power_mva,
#         ParamPowerFlowReferenceType.transformer_winding1_rated_voltage_ll_kv,
#         ParamPowerFlowReferenceType.transformer_winding2_rated_voltage_ll_kv,
#         ParamPowerFlowReferenceType.transformer_connection_clock,
#         ParamPowerFlowReferenceType.transformer_open_circuit_current_pct,
#         ParamPowerFlowReferenceType.transformer_open_circuit_loss_kw,
#         ParamPowerFlowReferenceType.transformer_short_circuit_voltage_pct,
#         ParamPowerFlowReferenceType.transformer_short_circuit_resistance_pct,
#         ParamPowerFlowReferenceType.transformer_short_circuit_loss_kw,
#         ParamPowerFlowReferenceType.tap_module,
#         ParamPowerFlowReferenceType.transformer_nominal_voltage_ratio,
#         ParamPowerFlowReferenceType.transformer_total_voltage_ratio,
#         ParamPowerFlowReferenceType.transformer_tap_ratio,
#         ParamPowerFlowReferenceType.transformer_winding1_resistance_pu,
#         ParamPowerFlowReferenceType.transformer_winding2_resistance_pu,
#         ParamPowerFlowReferenceType.transformer_winding1_inductance_pu_s,
#         ParamPowerFlowReferenceType.transformer_winding2_inductance_pu_s,
#         ParamPowerFlowReferenceType.transformer_mutual_inductance_pu_s,
#         ParamPowerFlowReferenceType.transformer_magnetizing_conductance_pu,
#     ],
#     DeviceType.LineDevice: [
#         ParamPowerFlowReferenceType.device_active,
#         ParamPowerFlowReferenceType.branch_rate_mva,
#         ParamPowerFlowReferenceType.branch_temp_base_deg_c,
#         ParamPowerFlowReferenceType.branch_temp_oper_deg_c,
#         ParamPowerFlowReferenceType.branch_alpha_per_deg_c,
#         ParamPowerFlowReferenceType.line_length_km,
#     ],
#     DeviceType.HVDCLineDevice: [],
#     DeviceType.SeriesReactanceDevice: [],
#     DeviceType.SwitchDevice: [],
#     DeviceType.UpfcDevice: [],
# }


def add_static_mapping_warning(
        logger: StaticParameterMappingDiagnosticSink | None,
        device_name: str,
        message: str,
        value: str,
        expected_value: str,
        device_property: str,
) -> None:
    """
    Add one diagnostic warning for a static mapping issue.

    :param logger: Optional driver logger or simulation-aware diagnostic context.
    :param device_name: Device name used in diagnostics.
    :param message: Warning message.
    :param value: Actual problematic value.
    :param expected_value: Expected value or condition.
    :param device_property: Device property involved in the warning.
    :return: None.
    """
    if logger is None:
        # The mapper can be used in small unit tests without a driver logger.
        # In that case, invalid optional mappings are skipped silently.
        pass
    elif isinstance(logger, StaticParameterMappingDiagnostics):
        logger.add_warning(
            message=message,
            device_name=device_name,
            value=value,
            expected_value=expected_value,
            device_property=device_property,
        )
    else:
        logger.add_warning(
            msg=message,
            device=device_name,
            value=value,
            expected_value=expected_value,
            device_class="Dynamic parameter mapping",
            device_property=device_property,
        )


def add_static_mapping_info(
        logger: StaticParameterMappingDiagnosticSink | None,
        device_name: str,
        message: str,
        value: str,
        expected_value: str,
        device_property: str,
) -> None:
    """Add one information entry describing static-mapping precedence.

    :param logger: Optional driver logger or simulation-aware diagnostic context.
    :param device_name: Device name used in diagnostics.
    :param message: Information message.
    :param value: Resolved mapping and overridden declaration.
    :param expected_value: Documented source-precedence contract.
    :param device_property: Device property involved in the information entry.
    :return: None.
    """
    if logger is None:
        # Low-level mapping remains usable without manufacturing a logger.
        pass
    elif isinstance(logger, StaticParameterMappingDiagnostics):
        logger.add_info(
            message=message,
            device_name=device_name,
            value=value,
            expected_value=expected_value,
            device_property=device_property,
        )
    else:
        logger.add_info(
            msg=message,
            device=device_name,
            value=value,
            expected_value=expected_value,
            device_class="Dynamic parameter mapping",
            device_property=device_property,
        )


def assign_api_mapping_value_if_present(
        mdl: Block,
        key: ParamPowerFlowReferenceType,
        value: float,
        logger: StaticParameterMappingDiagnosticSink | None,
        device_name: str,
        problem_mapping: Dict[Var, Const] | None = None,
) -> bool:
    """
    Assign one API-object initial value to the problem-side mapping if exposed.

    This function is the only low-level writer used by this module. It never
    writes into ``mdl.event_dict``, ``mdl.mode_dict`` or ``mdl.parameters``.
    Those collections define whether the target is continuous runtime,
    discrete runtime, or immutable; the problem-side mapping supplies only its
    initial value. When the target also has a
    concrete declaration, the final resolved API-object value is authoritative.
    Repeated assignments from the same API reference may refine a generic
    value with a device-specific value. Different references targeting one
    symbolic UID are accepted only when they resolve to the same value.

    :param mdl: Symbolic block receiving the parameter initial value.
    :param key: API-object reference key.
    :param value: Numerical initial value to assign.
    :param logger: Optional logger used to report invalid mapping contracts.
    :param device_name: Device name used in diagnostics.
    :param problem_mapping: Problem-side mapping shared by RMS and EMT assembly.
    :return: ``True`` if the value was assigned, ``False`` otherwise.
    """
    assigned: bool = False
    #TODO: is it necessary copy or not?
    api_obj_mapping: Dict[ParamPowerFlowReferenceType, Var] = mdl.api_obj_mapping

    # The mapping is optional: a model receives only the parameter values it
    # explicitly requests by exposing the enum key.
    target: Var | None = api_obj_mapping.get(key, None)

    if target is None:
        assigned = False
    else:
        target_is_constant: bool = target in mdl.parameters
        target_is_continuous_runtime: bool = target in mdl.event_dict
        target_is_discrete_runtime: bool = target in mdl.mode_dict
        declaration_count: int = (
            int(target_is_constant)
            + int(target_is_continuous_runtime)
            + int(target_is_discrete_runtime)
        )

        if declaration_count > 1:
            add_static_mapping_warning(
                logger=logger,
                device_name=device_name,
                message="Scripted model-template mapping conflict: API mapping target has multiple parameter roles; value skipped.",
                value=f"{mdl.name}: {key} -> {target.name}",
                expected_value=(
                    "Declare the mapped variable in exactly one of Block.parameters, "
                    + "Block.event_dict or Block.mode_dict."
                ),
                device_property="model template api_obj_mapping",
            )
            assigned = False
        elif declaration_count == 0:
            # API mappings are owner-local. A wrapper must not borrow a target
            # declared by a descendant because recursive discovery visits the
            # actual owner in both RMS and EMT.
            add_static_mapping_warning(
                logger=logger,
                device_name=device_name,
                message="Scripted model-template mapping conflict: API mapping target is not declared by the same block; value skipped.",
                value=f"{mdl.name}: {key} -> {target.name}",
                expected_value=(
                    "Declare the mapped variable in the same block's parameters, "
                    + "event_dict or mode_dict collection."
                ),
                device_property="model template api_obj_mapping",
            )
            assigned = False
        else:
            # Keep the value in the flat problem-side mapping. The destination
            # problem decides from the owner's declaration whether to register a
            # constant parameter or an event-capable runtime parameter.
            resolved_value: Const = value if isinstance(value, Const) else Const(float(value))
            if problem_mapping is not None:
                # Keep the established mapping current for helpers that inspect
                # it during assembly. The tracked form also retains one final
                # candidate per semantic source for deferred conflict checks.
                problem_mapping[target] = resolved_value
                if isinstance(problem_mapping, StaticParameterMappingValues):
                    problem_mapping.record_candidate(
                        parameter=target,
                        source_key=key,
                        value=resolved_value,
                        block_name=str(mdl.name),
                    )
                else:
                    pass
                assigned = True
            else:
                # Calls without problem storage still validate that the target
                # is owner-local, but have no destination to compare or write.
                assigned = True

    return assigned


def get_api_parameter_initial_value_by_uid(
        parameter: Var,
        problem_mapping: Dict[Var, Const],
) -> Const | None:
    """Return one resolved API-object initial value by symbolic UID.

    Saved dynamic models may contain cloned ``Var`` instances which preserve
    their canonical UID. Both RMS and EMT must therefore resolve the same
    problem-side mapping by UID instead of relying only on Python identity.

    :param parameter: Symbolic parameter whose initial value is requested.
    :param problem_mapping: Values resolved from owner-local API mappings.
    :return: Resolved constant, or ``None`` when the parameter has no mapping.
    """
    direct_value: Const | None = problem_mapping.get(parameter, None)

    if direct_value is not None:
        resolved_value: Const | None = direct_value
    else:
        resolved_value = None
        mapped_parameter: Var
        mapped_value: Const
        for mapped_parameter, mapped_value in problem_mapping.items():
            if resolved_value is None and mapped_parameter.uid == parameter.uid:
                resolved_value = mapped_value
            else:
                pass

    return resolved_value


def get_api_mapping_keys_for_parameter(
        root_block: Block,
        parameter: Var,
) -> List[ParamPowerFlowReferenceType]:
    """Return every API-object reference that targets one symbolic parameter.

    Dynamic models may expose the authoritative mapping on their wrapper root
    or on a nested owner block. Searching the complete hierarchy gives RMS and
    EMT the same ownership-aware context when an initial value cannot be
    resolved.

    :param root_block: Complete dynamic model assigned to the static device.
    :param parameter: Symbolic parameter whose mapping references are requested.
    :return: Mapping keys whose target has the same canonical UID.
    """
    mapping_keys: List[ParamPowerFlowReferenceType] = list()
    candidate_block: Block
    mapping_key: ParamPowerFlowReferenceType
    mapping_target: Var | None

    # UID equality is the persistence contract: saved models may reconstruct
    # equivalent Var instances which do not share Python object identity.
    for candidate_block in root_block.get_all_blocks():
        for mapping_key, mapping_target in candidate_block.api_obj_mapping.items():
            if mapping_target is None:
                pass
            else:
                if mapping_target.uid == parameter.uid:
                    mapping_keys.append(mapping_key)
                else:
                    pass

    return mapping_keys


def resolve_parameter_initial_expression(
        parameter: Var,
        declared_expression: Expr | Const,
        problem_mapping: Dict[Var, Const],
) -> Expr | Const:
    """Select the authoritative initial expression for one parameter.

    A resolved static-device mapping is authoritative over the model fallback.
    The caller still decides whether the parameter is immutable, continuous
    runtime, or discrete from the collection which declares it.

    :param parameter: Symbolic parameter being initialized.
    :param declared_expression: Fallback stored by the declaring block.
    :param problem_mapping: Problem-local values resolved from API mappings.
    :return: Mapped constant when available, otherwise the declared fallback.
    """
    mapped_expression: Const | None = get_api_parameter_initial_value_by_uid(
        parameter=parameter,
        problem_mapping=problem_mapping,
    )

    if mapped_expression is None:
        resolved_expression: Expr | Const = declared_expression
    else:
        resolved_expression = mapped_expression

    return resolved_expression


def resolve_constant_parameter_initial_value(
        device: ALL_DEV_TYPES,
        simulation_mode: DynamicSimulationMode,
        root_block: Block,
        owner_block: Block,
        parameter: Var,
        declared_value: Const,
        problem_mapping: Dict[Var, Const],
) -> Const:
    """Resolve and validate one immutable dynamic-model parameter.

    The same source precedence and contextual error are used for RMS and EMT.
    A null immutable fallback is valid only when the problem-local API mapping
    has supplied a concrete value.

    :param device: Static device which owns the dynamic model.
    :param simulation_mode: RMS or EMT domain requesting the value.
    :param root_block: Complete dynamic model assigned to ``device``.
    :param owner_block: Block which declares the immutable parameter.
    :param parameter: Symbolic immutable parameter.
    :param declared_value: Fallback stored in ``owner_block.parameters``.
    :param problem_mapping: Problem-local values resolved from API mappings.
    :return: Concrete constant which can be registered numerically.
    :raises ValueError: If neither the mapping nor the declaration is concrete.
    :raises TypeError: If the immutable declaration resolves to an expression.
    """
    resolved_expression: Expr | Const = resolve_parameter_initial_expression(
        parameter=parameter,
        declared_expression=declared_value,
        problem_mapping=problem_mapping,
    )

    if isinstance(resolved_expression, Const):
        resolved_value: Const = resolved_expression
    else:
        # Block.parameters is a constant-only contract. Keeping this validation
        # here prevents the two simulation domains from accepting different
        # representations of the same immutable declaration.
        raise TypeError(
            f"{simulation_mode.value} immutable parameter '{parameter.name}' "
            + f"(uid={parameter.uid}) in block '{owner_block.name}' of "
            + f"{device.device_type.value} '{device.name}' must resolve to Const."
        )

    if resolved_value.value is None:
        mapping_keys: List[ParamPowerFlowReferenceType] = get_api_mapping_keys_for_parameter(
            root_block=root_block,
            parameter=parameter,
        )
        mapping_names: List[str] = list()
        mapping_key: ParamPowerFlowReferenceType
        for mapping_key in mapping_keys:
            mapping_names.append(mapping_key.name)

        if len(mapping_names) == 0:
            mapping_diagnostic: str = "the parameter is not targeted by any api_obj_mapping entry"
        else:
            mapping_diagnostic = (
                "api_obj_mapping targets it through ["
                + ", ".join(mapping_names)
                + "], but the problem-local mapper produced no value"
            )

        raise ValueError(
            f"Unresolved {simulation_mode.value} constant parameter "
            + f"'{parameter.name}' (uid={parameter.uid}) in block '{owner_block.name}' of "
            + f"{device.device_type.value} '{device.name}': {mapping_diagnostic}. "
            + "A parameter declared in Block.parameters as Const(None) must be linked "
            + "to a supported static-device property through api_obj_mapping."
        )
    else:
        pass

    return resolved_value


def resolve_runtime_parameter_initial_expression(
        device: ALL_DEV_TYPES,
        simulation_mode: DynamicSimulationMode,
        root_block: Block,
        owner_block: Block,
        parameter: Var,
        declared_expression: Expr | Const,
        problem_mapping: Dict[Var, Const],
        allow_deferred_initialization: bool,
) -> Expr | Const:
    """Resolve and validate one event-capable parameter initial expression.

    The mapping chooses the initial source only; membership in ``event_dict``
    or ``mode_dict`` remains authoritative for mutability. A null result may be
    retained only when the caller has an explicit later initialization owner,
    such as power-flow seeding, mode logic, or the numerical initializer.

    :param device: Static device which owns the dynamic model.
    :param simulation_mode: RMS or EMT domain requesting the expression.
    :param root_block: Complete dynamic model assigned to ``device``.
    :param owner_block: Block which declares the runtime parameter.
    :param parameter: Symbolic runtime parameter.
    :param declared_expression: Fallback stored by the declaring block.
    :param problem_mapping: Problem-local values resolved from API mappings.
    :param allow_deferred_initialization: Whether a later explicit owner is
        guaranteed to replace a null placeholder.
    :return: Effective runtime initialization expression.
    :raises ValueError: If an ordinary runtime parameter has no usable source.
    """
    effective_expression: Expr | Const = resolve_parameter_initial_expression(
        parameter=parameter,
        declared_expression=declared_expression,
        problem_mapping=problem_mapping,
    )

    if isinstance(effective_expression, Const) and effective_expression.value is None:
        if allow_deferred_initialization:
            # The caller has identified a real later owner. The placeholder is
            # retained without changing the parameter's runtime declaration.
            pass
        else:
            mapping_keys: List[ParamPowerFlowReferenceType] = get_api_mapping_keys_for_parameter(
                root_block=root_block,
                parameter=parameter,
            )
            mapping_names: List[str] = list()
            mapping_key: ParamPowerFlowReferenceType
            for mapping_key in mapping_keys:
                mapping_names.append(mapping_key.name)

            if len(mapping_names) == 0:
                mapping_diagnostic: str = "no api_obj_mapping entry targets the parameter"
            else:
                mapping_diagnostic = (
                    "api_obj_mapping references ["
                    + ", ".join(mapping_names)
                    + "], but no concrete initial value was resolved"
                )

            raise ValueError(
                f"Unresolved {simulation_mode.value} dynamic parameter "
                + f"'{parameter.name}' (uid={parameter.uid}) in block '{owner_block.name}' of "
                + f"{device.device_type.value} '{device.name}': {mapping_diagnostic}. "
                + "Provide a numerical or symbolic value in the declaring Block.event_dict or Block.mode_dict, "
                + "a supported api_obj_mapping source, or an explicit problem-owned seed."
            )
    else:
        pass

    return effective_expression


def build_api_parameter_initial_values_by_uid(
        problem_mapping: Dict[Var, Const],
) -> Dict[int, Const]:
    """Index resolved API-object initial values by symbolic UID.

    EMT constructs flat parameter vectors from a complete block hierarchy. A
    UID-indexed snapshot gives constant and event-capable parameters the same
    lookup semantics used by RMS while avoiding repeated hierarchy scans.

    :param problem_mapping: Values resolved from owner-local API mappings.
    :return: Initial values indexed by canonical symbolic UID.
    """
    values_by_uid: Dict[int, Const] = dict()
    mapped_parameter: Var
    mapped_value: Const

    for mapped_parameter, mapped_value in problem_mapping.items():
        existing_value: Const | None = values_by_uid.get(mapped_parameter.uid, None)
        if existing_value is None:
            values_by_uid[mapped_parameter.uid] = mapped_value
        elif existing_value.value == mapped_value.value:
            pass
        else:
            raise ValueError(
                "Conflicting API-object initial values resolve to symbolic uid="
                + f"{mapped_parameter.uid}: {existing_value.value} and {mapped_value.value}."
            )

    return values_by_uid


def report_api_mapping_overrides_for_block(
        mdl: Block,
        problem_mapping: Dict[Var, Const],
        logger: StaticParameterMappingDiagnosticSink | None,
        device_name: str,
        reported_uids: Set[int],
) -> None:
    """Report concrete declarations replaced by final mapped values.

    Reporting happens only after all generic and device-specific assignments
    for the block have completed. The diagnostic therefore shows the value
    that will actually be consumed by RMS or EMT assembly.

    :param mdl: Owner block whose mapped declarations are inspected.
    :param problem_mapping: Final problem-side values for the current device.
    :param logger: Optional driver logger or simulation-aware context.
    :param device_name: Static device name used in diagnostics.
    :param reported_uids: Symbolic identities already reported for the device.
    :return: None.
    """
    key: ParamPowerFlowReferenceType
    target: Var | None

    for key, target in mdl.api_obj_mapping.items():
        if target is None:
            pass
        elif target.uid in reported_uids:
            pass
        else:
            reported_uids.add(target.uid)
            target_is_constant: bool = target in mdl.parameters
            target_is_continuous_runtime: bool = target in mdl.event_dict
            target_is_discrete_runtime: bool = target in mdl.mode_dict
            declaration_count: int = (
                int(target_is_constant)
                + int(target_is_continuous_runtime)
                + int(target_is_discrete_runtime)
            )

            if declaration_count != 1:
                # Invalid or mapping-only targets are diagnosed by the writer;
                # there is no authoritative local fallback to compare here.
                pass
            else:
                mapped_value: Const | None = get_api_parameter_initial_value_by_uid(
                    parameter=target,
                    problem_mapping=problem_mapping,
                )
                declared_value: Expr | Const
                if target_is_constant:
                    declared_value = mdl.parameters[target]
                elif target_is_continuous_runtime:
                    declared_value = mdl.event_dict[target]
                else:
                    declared_value = mdl.mode_dict[target]

                declaration_is_overridden: bool = False
                if mapped_value is None:
                    pass
                elif isinstance(declared_value, Const):
                    if declared_value.value is None:
                        pass
                    elif declared_value.value == mapped_value.value:
                        pass
                    else:
                        declaration_is_overridden = True
                else:
                    declaration_is_overridden = True

                if declaration_is_overridden and mapped_value is not None:
                    add_static_mapping_info(
                        logger=logger,
                        device_name=device_name,
                        message="API-object initial value overrides the model-template fallback.",
                        value=(
                            f"{mdl.name}: {key} -> {target.name}; "
                            + f"API={mapped_value.value}; template={declared_value}"
                        ),
                        expected_value=(
                            "api_obj_mapping is authoritative during initialization; "
                            + "remove the mapping to use the model-template declaration."
                        ),
                        device_property="model template api_obj_mapping",
                    )
                else:
                    pass


def api_mapping_has_any_key(
        mdl: Block,
        keys: List[ParamPowerFlowReferenceType],
) -> bool:
    """
    Return whether the block exposes at least one of the provided static keys.

    :param mdl: EMT symbolic block.
    :param keys: API-object enum keys to test.
    :return: ``True`` if any key is present in ``mdl.api_obj_mapping``.
    """
    has_key: bool = False
    api_obj_mapping: Dict[ParamPowerFlowReferenceType, Var] = mdl.api_obj_mapping

    if isinstance(api_obj_mapping, dict):
        key_index: int = 0

        while key_index < len(keys):
            key: ParamPowerFlowReferenceType = keys[key_index]

            if key in api_obj_mapping:
                # Do not break the loop: keeping the loop explicit avoids control
                # flow surprises and follows the local style constraints.
                has_key = True
            else:
                pass

            key_index += 1
    else:
        has_key = False

    return has_key


def _float_or_zero(value: float | None) -> float:
    """
    Return one scalar value, replacing ``None`` with zero.

    :param value: Optional scalar value.
    :return: Float scalar with ``None`` mapped to ``0.0``.
    """
    out: float

    if value is None:
        out = 0.0
    else:
        out = float(value)

    return out


def _abc_values_are_meaningful(
        phase_a: float | None,
        phase_b: float | None,
        phase_c: float | None,
) -> bool:
    """
    Return whether explicit ABC values should override balanced fallback.

    The static-device classes do not expose a dedicated "phase values are
    provided" flag. The practical contract used here is therefore explicit and
    conservative: if any phase value is numerically non-zero, the phase triplet is
    treated as meaningful and is preserved.

    :param phase_a: Phase-A scalar.
    :param phase_b: Phase-B scalar.
    :param phase_c: Phase-C scalar.
    :return: ``True`` when explicit phase values should be used.
    """
    value_a: float = _float_or_zero(phase_a)
    value_b: float = _float_or_zero(phase_b)
    value_c: float = _float_or_zero(phase_c)
    meaningful: bool

    if abs(value_a) > 0.0:
        meaningful = True
    else:
        if abs(value_b) > 0.0:
            meaningful = True
        else:
            if abs(value_c) > 0.0:
                meaningful = True
            else:
                meaningful = False

    return meaningful


def balanced_to_abc_power(total_value: float | None) -> np.ndarray:
    """
    Split one balanced total scalar equally into explicit ABC values.

    :param total_value: Balanced total scalar.
    :return: ABC array with one third of the total in each phase.
    """
    total_scalar: float = _float_or_zero(total_value)
    phase_scalar: float = total_scalar / 3.0
    phase_values: np.ndarray = np.zeros(3, dtype=np.float64)

    phase_values[0] = phase_scalar
    phase_values[1] = phase_scalar
    phase_values[2] = phase_scalar

    return phase_values


def _resolve_explicit_or_balanced_abc_values(
        phase_a: float | None,
        phase_b: float | None,
        phase_c: float | None,
        total_value: float | None,
) -> np.ndarray:
    """
    Resolve one ABC quantity from explicit phase values or from a balanced total.

    :param phase_a: Phase-A scalar.
    :param phase_b: Phase-B scalar.
    :param phase_c: Phase-C scalar.
    :param total_value: Balanced total scalar used as fallback.
    :return: Explicit ABC array.
    """
    phase_values: np.ndarray = np.zeros(3, dtype=np.float64)

    if _abc_values_are_meaningful(phase_a=phase_a, phase_b=phase_b, phase_c=phase_c):
        phase_values[0] = _float_or_zero(phase_a)
        phase_values[1] = _float_or_zero(phase_b)
        phase_values[2] = _float_or_zero(phase_c)
    else:
        phase_values = balanced_to_abc_power(total_value=total_value)

    return phase_values


def abc_to_nabc(phase_values_abc: np.ndarray) -> np.ndarray:
    """
    Expand an ABC phase array into fixed NABC order.

    :param phase_values_abc: Explicit ABC array.
    :return: NABC array with a zero neutral entry.
    """
    phase_values_nabc: np.ndarray = np.zeros(4, dtype=np.float64)

    phase_values_nabc[0] = 0.0
    phase_values_nabc[1] = float(phase_values_abc[0])
    phase_values_nabc[2] = float(phase_values_abc[1])
    phase_values_nabc[3] = float(phase_values_abc[2])

    return phase_values_nabc


def get_load_power_phase_values_pu_abc(load: Union[dev.Load|dev.StaticGenerator],
                                       grid: MultiCircuit) -> Tuple[np.ndarray, np.ndarray]:
    """
    Return explicit ABC active/reactive load powers in p.u. on ``grid.Sbase``.

    Explicit phase values are used when they are meaningfully populated.
    Otherwise, the balanced total values are split equally among phases.

    :param load: Load-like static device.
    :param grid: Static network model.
    :return: Pair ``(p_abc_pu, q_abc_pu)``.
    """
    p_mw_abc: np.ndarray = _resolve_explicit_or_balanced_abc_values(
        phase_a=load.Pa,
        phase_b=load.Pb,
        phase_c=load.Pc,
        total_value=load.P,
    )
    q_mvar_abc: np.ndarray = _resolve_explicit_or_balanced_abc_values(
        phase_a=load.Qa,
        phase_b=load.Qb,
        phase_c=load.Qc,
        total_value=load.Q,
    )
    p_pu_abc: np.ndarray = p_mw_abc / float(grid.Sbase)
    q_pu_abc: np.ndarray = q_mvar_abc / float(grid.Sbase)

    return p_pu_abc, q_pu_abc


def get_load_impedance_phase_values_pu_abc(load: dev.Load, grid: MultiCircuit) -> Tuple[np.ndarray, np.ndarray]:
    """
    Return explicit ABC ZIP-impedance powers in p.u. on ``grid.Sbase``.

    :param load: Load-like static device exposing ``G``/``B`` totals and
        ``G1``/``G2``/``G3`` plus ``B1``/``B2``/``B3`` phase values.
    :param grid: Static network model.
    :return: Pair ``(g_abc_pu, b_abc_pu)``.
    """
    g_mw_abc: np.ndarray = _resolve_explicit_or_balanced_abc_values(
        phase_a=load.G1,
        phase_b=load.G2,
        phase_c=load.G3,
        total_value=load.G,
    )
    b_mvar_abc: np.ndarray = _resolve_explicit_or_balanced_abc_values(
        phase_a=load.B1,
        phase_b=load.B2,
        phase_c=load.B3,
        total_value=load.B,
    )
    g_pu_abc: np.ndarray = g_mw_abc / float(grid.Sbase)
    b_pu_abc: np.ndarray = b_mvar_abc / float(grid.Sbase)

    return g_pu_abc, b_pu_abc


def get_load_current_phase_values_pu_abc(load: dev.Load, grid: MultiCircuit) -> Tuple[np.ndarray, np.ndarray]:
    """
    Return explicit ABC ZIP-current powers in p.u. on ``grid.Sbase``.

    :param load: Load-like static device exposing ``Ir``/``Ii`` totals and
        ``Ir1``/``Ir2``/``Ir3`` plus ``Ii1``/``Ii2``/``Ii3`` phase values.
    :param grid: Static network model.
    :return: Pair ``(ir_abc_pu, ii_abc_pu)``.
    """
    ir_mw_abc: np.ndarray = _resolve_explicit_or_balanced_abc_values(
        phase_a=load.Ir1,
        phase_b=load.Ir2,
        phase_c=load.Ir3,
        total_value=load.Ir,
    )
    ii_mvar_abc: np.ndarray = _resolve_explicit_or_balanced_abc_values(
        phase_a=load.Ii1,
        phase_b=load.Ii2,
        phase_c=load.Ii3,
        total_value=load.Ii,
    )
    ir_pu_abc: np.ndarray = ir_mw_abc / float(grid.Sbase)
    ii_pu_abc: np.ndarray = ii_mvar_abc / float(grid.Sbase)

    return ir_pu_abc, ii_pu_abc


def get_shunt_phase_values_pu_abc(shunt: dev.Shunt, grid: MultiCircuit) -> Tuple[np.ndarray, np.ndarray]:
    """
    Return explicit ABC shunt conductance/susceptance powers in p.u.

    Explicit phase values are used when meaningfully populated. Otherwise the
    balanced totals are split equally among phases.

    :param shunt: Shunt-like static device.
    :param grid: Static network model.
    :return: Pair ``(g_abc_pu, b_abc_pu)``.
    """
    g_mw_abc: np.ndarray = _resolve_explicit_or_balanced_abc_values(
        phase_a=shunt.Ga,
        phase_b=shunt.Gb,
        phase_c=shunt.Gc,
        total_value=shunt.G,
    )
    b_mvar_abc: np.ndarray = _resolve_explicit_or_balanced_abc_values(
        phase_a=shunt.Ba,
        phase_b=shunt.Bb,
        phase_c=shunt.Bc,
        total_value=shunt.B,
    )
    g_pu_abc: np.ndarray = g_mw_abc / float(grid.Sbase)
    b_pu_abc: np.ndarray = b_mvar_abc / float(grid.Sbase)

    return g_pu_abc, b_pu_abc


def get_current_injection_phase_values_pu_abc(
        current_injection: dev.CurrentInjection,
        grid: MultiCircuit,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Return explicit ABC current-injection powers in p.u. on ``grid.Sbase``.

    :param current_injection: Current-injection static device.
    :param grid: Static network model.
    :return: Pair ``(ir_abc_pu, ii_abc_pu)``.
    """
    ir_mw_abc: np.ndarray = _resolve_explicit_or_balanced_abc_values(
        phase_a=current_injection.Ir1,
        phase_b=current_injection.Ir2,
        phase_c=current_injection.Ir3,
        total_value=current_injection.Ir,
    )
    ii_mvar_abc: np.ndarray = _resolve_explicit_or_balanced_abc_values(
        phase_a=current_injection.Ii1,
        phase_b=current_injection.Ii2,
        phase_c=current_injection.Ii3,
        total_value=current_injection.Ii,
    )
    ir_pu_abc: np.ndarray = ir_mw_abc / float(grid.Sbase)
    ii_pu_abc: np.ndarray = ii_mvar_abc / float(grid.Sbase)

    return ir_pu_abc, ii_pu_abc


def shunt_connection_code(connection_type: ShuntConnectionType) -> float:
    """
    Convert a static shunt connection enum into a stable EMT code.

    :param connection_type: Static connection enum.
    :return: Numerical code used by static EMT parameters.
    """
    code: float

    if connection_type == ShuntConnectionType.GroundedStar:
        code = 1.0
    elif connection_type == ShuntConnectionType.FloatingStar:
        code = 2.0
    elif connection_type == ShuntConnectionType.NeutralStar:
        code = 3.0
    elif connection_type == ShuntConnectionType.Delta:
        code = 4.0
    else:
        code = 0.0

    return code


def external_grid_mode_code(mode: ExternalGridMode) -> float:
    """
    Convert a static external-grid mode enum into a stable EMT code.

    :param mode: External-grid mode.
    :return: Numerical code used by static EMT parameters.
    """
    code: float

    if mode == ExternalGridMode.PQ:
        code = 1.0
    elif mode == ExternalGridMode.PV:
        code = 2.0
    elif mode == ExternalGridMode.VD:
        code = 3.0
    else:
        code = 0.0

    return code


def controllable_shunt_mode_code(mode: ShuntControlMode) -> float:
    """
    Convert a controllable-shunt control mode into a stable EMT code.

    :param mode: Static shunt control mode.
    :return: Numerical code used by static EMT parameters.
    """
    code: float

    if mode == ShuntControlMode.Locked:
        code = 1.0
    elif mode == ShuntControlMode.Continuous:
        code = 2.0
    elif mode == ShuntControlMode.Discrete:
        code = 3.0
    else:
        code = 0.0

    return code


def build_device_dyn_ref_property_lookup(device: ALL_DEV_TYPES) -> Dict[ParamPowerFlowReferenceType, "GCProp"]:
    """
    Build the schema lookup of direct static-to-dynamic references.

    The automatic assignment path must read the inherited editable schema of the
    concrete device because many direct mappings are declared in shared parent
    classes. The returned lookup is keyed by ``ParamPowerFlowReferenceType`` so
    the dynamic template contract can be matched directly against the static
    schema declaration that owns the corresponding property value.

    :param device: Static device instance.
    :return: Mapping from dynamic reference enum to the declaring property.
    """
    dyn_ref_to_prop: Dict[ParamPowerFlowReferenceType, GCProp] = dict()
    prop: GCProp

    for prop in device.registered_properties.values():
        if prop.dyn_ref is not None:
            dyn_ref_to_prop[prop.dyn_ref] = prop
        else:
            pass

    return dyn_ref_to_prop


def build_device_direct_dyn_ref_keys(device: ALL_DEV_TYPES) -> List[ParamPowerFlowReferenceType]:
    """
    Build the ordered list of direct dynamic references for one device schema.

    The automatic direct-assignment path prefers the canonical list published by
    ``MultiCircuit.get_devices_static_params_mapping()``. Small unit tests may
    pass lightweight grid stand-ins without that method, so this helper rebuilds
    the same per-device information locally from the concrete inherited schema.

    :param device: Static device instance.
    :return: Ordered direct dynamic-reference list declared in the schema.
    """
    direct_keys: List[ParamPowerFlowReferenceType] = list()
    prop_lookup: Dict[ParamPowerFlowReferenceType, "GCProp"] = build_device_dyn_ref_property_lookup(device=device)
    key: ParamPowerFlowReferenceType

    for key in prop_lookup.keys():
        direct_keys.append(key)

    return direct_keys


def _get_direct_phase_property_value(device: ALL_DEV_TYPES, property_name: str) -> float:
    """
    Return one explicit phase-property value without reflection.

    The unified mapper keeps the automatic direct-mapping stage, but the
    repository rules forbid reflective access such as ``getattr``. This helper
    therefore resolves every supported phase property through explicit branches
    so the mapping remains refactorable and statically inspectable.

    :param device: Static device instance.
    :param property_name: Static property name.
    :return: Numerical property value.
    """
    value: float

    if property_name == "Pa":
        value = float(device.Pa)
    else:
        if property_name == "Pb":
            value = float(device.Pb)
        else:
            if property_name == "Pc":
                value = float(device.Pc)
            else:
                if property_name == "Qa":
                    value = float(device.Qa)
                else:
                    if property_name == "Qb":
                        value = float(device.Qb)
                    else:
                        if property_name == "Qc":
                            value = float(device.Qc)
                        else:
                            if property_name == "G1":
                                value = float(device.G1)
                            else:
                                if property_name == "G2":
                                    value = float(device.G2)
                                else:
                                    if property_name == "G3":
                                        value = float(device.G3)
                                    else:
                                        if property_name == "B1":
                                            value = float(device.B1)
                                        else:
                                            if property_name == "B2":
                                                value = float(device.B2)
                                            else:
                                                if property_name == "B3":
                                                    value = float(device.B3)
                                                else:
                                                    if property_name == "Ir1":
                                                        value = float(device.Ir1)
                                                    else:
                                                        if property_name == "Ir2":
                                                            value = float(device.Ir2)
                                                        else:
                                                            if property_name == "Ir3":
                                                                value = float(device.Ir3)
                                                            else:
                                                                if property_name == "Ii1":
                                                                    value = float(device.Ii1)
                                                                else:
                                                                    if property_name == "Ii2":
                                                                        value = float(device.Ii2)
                                                                    else:
                                                                        if property_name == "Ii3":
                                                                            value = float(device.Ii3)
                                                                        else:
                                                                            if property_name == "Ga":
                                                                                value = float(device.Ga)
                                                                            else:
                                                                                if property_name == "Gb":
                                                                                    value = float(device.Gb)
                                                                                else:
                                                                                    if property_name == "Gc":
                                                                                        value = float(device.Gc)
                                                                                    else:
                                                                                        if property_name == "Ba":
                                                                                            value = float(device.Ba)
                                                                                        else:
                                                                                            if property_name == "Bb":
                                                                                                value = float(device.Bb)
                                                                                            else:
                                                                                                if property_name == "Bc":
                                                                                                    value = float(device.Bc)
                                                                                                else:
                                                                                                    value = 0.0

    return value


def _get_direct_total_property_value(device: ALL_DEV_TYPES, total_property_name: str) -> float:
    """
    Return one explicit total-property value without reflection.

    The phase fallback path needs the balanced total associated with one phase
    property. Resolving it explicitly avoids dynamic attribute access while
    keeping the historical balanced fallback semantics identical.

    :param device: Static device instance.
    :param total_property_name: Total-property name.
    :return: Numerical property value.
    """
    value: float

    if total_property_name == "P":
        value = float(device.P)
    else:
        if total_property_name == "Q":
            value = float(device.Q)
        else:
            if total_property_name == "G":
                value = float(device.G)
            else:
                if total_property_name == "B":
                    value = float(device.B)
                else:
                    if total_property_name == "Ir":
                        value = float(device.Ir)
                    else:
                        if total_property_name == "Ii":
                            value = float(device.Ii)
                        else:
                            value = 0.0

    return value


def _resolve_direct_phase_power_value(
        device: ALL_DEV_TYPES,
        property_name: str,
        grid: MultiCircuit,
) -> float:
    """
    Resolve one direct phase value with balanced fallback preserved.

    The historical hand-written assignment path treats explicit phase values as
    authoritative only when at least one phase of the same quantity is
    meaningfully populated. Otherwise the balanced total is split equally among
    the three phases before converting to per unit. The automatic direct dyn-ref
    path must preserve that exact rule so existing EMT/RMS models keep the same
    numerical initialization behavior.

    :param device: Static device instance.
    :param property_name: Static phase-property name.
    :param grid: Static network model.
    :return: Per-unit phase quantity.
    """
    total_property_name: str | None = None
    explicit_phase_is_meaningful: bool = False

    if property_name == "Pa":
        total_property_name = "P"
    else:
        if property_name == "Pb":
            total_property_name = "P"
        else:
            if property_name == "Pc":
                total_property_name = "P"
            else:
                if property_name == "Qa":
                    total_property_name = "Q"
                else:
                    if property_name == "Qb":
                        total_property_name = "Q"
                    else:
                        if property_name == "Qc":
                            total_property_name = "Q"
                        else:
                            if property_name == "G1":
                                total_property_name = "G"
                            else:
                                if property_name == "G2":
                                    total_property_name = "G"
                                else:
                                    if property_name == "G3":
                                        total_property_name = "G"
                                    else:
                                        if property_name == "B1":
                                            total_property_name = "B"
                                        else:
                                            if property_name == "B2":
                                                total_property_name = "B"
                                            else:
                                                if property_name == "B3":
                                                    total_property_name = "B"
                                                else:
                                                    if property_name == "Ir1":
                                                        total_property_name = "Ir"
                                                    else:
                                                        if property_name == "Ir2":
                                                            total_property_name = "Ir"
                                                        else:
                                                            if property_name == "Ir3":
                                                                total_property_name = "Ir"
                                                            else:
                                                                if property_name == "Ii1":
                                                                    total_property_name = "Ii"
                                                                else:
                                                                    if property_name == "Ii2":
                                                                        total_property_name = "Ii"
                                                                    else:
                                                                        if property_name == "Ii3":
                                                                            total_property_name = "Ii"
                                                                        else:
                                                                            if property_name == "Ga":
                                                                                total_property_name = "G"
                                                                            else:
                                                                                if property_name == "Gb":
                                                                                    total_property_name = "G"
                                                                                else:
                                                                                    if property_name == "Gc":
                                                                                        total_property_name = "G"
                                                                                    else:
                                                                                        if property_name == "Ba":
                                                                                            total_property_name = "B"
                                                                                        else:
                                                                                            if property_name == "Bb":
                                                                                                total_property_name = "B"
                                                                                            else:
                                                                                                if property_name == "Bc":
                                                                                                    total_property_name = "B"
                                                                                                else:
                                                                                                    total_property_name = None

    if total_property_name is None:
        explicit_phase_is_meaningful = True
    else:
        if property_name in ("Pa", "Pb", "Pc"):
            explicit_phase_is_meaningful = _abc_values_are_meaningful(
                phase_a=float(device.Pa),
                phase_b=float(device.Pb),
                phase_c=float(device.Pc),
            )
        else:
            if property_name in ("Qa", "Qb", "Qc"):
                explicit_phase_is_meaningful = _abc_values_are_meaningful(
                    phase_a=float(device.Qa),
                    phase_b=float(device.Qb),
                    phase_c=float(device.Qc),
                )
            else:
                if property_name in ("G1", "G2", "G3"):
                    explicit_phase_is_meaningful = _abc_values_are_meaningful(
                        phase_a=float(device.G1),
                        phase_b=float(device.G2),
                        phase_c=float(device.G3),
                    )
                else:
                    if property_name in ("B1", "B2", "B3"):
                        explicit_phase_is_meaningful = _abc_values_are_meaningful(
                            phase_a=float(device.B1),
                            phase_b=float(device.B2),
                            phase_c=float(device.B3),
                        )
                    else:
                        if property_name in ("Ir1", "Ir2", "Ir3"):
                            explicit_phase_is_meaningful = _abc_values_are_meaningful(
                                phase_a=float(device.Ir1),
                                phase_b=float(device.Ir2),
                                phase_c=float(device.Ir3),
                            )
                        else:
                            if property_name in ("Ii1", "Ii2", "Ii3"):
                                explicit_phase_is_meaningful = _abc_values_are_meaningful(
                                    phase_a=float(device.Ii1),
                                    phase_b=float(device.Ii2),
                                    phase_c=float(device.Ii3),
                                )
                            else:
                                if property_name in ("Ga", "Gb", "Gc"):
                                    explicit_phase_is_meaningful = _abc_values_are_meaningful(
                                        phase_a=float(device.Ga),
                                        phase_b=float(device.Gb),
                                        phase_c=float(device.Gc),
                                    )
                                else:
                                    if property_name in ("Ba", "Bb", "Bc"):
                                        explicit_phase_is_meaningful = _abc_values_are_meaningful(
                                            phase_a=float(device.Ba),
                                            phase_b=float(device.Bb),
                                            phase_c=float(device.Bc),
                                        )
                                    else:
                                        explicit_phase_is_meaningful = True

    if explicit_phase_is_meaningful:
        return _get_direct_phase_property_value(device=device, property_name=property_name) / float(grid.Sbase)
    else:
        return (_get_direct_total_property_value(device=device, total_property_name=str(total_property_name)) / 3.0) / float(grid.Sbase)


def resolve_direct_dyn_ref_value(
        grid: MultiCircuit,
        device: ALL_DEV_TYPES,
        key: ParamPowerFlowReferenceType,
        property_name: str,
        raw_value: Any,
) -> float | None:
    """
    Resolve one direct property-backed static assignment value.

    This helper centralizes the direct conversion rules associated with
    ``GCProp.dyn_ref``. Direct property-backed references are resolved here,
    while grid-base values, derived equivalents, matrix contracts and legacy
    aliases intentionally return ``None`` so the historical explicit code path
    remains responsible for them.

    :param grid: Static network model.
    :param device: Static device instance.
    :param key: Dynamic reference requested by the template.
    :param property_name: Static property name declared in the schema.
    :param raw_value: Static property value read from the device.
    :return: Direct numerical value or ``None`` when explicit logic must handle it.
    """
    # Optional physical properties use ``None`` to declare absent evidence.
    # They must not become a synthetic zero or enter a numeric conversion; the
    # device-specific fallback remains responsible for the reduced model.
    if raw_value is None:
        return None
    else:
        pass

    if key == ParamPowerFlowReferenceType.g or key == ParamPowerFlowReferenceType.b:
        # Branch-like devices may expose scalar g/b template keys whose meaning
        # depends on the target dynamic model contract. For RMS phasor line
        # templates these are derived series admittance terms, not direct copies
        # of editable branch R/X properties. Leaving those keys to the explicit
        # device-specific mapper keeps the automatic dyn-ref path restricted to
        # genuinely direct assignments.
        return None
    else:
        pass

    if key in (
            ParamPowerFlowReferenceType.branch_rate_mva,
            ParamPowerFlowReferenceType.branch_temp_base_deg_c,
            ParamPowerFlowReferenceType.branch_temp_oper_deg_c,
            ParamPowerFlowReferenceType.branch_alpha_per_deg_c,
            ParamPowerFlowReferenceType.converter_control_mode_1,
            ParamPowerFlowReferenceType.converter_control_mode_2,
            ParamPowerFlowReferenceType.converter_control_target_1,
            ParamPowerFlowReferenceType.converter_control_target_2,
            ParamPowerFlowReferenceType.alpha1,
            ParamPowerFlowReferenceType.alpha2,
            ParamPowerFlowReferenceType.alpha3,
            ParamPowerFlowReferenceType.vsc_kdp_pu,
            ParamPowerFlowReferenceType.vsc_min_ac_voltage_pu,
    ):
        # These keys are contract-sensitive across EMT and RMS families.
        # The unified mapper therefore leaves them to the explicit per-device
        # handlers so the historical solver-specific meaning is preserved.
        return None
    else:
        pass

    if key == ParamPowerFlowReferenceType.device_active:
        return 1.0 if bool(raw_value) else 0.0
    else:
        if key == ParamPowerFlowReferenceType.injection_connection_type:
            return shunt_connection_code(raw_value)
        else:
            if key == ParamPowerFlowReferenceType.external_grid_mode_code:
                return external_grid_mode_code(raw_value)
            else:
                if key == ParamPowerFlowReferenceType.controllable_shunt_control_mode_code:
                    return controllable_shunt_mode_code(raw_value)
                else:
                    if key == ParamPowerFlowReferenceType.converter_control_mode_1:
                        return converter_control_code(raw_value)
                    else:
                        if key == ParamPowerFlowReferenceType.converter_control_mode_2:
                            return converter_control_code(raw_value)
                        else:
                            if key == ParamPowerFlowReferenceType.generator_control_mode:
                                return 1.0 if bool(device.is_controlled) else 0.0
                            else:
                                if key in (
                                        ParamPowerFlowReferenceType.generator_enabled_dispatch,
                                        ParamPowerFlowReferenceType.generator_must_run,
                                        ParamPowerFlowReferenceType.generator_use_reactive_power_curve,
                                ):
                                    return 1.0 if bool(raw_value) else 0.0
                                else:
                                    if key in (
                                            ParamPowerFlowReferenceType.Pl0,
                                            ParamPowerFlowReferenceType.Ql0,
                                            ParamPowerFlowReferenceType.load_g_pu,
                                            ParamPowerFlowReferenceType.load_b_pu,
                                            ParamPowerFlowReferenceType.load_ir_pu,
                                            ParamPowerFlowReferenceType.load_ii_pu,
                                            ParamPowerFlowReferenceType.load_contract_power_pu,
                                            ParamPowerFlowReferenceType.current_injection_ir_pu,
                                            ParamPowerFlowReferenceType.current_injection_ii_pu,
                                            ParamPowerFlowReferenceType.shunt_g_pu,
                                            ParamPowerFlowReferenceType.shunt_b_pu,
                                            ParamPowerFlowReferenceType.shunt_g0_pu,
                                            ParamPowerFlowReferenceType.shunt_b0_pu,
                                            ParamPowerFlowReferenceType.generator_p_pu,
                                            ParamPowerFlowReferenceType.generator_q_pu,
                                            ParamPowerFlowReferenceType.Pmin,
                                            ParamPowerFlowReferenceType.Pmax,
                                            ParamPowerFlowReferenceType.generator_qmin_pu,
                                            ParamPowerFlowReferenceType.generator_qmax_pu,
                                            ParamPowerFlowReferenceType.controllable_shunt_gmin_pu,
                                            ParamPowerFlowReferenceType.controllable_shunt_gmax_pu,
                                            ParamPowerFlowReferenceType.controllable_shunt_bmin_pu,
                                            ParamPowerFlowReferenceType.controllable_shunt_bmax_pu,
                                    ):
                                        return float(raw_value) / float(grid.Sbase)
                                    else:
                                        if key in (
                                                ParamPowerFlowReferenceType.Pl0_A,
                                                ParamPowerFlowReferenceType.Pl0_B,
                                                ParamPowerFlowReferenceType.Pl0_C,
                                                ParamPowerFlowReferenceType.Ql0_A,
                                                ParamPowerFlowReferenceType.Ql0_B,
                                                ParamPowerFlowReferenceType.Ql0_C,
                                                ParamPowerFlowReferenceType.load_ga_pu,
                                                ParamPowerFlowReferenceType.load_gb_pu,
                                                ParamPowerFlowReferenceType.load_gc_pu,
                                                ParamPowerFlowReferenceType.load_ba_pu,
                                                ParamPowerFlowReferenceType.load_bb_pu,
                                                ParamPowerFlowReferenceType.load_bc_pu,
                                                ParamPowerFlowReferenceType.load_ira_pu,
                                                ParamPowerFlowReferenceType.load_irb_pu,
                                                ParamPowerFlowReferenceType.load_irc_pu,
                                                ParamPowerFlowReferenceType.load_iia_pu,
                                                ParamPowerFlowReferenceType.load_iib_pu,
                                                ParamPowerFlowReferenceType.load_iic_pu,
                                                ParamPowerFlowReferenceType.current_injection_ira_pu,
                                                ParamPowerFlowReferenceType.current_injection_irb_pu,
                                                ParamPowerFlowReferenceType.current_injection_irc_pu,
                                                ParamPowerFlowReferenceType.current_injection_iia_pu,
                                                ParamPowerFlowReferenceType.current_injection_iib_pu,
                                                ParamPowerFlowReferenceType.current_injection_iic_pu,
                                                ParamPowerFlowReferenceType.shunt_ga_pu,
                                                ParamPowerFlowReferenceType.shunt_gb_pu,
                                                ParamPowerFlowReferenceType.shunt_gc_pu,
                                                ParamPowerFlowReferenceType.shunt_ba_pu,
                                                ParamPowerFlowReferenceType.shunt_bb_pu,
                                                ParamPowerFlowReferenceType.shunt_bc_pu,
                                        ):
                                            return _resolve_direct_phase_power_value(
                                                device=device,
                                                property_name=property_name,
                                                grid=grid,
                                            )
                                        else:
                                            if key in (
                                                    ParamPowerFlowReferenceType.R1,
                                                    ParamPowerFlowReferenceType.X1,
                                                    ParamPowerFlowReferenceType.X0,
                                                    ParamPowerFlowReferenceType.generator_power_factor,
                                                    ParamPowerFlowReferenceType.generator_vset_pu,
                                                    ParamPowerFlowReferenceType.generator_snom_mva,
                                                    ParamPowerFlowReferenceType.generator_r0_pu,
                                                    ParamPowerFlowReferenceType.generator_r2_pu,
                                                    ParamPowerFlowReferenceType.generator_x2_pu,
                                                    ParamPowerFlowReferenceType.battery_enom_mwh,
                                                    ParamPowerFlowReferenceType.battery_soc_0_pu,
                                                    ParamPowerFlowReferenceType.battery_max_soc_pu,
                                                    ParamPowerFlowReferenceType.battery_min_soc_pu,
                                                    ParamPowerFlowReferenceType.battery_charge_efficiency_pu,
                                                    ParamPowerFlowReferenceType.battery_discharge_efficiency_pu,
                                                    ParamPowerFlowReferenceType.battery_discharge_per_cycle_pu,
                                                    ParamPowerFlowReferenceType.branch_rate_mva,
                                                    ParamPowerFlowReferenceType.branch_temp_base_deg_c,
                                                    ParamPowerFlowReferenceType.branch_temp_oper_deg_c,
                                                    ParamPowerFlowReferenceType.branch_alpha_per_deg_c,
                                                    ParamPowerFlowReferenceType.alpha1,
                                                    ParamPowerFlowReferenceType.alpha2,
                                                    ParamPowerFlowReferenceType.alpha3,
                                                    ParamPowerFlowReferenceType.converter_control_target_1,
                                                    ParamPowerFlowReferenceType.converter_control_target_2,
                                                    ParamPowerFlowReferenceType.vsc_kdp_pu,
                                                    ParamPowerFlowReferenceType.vsc_min_ac_voltage_pu,
                                                    ParamPowerFlowReferenceType.dc_line_r_pu,
                                                    ParamPowerFlowReferenceType.dc_line_l_pu_seconds,
                                                    ParamPowerFlowReferenceType.dc_line_length_km,
                                                    ParamPowerFlowReferenceType.transformer_rated_power_mva,
                                                    ParamPowerFlowReferenceType.transformer_winding1_rated_voltage_ll_kv,
                                                    ParamPowerFlowReferenceType.transformer_winding2_rated_voltage_ll_kv,
                                                    ParamPowerFlowReferenceType.transformer_connection_clock,
                                                    ParamPowerFlowReferenceType.transformer_open_circuit_current_pct,
                                                    ParamPowerFlowReferenceType.transformer_open_circuit_loss_kw,
                                                    ParamPowerFlowReferenceType.transformer_short_circuit_voltage_pct,
                                                    ParamPowerFlowReferenceType.transformer_short_circuit_loss_kw,
                                                    ParamPowerFlowReferenceType.tap_module,
                                                    ParamPowerFlowReferenceType.static_generator_snom_mva,
                                                    ParamPowerFlowReferenceType.external_grid_vm_pu,
                                                    ParamPowerFlowReferenceType.external_grid_va_rad,
                                                    ParamPowerFlowReferenceType.controllable_shunt_step,
                                                    ParamPowerFlowReferenceType.controllable_shunt_vset_pu,
                                                    ParamPowerFlowReferenceType.controllable_shunt_vmin_pu,
                                                    ParamPowerFlowReferenceType.controllable_shunt_vmax_pu,
                                                    ParamPowerFlowReferenceType.line_length_km,
                                                    ParamPowerFlowReferenceType.r,
                                                    ParamPowerFlowReferenceType.l,
                                                    ParamPowerFlowReferenceType.g,
                                                    ParamPowerFlowReferenceType.b,
                                                    ParamPowerFlowReferenceType.bsh,
                                                    ParamPowerFlowReferenceType.gFe,
                                            ):
                                                return float(raw_value)
                                            else:
                                                return None


def assign_direct_dyn_ref_properties_for_device(
        grid: MultiCircuit,
        device: ALL_DEV_TYPES,
        mdl: Block,
        problem_mapping: Dict[Var, Const],
        logger: StaticParameterMappingDiagnosticSink | None,
) -> Set[ParamPowerFlowReferenceType]:
    """
    Automatically assign the direct property-backed dynamic references.

    The broader static-mapping algorithm first handles every key explicitly
    declared through ``GCProp.dyn_ref`` and convertible by direct rules. After
    that, the device-specific explicit code remains responsible for grid-base
    quantities, derived equivalents, matrix contracts and historical aliases.

    :param grid: Static network model.
    :param device: Static device instance.
    :param mdl: Dynamic block receiving constants.
    :param problem_mapping: Dictionary that stores each parameter with their value.
    :param logger: Optional logger.
    :return: Set of keys assigned automatically.
    """
    direct_keys_by_device_type: Dict[DeviceType, List[ParamPowerFlowReferenceType]] | None = None
    direct_keys: List[ParamPowerFlowReferenceType] | None = None
    dyn_ref_to_prop: Dict[ParamPowerFlowReferenceType, "GCProp"] = build_device_dyn_ref_property_lookup(device=device)
    assigned_keys: Set[ParamPowerFlowReferenceType] = set()
    key: ParamPowerFlowReferenceType

    if isinstance(grid, MultiCircuit):
        direct_keys_by_device_type = grid.get_devices_static_params_mapping()
    else:
        direct_keys_by_device_type = None

    if direct_keys_by_device_type is None:
        direct_keys = build_device_direct_dyn_ref_keys(device=device)
    else:
        direct_keys = direct_keys_by_device_type.get(device.device_type, None)

    if direct_keys is None:
        return assigned_keys
    else:
        pass

    for key in direct_keys:
        prop: GCProp | None = dyn_ref_to_prop.get(key, None)

        if prop is None:
            pass
        else:
            raw_value: Any = device.get_property_value(prop=prop, t_idx=None)
            resolved_value: float | None = resolve_direct_dyn_ref_value(
                grid=grid,
                device=device,
                key=key,
                property_name=prop.name,
                raw_value=raw_value,
            )

            if resolved_value is None:
                pass
            else:
                if assign_api_mapping_value_if_present(
                        mdl=mdl,
                        key=key,
                        value=resolved_value,
                        logger=logger,
                        device_name=str(device.name),
                        problem_mapping=problem_mapping,
                ):
                    assigned_keys.add(key)
                else:
                    pass

    return assigned_keys


def assign_static_api_object_mapping_for_device(
        grid: MultiCircuit,
        device: ALL_DEV_TYPES,
        mdl: Block,
        problem_mapping: Dict[Var, Const] | None = None,
        logger: StaticParameterMappingDiagnosticSink | None = None,
) -> None:
    """Resolve device-backed initial values for a complete block hierarchy.

    Both RMS and EMT call this public entry point once for each device model.
    Recursion is kept here so every descendant is treated by the same
    owner-local mapping rules and wrappers never need to duplicate a child's
    ``api_obj_mapping`` entries.

    :param grid: Static network model containing system base values.
    :param device: Static grid device associated with the dynamic model.
    :param mdl: Root block of the RMS or EMT model hierarchy.
    :param problem_mapping: Destination for resolved initial values.
    :param logger: Optional driver logger or simulation-aware diagnostics context.
    :return: None.
    """
    destination_mapping: Dict[Var, Const]
    if problem_mapping is None:
        destination_mapping = dict()
    else:
        destination_mapping = problem_mapping

    # Source metadata exists only while this device hierarchy is assembled.
    # The caller still receives the established plain Var-to-Const contract.
    tracked_mapping: StaticParameterMappingValues = StaticParameterMappingValues(
        initial_values=destination_mapping,
    )
    model_blocks: List[Block] = mdl.get_all_blocks()
    block: Block
    for block in model_blocks:
        _assign_static_api_object_mapping_for_block(
            grid=grid,
            device=device,
            mdl=block,
            problem_mapping=tracked_mapping,
            logger=logger,
        )

    # Compare only the final candidate produced by each API reference. This
    # separates legitimate same-reference refinement from true source clashes.
    tracked_mapping.finalize_candidates(
        logger=logger,
        device_name=str(device.name),
    )

    # Diagnostics are emitted after every assignment layer has completed so
    # they always display the final effective value consumed by the problem.
    reported_uids: Set[int] = set()
    for block in model_blocks:
        report_api_mapping_overrides_for_block(
            mdl=block,
            problem_mapping=tracked_mapping,
            logger=logger,
            device_name=str(device.name),
            reported_uids=reported_uids,
        )

    if problem_mapping is None:
        pass
    else:
        problem_mapping.clear()
        problem_mapping.update(tracked_mapping)


def _assign_static_api_object_mapping_for_block(
        grid: MultiCircuit,
        device: ALL_DEV_TYPES,
        mdl: Block,
        problem_mapping: Dict[Var, Const] | None = None,
        logger: StaticParameterMappingDiagnosticSink | None = None,
) -> None:
    """
    Assign API-object parameter initial values for one dynamic-model block.

    The dispatcher is generic with respect to RMS/EMT templates. A template receives
    values only for the ``ParamPowerFlowReferenceType`` keys it exposes in
    ``mdl.api_obj_mapping``. Adding a new EMT model for an already-supported
    ``DeviceType`` should not require modifying either problem builder.

    :param grid: Static network model containing base values.
    :param device: Static grid device owning the EMT model.
    :param mdl: Owner block requesting device-backed initial values.
    :param problem_mapping: Dictionary that stores each parameter with its initial value.
    :param logger: Optional driver logger or simulation-aware diagnostics context.
    :return: None.
    """
    direct_assigned_keys: Set[ParamPowerFlowReferenceType] = set()

    if problem_mapping is None:
        problem_mapping = dict()
    else:
        pass

    # Grid bases are available to any device declaring these static mappings.
    for reference, value in (
        (ParamPowerFlowReferenceType.freq, float(grid.fBase)),
        (ParamPowerFlowReferenceType.omega_base, 2.0 * np.pi * float(grid.fBase)),
        (ParamPowerFlowReferenceType.ws, 2.0 * np.pi * float(grid.fBase)),
    ):
        assign_api_mapping_value_if_present(
            mdl=mdl,
            key=reference,
            value=value,
            logger=logger,
            device_name=str(device.name),
            problem_mapping=problem_mapping,
        )

    direct_assigned_keys = assign_direct_dyn_ref_properties_for_device(
        grid=grid,
        device=device,
        mdl=mdl,
        problem_mapping=problem_mapping,
        logger=logger,
    )

    api_obj_mapping: Dict = mdl.api_obj_mapping

    if isinstance(api_obj_mapping, dict):
        if len(api_obj_mapping) == 0:
            pass
        else:
            # The dispatch is based on the static device type, not on the EMT
            # template name. The template only selects a subset of keys.
            device_type: DeviceType = device.device_type

            if device_type == DeviceType.LoadDevice:
                assign_load_static_api_mapping(
                    grid=grid,
                    load=device,
                    mdl=mdl,
                    problem_mapping=problem_mapping,
                    logger=logger,
                    direct_assigned_keys=direct_assigned_keys,
                )
            elif device_type == DeviceType.StaticGeneratorDevice:
                assign_static_generator_static_api_mapping(
                    grid=grid,
                    static_generator=device,
                    mdl=mdl,
                    problem_mapping=problem_mapping,
                    logger=logger,
                    direct_assigned_keys=direct_assigned_keys,
                )
            elif device_type == DeviceType.ExternalGridDevice:
                assign_external_grid_static_api_mapping(
                    grid=grid,
                    external_grid=device,
                    mdl=mdl,
                    problem_mapping=problem_mapping,
                    logger=logger,
                    direct_assigned_keys=direct_assigned_keys,
                )
            elif device_type == DeviceType.ShuntDevice:
                assign_shunt_static_api_mapping(
                    grid=grid,
                    shunt=device,
                    mdl=mdl,
                    problem_mapping=problem_mapping,
                    logger=logger,
                    direct_assigned_keys=direct_assigned_keys,
                )
            elif device_type == DeviceType.ControllableShuntDevice:
                assign_controllable_shunt_static_api_mapping(
                    grid=grid,
                    controllable_shunt=device,
                    mdl=mdl,
                    problem_mapping=problem_mapping,
                    logger=logger,
                    direct_assigned_keys=direct_assigned_keys,
                )
            elif device_type == DeviceType.CurrentInjectionDevice:
                assign_current_injection_static_api_mapping(
                    grid=grid,
                    current_injection=device,
                    mdl=mdl,
                    problem_mapping=problem_mapping,
                    logger=logger,
                    direct_assigned_keys=direct_assigned_keys,
                )
            elif device_type == DeviceType.GeneratorDevice:
                assign_generator_static_api_mapping(
                    grid=grid,
                    generator=device,
                    mdl=mdl,
                    problem_mapping=problem_mapping,
                    logger=logger,
                    direct_assigned_keys=direct_assigned_keys,
                )
            elif device_type == DeviceType.BatteryDevice:
                assign_battery_static_api_mapping(
                    grid=grid,
                    battery=device,
                    mdl=mdl,
                    problem_mapping=problem_mapping,
                    logger=logger,
                    direct_assigned_keys=direct_assigned_keys,
                )
            elif device_type == DeviceType.VscDevice:
                assign_vsc_static_api_mapping(
                    grid=grid,
                    vsc=device,
                    mdl=mdl,
                    problem_mapping=problem_mapping,
                    logger=logger,
                    direct_assigned_keys=direct_assigned_keys,
                )
            elif device_type == DeviceType.DCLineDevice:
                if isinstance(device, DcLine):
                    assign_dc_line_static_api_mapping(
                        grid=grid,
                        dc_line=device,
                        mdl=mdl,
                        problem_mapping=problem_mapping,
                        logger=logger,
                        direct_assigned_keys=direct_assigned_keys,
                    )
                else:
                    add_static_mapping_warning(
                        logger=logger,
                        device_name=str(device.name),
                        message="DCLineDevice static mapping skipped because the object type is not DcLine.",
                        value=str(device_type),
                        expected_value="DcLine instance",
                        device_property="device_type",
                    )
            elif device_type == DeviceType.Transformer2WDevice:
                if isinstance(device, Transformer2W):
                    assign_transformer2w_static_api_mapping(
                        grid=grid,
                        transformer=device,
                        mdl=mdl,
                        problem_mapping=problem_mapping,
                        logger=logger,
                        direct_assigned_keys=direct_assigned_keys,
                    )
                else:
                    add_static_mapping_warning(
                        logger=logger,
                        device_name=str(device.name),
                        message="Transformer2WDevice static mapping skipped because the object type is not Transformer2W.",
                        value=str(device_type),
                        expected_value="Transformer2W instance",
                        device_property="device_type",
                    )
            elif device_type == DeviceType.WindingDevice:
                if isinstance(device, Transformer2W):
                    assign_transformer2w_static_api_mapping(
                        grid=grid,
                        transformer=device,
                        mdl=mdl,
                        problem_mapping=problem_mapping,
                        logger=logger,
                        direct_assigned_keys=direct_assigned_keys,
                    )
                else:
                    add_static_mapping_warning(
                        logger=logger,
                        device_name=str(device.name),
                        message="WindingDevice static mapping skipped because the object type is not Transformer2W-compatible.",
                        value=str(device_type),
                        expected_value="Transformer2W-compatible instance",
                        device_property="device_type",
                    )
            elif device_type == DeviceType.LineDevice:
                assign_line_static_api_mapping(
                    grid=grid,
                    line=device,
                    mdl=mdl,
                    problem_mapping=problem_mapping,
                    logger=logger,
                    direct_assigned_keys=direct_assigned_keys,
                )
            elif device_type == DeviceType.HVDCLineDevice:
                assign_hvdc_line_static_api_mapping(
                    hvdc_line=device,
                    mdl=mdl,
                    problem_mapping=problem_mapping,
                    logger=logger,
                )
            elif device_type == DeviceType.SeriesReactanceDevice:
                assign_series_reactance_static_api_mapping(
                    series_reactance=device,
                    mdl=mdl,
                    problem_mapping=problem_mapping,
                    logger=logger,
                )
            elif device_type == DeviceType.SwitchDevice:
                assign_switch_static_api_mapping(
                    switch=device,
                    mdl=mdl,
                    problem_mapping=problem_mapping,
                    logger=logger,
                    direct_assigned_keys=direct_assigned_keys,
                )
            elif device_type == DeviceType.UpfcDevice:
                assign_upfc_static_api_mapping(
                    upfc=device,
                    mdl=mdl,
                    problem_mapping=problem_mapping,
                    logger=logger,
                )
            else:
                # Compatibility fallback: older branch-like models may expose
                # line matrix keys even if their device_type is more generic.
                # The fallback activates only when the EMT template explicitly
                # requests line-matrix keys.
                if api_mapping_has_any_key(mdl=mdl, keys=get_all_line_matrix_keys()):
                    assign_line_static_api_mapping(
                        grid=grid,
                        line=device,
                        mdl=mdl,
                        problem_mapping=problem_mapping,
                        logger=logger,
                        direct_assigned_keys=direct_assigned_keys,
                    )
                else:
                    pass
    else:
        pass


def converter_control_code(control_tpe: ConverterControlType | None) -> float:
    """
    Convert a static VSC control enum to the EMT template numerical code.

    :param control_tpe: Converter control enum or ``None``.
    :return: Numerical control code used by existing EMT templates.
    """
    code: float

    if control_tpe is None:
        code = 0.0
    elif control_tpe == ConverterControlType.Vm_dc:
        code = 1.0
    elif control_tpe == ConverterControlType.Vm_ac:
        code = 2.0
    elif control_tpe == ConverterControlType.Va_ac:
        code = 3.0
    elif control_tpe == ConverterControlType.Qac:
        code = 4.0
    elif control_tpe == ConverterControlType.Pdc:
        code = 5.0
    elif control_tpe == ConverterControlType.Pac:
        code = 6.0
    elif control_tpe == ConverterControlType.Pdc_angle_droop:
        code = 7.0
    elif control_tpe == ConverterControlType.Imax:
        code = 8.0
    else:
        code = 0.0

    return code


def xfmr_connection_matrix(winding_tpe: WindingType) -> np.ndarray:
    """
    Return the 3x3 transformer winding connection matrix.

    :param winding_tpe: Transformer winding connection type.
    :return: 3x3 winding connection matrix.
    """
    matrix: np.ndarray

    if winding_tpe in (
            WindingType.GroundedStar,
            WindingType.NeutralStar,
            WindingType.FloatingStar,
    ):
        matrix = np.eye(3, dtype=float)
    else:
        if winding_tpe == WindingType.Delta:
            matrix = np.array(
                [
                    [1.0, 0.0, -1.0],
                    [-1.0, 1.0, 0.0],
                    [0.0, -1.0, 1.0],
                ],
                dtype=float,
            ) / np.sqrt(3.0)
        else:
            matrix = np.eye(3, dtype=float)

    return matrix


def xfmr_phase_permutation_matrix(clock: int) -> np.ndarray:
    """
    Return the transformer phase permutation matrix from vector-group clock.

    :param clock: Transformer vector-group clock number.
    :return: 3x3 phase permutation matrix.
    """
    matrix: np.ndarray
    shift: int = (int(clock) // 4) % 3

    if shift == 0:
        matrix = np.eye(3, dtype=float)
    else:
        if shift == 1:
            matrix = np.array(
                [
                    [0.0, 1.0, 0.0],
                    [0.0, 0.0, 1.0],
                    [1.0, 0.0, 0.0],
                ],
                dtype=float,
            )
        else:
            matrix = np.array(
                [
                    [0.0, 0.0, 1.0],
                    [1.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                ],
                dtype=float,
            )

    return matrix


def get_transformer_from_connection_keys() -> List[List[ParamPowerFlowReferenceType]]:
    """
    Return 3x3 from-side transformer connection mapping keys.

    :return: Matrix of from-side API-object keys.
    """
    keys: List[List[ParamPowerFlowReferenceType]] = list([
        list([
            ParamPowerFlowReferenceType.transformer_from_connection_aa,
            ParamPowerFlowReferenceType.transformer_from_connection_ab,
            ParamPowerFlowReferenceType.transformer_from_connection_ac,
        ]),
        list([
            ParamPowerFlowReferenceType.transformer_from_connection_ba,
            ParamPowerFlowReferenceType.transformer_from_connection_bb,
            ParamPowerFlowReferenceType.transformer_from_connection_bc,
        ]),
        list([
            ParamPowerFlowReferenceType.transformer_from_connection_ca,
            ParamPowerFlowReferenceType.transformer_from_connection_cb,
            ParamPowerFlowReferenceType.transformer_from_connection_cc,
        ]),
    ])

    return keys


def get_transformer_to_connection_keys() -> List[List[ParamPowerFlowReferenceType]]:
    """
    Return 3x3 to-side transformer connection mapping keys.

    :return: Matrix of to-side API-object keys.
    """
    keys: List[List[ParamPowerFlowReferenceType]] = list([
        list([
            ParamPowerFlowReferenceType.transformer_to_connection_aa,
            ParamPowerFlowReferenceType.transformer_to_connection_ab,
            ParamPowerFlowReferenceType.transformer_to_connection_ac,
        ]),
        list([
            ParamPowerFlowReferenceType.transformer_to_connection_ba,
            ParamPowerFlowReferenceType.transformer_to_connection_bb,
            ParamPowerFlowReferenceType.transformer_to_connection_bc,
        ]),
        list([
            ParamPowerFlowReferenceType.transformer_to_connection_ca,
            ParamPowerFlowReferenceType.transformer_to_connection_cb,
            ParamPowerFlowReferenceType.transformer_to_connection_cc,
        ]),
    ])

    return keys


def assign_3x3_static_matrix(
        mdl: Block,
        matrix: np.ndarray,
        keys: List[List[ParamPowerFlowReferenceType]],
        logger: StaticParameterMappingDiagnosticSink | None,
        device_name: str,
        problem_mapping: Dict[Var, Const],
) -> None:
    """
    Assign a 3x3 static matrix through a 3x3 API-object key matrix.

    :param mdl: EMT block.
    :param matrix: Numerical 3x3 matrix.
    :param keys: API-object key matrix.
    :param logger: Optional logger.
    :param device_name: Device name used in diagnostics.
    :param problem_mapping: mapping to save parameters values in RMS problem
    :return: None.
    """
    row_index: int = 0

    while row_index < 3:
        col_index: int = 0

        while col_index < 3:
            assign_api_mapping_value_if_present(
                mdl=mdl,
                key=keys[row_index][col_index],
                value=float(matrix[row_index, col_index]),
                logger=logger,
                device_name=device_name,
                problem_mapping=problem_mapping,
            )
            col_index += 1

        row_index += 1


def get_transformer_equivalent_circuit_derived_keys() -> List[ParamPowerFlowReferenceType]:
    """
    Return transformer equivalent-circuit derived-value keys.

    :return: Derived equivalent-circuit API-object keys.
    """
    keys: List[ParamPowerFlowReferenceType] = list([
        ParamPowerFlowReferenceType.transformer_winding1_resistance_pu,
        ParamPowerFlowReferenceType.transformer_winding2_resistance_pu,
        ParamPowerFlowReferenceType.transformer_winding1_inductance_pu_s,
        ParamPowerFlowReferenceType.transformer_winding2_inductance_pu_s,
        ParamPowerFlowReferenceType.transformer_mutual_inductance_pu_s,
        ParamPowerFlowReferenceType.transformer_magnetizing_conductance_pu,
    ])

    return keys


def transformer_equivalent_circuit_values_are_requested(mdl: Block) -> bool:
    """
    Return whether any transformer equivalent-circuit derived value is requested.

    This helper is only a computation guard. It is not a template-family or
    model-family detector.

    :param mdl: EMT block.
    :return: ``True`` if any derived transformer key is exposed.
    """
    return api_mapping_has_any_key(mdl=mdl, keys=get_transformer_equivalent_circuit_derived_keys())


def compute_transformer_equivalent_circuit_values(
        omega_base: float,
        transformer_r_pu: float,
        transformer_x_pu: float,
        transformer_g_pu: float,
        transformer_b_pu: float,
        total_voltage_ratio: float,
        total_voltage_ratio_square: float,
        eps_value: float,
) -> Tuple[float, float, float, float, float, float]:
    """
    Compute derived transformer equivalent-circuit values from static data.

    :param omega_base: Angular base frequency in rad/s.
    :param transformer_r_pu: Total series resistance in p.u.
    :param transformer_x_pu: Total series reactance in p.u.
    :param transformer_g_pu: Magnetizing conductance in p.u.
    :param transformer_b_pu: Magnetizing susceptance in p.u.
    :param total_voltage_ratio: Total nominal-times-tap voltage ratio.
    :param total_voltage_ratio_square: Square of the total voltage ratio.
    :param eps_value: Numerical guard constant.
    :return: Tuple ``(r1, r2, l1, l2, mutual_inductance, g_core)``.
    """
    r1_value: float = 0.5 * transformer_r_pu
    r2_value: float = 0.5 * transformer_r_pu / (total_voltage_ratio_square + eps_value)
    leakage_l_primary: float = 0.5 * transformer_x_pu / (omega_base + eps_value)
    leakage_l_secondary: float = leakage_l_primary / (total_voltage_ratio_square + eps_value)
    x_magnetizing: float

    if abs(transformer_b_pu) > eps_value:
        x_magnetizing = 1.0 / abs(transformer_b_pu)
    else:
        # A zero static shunt susceptance means that the PF model has no
        # magnetizing branch.  Keep a finite value for the coupled-winding
        # matrix, but make the approximation electrically negligible.  The
        # former 1000 pu fallback injected 0.001 pu of unmodelled magnetizing
        # current and produced a deterministic 0.2 MW peak-to-peak power ripple
        # on a 100 MVA base immediately after EMT initialization.
        x_magnetizing = max(1.0e7, 1.0e6 * max(abs(transformer_x_pu), 1.0))

    magnetizing_l_primary: float = x_magnetizing / (omega_base + eps_value)
    magnetizing_l_secondary: float = magnetizing_l_primary / (total_voltage_ratio_square + eps_value)
    mutual_inductance: float = magnetizing_l_primary / (total_voltage_ratio + eps_value)
    l1_value: float = leakage_l_primary + magnetizing_l_primary
    l2_value: float = leakage_l_secondary + magnetizing_l_secondary
    g_core: float = transformer_g_pu

    return r1_value, r2_value, l1_value, l2_value, mutual_inductance, g_core


def get_line_r_keys() -> List[List[ParamPowerFlowReferenceType]]:
    """
    Return the fixed 4x4 NABC resistance mapping keys.

    :return: Matrix of resistance API-object keys.
    """
    keys: List[List[ParamPowerFlowReferenceType]] = list([
        list([
            ParamPowerFlowReferenceType.Rnn,
            ParamPowerFlowReferenceType.Rna,
            ParamPowerFlowReferenceType.Rnb,
            ParamPowerFlowReferenceType.Rnc,
        ]),
        list([
            ParamPowerFlowReferenceType.Ran,
            ParamPowerFlowReferenceType.Raa,
            ParamPowerFlowReferenceType.Rab,
            ParamPowerFlowReferenceType.Rac,
        ]),
        list([
            ParamPowerFlowReferenceType.Rbn,
            ParamPowerFlowReferenceType.Rba,
            ParamPowerFlowReferenceType.Rbb,
            ParamPowerFlowReferenceType.Rbc,
        ]),
        list([
            ParamPowerFlowReferenceType.Rcn,
            ParamPowerFlowReferenceType.Rca,
            ParamPowerFlowReferenceType.Rcb,
            ParamPowerFlowReferenceType.Rcc,
        ]),
    ])

    return keys


def get_line_linv_keys() -> List[List[ParamPowerFlowReferenceType]]:
    """
    Return the fixed 4x4 NABC inverse-inductance mapping keys.

    :return: Matrix of inverse-inductance API-object keys.
    """
    keys: List[List[ParamPowerFlowReferenceType]] = list([
        list([
            ParamPowerFlowReferenceType.Linv_nn,
            ParamPowerFlowReferenceType.Linv_na,
            ParamPowerFlowReferenceType.Linv_nb,
            ParamPowerFlowReferenceType.Linv_nc,
        ]),
        list([
            ParamPowerFlowReferenceType.Linv_an,
            ParamPowerFlowReferenceType.Linv_aa,
            ParamPowerFlowReferenceType.Linv_ab,
            ParamPowerFlowReferenceType.Linv_ac,
        ]),
        list([
            ParamPowerFlowReferenceType.Linv_bn,
            ParamPowerFlowReferenceType.Linv_ba,
            ParamPowerFlowReferenceType.Linv_bb,
            ParamPowerFlowReferenceType.Linv_bc,
        ]),
        list([
            ParamPowerFlowReferenceType.Linv_cn,
            ParamPowerFlowReferenceType.Linv_ca,
            ParamPowerFlowReferenceType.Linv_cb,
            ParamPowerFlowReferenceType.Linv_cc,
        ]),
    ])

    return keys


def get_line_c_keys() -> List[List[ParamPowerFlowReferenceType]]:
    """
    Return the fixed 4x4 NABC capacitance mapping keys.

    :return: Matrix of capacitance API-object keys.
    """
    keys: List[List[ParamPowerFlowReferenceType]] = list([
        list([
            ParamPowerFlowReferenceType.Cnn,
            ParamPowerFlowReferenceType.Cna,
            ParamPowerFlowReferenceType.Cnb,
            ParamPowerFlowReferenceType.Cnc,
        ]),
        list([
            ParamPowerFlowReferenceType.Can,
            ParamPowerFlowReferenceType.Caa,
            ParamPowerFlowReferenceType.Cab,
            ParamPowerFlowReferenceType.Cac,
        ]),
        list([
            ParamPowerFlowReferenceType.Cbn,
            ParamPowerFlowReferenceType.Cba,
            ParamPowerFlowReferenceType.Cbb,
            ParamPowerFlowReferenceType.Cbc,
        ]),
        list([
            ParamPowerFlowReferenceType.Ccn,
            ParamPowerFlowReferenceType.Cca,
            ParamPowerFlowReferenceType.Ccb,
            ParamPowerFlowReferenceType.Ccc,
        ]),
    ])

    return keys


def get_line_g_keys() -> List[List[ParamPowerFlowReferenceType]]:
    """Return physical per-terminal shunt-conductance keys in fixed NABC order.

    :return: Four rows of physical conductance API references, including coupling.
    """
    keys: List[List[ParamPowerFlowReferenceType]] = list([
        list([
            ParamPowerFlowReferenceType.Gnn,
            ParamPowerFlowReferenceType.Gna,
            ParamPowerFlowReferenceType.Gnb,
            ParamPowerFlowReferenceType.Gnc,
        ]),
        list([
            ParamPowerFlowReferenceType.Gan,
            ParamPowerFlowReferenceType.Gaa,
            ParamPowerFlowReferenceType.Gab,
            ParamPowerFlowReferenceType.Gac,
        ]),
        list([
            ParamPowerFlowReferenceType.Gbn,
            ParamPowerFlowReferenceType.Gba,
            ParamPowerFlowReferenceType.Gbb,
            ParamPowerFlowReferenceType.Gbc,
        ]),
        list([
            ParamPowerFlowReferenceType.Gcn,
            ParamPowerFlowReferenceType.Gca,
            ParamPowerFlowReferenceType.Gcb,
            ParamPowerFlowReferenceType.Gcc,
        ]),
    ])

    return keys


def flatten_matrix_keys(
        matrix_keys: List[List[ParamPowerFlowReferenceType]],
) -> List[ParamPowerFlowReferenceType]:
    """
    Flatten a matrix of API-object enum keys.

    :param matrix_keys: Matrix of API-object keys.
    :return: Flat list of keys.
    """
    flat_keys: List[ParamPowerFlowReferenceType] = list()
    row_index: int = 0

    while row_index < len(matrix_keys):
        col_index: int = 0

        while col_index < len(matrix_keys[row_index]):
            flat_keys.append(matrix_keys[row_index][col_index])
            col_index += 1

        row_index += 1

    return flat_keys


def get_all_line_matrix_keys() -> List[ParamPowerFlowReferenceType]:
    """
    Return every line R, Linv, C and physical G API-object key.

    :return: Flat list of all line matrix mapping keys.
    """
    all_keys: List[ParamPowerFlowReferenceType] = list()
    key_matrices: List[List[List[ParamPowerFlowReferenceType]]] = list([
        get_line_r_keys(),
        get_line_linv_keys(),
        get_line_c_keys(),
        get_line_g_keys(),
    ])
    matrix_index: int = 0

    while matrix_index < len(key_matrices):
        flat_keys: List[ParamPowerFlowReferenceType] = flatten_matrix_keys(key_matrices[matrix_index])
        key_index: int = 0

        while key_index < len(flat_keys):
            all_keys.append(flat_keys[key_index])
            key_index += 1

        matrix_index += 1

    return all_keys


def get_line_active_global_indices(line: dev.Line) -> List[int]:
    """
    Return active NABC phase indices for a line-like device.

    :param line: Line-like branch device.
    :return: Active indices in fixed NABC order.
    """
    phase_mask: List[bool] = list([
        bool(line.ys.phN),
        bool(line.ys.phA),
        bool(line.ys.phB),
        bool(line.ys.phC),
    ])
    active_indices: List[int] = list()
    phase_index: int = 0

    while phase_index < len(phase_mask):
        if phase_mask[phase_index]:
            active_indices.append(phase_index)
        else:
            pass

        phase_index += 1

    return active_indices


def build_uncoupled_line_static_matrices(
        line: dev.Line,
        omega_base: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Build uncoupled fallback line matrices.

    This fallback consumes the line's total positive-sequence ``R``, ``X`` and
    ``B`` values, which are already expressed in per unit. It converts the
    frequency-domain reactance and susceptance into the time-domain EMT
    inductance and half-line capacitance coefficients.

    :param line: Line-like branch device.
    :param omega_base: Base angular frequency.
    :return: Tuple ``(R, L, C)`` in EMT per-unit form.
    """
    r_value: float = float(line.R)
    x_value: float = float(line.X)
    b_value: float = float(line.B)

    r_full: np.ndarray = np.zeros((3, 3), dtype=np.float64)
    x_full: np.ndarray = np.zeros((3, 3), dtype=np.float64)
    bsh_full: np.ndarray = np.zeros((3, 3), dtype=np.float64)
    phase_index: int = 0

    while phase_index < 3:
        r_full[phase_index, phase_index] = r_value
        x_full[phase_index, phase_index] = x_value
        bsh_full[phase_index, phase_index] = b_value
        phase_index += 1

    l_full: np.ndarray = x_full / (omega_base + 1.0e-20)
    c_full: np.ndarray = (bsh_full / (omega_base + 1.0e-20)) / 2.0

    return r_full, l_full, c_full


def build_line_static_matrices(
        grid: MultiCircuit,
        line: dev.Line,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Build line R, L, C and physical G matrices in EMT per-unit form.

    :param grid: Static network model.
    :param line: Line-like branch device.
    :return: Tuple ``(R, L, C, G)`` in reduced active-phase coordinates. C and
        physical G are per-terminal half-shunts; R and L are total series values.
    """
    frequency_base: float = float(grid.fBase)
    omega_base: float = 2.0 * np.pi * frequency_base
    voltage_base: float = float(line.bus_from.Vnom) * 1.0e3
    sbase_va: float = float(grid.Sbase) * 1.0e6
    zbase: float = (voltage_base * voltage_base) / sbase_va
    ybase: float = 1.0 / zbase
    r_full: np.ndarray
    l_full: np.ndarray
    c_full: np.ndarray
    g_full: np.ndarray
    z_phys: np.ndarray | None = None
    y_phys: np.ndarray | None = None

    # EMT line templates consume a phase-domain matrix contract. The canonical
    # static source for that contract is the line three-phase admittance data
    # already stored on the device as ``ys`` and ``ysh``. This must remain true
    # regardless of whether the line came from a tower template, a sequence
    # template or a directly entered balanced positive-sequence R/X/B model,
    # because all of those paths can populate ``ys`` and ``ysh`` consistently.
    z_phys, y_phys = build_physical_line_matrices_from_stored_admittances(
        line=line,
        sbase_mva=float(grid.Sbase),
    )

    if z_phys is None or y_phys is None:
        line_ys_matrix: np.ndarray = line.ys.values
        line_ysh_matrix: np.ndarray = line.ysh.values
        active_indices: List[int] = get_line_active_global_indices(line)
        matrix_size: int = int(line_ys_matrix.shape[0])

        if matrix_size == 4 and len(active_indices) > 0:
            reduced_selector: np.ndarray = np.array(active_indices, dtype=int)
            ys_reduced: np.ndarray = line_ys_matrix[np.ix_(reduced_selector, reduced_selector)]
            ysh_reduced: np.ndarray = line_ysh_matrix[np.ix_(reduced_selector, reduced_selector)]
        else:
            ys_reduced = line_ys_matrix
            ysh_reduced = line_ysh_matrix

        try:
            z_pu: np.ndarray = np.linalg.inv(ys_reduced)
        except np.linalg.LinAlgError:
            z_pu = np.linalg.pinv(ys_reduced)

        ysh_pu: np.ndarray = ysh_reduced
        r_full = np.real(z_pu)
        x_full: np.ndarray = np.imag(z_pu)
        l_full = x_full / (omega_base + 1.0e-20)
        bsh_full: np.ndarray = np.imag(ysh_pu)
        c_full = (bsh_full / (omega_base + 1.0e-20)) / 2.0
        # Stored real shunts use the same historical scale as static compilation.
        g_full = np.real(ysh_pu) * 1.0e-6 / 2.0
    else:
        z_pu = z_phys / zbase
        y_pu = y_phys / ybase
        r_full = np.real(z_pu)
        x_full = np.imag(z_pu)
        l_full = x_full / (omega_base + 1.0e-20)
        bsh_full = np.imag(y_pu)
        c_full = (bsh_full / (omega_base + 1.0e-20)) / 2.0
        # The canonical conversion already recovered total physical admittance.
        g_full = np.real(y_pu) / 2.0

    active_indices: List[int] = get_line_active_global_indices(line)
    matrix_size: int = int(r_full.shape[0])

    if matrix_size == len(active_indices):
        return r_full, l_full, c_full, g_full
    else:
        pass

    if matrix_size == 4:
        reduced_selector: np.ndarray = np.array(active_indices, dtype=int)
        r_reduced: np.ndarray = r_full[np.ix_(reduced_selector, reduced_selector)]
        l_reduced: np.ndarray = l_full[np.ix_(reduced_selector, reduced_selector)]
        c_reduced: np.ndarray = c_full[np.ix_(reduced_selector, reduced_selector)]
        g_reduced: np.ndarray = g_full[np.ix_(reduced_selector, reduced_selector)]
        return r_reduced, l_reduced, c_reduced, g_reduced
    else:
        return r_full, l_full, c_full, g_full


def validate_line_static_matrices(
        line: dev.Line,
        r_full: np.ndarray,
        l_full: np.ndarray,
        c_full: np.ndarray,
        g_full: np.ndarray,
        n_active: int,
        logger: StaticParameterMappingDiagnosticSink | None,
) -> bool:
    """
    Validate reduced line matrix dimensions before assignment.

    :param line: Line-like branch device.
    :param r_full: Reduced resistance matrix.
    :param l_full: Reduced inductance matrix.
    :param c_full: Reduced capacitance matrix.
    :param g_full: Reduced per-terminal physical conductance matrix.
    :param n_active: Number of active physical phases.
    :param logger: Optional logger.
    :return: ``True`` if all matrices match the active-phase shape.
    """
    valid: bool = True
    expected_shape: Tuple[int, int] = (n_active, n_active)
    device_name: str = str(line.name)

    if r_full.shape != expected_shape:
        add_static_mapping_warning(
            logger=logger,
            device_name=device_name,
            message="Line static mapping skipped because R matrix shape is inconsistent.",
            value=str(r_full.shape),
            expected_value=str(expected_shape),
            device_property="line_static_matrix_shape",
        )
        valid = False
    else:
        pass

    if l_full.shape != expected_shape:
        add_static_mapping_warning(
            logger=logger,
            device_name=device_name,
            message="Line static mapping skipped because L matrix shape is inconsistent.",
            value=str(l_full.shape),
            expected_value=str(expected_shape),
            device_property="line_static_matrix_shape",
        )
        valid = False
    else:
        pass

    if c_full.shape != expected_shape:
        add_static_mapping_warning(
            logger=logger,
            device_name=device_name,
            message="Line static mapping skipped because C matrix shape is inconsistent.",
            value=str(c_full.shape),
            expected_value=str(expected_shape),
            device_property="line_static_matrix_shape",
        )
        valid = False
    else:
        pass

    if g_full.shape != expected_shape:
        add_static_mapping_warning(
            logger=logger,
            device_name=device_name,
            message="Line physical conductance mapping skipped because G matrix shape is inconsistent.",
            value=str(g_full.shape),
            expected_value=str(expected_shape),
            device_property="line_static_matrix_shape",
        )
        valid = False
    else:
        pass

    return valid


def assign_common_injection_static_api_mapping(
        grid: MultiCircuit,
        device: ALL_DEV_TYPES,
        mdl: Block,
        problem_mapping: Dict[Var, Const],
        logger: StaticParameterMappingDiagnosticSink | None,
) -> None:
    """
    Assign static parameters inherited from ``InjectionParent``.

    ``injection_connection_type`` is a stable numeric encoding of the static
    connection enum. The inherited ``device_active`` property follows the
    common direct ``GCProp.dyn_ref`` path used by every device family.

    :param grid: Static network model.
    :param device: Injection-like static device.
    :param mdl: EMT block receiving constants.
    :param problem_mapping: mapping to save parameters values in RMS problem
    :param logger: Optional logger.
    :return: None.
    """
    device_name: str = str(device.name)

    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.injection_connection_type,
        value=shunt_connection_code(device.conn),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )


def assign_common_branch_static_api_mapping(
        device: ALL_DEV_TYPES,
        mdl: Block,
        problem_mapping: Dict[Var, Const],
        logger: StaticParameterMappingDiagnosticSink | None,
) -> None:
    """
    Assign contract-sensitive static parameters inherited from ``BranchParent``.

    The inherited ``device_active`` property follows the common direct
    ``GCProp.dyn_ref`` path. This handler is reserved for branch properties
    whose conversion remains explicit in the shared RMS/EMT mapper.

    :param device: Branch-like static device.
    :param mdl: EMT block receiving constants.
    :param problem_mapping: mapping to save parameters values in RMS problem
    :param logger: Optional logger.
    :return: None.
    """
    device_name: str = str(device.name)

    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.branch_rate_mva,
        value=float(device.rate),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.branch_temp_base_deg_c,
        value=float(device.temp_base),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.branch_temp_oper_deg_c,
        value=float(device.temp_oper),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.branch_alpha_per_deg_c,
        value=float(device.alpha),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )


def assign_load_static_api_mapping(
        grid: MultiCircuit,
        load: dev.Load,
        mdl: Block,
        problem_mapping: Dict[Var, Const],
        logger: StaticParameterMappingDiagnosticSink | None,
        direct_assigned_keys: Set[ParamPowerFlowReferenceType],
) -> None:
    """
    Assign static load parameters exposed by ``mdl.api_obj_mapping``.

    :param grid: Static network model.
    :param load: Load device.
    :param mdl: Load EMT block.
    :param problem_mapping: Dictionary that stores each parameter with their value.
    :param logger: Optional logger.
    :return: None.
    """
    device_name: str = str(load.name)
    sbase: float = float(grid.Sbase)

    if load.bus.is_dc:
        # DC loads follow the same ZIP semantics as the generic load device.
        # The constant-power term stays in ``Pl0`` and the impedance term stays
        # in ``g`` so the EMT and RMS representations preserve the user-declared
        # physical meaning instead of silently rewriting one term into another.
        dc_p_value: float = float(load.P) / sbase
        dc_g_value: float = float(load.G) / sbase

        assign_api_mapping_value_if_present(
            mdl=mdl,
            key=ParamPowerFlowReferenceType.Pl0,
            value=dc_p_value,
            logger=logger,
            device_name=device_name,
            problem_mapping=problem_mapping,
        )
        assign_api_mapping_value_if_present(
            mdl=mdl,
            key=ParamPowerFlowReferenceType.g,
            value=dc_g_value,
            logger=logger,
            device_name=device_name,
            problem_mapping=problem_mapping,
        )
    else:
        omega_base: float = 2.0 * np.pi * float(grid.fBase)
        assign_api_mapping_value_if_present(
            mdl=mdl,
            key=ParamPowerFlowReferenceType.Pl0,
            # RMS network injections use generation-positive signs, whereas
            # the static Load API stores consumed P/Q as positive values.
            value=-float(load.P) / sbase,
            logger=logger,
            device_name=device_name,
            problem_mapping=problem_mapping,
        )
        assign_api_mapping_value_if_present(
            mdl=mdl,
            key=ParamPowerFlowReferenceType.Ql0,
            value=-float(load.Q) / sbase,
            logger=logger,
            device_name=device_name,
            problem_mapping=problem_mapping,
        )
        assign_api_mapping_value_if_present(
            mdl=mdl,
            key=ParamPowerFlowReferenceType.omega_base,
            value=omega_base,
            logger=logger,
            device_name=device_name,
            problem_mapping=problem_mapping,
        )


def assign_static_generator_static_api_mapping(
        grid: MultiCircuit,
        static_generator: dev.StaticGenerator,
        mdl: Block,
        problem_mapping: Dict[Var, Const],
        logger: StaticParameterMappingDiagnosticSink | None,
        direct_assigned_keys: Set[ParamPowerFlowReferenceType],
) -> None:
    """
    Assign static StaticGenerator parameters exposed by ``mdl.api_obj_mapping``.

    :param grid: Static network model.
    :param static_generator: Static-generator device.
    :param mdl: EMT block.
    :param logger: Optional logger.
    :return: None.
    """
    device_name: str = str(static_generator.name)
    omega_base: float = 2.0 * np.pi * float(grid.fBase)
    phase_p_pu_abc: np.ndarray
    phase_q_pu_abc: np.ndarray

    phase_p_pu_abc, phase_q_pu_abc = get_load_power_phase_values_pu_abc(load=static_generator, grid=grid)

    assign_common_injection_static_api_mapping(
        grid=grid,
        device=static_generator,
        mdl=mdl,
        problem_mapping=problem_mapping,
        logger=logger,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.Pl0,
        value=float(static_generator.P) / float(grid.Sbase),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.Ql0,
        value=float(static_generator.Q) / float(grid.Sbase),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.Pl0_A,
        value=float(phase_p_pu_abc[0]),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.Pl0_B,
        value=float(phase_p_pu_abc[1]),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.Pl0_C,
        value=float(phase_p_pu_abc[2]),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.Ql0_A,
        value=float(phase_q_pu_abc[0]),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.Ql0_B,
        value=float(phase_q_pu_abc[1]),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.Ql0_C,
        value=float(phase_q_pu_abc[2]),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.omega_base,
        value=omega_base,
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.static_generator_snom_mva,
        value=float(static_generator.Snom),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )


def assign_external_grid_static_api_mapping(
        grid: MultiCircuit,
        external_grid: dev.ExternalGrid,
        mdl: Block,
        problem_mapping: Dict[Var, Const],
        logger: StaticParameterMappingDiagnosticSink | None,
        direct_assigned_keys: Set[ParamPowerFlowReferenceType],
) -> None:
    """
    Assign static ExternalGrid parameters exposed by ``mdl.api_obj_mapping``.

    :param grid: Static network model.
    :param external_grid: External-grid device.
    :param mdl: EMT block.
    :param logger: Optional logger.
    :return: None.
    """
    omega_base: float = 2.0 * np.pi * float(grid.fBase)
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.omega_base,
        value=omega_base,
        logger=logger,
        device_name=str(external_grid.name),
        problem_mapping=problem_mapping,
    )


def assign_shunt_static_api_mapping(
        grid: MultiCircuit,
        shunt: dev.Shunt,
        mdl: Block,
        problem_mapping: Dict[Var, Const],
        logger: StaticParameterMappingDiagnosticSink | None,
        direct_assigned_keys: Set[ParamPowerFlowReferenceType],
) -> None:
    """
    Assign static Shunt parameters exposed by ``mdl.api_obj_mapping``.

    :param grid: Static network model.
    :param shunt: Shunt device.
    :param mdl: EMT block.
    :param logger: Optional logger.
    :return: None.
    """
    _ = direct_assigned_keys

    # The generic direct mapper deliberately leaves the historical ``g`` and
    # ``b`` keys unresolved because they mean series admittance for branches.
    # For a shunt their meaning is unambiguous: the static MW/MVAr-at-1-pu
    # values become system-per-unit conductance and susceptance.
    device_name: str = str(shunt.name)
    for key, value in (
            (ParamPowerFlowReferenceType.g, float(shunt.G) / float(grid.Sbase)),
            (ParamPowerFlowReferenceType.b, float(shunt.B) / float(grid.Sbase)),
    ):
        assign_api_mapping_value_if_present(
            mdl=mdl,
            key=key,
            value=value,
            logger=logger,
            device_name=device_name,
            problem_mapping=problem_mapping,
        )

    # Also support templates using the unambiguous shunt-specific references.
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.shunt_g_pu,
        value=float(shunt.G) / float(grid.Sbase),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.shunt_b_pu,
        value=float(shunt.B) / float(grid.Sbase),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )


def assign_controllable_shunt_static_api_mapping(
        grid: MultiCircuit,
        controllable_shunt: dev.ControllableShunt,
        mdl: Block,
        problem_mapping: Dict[Var, Const],
        logger: StaticParameterMappingDiagnosticSink | None,
        direct_assigned_keys: Set[ParamPowerFlowReferenceType],
) -> None:
    """
    Assign static ControllableShunt parameters exposed by ``mdl.api_obj_mapping``.

    :param problem_mapping:
    :param grid: Static network model.
    :param controllable_shunt: Controllable shunt device.
    :param mdl: EMT block.
    :param logger: Optional logger.
    :return: None.
    """
    device_name: str = str(controllable_shunt.name)
    assign_shunt_static_api_mapping(
        grid=grid,
        shunt=controllable_shunt,
        mdl=mdl,
        problem_mapping=problem_mapping,
        logger=logger,
        direct_assigned_keys=direct_assigned_keys,
    )


def assign_current_injection_static_api_mapping(
        grid: MultiCircuit,
        current_injection: dev.CurrentInjection,
        mdl: Block,
        problem_mapping: Dict[Var, Const],
        logger: StaticParameterMappingDiagnosticSink | None,
        direct_assigned_keys: Set[ParamPowerFlowReferenceType],
) -> None:
    """
    Assign static CurrentInjection parameters exposed by ``mdl.api_obj_mapping``.

    :param grid: Static network model.
    :param current_injection: Current-injection device.
    :param mdl: EMT block.
    :param logger: Optional logger.
    :return: None.
    """
    if direct_assigned_keys is None:
        pass
    else:
        pass


def assign_generator_static_api_mapping(
        grid: MultiCircuit,
        generator: dev.Generator,
        mdl: Block,
        problem_mapping: Dict[Var, Const],
        logger: StaticParameterMappingDiagnosticSink | None,
        direct_assigned_keys: Set[ParamPowerFlowReferenceType],
) -> None:
    """
    Assign static generator parameters exposed by ``mdl.api_obj_mapping``.

    :param problem_mapping:
    :param grid: Static network model.
    :param generator: Generator device.
    :param mdl: Generator EMT block.
    :param logger: Optional logger.
    :return: None.
    """
    device_name: str = str(generator.name)
    omega_base: float = 2.0 * np.pi * float(grid.fBase)

    assign_common_injection_static_api_mapping(
        grid=grid,
        device=generator,
        mdl=mdl,
        problem_mapping=problem_mapping,
        logger=logger,
    )

    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.Sbase,
        value=float(grid.Sbase),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )

    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.omega_base,
        value=omega_base,
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.ws,
        value=omega_base,
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.generator_p_pu,
        value=float(generator.P) / float(grid.Sbase),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.generator_q_pu,
        value=float(generator.Q) / float(grid.Sbase),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.Pmin,
        value=float(generator.Pmin) / float(grid.Sbase),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.Pmax,
        value=float(generator.Pmax) / float(grid.Sbase),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.generator_qmin_pu,
        value=float(generator.Qmin) / float(grid.Sbase),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.generator_qmax_pu,
        value=float(generator.Qmax) / float(grid.Sbase),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.generator_power_factor,
        value=float(generator.Pf),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.generator_vset_pu,
        value=float(generator.Vset),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.generator_snom_mva,
        value=float(generator.Snom),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.pv_rated_power_pu,
        value=float(generator.Snom) / float(grid.Sbase),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.generator_r0_pu,
        value=float(generator.R0),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.generator_r2_pu,
        value=float(generator.R2),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.generator_x2_pu,
        value=float(generator.X2),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.generator_control_mode,
        value=1.0 if bool(generator.is_controlled) else 0.0,
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.generator_enabled_dispatch,
        value=1.0 if bool(generator.enabled_dispatch) else 0.0,
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.generator_must_run,
        value=1.0 if bool(generator.must_run) else 0.0,
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.generator_use_reactive_power_curve,
        value=1.0 if bool(generator.use_reactive_power_curve) else 0.0,
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.generator_device_sbase_mva,
        value=float(generator.Sbase),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.freq,
        value=float(generator.freq),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.R1,
        value=float(generator.R1),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.X1,
        value=float(generator.X1),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.X0,
        value=float(generator.X0),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )


def assign_battery_static_api_mapping(
        grid: MultiCircuit,
        battery: dev.Battery,
        mdl: Block,
        problem_mapping: Dict[Var, Const],
        logger: StaticParameterMappingDiagnosticSink | None,
        direct_assigned_keys: Set[ParamPowerFlowReferenceType],
) -> None:
    """
    Assign static Battery parameters exposed by ``mdl.api_obj_mapping``.

    :param problem_mapping:
    :param grid: Static network model.
    :param battery: Battery device.
    :param mdl: EMT block.
    :param logger: Optional logger.
    :return: None.
    """
    device_name: str = str(battery.name)
    assign_generator_static_api_mapping(
        grid=grid,
        generator=battery,
        mdl=mdl,
        problem_mapping=problem_mapping,
        logger=logger,
        direct_assigned_keys=direct_assigned_keys,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.battery_enom_mwh,
        value=float(battery.Enom),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.battery_soc_0_pu,
        value=float(battery.soc_0),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.battery_max_soc_pu,
        value=float(battery.max_soc),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.battery_min_soc_pu,
        value=float(battery.min_soc),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.battery_charge_efficiency_pu,
        value=float(battery.charge_efficiency),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.battery_discharge_efficiency_pu,
        value=float(battery.discharge_efficiency),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.battery_charge_per_cycle_pu,
        value=float(battery.charge_per_cycle),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.battery_discharge_per_cycle_pu,
        value=float(battery.discharge_per_cycle),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )


def assign_vsc_static_api_mapping(
        grid: MultiCircuit,
        vsc: dev.VSC,
        mdl: Block,
        problem_mapping: Dict[Var, Const],
        logger: StaticParameterMappingDiagnosticSink | None,
        direct_assigned_keys: Set[ParamPowerFlowReferenceType],
) -> None:
    """
    Assign static VSC parameters exposed by ``mdl.api_obj_mapping``.

    Loss coefficients are static device data, unlike the operating-point losses
    and terminal powers that must be obtained from power-flow initialization.

    :param problem_mapping: Destination for resolved initial parameter values.
    :param grid: Static network model.
    :param vsc: VSC device.
    :param mdl: VSC RMS or EMT block exposing the requested static mappings.
    :param logger: Optional logger.
    :param direct_assigned_keys: Keys already handled by the direct property mapper.
    :return: None.
    """
    device_name: str = str(vsc.name)
    omega_base: float = 2.0 * np.pi * float(grid.fBase)

    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.Sbase,
        value=float(grid.Sbase),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.omega_base,
        value=omega_base,
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )

    # The direct mapper deliberately delegates these coefficients to the VSC
    # handler. Resolve the actual device values, including zero, without adding
    # template fallbacks or changing the dynamic event parameters.
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.alpha1,
        value=float(vsc.alpha1),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.alpha2,
        value=float(vsc.alpha2),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.alpha3,
        value=float(vsc.alpha3),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )


def assign_dc_line_static_api_mapping(
        grid: MultiCircuit,
        dc_line: DcLine,
        mdl: Block,
        problem_mapping: Dict[Var, Const],
        logger: StaticParameterMappingDiagnosticSink | None,
        direct_assigned_keys: Set[ParamPowerFlowReferenceType],
) -> None:
    """
    Assign static DC-line parameters exposed by ``mdl.api_obj_mapping``.

    :param grid: Circuit providing the system power base.
    :param dc_line: DC line device.
    :param mdl: DC line EMT block.
    :param logger: Optional logger.
    :return: None.
    """
    device_name: str = str(dc_line.name)
    eps_value: float = 1.0e-12
    resistance_value: float = float(dc_line.R_corrected)
    conductance_value: float = 1.0 / max(abs(resistance_value), eps_value)
    dynamic_values_logger: Logger | None
    if isinstance(logger, StaticParameterMappingDiagnostics):
        # The DC-line helper emits its own physical-model warning, therefore
        # it receives the original driver logger rather than mapping metadata.
        dynamic_values_logger = logger.get_logger()
    else:
        dynamic_values_logger = logger

    dynamic_values: Tuple[float, float] = dc_line.get_dynamic_values_pu_seconds(
        Sbase=float(grid.Sbase),
        logger=dynamic_values_logger,
    )

    assign_common_branch_static_api_mapping(
        device=dc_line,
        mdl=mdl,
        problem_mapping=problem_mapping,
        logger=logger,
    )

    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.g,
        value=conductance_value,
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.b,
        value=0.0,
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.bsh,
        value=0.0,
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.dc_line_r_pu,
        value=resistance_value,
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.dc_line_l_pu_seconds,
        value=float(dynamic_values[0]),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.dc_line_length_km,
        value=float(dc_line.length),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )


def assign_transformer2w_static_api_mapping(
        grid: MultiCircuit,
        transformer: Transformer2W,
        mdl: Block,
        problem_mapping: Dict[Var, Const],
        logger: StaticParameterMappingDiagnosticSink | None,
        direct_assigned_keys: Set[ParamPowerFlowReferenceType],
) -> None:
    """
    Assign static Transformer2W parameters exposed by ``mdl.api_obj_mapping``.

    :param grid: Static network model.
    :param transformer: Two-winding transformer device.
    :param mdl: Transformer EMT block.
    :param logger: Optional logger.
    :param problem_mapping:
    :return: None.
    """

    assign_api_mapping_value_if_present(
        mdl=mdl, key=ParamPowerFlowReferenceType.Sbase, value=float(grid.Sbase),
        logger=logger, device_name=str(transformer.name), problem_mapping=problem_mapping,
    )

    vtap_f, vtap_t = transformer.get_virtual_taps()

    assign_common_branch_static_api_mapping(
        device=transformer,
        mdl=mdl,
        problem_mapping=problem_mapping,
        logger=logger,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.r,
        value=float(transformer.R),
        logger=logger,
        device_name=transformer.name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.x,
        value=float(transformer.X),
        logger=logger,
        device_name=transformer.name,
        problem_mapping=problem_mapping,
    )
    needs_series_admittance: bool = (
        ParamPowerFlowReferenceType.g in mdl.api_obj_mapping
        or ParamPowerFlowReferenceType.b in mdl.api_obj_mapping
    )
    if needs_series_admittance:
        series_impedance_square: float = float(
            transformer.R ** 2 + transformer.X ** 2
        )
        if series_impedance_square > 1.0e-24:
            assign_api_mapping_value_if_present(
                mdl=mdl,
                key=ParamPowerFlowReferenceType.g,
                value=float(transformer.R / series_impedance_square),
                logger=logger,
                device_name=transformer.name,
                problem_mapping=problem_mapping,
            )
            assign_api_mapping_value_if_present(
                mdl=mdl,
                key=ParamPowerFlowReferenceType.b,
                value=float(-transformer.X / series_impedance_square),
                logger=logger,
                device_name=transformer.name,
                problem_mapping=problem_mapping,
            )
        else:
            add_static_mapping_warning(
                logger=logger,
                device_name=str(transformer.name),
                message="Transformer series admittance requires non-zero impedance.",
                value=series_impedance_square,
                expected_value="R squared plus X squared greater than 1e-24",
                device_property="R/X",
            )
    else:
        pass
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.bsh,
        value=float(transformer.B),
        logger=logger,
        device_name=transformer.name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.gFe,
        value=float(transformer.G),
        logger=logger,
        device_name=transformer.name,
        problem_mapping=problem_mapping,
    )

    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.vtap_f,
        value=float(vtap_f),
        logger=logger,
        device_name=transformer.name,
        problem_mapping=problem_mapping,
    )

    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.vtap_t,
        value=float(vtap_t),
        logger=logger,
        device_name=transformer.name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.tap_module,
        value=float(transformer.tap_module),
        logger=logger,
        device_name=transformer.name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.tap_phase,
        value=float(transformer.tap_phase),
        logger=logger,
        device_name=transformer.name,
        problem_mapping=problem_mapping,
    )

    device_name: str = str(transformer.name)
    eps_value: float = 1.0e-12
    omega_base: float = 2.0 * np.pi * float(grid.fBase)
    sn_value: float = max(float(transformer.Sn), 1.0e-9)
    pcu_kw_value: float = max(float(transformer.Pcu), 0.0)
    pfe_kw_value: float = max(float(transformer.Pfe), 0.0)
    i0_pct_value: float = max(float(transformer.I0), 0.0)
    hv_nominal_kv: float
    lv_nominal_kv: float

    if transformer.HV is not None and float(transformer.HV) > eps_value:
        hv_nominal_kv = float(transformer.HV)
    else:
        hv_nominal_kv = float(transformer.bus_from.Vnom)

    if transformer.LV is not None and float(transformer.LV) > eps_value:
        lv_nominal_kv = float(transformer.LV)
    else:
        lv_nominal_kv = float(transformer.bus_to.Vnom)

    tap_module_value: float = float(transformer.tap_module)
    if abs(tap_module_value) <= eps_value:
        tap_module_value = 1.0
    else:
        pass

    tap_phase_value: float = float(transformer.tap_phase)

    if abs(lv_nominal_kv) > eps_value:
        nominal_voltage_ratio: float = hv_nominal_kv / lv_nominal_kv
    else:
        nominal_voltage_ratio = 1.0

    total_voltage_ratio: float = nominal_voltage_ratio * tap_module_value
    total_voltage_ratio_square: float = total_voltage_ratio * total_voltage_ratio
    transformer_r_pu: float = float(transformer.R)
    transformer_x_pu: float = float(transformer.X)
    transformer_g_pu: float = float(transformer.G)
    transformer_b_pu: float = float(transformer.B)

    if float(transformer.Vsc) > 0.0:
        vsc_pct_value: float = float(transformer.Vsc)
    else:
        vsc_pct_value = 100.0 * np.sqrt(
            max(
                transformer_r_pu * transformer_r_pu + transformer_x_pu * transformer_x_pu,
                0.0,
            )
        )

    if pcu_kw_value > 0.0 and sn_value > eps_value:
        short_circuit_resistance_pct: float = pcu_kw_value / (10.0 * sn_value)
    else:
        short_circuit_resistance_pct = 100.0 * transformer_r_pu

    from_connection_matrix: np.ndarray = xfmr_connection_matrix(transformer.conn_f)
    to_connection_matrix: np.ndarray = xfmr_connection_matrix(transformer.conn_t)
    permutation_matrix: np.ndarray = xfmr_phase_permutation_matrix(int(transformer.vector_group_number))
    to_effective_connection_matrix: np.ndarray = permutation_matrix @ to_connection_matrix

    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.omega_base,
        value=omega_base,
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.transformer_rated_power_mva,
        value=sn_value,
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.transformer_winding1_rated_voltage_ll_kv,
        value=hv_nominal_kv,
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.transformer_winding2_rated_voltage_ll_kv,
        value=lv_nominal_kv,
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.transformer_connection_clock,
        value=float(transformer.vector_group_number),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.transformer_open_circuit_current_pct,
        value=i0_pct_value,
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.transformer_open_circuit_loss_kw,
        value=pfe_kw_value,
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.transformer_short_circuit_voltage_pct,
        value=vsc_pct_value,
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.transformer_short_circuit_resistance_pct,
        value=short_circuit_resistance_pct,
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.transformer_short_circuit_loss_kw,
        value=pcu_kw_value,
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.tap_module,
        value=tap_module_value,
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.transformer_nominal_voltage_ratio,
        value=nominal_voltage_ratio,
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.transformer_total_voltage_ratio,
        value=total_voltage_ratio,
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )

    # ``transformer_tap_ratio`` is preserved as a legacy alias for the plain tap
    # module so that existing direct EMT templates keep their historical meaning.
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.transformer_tap_ratio,
        value=tap_module_value,
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )

    if transformer_equivalent_circuit_values_are_requested(mdl=mdl):
        if abs(tap_phase_value) > eps_value:
            add_static_mapping_warning(
                logger=logger,
                device_name=device_name,
                message="Transformer equivalent-circuit derived values skipped because tap_phase is non-zero.",
                value=str(tap_phase_value),
                expected_value="tap_phase close to zero",
                device_property="tap_phase",
            )
        else:
            r1_value: float
            r2_value: float
            l1_value: float
            l2_value: float
            mutual_inductance: float
            g_core: float
            determinant_value: float

            r1_value, r2_value, l1_value, l2_value, mutual_inductance, g_core = compute_transformer_equivalent_circuit_values(
                omega_base=omega_base,
                transformer_r_pu=transformer_r_pu,
                transformer_x_pu=transformer_x_pu,
                transformer_g_pu=transformer_g_pu,
                transformer_b_pu=transformer_b_pu,
                total_voltage_ratio=total_voltage_ratio,
                total_voltage_ratio_square=total_voltage_ratio_square,
                eps_value=eps_value,
            )
            determinant_value = l1_value * l2_value - mutual_inductance * mutual_inductance

            if determinant_value <= eps_value:
                add_static_mapping_warning(
                    logger=logger,
                    device_name=device_name,
                    message="Transformer equivalent-circuit derived inductance values skipped because the inductance matrix is non-physical.",
                    value=str(determinant_value),
                    expected_value="positive inductance matrix determinant",
                    device_property="transformer_equivalent_circuit",
                )
            else:
                assign_api_mapping_value_if_present(
                    mdl=mdl,
                    key=ParamPowerFlowReferenceType.transformer_winding1_resistance_pu,
                    value=r1_value,
                    logger=logger,
                    device_name=device_name,
                    problem_mapping=problem_mapping,
                )
                assign_api_mapping_value_if_present(
                    mdl=mdl,
                    key=ParamPowerFlowReferenceType.transformer_winding2_resistance_pu,
                    value=r2_value,
                    logger=logger,
                    device_name=device_name,
                    problem_mapping=problem_mapping,
                )
                assign_api_mapping_value_if_present(
                    mdl=mdl,
                    key=ParamPowerFlowReferenceType.transformer_winding1_inductance_pu_s,
                    value=l1_value,
                    logger=logger,
                    device_name=device_name,
                    problem_mapping=problem_mapping,
                )
                assign_api_mapping_value_if_present(
                    mdl=mdl,
                    key=ParamPowerFlowReferenceType.transformer_winding2_inductance_pu_s,
                    value=l2_value,
                    logger=logger,
                    device_name=device_name,
                    problem_mapping=problem_mapping,
                )
                assign_api_mapping_value_if_present(
                    mdl=mdl,
                    key=ParamPowerFlowReferenceType.transformer_mutual_inductance_pu_s,
                    value=mutual_inductance,
                    logger=logger,
                    device_name=device_name,
                    problem_mapping=problem_mapping,
                )
                assign_api_mapping_value_if_present(
                    mdl=mdl,
                    key=ParamPowerFlowReferenceType.transformer_magnetizing_conductance_pu,
                    value=g_core,
                    logger=logger,
                    device_name=device_name,
                    problem_mapping=problem_mapping,
                )
    else:
        pass

    assign_3x3_static_matrix(
        mdl=mdl,
        matrix=from_connection_matrix,
        keys=get_transformer_from_connection_keys(),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_3x3_static_matrix(
        mdl=mdl,
        matrix=to_effective_connection_matrix,
        keys=get_transformer_to_connection_keys(),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )


def assign_line_static_api_mapping(
        grid: MultiCircuit,
        line: dev.Line,
        mdl: Block,
        problem_mapping: Dict[Var, Const],
        logger: StaticParameterMappingDiagnosticSink | None,
        direct_assigned_keys: Set[ParamPowerFlowReferenceType],
) -> None:
    """
    Assign static line R, Linv and C parameters exposed by ``api_obj_mapping``.

    The physical reduced matrix is projected into the fixed 4x4 NABC API-object
    contract. Exposed inactive-phase entries are explicitly zeroed, preserving the
    previous template semantics while allowing partial key subsets.

    :param problem_mapping:
    :param grid: Static network model.
    :param line: Line-like branch device.
    :param mdl: Line EMT block.
    :param logger: Optional logger.
    :return: None.
    """
    device_name: str = str(line.name)

    assign_common_branch_static_api_mapping(
        device=line,
        mdl=mdl,
        problem_mapping=problem_mapping,
        logger=logger,
    )

    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.g,
        value=float(line.R / (line.R ** 2 + line.X ** 2)),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.r,
        value=float(line.R),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.l,
        value=float(line.X),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.line_length_km,
        value=float(line.length),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.b,
        value=float(-line.X / (line.R ** 2 + line.X ** 2)),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.bsh,
        value=float(line.B),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )
    # Unlike injection G, Line.G is already the total system per-unit shunt.
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.shunt_g_pu,
        value=float(line.G),
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )

    active_indices: List[int] = get_line_active_global_indices(line)
    n_active: int = len(active_indices)

    if n_active == 0:
        add_static_mapping_warning(
            logger=logger,
            device_name=device_name,
            message="Line static mapping skipped because no physical phases are active.",
            value="0 active phases",
            expected_value="at least one active phase",
            device_property="line_phases",
        )
    else:
        r_full: np.ndarray
        l_full: np.ndarray
        c_full: np.ndarray
        g_full: np.ndarray
        r_full, l_full, c_full, g_full = build_line_static_matrices(
            grid=grid,
            line=line,
        )

        matrices_are_valid: bool = validate_line_static_matrices(
            line=line,
            r_full=r_full,
            l_full=l_full,
            c_full=c_full,
            g_full=g_full,
            n_active=n_active,
            logger=logger,
        )

        if matrices_are_valid:
            # Project physical shunts independently of unrequested series inversion.
            # Inactive exposed slots remain zero in the fixed NABC contract.
            g_keys: List[List[ParamPowerFlowReferenceType]] = get_line_g_keys()
            g_nabc: np.ndarray = np.zeros((4, 4), dtype=np.float64)
            phase_selector: np.ndarray = np.array(active_indices, dtype=int)
            g_nabc[np.ix_(phase_selector, phase_selector)] = g_full
            g_row: int
            g_col: int
            for g_row in range(4):
                for g_col in range(4):
                    assign_api_mapping_value_if_present(
                        mdl=mdl,
                        key=g_keys[g_row][g_col],
                        value=float(g_nabc[g_row, g_col]),
                        logger=logger,
                        device_name=device_name,
                        problem_mapping=problem_mapping,
                    )
        else:
            pass

        legacy_matrices_requested: bool = (
            api_mapping_has_any_key(mdl=mdl, keys=flatten_matrix_keys(get_line_r_keys()))
            or api_mapping_has_any_key(mdl=mdl, keys=flatten_matrix_keys(get_line_linv_keys()))
            or api_mapping_has_any_key(mdl=mdl, keys=flatten_matrix_keys(get_line_c_keys()))
        )
        if matrices_are_valid and legacy_matrices_requested:
            linv_full: np.ndarray

            try:
                # The physically meaningful criterion is invertibility, not the
                # absolute determinant magnitude. Small but diagonal inductance
                # matrices are valid after per-unit scaling and should not be
                # rejected only because their determinant is numerically tiny.
                linv_full = np.linalg.inv(l_full)
            except np.linalg.LinAlgError:
                determinant_value: float = float(np.linalg.det(l_full))
                add_static_mapping_warning(
                    logger=logger,
                    device_name=device_name,
                    message="Line static mapping skipped because inductance matrix is singular.",
                    value=str(determinant_value),
                    expected_value="invertible inductance matrix",
                    device_property="line_inductance_matrix",
                )
            else:
                r_keys: List[List[ParamPowerFlowReferenceType]] = get_line_r_keys()
                linv_keys: List[List[ParamPowerFlowReferenceType]] = get_line_linv_keys()
                c_keys: List[List[ParamPowerFlowReferenceType]] = get_line_c_keys()

                # First zero every exposed slot of the fixed NABC map. This is
                # important for templates that expose inactive neutral/phase keys.
                global_row: int = 0
                while global_row < 4:
                    global_col: int = 0

                    while global_col < 4:
                        assign_api_mapping_value_if_present(
                            mdl=mdl,
                            key=r_keys[global_row][global_col],
                            value=0.0,
                            logger=logger,
                            device_name=device_name,
                            problem_mapping=problem_mapping,
                        )
                        assign_api_mapping_value_if_present(
                            mdl=mdl,
                            key=linv_keys[global_row][global_col],
                            value=0.0,
                            logger=logger,
                            device_name=device_name,
                            problem_mapping=problem_mapping,
                        )
                        assign_api_mapping_value_if_present(
                            mdl=mdl,
                            key=c_keys[global_row][global_col],
                            value=0.0,
                            logger=logger,
                            device_name=device_name,
                            problem_mapping=problem_mapping,
                        )
                        global_col += 1

                    global_row += 1

                # Then project reduced active-phase values into the fixed NABC
                # contract. Only keys requested by the EMT model are written.
                reduced_row: int = 0
                while reduced_row < n_active:
                    mapped_global_row: int = active_indices[reduced_row]
                    reduced_col: int = 0

                    while reduced_col < n_active:
                        mapped_global_col: int = active_indices[reduced_col]

                        assign_api_mapping_value_if_present(
                            mdl=mdl,
                            key=r_keys[mapped_global_row][mapped_global_col],
                            value=float(r_full[reduced_row, reduced_col]),
                            logger=logger,
                            device_name=device_name,
                            problem_mapping=problem_mapping,
                        )
                        assign_api_mapping_value_if_present(
                            mdl=mdl,
                            key=linv_keys[mapped_global_row][mapped_global_col],
                            value=float(linv_full[reduced_row, reduced_col]),
                            logger=logger,
                            device_name=device_name,
                            problem_mapping=problem_mapping,
                        )
                        assign_api_mapping_value_if_present(
                            mdl=mdl,
                            key=c_keys[mapped_global_row][mapped_global_col],
                            value=float(c_full[reduced_row, reduced_col]),
                            logger=logger,
                            device_name=device_name,
                            problem_mapping=problem_mapping,
                        )
                        reduced_col += 1

                    reduced_row += 1
        else:
            pass


def assign_hvdc_line_static_api_mapping(
        hvdc_line: dev.HvdcLine,
        mdl: Block,
        problem_mapping: Dict[Var, Const],
        logger: StaticParameterMappingDiagnosticSink | None,
) -> None:
    """
    Intentionally leave HVDC-line static mapping as a no-op.

    Reachability exists in the EMT builder, but there is no established EMT
    template/static-key contract for ``HvdcLine`` yet.

    :param hvdc_line: HVDC-line device.
    :param mdl: EMT block.
    :param logger: Optional logger.
    :return: None.
    """
    if logger is None:
        pass
    else:
        pass


def assign_series_reactance_static_api_mapping(
        series_reactance: dev.SeriesReactance,
        mdl: Block,
        problem_mapping: Dict[Var, Const],
        logger: StaticParameterMappingDiagnosticSink | None,
) -> None:
    """
    Intentionally leave series-reactance static mapping as a no-op.

    Reachability exists in the EMT builder, but there is no established EMT
    template/static-key contract for ``SeriesReactance`` yet.

    :param series_reactance: Series-reactance device.
    :param mdl: EMT block.
    :param problem_mapping: Dictionary with static parameters and their values
    :param logger: Optional logger.
    :return: None.
    """
    if logger is None:
        pass
    else:
        pass


def assign_switch_static_api_mapping(
        switch: dev.Switch,
        mdl: Block,
        problem_mapping: Dict[Var, Const],
        logger: StaticParameterMappingDiagnosticSink | None,
        direct_assigned_keys: Set[ParamPowerFlowReferenceType],
) -> None:
    """
    Assign static switch parameters exposed by ``mdl.api_obj_mapping``.

    The EMT switch template uses a closed-state conductance parameter in its
    dynamic current equation. The static switch device exposes series
    resistance and reactance in p.u., therefore the EMT template must receive
    the real part of the corresponding series admittance so the reduced EMT
    branch remains consistent with the static device data.

    :param switch: Switch device.
    :param mdl: EMT block.
    :param problem_mapping: Dictionary with static parameters and their values
    :param logger: Optional logger.
    :return: None.
    """
    device_name: str = str(switch.name)
    resistance_value: float = float(switch.R)
    reactance_value: float = float(switch.X)
    impedance_sq_value: float = resistance_value * resistance_value + reactance_value * reactance_value
    eps_value: float = 1.0e-12
    conductance_value: float

    # The switch still inherits the common branch static fields such as active
    # state and rating. Those values are assigned first so the EMT branch keeps
    # the same metadata contract as the other branch-like templates.
    assign_common_branch_static_api_mapping(
        device=switch,
        mdl=mdl,
        problem_mapping=problem_mapping,
        logger=logger,
    )

    # The reduced EMT switch stores only a conductance, so the static R/X data
    # must be projected to the real part of the branch admittance. The epsilon
    # guard avoids a singular division for near-ideal static switches.
    if impedance_sq_value > eps_value:
        conductance_value = resistance_value / impedance_sq_value
    else:
        conductance_value = 1.0 / eps_value

    # The EMT template explicitly requests this quantity through the static
    # ParamPowerFlowReferenceType.g key, so the standard static API-object
    # assignment path must populate the constant-parameter mapping.
    assign_api_mapping_value_if_present(
        mdl=mdl,
        key=ParamPowerFlowReferenceType.g,
        value=conductance_value,
        logger=logger,
        device_name=device_name,
        problem_mapping=problem_mapping,
    )


def assign_upfc_static_api_mapping(
        upfc: dev.UPFC,
        mdl: Block,
        problem_mapping: Dict[Var, Const],
        logger: StaticParameterMappingDiagnosticSink | None,
) -> None:
    """
    Intentionally leave UPFC static mapping as a no-op.

    Reachability exists in the EMT builder, but there is no established EMT
    template/static-key contract for ``Upfc`` yet.

    :param upfc: UPFC device.
    :param mdl: EMT block.
    :param problem_mapping: Dictionary with static parameters and their values
    :param logger: Optional logger.
    :return: None.
    """
    if logger is None:
        pass
    else:
        pass
