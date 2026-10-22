# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""
Aggregate RAW object typing aliases across supported PSSE versions.
"""

from typing import TypeAlias
from VeraGridEngine.IO.raw.versioned.base.sub import RawSub
from VeraGridEngine.IO.raw.versioned.base.mon import RawMon
from VeraGridEngine.IO.raw.versioned.base.con_ import RawCon
from VeraGridEngine.IO.raw.versioned.base.dyr import RawDyr
from VeraGridEngine.IO.raw.versioned.base.seq import RawSeq
from VeraGridEngine.IO.raw.versioned.base.rop import RawRop
from VeraGridEngine.IO.raw.versioned.base.gcp import RawGcp
from VeraGridEngine.IO.raw.versioned.base.loc import RawLoc

from VeraGridEngine.IO.raw.versioned.v29.area import RawAreaV29
from VeraGridEngine.IO.raw.versioned.v29.zone import RawZoneV29
from VeraGridEngine.IO.raw.versioned.v29.bus import RawBusV29
from VeraGridEngine.IO.raw.versioned.v29.load import RawLoadV29
from VeraGridEngine.IO.raw.versioned.v29.fixed_shunt import RawFixedShuntV29
from VeraGridEngine.IO.raw.versioned.v29.generator import RawGeneratorV29
from VeraGridEngine.IO.raw.versioned.v29.switched_shunt import RawSwitchedShuntV29
from VeraGridEngine.IO.raw.versioned.v29.transformer import RawTransformerV29
from VeraGridEngine.IO.raw.versioned.v29.branch import RawBranchV29
from VeraGridEngine.IO.raw.versioned.v29.vsc_dc_line import RawVscDCLineV29
from VeraGridEngine.IO.raw.versioned.v29.two_terminal_dc_line import RawTwoTerminalDCLineV29
from VeraGridEngine.IO.raw.versioned.v29.facts import RawFACTSV29
from VeraGridEngine.IO.raw.versioned.v29.system_switching_device import RawSystemSwitchingDeviceV29
from VeraGridEngine.IO.raw.versioned.v29.induction_machine import RawInductionMachineV29
from VeraGridEngine.IO.raw.versioned.v29.inter_area import RawInterAreaV29
from VeraGridEngine.IO.raw.versioned.v29.owner import RawOwnerV29
from VeraGridEngine.IO.raw.versioned.v29.substation import RawSubstationV29
from VeraGridEngine.IO.raw.versioned.v29.gne_device import RawGneDeviceV29
from VeraGridEngine.IO.raw.versioned.v29.impedance_correction_table import RawImpedanceCorrectionTableV29
from VeraGridEngine.IO.raw.versioned.v29.multi_section_line import RawMultiLineSectionV29
from VeraGridEngine.IO.raw.versioned.v30.area import RawAreaV30
from VeraGridEngine.IO.raw.versioned.v30.zone import RawZoneV30
from VeraGridEngine.IO.raw.versioned.v30.bus import RawBusV30
from VeraGridEngine.IO.raw.versioned.v30.load import RawLoadV30
from VeraGridEngine.IO.raw.versioned.v30.fixed_shunt import RawFixedShuntV30
from VeraGridEngine.IO.raw.versioned.v30.generator import RawGeneratorV30
from VeraGridEngine.IO.raw.versioned.v30.switched_shunt import RawSwitchedShuntV30
from VeraGridEngine.IO.raw.versioned.v30.transformer import RawTransformerV30
from VeraGridEngine.IO.raw.versioned.v30.branch import RawBranchV30
from VeraGridEngine.IO.raw.versioned.v30.vsc_dc_line import RawVscDCLineV30
from VeraGridEngine.IO.raw.versioned.v30.two_terminal_dc_line import RawTwoTerminalDCLineV30
from VeraGridEngine.IO.raw.versioned.v30.facts import RawFACTSV30
from VeraGridEngine.IO.raw.versioned.v30.system_switching_device import RawSystemSwitchingDeviceV30
from VeraGridEngine.IO.raw.versioned.v30.induction_machine import RawInductionMachineV30
from VeraGridEngine.IO.raw.versioned.v30.inter_area import RawInterAreaV30
from VeraGridEngine.IO.raw.versioned.v30.owner import RawOwnerV30
from VeraGridEngine.IO.raw.versioned.v30.substation import RawSubstationV30
from VeraGridEngine.IO.raw.versioned.v30.gne_device import RawGneDeviceV30
from VeraGridEngine.IO.raw.versioned.v30.impedance_correction_table import RawImpedanceCorrectionTableV30
from VeraGridEngine.IO.raw.versioned.v30.multi_section_line import RawMultiLineSectionV30
from VeraGridEngine.IO.raw.versioned.v31.area import RawAreaV31
from VeraGridEngine.IO.raw.versioned.v31.zone import RawZoneV31
from VeraGridEngine.IO.raw.versioned.v31.bus import RawBusV31
from VeraGridEngine.IO.raw.versioned.v31.load import RawLoadV31
from VeraGridEngine.IO.raw.versioned.v31.fixed_shunt import RawFixedShuntV31
from VeraGridEngine.IO.raw.versioned.v31.generator import RawGeneratorV31
from VeraGridEngine.IO.raw.versioned.v31.switched_shunt import RawSwitchedShuntV31
from VeraGridEngine.IO.raw.versioned.v31.transformer import RawTransformerV31
from VeraGridEngine.IO.raw.versioned.v31.branch import RawBranchV31
from VeraGridEngine.IO.raw.versioned.v31.vsc_dc_line import RawVscDCLineV31
from VeraGridEngine.IO.raw.versioned.v31.two_terminal_dc_line import RawTwoTerminalDCLineV31
from VeraGridEngine.IO.raw.versioned.v31.facts import RawFACTSV31
from VeraGridEngine.IO.raw.versioned.v31.system_switching_device import RawSystemSwitchingDeviceV31
from VeraGridEngine.IO.raw.versioned.v31.induction_machine import RawInductionMachineV31
from VeraGridEngine.IO.raw.versioned.v31.inter_area import RawInterAreaV31
from VeraGridEngine.IO.raw.versioned.v31.owner import RawOwnerV31
from VeraGridEngine.IO.raw.versioned.v31.substation import RawSubstationV31
from VeraGridEngine.IO.raw.versioned.v31.gne_device import RawGneDeviceV31
from VeraGridEngine.IO.raw.versioned.v31.impedance_correction_table import RawImpedanceCorrectionTableV31
from VeraGridEngine.IO.raw.versioned.v31.multi_section_line import RawMultiLineSectionV31
from VeraGridEngine.IO.raw.versioned.v32.area import RawAreaV32
from VeraGridEngine.IO.raw.versioned.v32.zone import RawZoneV32
from VeraGridEngine.IO.raw.versioned.v32.bus import RawBusV32
from VeraGridEngine.IO.raw.versioned.v32.load import RawLoadV32
from VeraGridEngine.IO.raw.versioned.v32.fixed_shunt import RawFixedShuntV32
from VeraGridEngine.IO.raw.versioned.v32.generator import RawGeneratorV32
from VeraGridEngine.IO.raw.versioned.v32.switched_shunt import RawSwitchedShuntV32
from VeraGridEngine.IO.raw.versioned.v32.transformer import RawTransformerV32
from VeraGridEngine.IO.raw.versioned.v32.branch import RawBranchV32
from VeraGridEngine.IO.raw.versioned.v32.vsc_dc_line import RawVscDCLineV32
from VeraGridEngine.IO.raw.versioned.v32.two_terminal_dc_line import RawTwoTerminalDCLineV32
from VeraGridEngine.IO.raw.versioned.v32.facts import RawFACTSV32
from VeraGridEngine.IO.raw.versioned.v32.system_switching_device import RawSystemSwitchingDeviceV32
from VeraGridEngine.IO.raw.versioned.v32.induction_machine import RawInductionMachineV32
from VeraGridEngine.IO.raw.versioned.v32.inter_area import RawInterAreaV32
from VeraGridEngine.IO.raw.versioned.v32.owner import RawOwnerV32
from VeraGridEngine.IO.raw.versioned.v32.substation import RawSubstationV32
from VeraGridEngine.IO.raw.versioned.v32.gne_device import RawGneDeviceV32
from VeraGridEngine.IO.raw.versioned.v32.impedance_correction_table import RawImpedanceCorrectionTableV32
from VeraGridEngine.IO.raw.versioned.v32.multi_section_line import RawMultiLineSectionV32
from VeraGridEngine.IO.raw.versioned.v33.area import RawAreaV33
from VeraGridEngine.IO.raw.versioned.v33.zone import RawZoneV33
from VeraGridEngine.IO.raw.versioned.v33.bus import RawBusV33
from VeraGridEngine.IO.raw.versioned.v33.load import RawLoadV33
from VeraGridEngine.IO.raw.versioned.v33.fixed_shunt import RawFixedShuntV33
from VeraGridEngine.IO.raw.versioned.v33.generator import RawGeneratorV33
from VeraGridEngine.IO.raw.versioned.v33.switched_shunt import RawSwitchedShuntV33
from VeraGridEngine.IO.raw.versioned.v33.transformer import RawTransformerV33
from VeraGridEngine.IO.raw.versioned.v33.branch import RawBranchV33
from VeraGridEngine.IO.raw.versioned.v33.vsc_dc_line import RawVscDCLineV33
from VeraGridEngine.IO.raw.versioned.v33.two_terminal_dc_line import RawTwoTerminalDCLineV33
from VeraGridEngine.IO.raw.versioned.v33.facts import RawFACTSV33
from VeraGridEngine.IO.raw.versioned.v33.system_switching_device import RawSystemSwitchingDeviceV33
from VeraGridEngine.IO.raw.versioned.v33.induction_machine import RawInductionMachineV33
from VeraGridEngine.IO.raw.versioned.v33.inter_area import RawInterAreaV33
from VeraGridEngine.IO.raw.versioned.v33.owner import RawOwnerV33
from VeraGridEngine.IO.raw.versioned.v34.node import RawNodeV34
from VeraGridEngine.IO.raw.versioned.v34.substation_switching_device import RawSubstationSwitchingDeviceV34
from VeraGridEngine.IO.raw.versioned.v34.equipment_terminal import RawEquipmentTerminalV34
from VeraGridEngine.IO.raw.versioned.v33.substation import RawSubstationV33
from VeraGridEngine.IO.raw.versioned.v33.gne_device import RawGneDeviceV33
from VeraGridEngine.IO.raw.versioned.v33.impedance_correction_table import RawImpedanceCorrectionTableV33
from VeraGridEngine.IO.raw.versioned.v33.multi_section_line import RawMultiLineSectionV33
from VeraGridEngine.IO.raw.versioned.v34.area import RawAreaV34
from VeraGridEngine.IO.raw.versioned.v34.zone import RawZoneV34
from VeraGridEngine.IO.raw.versioned.v34.bus import RawBusV34
from VeraGridEngine.IO.raw.versioned.v34.load import RawLoadV34
from VeraGridEngine.IO.raw.versioned.v34.fixed_shunt import RawFixedShuntV34
from VeraGridEngine.IO.raw.versioned.v34.generator import RawGeneratorV34
from VeraGridEngine.IO.raw.versioned.v34.switched_shunt import RawSwitchedShuntV34
from VeraGridEngine.IO.raw.versioned.v34.transformer import RawTransformerV34
from VeraGridEngine.IO.raw.versioned.v34.branch import RawBranchV34
from VeraGridEngine.IO.raw.versioned.v34.vsc_dc_line import RawVscDCLineV34
from VeraGridEngine.IO.raw.versioned.v34.two_terminal_dc_line import RawTwoTerminalDCLineV34
from VeraGridEngine.IO.raw.versioned.v34.facts import RawFACTSV34
from VeraGridEngine.IO.raw.versioned.v34.system_switching_device import RawSystemSwitchingDeviceV34
from VeraGridEngine.IO.raw.versioned.v34.induction_machine import RawInductionMachineV34
from VeraGridEngine.IO.raw.versioned.v34.inter_area import RawInterAreaV34
from VeraGridEngine.IO.raw.versioned.v34.owner import RawOwnerV34
from VeraGridEngine.IO.raw.versioned.v34.substation import RawSubstationV34
from VeraGridEngine.IO.raw.versioned.v34.gne_device import RawGneDeviceV34
from VeraGridEngine.IO.raw.versioned.v34.impedance_correction_table import RawImpedanceCorrectionTableV34
from VeraGridEngine.IO.raw.versioned.v34.multi_section_line import RawMultiLineSectionV34
from VeraGridEngine.IO.raw.versioned.v35.area import RawAreaV35
from VeraGridEngine.IO.raw.versioned.v35.zone import RawZoneV35
from VeraGridEngine.IO.raw.versioned.v35.bus import RawBusV35
from VeraGridEngine.IO.raw.versioned.v35.load import RawLoadV35
from VeraGridEngine.IO.raw.versioned.v35.fixed_shunt import RawFixedShuntV35
from VeraGridEngine.IO.raw.versioned.v35.generator import RawGeneratorV35
from VeraGridEngine.IO.raw.versioned.v35.switched_shunt import RawSwitchedShuntV35
from VeraGridEngine.IO.raw.versioned.v35.transformer import RawTransformerV35
from VeraGridEngine.IO.raw.versioned.v35.branch import RawBranchV35
from VeraGridEngine.IO.raw.versioned.v35.vsc_dc_line import RawVscDCLineV35
from VeraGridEngine.IO.raw.versioned.v35.two_terminal_dc_line import RawTwoTerminalDCLineV35
from VeraGridEngine.IO.raw.versioned.v35.facts import RawFACTSV35
from VeraGridEngine.IO.raw.versioned.v35.system_switching_device import RawSystemSwitchingDeviceV35
from VeraGridEngine.IO.raw.versioned.v35.induction_machine import RawInductionMachineV35
from VeraGridEngine.IO.raw.versioned.v35.inter_area import RawInterAreaV35
from VeraGridEngine.IO.raw.versioned.v35.owner import RawOwnerV35
from VeraGridEngine.IO.raw.versioned.v35.node import RawNodeV35
from VeraGridEngine.IO.raw.versioned.v35.substation_switching_device import RawSubstationSwitchingDeviceV35
from VeraGridEngine.IO.raw.versioned.v35.equipment_terminal import RawEquipmentTerminalV35
from VeraGridEngine.IO.raw.versioned.v35.substation import RawSubstationV35
from VeraGridEngine.IO.raw.versioned.v35.gne_device import RawGneDeviceV35
from VeraGridEngine.IO.raw.versioned.v35.impedance_correction_table import RawImpedanceCorrectionTableV35
from VeraGridEngine.IO.raw.versioned.v35.multi_section_line import RawMultiLineSectionV35
from VeraGridEngine.IO.raw.versioned.v36.area import RawAreaV36
from VeraGridEngine.IO.raw.versioned.v36.zone import RawZoneV36
from VeraGridEngine.IO.raw.versioned.v36.bus import RawBusV36
from VeraGridEngine.IO.raw.versioned.v36.load import RawLoadV36
from VeraGridEngine.IO.raw.versioned.v36.fixed_shunt import RawFixedShuntV36
from VeraGridEngine.IO.raw.versioned.v36.generator import RawGeneratorV36
from VeraGridEngine.IO.raw.versioned.v36.switched_shunt import RawSwitchedShuntV36
from VeraGridEngine.IO.raw.versioned.v36.transformer import RawTransformerV36
from VeraGridEngine.IO.raw.versioned.v36.branch import RawBranchV36
from VeraGridEngine.IO.raw.versioned.v36.vsc_dc_line import RawVscDCLineV36
from VeraGridEngine.IO.raw.versioned.v36.two_terminal_dc_line import RawTwoTerminalDCLineV36
from VeraGridEngine.IO.raw.versioned.v36.facts import RawFACTSV36
from VeraGridEngine.IO.raw.versioned.v36.system_switching_device import RawSystemSwitchingDeviceV36
from VeraGridEngine.IO.raw.versioned.v36.induction_machine import RawInductionMachineV36
from VeraGridEngine.IO.raw.versioned.v36.inter_area import RawInterAreaV36
from VeraGridEngine.IO.raw.versioned.v36.owner import RawOwnerV36
from VeraGridEngine.IO.raw.versioned.v36.node import RawNodeV36
from VeraGridEngine.IO.raw.versioned.v36.substation_switching_device import RawSubstationSwitchingDeviceV36
from VeraGridEngine.IO.raw.versioned.v36.equipment_terminal import RawEquipmentTerminalV36
from VeraGridEngine.IO.raw.versioned.v36.substation import RawSubstationV36
from VeraGridEngine.IO.raw.versioned.v36.gne_device import RawGneDeviceV36
from VeraGridEngine.IO.raw.versioned.v36.impedance_correction_table import RawImpedanceCorrectionTableV36
from VeraGridEngine.IO.raw.versioned.v36.multi_section_line import RawMultiLineSectionV36

RawAreaLike: TypeAlias = RawAreaV29 | RawAreaV30 | RawAreaV31 | RawAreaV32 | RawAreaV33 | RawAreaV34 | RawAreaV35 | RawAreaV36
RawZoneLike: TypeAlias = RawZoneV29 | RawZoneV30 | RawZoneV31 | RawZoneV32 | RawZoneV33 | RawZoneV34 | RawZoneV35 | RawZoneV36
RawBusLike: TypeAlias = RawBusV29 | RawBusV30 | RawBusV31 | RawBusV32 | RawBusV33 | RawBusV34 | RawBusV35 | RawBusV36
RawLoadLike: TypeAlias = RawLoadV29 | RawLoadV30 | RawLoadV31 | RawLoadV32 | RawLoadV33 | RawLoadV34 | RawLoadV35 | RawLoadV36
RawFixedShuntLike: TypeAlias = RawFixedShuntV29 | RawFixedShuntV30 | RawFixedShuntV31 | RawFixedShuntV32 | RawFixedShuntV33 | RawFixedShuntV34 | RawFixedShuntV35 | RawFixedShuntV36
RawGeneratorLike: TypeAlias = RawGeneratorV29 | RawGeneratorV30 | RawGeneratorV31 | RawGeneratorV32 | RawGeneratorV33 | RawGeneratorV34 | RawGeneratorV35 | RawGeneratorV36
RawSwitchedShuntLike: TypeAlias = RawSwitchedShuntV29 | RawSwitchedShuntV30 | RawSwitchedShuntV31 | RawSwitchedShuntV32 | RawSwitchedShuntV33 | RawSwitchedShuntV34 | RawSwitchedShuntV35 | RawSwitchedShuntV36
RawTransformerLike: TypeAlias = RawTransformerV29 | RawTransformerV30 | RawTransformerV31 | RawTransformerV32 | RawTransformerV33 | RawTransformerV34 | RawTransformerV35 | RawTransformerV36
RawBranchLike: TypeAlias = RawBranchV29 | RawBranchV30 | RawBranchV31 | RawBranchV32 | RawBranchV33 | RawBranchV34 | RawBranchV35 | RawBranchV36
RawVscDCLineLike: TypeAlias = RawVscDCLineV29 | RawVscDCLineV30 | RawVscDCLineV31 | RawVscDCLineV32 | RawVscDCLineV33 | RawVscDCLineV34 | RawVscDCLineV35 | RawVscDCLineV36
RawTwoTerminalDCLineLike: TypeAlias = RawTwoTerminalDCLineV29 | RawTwoTerminalDCLineV30 | RawTwoTerminalDCLineV31 | RawTwoTerminalDCLineV32 | RawTwoTerminalDCLineV33 | RawTwoTerminalDCLineV34 | RawTwoTerminalDCLineV35 | RawTwoTerminalDCLineV36
RawFACTSLike: TypeAlias = RawFACTSV29 | RawFACTSV30 | RawFACTSV31 | RawFACTSV32 | RawFACTSV33 | RawFACTSV34 | RawFACTSV35 | RawFACTSV36
RawSystemSwitchingDeviceLike: TypeAlias = RawSystemSwitchingDeviceV29 | RawSystemSwitchingDeviceV30 | RawSystemSwitchingDeviceV31 | RawSystemSwitchingDeviceV32 | RawSystemSwitchingDeviceV33 | RawSystemSwitchingDeviceV34 | RawSystemSwitchingDeviceV35 | RawSystemSwitchingDeviceV36
RawInductionMachineLike: TypeAlias = RawInductionMachineV29 | RawInductionMachineV30 | RawInductionMachineV31 | RawInductionMachineV32 | RawInductionMachineV33 | RawInductionMachineV34 | RawInductionMachineV35 | RawInductionMachineV36
RawInterAreaLike: TypeAlias = RawInterAreaV29 | RawInterAreaV30 | RawInterAreaV31 | RawInterAreaV32 | RawInterAreaV33 | RawInterAreaV34 | RawInterAreaV35 | RawInterAreaV36
RawOwnerLike: TypeAlias = RawOwnerV29 | RawOwnerV30 | RawOwnerV31 | RawOwnerV32 | RawOwnerV33 | RawOwnerV34 | RawOwnerV35 | RawOwnerV36
RawSubstationLike: TypeAlias = RawSubstationV29 | RawSubstationV30 | RawSubstationV31 | RawSubstationV32 | RawSubstationV33 | RawSubstationV34 | RawSubstationV35 | RawSubstationV36
RawNodeLike: TypeAlias = RawNodeV34 | RawNodeV35 | RawNodeV36
RawSubstationSwitchingDeviceLike: TypeAlias = (
    RawSubstationSwitchingDeviceV34 | RawSubstationSwitchingDeviceV35 | RawSubstationSwitchingDeviceV36
)
RawEquipmentTerminalLike: TypeAlias = RawEquipmentTerminalV34 | RawEquipmentTerminalV35 | RawEquipmentTerminalV36
RawGneDeviceLike: TypeAlias = RawGneDeviceV29 | RawGneDeviceV30 | RawGneDeviceV31 | RawGneDeviceV32 | RawGneDeviceV33 | RawGneDeviceV34 | RawGneDeviceV35 | RawGneDeviceV36
RawImpedanceCorrectionTableLike: TypeAlias = RawImpedanceCorrectionTableV29 | RawImpedanceCorrectionTableV30 | RawImpedanceCorrectionTableV31 | RawImpedanceCorrectionTableV32 | RawImpedanceCorrectionTableV33 | RawImpedanceCorrectionTableV34 | RawImpedanceCorrectionTableV35 | RawImpedanceCorrectionTableV36
RawMultiLineSectionLike: TypeAlias = RawMultiLineSectionV29 | RawMultiLineSectionV30 | RawMultiLineSectionV31 | RawMultiLineSectionV32 | RawMultiLineSectionV33 | RawMultiLineSectionV34 | RawMultiLineSectionV35 | RawMultiLineSectionV36

# Concrete v33-v36 documents inherit these bases and retain their own grammar.
PsseAuxiliaryDocument: TypeAlias = RawSub | RawMon | RawCon | RawDyr | RawSeq | RawRop | RawGcp | RawLoc
