import numpy as np
import pandas as pd
import networkx as nx
import GridCalEngine as gce

import warnings

# Suppress all warnings
warnings.filterwarnings("ignore")


def CreateGrid(load=True):
    Vbase = 10  # kV
    Sbase = 100
    # zbase = Vbase ** 2 / Sbase  # Calculate base impedance
    # length_km = 1

    # ru1 = 0.01 * length_km / zbase
    # ru2 = 0.02 * length_km / zbase
    # ru3 = 0.03 * length_km / zbase
    # xu1 = 0.03 * length_km / zbase
    # xu2 = 0.05 * length_km / zbase
    # xu3 = 0.08 * length_km / zbase
    # cu = 0

    m_circuit = gce.MultiCircuit()
    m_circuit.Sbase = Sbase
    b1 = gce.Bus('b1', Vnom=Vbase, is_slack=True)
    b2 = gce.Bus('b2', Vnom=Vbase)
    b3 = gce.Bus('b3', Vnom=Vbase)
    m_circuit.add_bus(b1)
    m_circuit.add_bus(b2)
    m_circuit.add_bus(b3)

    br0 = gce.Line(b1, b2, name='l1')
    br0.fill_design_properties(r_ohm=0.01, x_ohm=0.03, c_nf=0.0,
                               length=1.0, Imax=1.0, freq=m_circuit.fBase, Sbase=m_circuit.Sbase)
    br1 = gce.Line(b1, b3, name='l2')
    br1.fill_design_properties(r_ohm=0.02, x_ohm=0.05, c_nf=0.0,
                               length=1.0, Imax=1.0, freq=m_circuit.fBase, Sbase=m_circuit.Sbase)
    br2 = gce.Line(b2, b3, name='l3')
    br2.fill_design_properties(r_ohm=0.03, x_ohm=0.08, c_nf=0.0,
                               length=1.0, Imax=1.0, freq=m_circuit.fBase, Sbase=m_circuit.Sbase)
    m_circuit.add_line(br0)
    m_circuit.add_line(br1)
    m_circuit.add_line(br2)

    if load:
        load1 = gce.Load('load 1', P=50, Q=30)
        load2 = gce.Load('load 2', P=150, Q=80)
        m_circuit.add_load(b2, load1)
        m_circuit.add_load(b3, load2)

    return m_circuit


def ExecutePF(grid, show=False):
    options = gce.PowerFlowOptions(gce.SolverType.NR, verbose=False, retry_with_other_methods=False)
    power_flow = gce.PowerFlowDriver(grid, options)
    power_flow.run()

    losses = power_flow.results.losses.sum()
    bus_df = power_flow.results.get_bus_df()
    branch_df = power_flow.results.get_branch_df()
    if show:
        print('Converged:', power_flow.results.converged, 'error:', power_flow.results.error)
        print(losses)
        print(bus_df)
        print(branch_df)

    return losses, bus_df, branch_df


print("Red con cargas , se ejecuta PF para ver el resultado y comparar con la estimación de estado")
m_circuit1 = CreateGrid(load=True)
losses, bus_df, branch_df = ExecutePF(m_circuit1, show=True)

print("\\n")
print("creo una red sin cargas y les añado medidas, con los valores de pandapower")
m_circuit2 = CreateGrid(load=False)
m_circuit2.add_vm_measurement(gce.Devices.VmMeasurement(1.006, 0.004, m_circuit2.buses[0]))
m_circuit2.add_vm_measurement(gce.Devices.VmMeasurement(0.968, 0.004, m_circuit2.buses[1]))
m_circuit2.add_pi_measurement(gce.Devices.PiMeasurement(0.501, 0.010, m_circuit2.buses[1]))
m_circuit2.add_qi_measurement(gce.Devices.QiMeasurement(0.286, 0.010, m_circuit2.buses[1]))
m_circuit2.add_pf_measurement(gce.Devices.PfMeasurement(0.888, 0.008, m_circuit2.lines[0]))
m_circuit2.add_pf_measurement(gce.Devices.PfMeasurement(1.173, 0.008, m_circuit2.lines[1]))
m_circuit2.add_qf_measurement(gce.Devices.QfMeasurement(0.568, 0.008, m_circuit2.lines[0]))
m_circuit2.add_qf_measurement(gce.Devices.QfMeasurement(0.663, 0.008, m_circuit2.lines[1]))
# Declare the simulation driver and run
se = gce.StateEstimation(circuit=m_circuit2)
se.run()
print('Converged:', se.results.converged, 'error:', se.results.error)
print(se.results.get_bus_df())
# print(se.results.get_branch_df())
print("\\n")
print("de momento no he creado la red con medidas con ruido")
