# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.Templates.Emt.load_RLC_emt_template import (get_shunt_c_emt_template,
                                                                 get_ground_emt_template,
                                                                 get_grounding_link_emt_template,
                                                                 get_shunt_l_emt_template,
                                                                 get_shunt_r_emt_template,
                                                                 get_shunt_rlc_combo_emt_template, )
from VeraGridEngine.Templates.Emt.generator_emt_type_template import (get_simple_generator_emt_template,
                                                                       get_generator_sauer_pai_type_emt_template,
                                                                       get_exciter_emt,
                                                                       get_governor_emt,
                                                                       get_stabilizer_emt,
                                                                       get_complete_generator_template_emt)
from VeraGridEngine.Templates.Emt.stamp_synchronous_generator_emt_template import (get_stamp_synchronous_generator_emt_template,
                                                                                   get_stamp_synchronous_machine_6th_order_emt_template,
                                                                                   get_stamp_ac4a_exciter_emt,
                                                                                   get_stamp_ieeeg1_governor_emt,
                                                                                   get_stamp_pss2a_emt)
from VeraGridEngine.Templates.Emt.load_exponential_emt_template import get_exponential_load_emt
from VeraGridEngine.Templates.Emt.load_zip_emt_template import get_load_ZIP_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Templates.Emt.converter_emt_template import get_emt_ideal_converter, get_full_pseudo_emt_converter
from VeraGridEngine.Templates.Emt.converter_switched_emt_template import get_switched_emt_converter
from VeraGridEngine.Templates.Emt.bridge_2level_3ph_emt_template import get_bridge_2level_3ph_emt_template
from VeraGridEngine.Templates.Emt.bridge_filter_2level_3ph_emt_template import get_bridge_filter_2level_3ph_emt_template
from VeraGridEngine.Templates.Emt.bridge_filter_control_2level_3ph_emt_template import get_bridge_filter_control_2level_3ph_emt_template
from VeraGridEngine.Templates.Emt.dc_load_emt_template import get_dc_load_emt_template
from VeraGridEngine.Templates.Emt.dc_line_emt_template import get_dc_line_emt_template, get_dc_line_with_power_input_emt_template
from VeraGridEngine.Templates.Emt.dc_source_emt_template import get_controlled_dc_current_source_emt_template
from VeraGridEngine.Templates.Emt.dc_source_emt_template import get_controlled_dc_voltage_source_emt_template
from VeraGridEngine.Templates.Emt.dc_source_emt_template import get_dc_current_source_emt_template
from VeraGridEngine.Templates.Emt.dc_source_emt_template import get_dc_voltage_source_emt_template
from VeraGridEngine.Templates.Emt.balanced_source_emt_template import get_balanced_3ph_current_source_emt_template
from VeraGridEngine.Templates.Emt.balanced_source_emt_template import get_balanced_3ph_voltage_source_emt_template
from VeraGridEngine.Templates.Emt.balanced_source_emt_template import get_controlled_balanced_3ph_current_source_emt_template
from VeraGridEngine.Templates.Emt.balanced_source_emt_template import get_controlled_balanced_3ph_voltage_source_emt_template
from VeraGridEngine.Templates.Emt.arbitrary_source_emt_template import get_arbitrary_waveform_current_source_emt_template
from VeraGridEngine.Templates.Emt.arbitrary_source_emt_template import get_arbitrary_waveform_voltage_source_emt_template
from VeraGridEngine.Templates.Emt.transient_source_emt_template import get_cigre_surge_current_source_emt_template
from VeraGridEngine.Templates.Emt.transient_source_emt_template import get_double_exponential_current_source_emt_template
from VeraGridEngine.Templates.Emt.transient_source_emt_template import get_heidler_current_source_emt_template
from VeraGridEngine.Templates.Emt.transient_source_emt_template import get_ramp_current_source_emt_template
from VeraGridEngine.Templates.Emt.transient_source_emt_template import get_ramp_voltage_source_emt_template
from VeraGridEngine.Templates.Emt.transient_source_emt_template import get_step_current_source_emt_template
from VeraGridEngine.Templates.Emt.transient_source_emt_template import get_step_voltage_source_emt_template
from VeraGridEngine.Templates.Emt.source_emt_template import get_controlled_current_source_emt_template
from VeraGridEngine.Templates.Emt.source_emt_template import get_controlled_voltage_source_emt_template
from VeraGridEngine.Templates.Emt.source_emt_template import get_current_source_emt_template
from VeraGridEngine.Templates.Emt.source_emt_template import get_voltage_source_emt_template
from VeraGridEngine.Templates.Emt.switch_emt_template import get_switch_emt_template
from VeraGridEngine.Templates.Emt.fault_emt_template import get_fault_emt_template
from VeraGridEngine.Templates.Emt.nonlinear_resistor_emt_template import get_nonlinear_resistor_emt_template
from VeraGridEngine.Templates.Emt.valve_emt_template import get_valve_emt_template
from VeraGridEngine.Templates.Emt.transformer_emt_template import get_transformer_emt_template
from VeraGridEngine.Templates.Emt.xfmr_emt_template import get_xfmr_emt_template
from VeraGridEngine.Templates.Emt.induction_motor_emt_template import (get_induction_motor_emt_template,
                                                                       get_induction_motor_double_cage_emt_template,
                                                                       get_induction_motor_single_cage_emt_template)
from VeraGridEngine.Templates.Emt.bergeron_line_emt_template import get_bergeron_line_emt_template
from VeraGridEngine.Templates.Emt.jmarti_line_emt_template import get_jmarti_line_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.bess_avm_emt_template import get_bess_avm_grid_following_emt_template, get_battery_avm_emt_template
from VeraGridEngine.Templates.Emt.pv_emt_template import (get_pv_grid_following_emt_template,
                                                          get_pv_avm_grid_following_emt_template,
                                                          get_pv_avm_boost_grid_following_emt_template)
from VeraGridEngine.Templates.Emt.vsc_gfm_emt import get_gfm_emt_template
from VeraGridEngine.Templates.Emt.emt_gfm_upc import build_emt_gfm_aggregated_model
from VeraGridEngine.Templates.Emt.empty_emt_template import get_empty_emt_template
from VeraGridEngine.Templates.Emt.arbitrary_source_emt_template import ArbitraryWaveformVoltageSourceEmtTemplate, ArbitraryWaveformCurrentSourceEmtTemplate
from VeraGridEngine.Templates.Emt.balanced_source_emt_template import  Balanced3phCurrentSourceEmtTemplate, ControlledBalanced3phCurrentSourceEmtTemplate, Balanced3phVoltageSourceEmtTemplate, ControlledBalanced3phVoltageSourceEmtTemplate
from VeraGridEngine.Templates.Emt.dc_source_emt_template import DcCurrentSourceEmtTemplate, ControlledDcVoltageSourceEmtTemplate, DcVoltageSourceEmtTemplate, ControlledDcCurrentSourceEmtTemplate
from VeraGridEngine.Templates.Emt.induction_motor_emt_template import InductionMotorEmtTemplate
from VeraGridEngine.Templates.Emt.load_zip_emt_template import LoadZIPEmtTemplate
from VeraGridEngine.Templates.Emt.load_exponential_emt_template import ExponentialLoadEmtTemplate
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import GroundingLinkEmtTemplate, ShuntRComboEmtTemplate, ShuntLComboEmtTemplate, ShuntCComboEmtTemplate
from VeraGridEngine.Templates.Emt.source_emt_template import ControlledCurrentSourceEmtTemplate, ControlledVoltageSourceEmtTemplate, VoltageSourceEmtTemplate, CurrentSourceEmtTemplate
from VeraGridEngine.Templates.Emt.switch_emt_template import SwitchEmtTemplate
from VeraGridEngine.Templates.Emt.transient_source_emt_template import StepVoltageSourceEmtTemplate, StepCurrentSourceEmtTemplate, RampVoltageSourceEmtTemplate, RampCurrentSourceEmtTemplate, DoubleExponentialCurrentSourceEmtTemplate, HeidlerCurrentSourceEmtTemplate, CigreSurgeCurrentSourceEmtTemplate
from VeraGridEngine.Templates.Emt.fault_emt_template import FaultEmtTemplate
from VeraGridEngine.Templates.Emt.transformer_emt_template import TransformerEmtTemplate, get_transformer_emt_template
from VeraGridEngine.Templates.Emt.xfmr_emt_template import XfmrEmtTemplate, get_xfmr_emt_template
from VeraGridEngine.Templates.Emt.bergeron_line_emt_template import BergeronLineEmtTemplate
from VeraGridEngine.Templates.Emt.pi_line_emt_template import PiLineEmtTemplate
from VeraGridEngine.Templates.Emt.nonlinear_resistor_emt_template import NonLinearResistorEmtTemplate, get_nonlinear_resistor_emt_template
from VeraGridEngine.Templates.Emt.jmarti_line_emt_template import JmartiLineEmtTemplate
from VeraGridEngine.Templates.BasicBlockCatalog.lookup_array_runtime_templates import LookupArrayLinearRuntimeTemplate, InverseLookupArrayLinearRuntimeTemplate, LookupArraySplineRuntimeTemplate, LookupMatrixLinearRuntimeTemplate, LookupMatrixSplineRuntimeTemplate
