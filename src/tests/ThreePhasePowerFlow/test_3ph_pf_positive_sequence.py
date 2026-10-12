import os
import numpy as np
import pandas as pd
import VeraGridEngine.api as vge
from VeraGridEngine.IO.file_open import FileOpen
from VeraGridEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions


TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')


def test_3bus_ps_3ph() -> None:
    '''
    This test executes a positive-sequence and a three-phase power flow simulations into a 3-bus simple system
    and compares the results between both solvers.
    '''
    grid = vge.MultiCircuit()

    # ----------------------------------------------------------------------------------------------------------------------
    # Buses
    # ----------------------------------------------------------------------------------------------------------------------
    bus_slack = vge.Bus(name='Slack', xpos=0, ypos=0)
    bus_slack.is_slack = True
    grid.add_bus(obj=bus_slack)

    bus_pv = vge.Bus(name='PV', xpos=0, ypos=200)
    grid.add_bus(obj=bus_pv)

    bus_pq = vge.Bus(name='PQ', xpos=0, ypos=200)
    grid.add_bus(obj=bus_pq)

    # ----------------------------------------------------------------------------------------------------------------------
    # Generators
    # ----------------------------------------------------------------------------------------------------------------------
    gen_slack = vge.Generator()
    grid.add_generator(bus=bus_slack, api_obj=gen_slack)

    gen_pv = vge.Generator(P=5, control_mode=vge.GeneratorControlMode.V,
                          r0=0.01, x0=0.08, r2=0.02, x2=0.10)
    grid.add_generator(bus=bus_pv, api_obj=gen_pv)

    # ----------------------------------------------------------------------------------------------------------------------
    # Line
    # ----------------------------------------------------------------------------------------------------------------------
    line_slack_pv = vge.Line(bus_from=bus_slack,
                             bus_to=bus_pv,
                             name='Slack-PV',
                             r=0.1,
                             x=1.0,
                             b=0.1)
    grid.add_line(obj=line_slack_pv)

    line_slack_pq = vge.Line(bus_from=bus_slack,
                             bus_to=bus_pq,
                             name='Slack-PQ',
                             r=0.1,
                             x=1.0,
                             b=0.1)
    grid.add_line(obj=line_slack_pq)

    line_pv_pq = vge.Line(bus_from=bus_pv,
                          bus_to=bus_pq,
                          name='PV-PQ',
                          r=0.1,
                          x=1.0,
                          b=0.1)
    grid.add_line(obj=line_pv_pq)

    # ----------------------------------------------------------------------------------------------------------------------
    # Load
    # ----------------------------------------------------------------------------------------------------------------------
    load = vge.Load(P=10.0,
                    Q=5.0)
    grid.add_load(bus=bus_pq, api_obj=load)

    # ----------------------------------------------------------------------------------------------------------------------
    # Run power flow
    # ----------------------------------------------------------------------------------------------------------------------
    res_ps = vge.power_flow(grid=grid, options=vge.PowerFlowOptions())
    v_ps = np.abs(res_ps.voltage)

    # ----------------------------------------------------------------------------------------------------------------------
    # Run three-phase power flow
    # ----------------------------------------------------------------------------------------------------------------------
    res_3ph = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions())
    v_3ph_a = np.abs(res_3ph.voltage_A)
    v_3ph_b = np.abs(res_3ph.voltage_B)
    v_3ph_c = np.abs(res_3ph.voltage_C)

    # ----------------------------------------------------------------------------------------------------------------------
    # Comparison
    # ----------------------------------------------------------------------------------------------------------------------
    assert np.allclose(v_ps, v_3ph_a, atol=1e-4)
    assert np.allclose(v_ps, v_3ph_b, atol=1e-4)
    assert np.allclose(v_ps, v_3ph_c, atol=1e-4)


def test_3bus_ps_3ph_with_q_control_enabled() -> None:
    """
    Three-phase NR power flow must keep its internal S0 state when Q control is enabled.
    """
    grid = vge.MultiCircuit()

    bus_slack = vge.Bus(name='Slack', xpos=0, ypos=0)
    bus_slack.is_slack = True
    grid.add_bus(obj=bus_slack)

    bus_pv = vge.Bus(name='PV', xpos=0, ypos=200)
    grid.add_bus(obj=bus_pv)

    bus_pq = vge.Bus(name='PQ', xpos=0, ypos=200)
    grid.add_bus(obj=bus_pq)

    gen_slack = vge.Generator()
    grid.add_generator(bus=bus_slack, api_obj=gen_slack)

    gen_pv = vge.Generator(P=5.0, control_mode=vge.GeneratorControlMode.V,
                          r0=0.01, x0=0.08, r2=0.02, x2=0.10)
    grid.add_generator(bus=bus_pv, api_obj=gen_pv)

    grid.add_line(obj=vge.Line(bus_from=bus_slack, bus_to=bus_pv, name='Slack-PV', r=0.1, x=1.0, b=0.1))
    grid.add_line(obj=vge.Line(bus_from=bus_slack, bus_to=bus_pq, name='Slack-PQ', r=0.1, x=1.0, b=0.1))
    grid.add_line(obj=vge.Line(bus_from=bus_pv, bus_to=bus_pq, name='PV-PQ', r=0.1, x=1.0, b=0.1))

    load = vge.Load(P=10.0, Q=5.0)
    grid.add_load(bus=bus_pq, api_obj=load)

    options = vge.PowerFlowOptions(
        solver_type=vge.SolverType.NR,
        control_q=True,
        retry_with_other_methods=False,
        verbose=0,
    )

    res_3ph = vge.power_flow3ph(grid=grid, options=options)

    assert np.all(np.isfinite(np.abs(res_3ph.voltage_A)))
    assert np.all(np.isfinite(np.abs(res_3ph.voltage_B)))
    assert np.all(np.isfinite(np.abs(res_3ph.voltage_C)))


def test_ieee_grids_3ph() -> None:
    """
    Checks the .RAW files of IEEE grids against the PSS/e results
    This test checks 2 things:
    - PSS/e import fidelity
    - PSS/e vs VeraGrid results, for both positive-sequence and three-phase methods
    """

    files = [
        ('IEEE 14 bus.raw', 'IEEE 14 bus.sav.xlsx'),
        ('IEEE 30 bus.raw', 'IEEE 30 bus.sav.xlsx'),
        ('IEEE 118 Bus v2.raw', 'IEEE 118 Bus.sav.xlsx'),
    ]

    options = PowerFlowOptions(verbose=0,
                               control_q=False,
                               retry_with_other_methods=False)

    for f1, f2 in files:
        print(f1, end=' ')

        fname = os.path.join(TEST_DATA_DIR, 'grids', 'RAW', f1)
        main_circuit = FileOpen(fname).open()

        # These balanced RAW fixtures do not include sequence machine data.
        # Complete the test inputs; Z0/Z2 do not affect the balanced reference solution.
        generator: vge.Generator
        for generator in main_circuit.generators:
            generator.R0, generator.X0 = 0.01, 0.08
            generator.R2, generator.X2 = 0.02, 0.10

        # vge.save_file(grid=main_circuit, filename='positive_sequence_3ph_pf.veragrid')

        # Positive-sequence power flow
        res_ps = vge.power_flow(grid=main_circuit, options=options)
        v_ps = np.abs(res_ps.voltage)

        # Three-phase power flow
        res_3ph = vge.power_flow3ph(grid=main_circuit, options=options)
        v_3ph_a = np.abs(res_3ph.voltage_A)
        v_3ph_b = np.abs(res_3ph.voltage_B)
        v_3ph_c = np.abs(res_3ph.voltage_C)

        # load the associated results file
        df_v = pd.read_excel(os.path.join(TEST_DATA_DIR, 'results', f2), sheet_name='Vabs', index_col=0)
        v_psse = df_v.values[:, 0]

        # comparison
        assert np.allclose(v_3ph_a, v_3ph_b, atol=1e-4) # Voltage of phase A against voltage of phase B
        assert np.allclose(v_3ph_b, v_3ph_c, atol=1e-4)  # Voltage of phase B against voltage of phase C
        assert np.allclose(v_3ph_c, v_3ph_a, atol=1e-4)  # Voltage of phase C against voltage of phase A
        assert np.allclose(v_3ph_a, v_ps, atol=1e-4)  # Voltage of phase A against voltage of positive-sequence
        assert np.allclose(v_3ph_a, v_psse, atol=1e-4)  # Voltage of phase A against voltage of PSSE
