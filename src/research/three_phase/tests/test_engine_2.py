"""
5 buses test of fully unbalanced grid with multiple phases conductors and transposition
"""
from research.three_phase.Engine import *

if __name__ == "__main__":

    # declare buses and their attached devices
    b0 = Bus("B0", number_of_phases=3, Vnom=10.0, is_slack=True)
    b0.add_generator(Generator("", P=np.array([2.5, 2.5, 2.5]), v=1.01, conn=[0, 1, 2], conn_type=Connection.Delta))

    b1 = Bus("B1", number_of_phases=3, Vnom=10.0)

    b2 = Bus("B2", number_of_phases=3, Vnom=10.0)
    b2.add_load(LoadSIY("",
                        S=np.array([2+2j, 2+2j, 2+2j]) / 100,
                        I=np.array([0, 0, 0]),
                        Y=np.array([0, 0, 0]),
                        conn=[0, 1, 2],
                        conn_type=Connection.Delta))

    b3 = Bus("B3", number_of_phases=1, Vnom=10.0)
    b3.add_load(LoadSIY("",
                        S=np.array([1.2]) / 100,
                        I=np.array([0]),
                        Y=np.array([0]),
                        conn=[0]))

    # b3 = Bus("B3", number_of_phases=3, Vnom=10.0)
    # b3.add_load(LoadSIY("",
    #                     S=np.array([1.2, 1, 1.3]) / 100,
    #                     I=np.array([0, 0, 0]),
    #                     Y=np.array([0, 0, 0]),
    #                     conn=[0, 1, 2]))

    b4 = Bus("B4", number_of_phases=2, Vnom=10.0)
    b4.add_load(LoadSIY("",
                        S=np.array([2.2 + 1.2j, 2.2 + 1.2j]) / 100,
                        I=np.array([0, 0]),
                        Y=np.array([0, 0]),
                        conn=[0, 1],
                        conn_type=Connection.Delta))

    # line types
    line_t3 = LineTypeABC(name="three phase line type", phases=3,
                          zABC=np.array([[0.4013 + 1.4133j, 0.0953 + 0.8515j, 0.0953 + 0.7266j],
                                         [0.0953 + 0.8515j, 0.4013 + 1.4133j, 0.0943 + 0.7802j],
                                         [0.0953 + 0.7266j, 0.0953 + 0.7802j, 0.4013 + 1.4133j]]),
                          ysh_ABC=np.array([[5.6712j, -1.8362j, -0.7034j],
                                            [-1.8362j, 5.9774j, -1.169j],
                                            [-0.7034j, -1.169j, 5.3911j]]) * 1e-6)

    line_t2 = LineTypeABC(name="two phase line type", phases=2,
                          zABC=np.array([[0.4013 + 1.4133j, 0.0953 + 0.8515j],
                                         [0.0953 + 0.8515j, 0.4013 + 1.4133j]]),
                          ysh_ABC=np.array([[5.6712j, -1.8362j],
                                            [-1.8362j, 5.9774j]]) * 1e-6)

    line_t1 = LineTypeABC(name="single phase line type", phases=1,
                          zABC=np.array([[0.4013 + 1.4133j]]),
                          ysh_ABC=np.array([[5.6712j]]) * 1e-6)

    # declare lines
    lne1 = Line("L1", line_t3, bus_from=b0, bus_to=b1, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=10.0, rating=10)
    lne2 = Line("L2", line_t3, bus_from=b1, bus_to=b2, conn_from=[0, 1, 2], conn_to=[1, 2, 0], length=10.0, rating=20)
    lne3 = Line("L3", line_t1, bus_from=b1, bus_to=b3, conn_from=[2], conn_to=[0], length=10.0, rating=30)
    lne4 = Line("L4", line_t2, bus_from=b2, bus_to=b4, conn_from=[0, 1], conn_to=[0, 1], length=10.0, rating=40)

    circuit_ = Circuit(Sbase=100)
    circuit_.buses.append(b0)
    circuit_.buses.append(b1)
    circuit_.buses.append(b2)
    circuit_.buses.append(b3)
    circuit_.buses.append(b4)

    circuit_.branches.append(lne1)
    circuit_.branches.append(lne2)
    circuit_.branches.append(lne3)
    circuit_.branches.append(lne4)

    data = circuit_.compile()

    power_flow = PowerFlow(circuit_)
    results = power_flow.run(method=PowerFlowMethods.NewtonRaphson, verbose=True, max_iter=10)

    print('\nVoltage solution')
    print('converged', results.converged, ', err:', results.error)
    print(np.abs(results.V))

    print('\nPacked voltages per bus')
    Vpack = circuit_.pack_node_solution(results.V)
    for i in range(len(circuit_.buses)):
        print(str(circuit_.buses[i]), ':', abs(Vpack[i]), ' p.u. ->\t', abs(Vpack[i]) * circuit_.buses[i].Vnom, 'kV')

    print('\nPacked power per bus')
    Spack = circuit_.pack_node_solution(results.Sbus)
    for i in range(len(circuit_.buses)):
        print(str(circuit_.buses[i]), ':', Spack[i].real, ' p.u. ->\t', Spack[i].real * circuit_.Sbase, 'MW')

    print('\nPacked branch power')
    Sbr = circuit_.pack_branch_solution(results.Sbranch)
    for i in range(len(circuit_.branches)):
        print(str(circuit_.branches[i]), ':', Sbr[i].real, ' p.u. ->\t', Sbr[i].real * circuit_.Sbase, 'MW')