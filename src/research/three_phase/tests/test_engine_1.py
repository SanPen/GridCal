
from research.three_phase.Engine import *

np.set_printoptions(linewidth=100000)

if __name__ == "__main__":

    P = np.array([2.5, 2.5, 2.5])
    S = np.array([2+2j, 20+2j, 40+3j])

    b1 = Bus("B1", number_of_phases=3, Vnom=10.0)
    b1.is_slack = True
    b1.add_generator(Generator("", P=P, v=1.0))

    b2 = Bus("B2", number_of_phases=3, Vnom=10.0)
    b2.add_load(LoadSIY("", S, np.zeros_like(S), np.zeros_like(S)))

    b3 = Bus("B3", number_of_phases=3, Vnom=10.0)
    # b3.add_generator(Generator("", P=P*0.5, v=1.0))

    line_type1 = LineTypeSeq(name="",
                             Z_SEQ=np.array([0.4606 + 1.7536j, 0.1808 + 0.6054j, 0.1808 + 0.6054j])/100,
                             Ysh_SEQ=np.array([0, 0, 0]))

    lne1 = Line("L1", line_type1, bus_from=b1, bus_to=b2, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=100.0)
    lne2 = Line("L2", line_type1, bus_from=b2, bus_to=b3, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=10.0)

    circuit_ = Circuit(Sbase=100)
    circuit_.buses.append(b1)
    circuit_.buses.append(b2)
    circuit_.buses.append(b3)

    circuit_.branches.append(lne1)
    circuit_.branches.append(lne2)

    data = circuit_.compile()

    print("Ybus")
    print(data.Ybus.todense())

    print("Sbus")
    print(data.Sbus)

    print("Vbus")
    print(data.Vbus)

    pf = PowerFlow(circuit_)
    results = pf.run(method=PowerFlowMethods.NewtonRaphson, verbose=True)

    print('\nVoltage solution')
    print('converged', results.converged, ', err:', results.error)
    print(np.abs(results.V))

    print('\nPacked voltages per bus')
    Vpack = circuit_.pack_node_solution(results.V)
    for i in range(len(circuit_.buses)):
        print(str(circuit_.buses[i]), ':', abs(Vpack[i]), ' p.u. ->\t', abs(Vpack[i]) * circuit_.buses[i].Vnom, 'kV')
