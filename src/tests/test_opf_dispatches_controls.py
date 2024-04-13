# GridCal
# Copyright (C) 2024 Santiago Peñate Vera
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
import os
from GridCalEngine.api import *
from GridCalEngine.enumerations import HvdcControlType, TransformerControlType, TapAngleControl


def test_opf_hvdc():
    fname = os.path.join('data', 'grids', 'IEEE39_hvdc.gridcal')

    main_circuit = FileOpen(fname).open()

    power_flow_options = PowerFlowOptions(SolverType.NR,
                                          verbose=False,
                                          initialize_with_existing_solution=False,
                                          multi_core=False,
                                          dispatch_storage=True,
                                          control_q=ReactivePowerControlMode.NoControl,
                                          control_p=True,
                                          retry_with_other_methods=False)

    opf_options = OptimalPowerFlowOptions(verbose=False,
                                          solver=SolverType.LINEAR_OPF,
                                          power_flow_options=power_flow_options,
                                          mip_solver=MIPSolvers.CBC,
                                          generate_report=True)

    # HVDC dispatch on
    main_circuit.hvdc_lines[0].dispatchable = True

    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()

    pf_on = opf.results.hvdc_Pf[0]

    # HVDC dispatch off
    main_circuit.hvdc_lines[0].dispatchable = False

    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()

    pf_off = opf.results.hvdc_Pf[0]

    # check that no error or warning is generated
    assert opf.logger.error_count() == 0
    assert pf_on != pf_off
    assert np.isclose(pf_off, 0.0, atol=1e-5)


def test_opf_gen():
    fname = os.path.join('data', 'grids', 'IEEE39_hvdc.gridcal')

    main_circuit = FileOpen(fname).open()

    power_flow_options = PowerFlowOptions(SolverType.NR,
                                          verbose=False,
                                          initialize_with_existing_solution=False,
                                          multi_core=False,
                                          dispatch_storage=True,
                                          control_q=ReactivePowerControlMode.NoControl,
                                          control_p=True,
                                          retry_with_other_methods=False)

    opf_options = OptimalPowerFlowOptions(verbose=False,
                                          solver=SolverType.LINEAR_OPF,
                                          power_flow_options=power_flow_options,
                                          mip_solver=MIPSolvers.CBC,
                                          generate_report=True)

    # Gen dispatch on
    main_circuit.generators[0].enabled_dispatch = True
    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()
    pgen_on = opf.results.generator_power[0]

    # Gen dispatch off
    main_circuit.generators[0].enabled_dispatch = False
    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()
    pgen_off = opf.results.generator_power[0]

    # Gen dispatch back on
    main_circuit.generators[0].enabled_dispatch = True
    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()
    pgen_on2 = opf.results.generator_power[0]

    assert opf.logger.error_count() == 0
    assert pgen_on != pgen_off
    assert np.isclose(pgen_on, pgen_on2, atol=1e-10)


def test_opf_line_monitoring():
    fname = os.path.join('data', 'grids', 'IEEE39_hvdc.gridcal')

    main_circuit = FileOpen(fname).open()

    power_flow_options = PowerFlowOptions(SolverType.NR,
                                          verbose=False,
                                          initialize_with_existing_solution=False,
                                          multi_core=False,
                                          dispatch_storage=True,
                                          control_q=ReactivePowerControlMode.NoControl,
                                          control_p=True,
                                          retry_with_other_methods=False)

    opf_options = OptimalPowerFlowOptions(verbose=False,
                                          solver=SolverType.LINEAR_OPF,
                                          power_flow_options=power_flow_options,
                                          mip_solver=MIPSolvers.CBC,
                                          generate_report=True)

    # branch 2 monitoring on
    br_idx = 2
    main_circuit.lines[br_idx].monitor_loading = True
    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()
    pf_on = opf.results.Sf[br_idx]

    # HVDC dispatch off
    main_circuit.lines[br_idx].monitor_loading = False
    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()
    pf_off = opf.results.Sf[br_idx]

    # HVDC dispatch back on
    main_circuit.lines[br_idx].monitor_loading = True
    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()
    pf_on2 = opf.results.Sf[br_idx]

    # check that no error or warning is generated
    assert opf.logger.error_count() == 0
    assert pf_on != pf_off
    assert np.isclose(pf_on, pf_on2, atol=1e-10)


def test_opf_hvdc_controls():
    fname = os.path.join('data', 'grids', 'IEEE39_hvdc.gridcal')

    main_circuit = FileOpen(fname).open()

    power_flow_options = PowerFlowOptions(SolverType.NR,
                                          verbose=False,
                                          initialize_with_existing_solution=False,
                                          multi_core=False,
                                          dispatch_storage=True,
                                          control_q=ReactivePowerControlMode.NoControl,
                                          control_p=True,
                                          retry_with_other_methods=False)

    opf_options = OptimalPowerFlowOptions(verbose=False,
                                          solver=SolverType.LINEAR_OPF,
                                          power_flow_options=power_flow_options,
                                          mip_solver=MIPSolvers.CBC,
                                          generate_report=True)

    # HVDC free mode
    main_circuit.hvdc_lines[0].control_mode = HvdcControlType.type_0_free
    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()
    pf_free = opf.results.hvdc_Pf[0]

    # HVDC Pset mode
    main_circuit.hvdc_lines[0].control_mode = HvdcControlType.type_1_Pset
    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()
    pf_pset = opf.results.hvdc_Pf[0]

    # HVDC Pset mode non dispatchable
    main_circuit.hvdc_lines[0].dispatchable = False
    main_circuit.hvdc_lines[0].control_mode = HvdcControlType.type_1_Pset
    main_circuit.hvdc_lines[0].Pset = 50  # MW
    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()
    pf_pset2 = opf.results.hvdc_Pf[0]

    # check that no error or warning is generated
    assert opf.logger.error_count() == 0
    assert pf_free != pf_pset
    assert np.isclose(abs(pf_pset), main_circuit.hvdc_lines[0].rate, atol=1e-3)
    assert np.isclose(pf_pset2, 50, atol=1e-5)


def test_opf_trafo_controls():
    fname = os.path.join('data', 'grids', 'IEEE39_trafo.gridcal')

    main_circuit = FileOpen(fname).open()

    power_flow_options = PowerFlowOptions(SolverType.NR,
                                          verbose=False,
                                          initialize_with_existing_solution=False,
                                          multi_core=False,
                                          dispatch_storage=True,
                                          control_q=ReactivePowerControlMode.NoControl,
                                          control_p=True,
                                          retry_with_other_methods=False)

    opf_options = OptimalPowerFlowOptions(verbose=False,
                                          solver=SolverType.LINEAR_OPF,
                                          power_flow_options=power_flow_options,
                                          mip_solver=MIPSolvers.CBC,
                                          generate_report=True)

    # trafo fixed
    main_circuit.transformers2w[0].control_mode = TransformerControlType.fixed
    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()
    pf1 = opf.results.Sf[48]

    # trafo controlling
    main_circuit.transformers2w[0].control_mode = TransformerControlType.Pf
    main_circuit.transformers2w[0].tap_angle_control_mode = TapAngleControl.Pf
    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()
    pf2 = opf.results.Sf[48]

    # trafo back to fixed
    main_circuit.transformers2w[0].control_mode = TransformerControlType.fixed
    opf = OptimalPowerFlowDriver(grid=main_circuit,
                                 options=opf_options)
    opf.run()
    pf3 = opf.results.Sf[48]

    # check that no error or warning is generated
    assert opf.logger.error_count() == 0
    assert pf1 != pf2
    assert np.isclose(pf1, pf3, atol=1e-3)

