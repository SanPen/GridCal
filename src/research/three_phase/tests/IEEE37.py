
from research.three_phase.Engine import *

if __name__ == "__main__":

    freq = 60
    w = 2 * np.pi * freq

    # Declare buses ####################################################################################################

    source = Bus('source', 3, Vnom=230, is_slack=True, x=40, y=0)
    b701 = Bus('b701', 3, Vnom=4.8, x=40, y=-20)
    b702 = Bus('b702', 3, Vnom=4.8, x=40, y=-40)
    b705 = Bus('b705', 3, Vnom=4.8, x=20, y=-40)
    b713 = Bus('b713', 3, Vnom=4.8, x=60, y=-40)
    b703 = Bus('b703', 3, Vnom=4.8, x=40, y=-80)
    b727 = Bus('b727', 3, Vnom=4.8, x=30, y=-80)
    b730 = Bus('b730', 3, Vnom=4.8, x=40, y=-140)
    b704 = Bus('b704', 3, Vnom=4.8, x=80, y=-40)
    b714 = Bus('b714', 3, Vnom=4.8, x=80, y=-60)
    b720 = Bus('b720', 3, Vnom=4.8, x=100, y=-40)
    b742 = Bus('b742', 3, Vnom=4.8, x=0, y=-40)
    b712 = Bus('b712', 3, Vnom=4.8, x=20, y=-20)
    b706 = Bus('b706', 3, Vnom=4.8, x=100, y=-60)
    b725 = Bus('b725', 3, Vnom=4.8, x=100, y=-80)
    b707 = Bus('b707', 3, Vnom=4.8, x=100, y=-20)
    b724 = Bus('b724', 3, Vnom=4.8, x=100, y=-0)
    b722 = Bus('b722', 3, Vnom=4.8, x=80, y=-20)
    b708 = Bus('b708', 3, Vnom=4.8, x=20, y=-160)
    b733 = Bus('b733', 3, Vnom=4.8, x=20, y=-180)
    b732 = Bus('b732', 3, Vnom=4.8, x=0, y=-160)
    b709 = Bus('b709', 3, Vnom=4.8, x=40, y=-160)
    b731 = Bus('b731', 3, Vnom=4.8, x=60, y=-160)
    b710 = Bus('b710', 3, Vnom=4.8, x=0, y=-200)
    b735 = Bus('b735', 3, Vnom=4.8, x=0, y=-220)
    b736 = Bus('b736', 3, Vnom=4.8, x=0, y=-180)
    b711 = Bus('b711', 3, Vnom=4.8, x=80, y=-220)
    b741 = Bus('b741', 3, Vnom=4.8, x=100, y=-220)
    b740 = Bus('b740', 3, Vnom=4.8, x=80, y=-200)
    b718 = Bus('b718', 3, Vnom=4.8, x=80, y=-80)
    b744 = Bus('b744', 3, Vnom=4.8, x=10, y=-80)
    b734 = Bus('b734', 3, Vnom=4.8, x=20, y=-200)
    b737 = Bus('b737', 3, Vnom=4.8, x=20, y=-220)
    b738 = Bus('b738', 3, Vnom=4.8, x=40, y=-220)
    b728 = Bus('b728', 3, Vnom=4.8, x=10, y=-120)
    b729 = Bus('b729', 3, Vnom=4.8, x=0, y=-80)
    b775 = Bus('b775', 3, Vnom=0.48, x=40, y=-180)
    b799 = Bus('799', 3, Vnom=4.8, x=40, y=-10)
    # b799r = Bus('b799r', 3, Vnom=4.8, x=40, y=-30)

    # declare loads ####################################################################################################
    b701.add_load(LoadSIY('S701a', S=np.array([140 + 70j, 0, 0]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]),
                          conn=[0, 1],
                          conn_type=Connection.Delta))

    b701.add_load(LoadSIY('S701b', S=np.array([0, 140 + 70j, 0]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[1, 2],
                          conn_type=Connection.Delta))

    b701.add_load(LoadSIY('S701c', S=np.array([0, 0, 350 + 175j]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[0, 2],
                          conn_type=Connection.Delta))

    b712.add_load(LoadSIY('S712c', S=np.array([0, 0, 85 + 40j]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[0, 2],
                          conn_type=Connection.Delta))

    b713.add_load(LoadSIY('S713c', S=np.array([0, 0, 85 + 40j]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[0, 2],
                          conn_type=Connection.Delta))

    b714.add_load(LoadSIY('S714a', S=np.array([17 + 8j, 0, 0]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[0, 1],
                          conn_type=Connection.Delta))

    b714.add_load(LoadSIY('S714b', S=np.array([0, 21 + 10j, 0]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[1, 2],
                          conn_type=Connection.Delta))

    b718.add_load(LoadSIY('S718a', S=np.array([85 + 40j, 0, 0]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[0, 1],
                          conn_type=Connection.Delta))

    b720.add_load(LoadSIY('S720c', S=np.array([0, 0, 85 + 40j]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[0, 2],
                          conn_type=Connection.Delta))

    b722.add_load(LoadSIY('S722b', S=np.array([0, 140 + 70j, 0]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[1, 2],
                          conn_type=Connection.Delta))

    b722.add_load(LoadSIY('S722c', S=np.array([0, 0, 21 + 10j]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[0, 2],
                          conn_type=Connection.Delta))

    b724.add_load(LoadSIY('S724b', S=np.array([0, 42 + 21j, 0]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[1, 2],
                          conn_type=Connection.Delta))

    b725.add_load(LoadSIY('S725b', S=np.array([0, 42 + 21j, 0]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[1, 2],
                          conn_type=Connection.Delta))

    b727.add_load(LoadSIY('S727c', S=np.array([0, 0, 42 + 21j]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[0, 2],
                          conn_type=Connection.Delta))

    b728.add_load(LoadSIY('S728', S=np.array([42 + 21j, 42 + 21j, 42 + 21j]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]),
                          conn=[0, 1, 2],
                          conn_type=Connection.Delta))

    b729.add_load(LoadSIY('S729a', S=np.array([42 + 21j, 0, 0]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[0, 1],
                          conn_type=Connection.Delta))

    b730.add_load(LoadSIY('S730c', S=np.array([0, 0, 85 + 40j]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[0, 2],
                          conn_type=Connection.Delta))

    b731.add_load(LoadSIY('S731b', S=np.array([0, 85 + 40j, 0]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[1, 2],
                          conn_type=Connection.Delta))

    b732.add_load(LoadSIY('S732c', S=np.array([0, 0, 42 + 21j]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[0, 2],
                          conn_type=Connection.Delta))

    b733.add_load(LoadSIY('S733a', S=np.array([85 + 40j, 0, 0]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[0, 1],
                          conn_type=Connection.Delta))

    b734.add_load(LoadSIY('S734c', S=np.array([0, 0, 42 + 21j]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[0, 2],
                          conn_type=Connection.Delta))

    b735.add_load(LoadSIY('S735c', S=np.array([0, 0, 85 + 40j]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[0, 2],
                          conn_type=Connection.Delta))

    b736.add_load(LoadSIY('S736b', S=np.array([0, 42 + 21j, 0]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[1, 2],
                          conn_type=Connection.Delta))

    b737.add_load(LoadSIY('S737a', S=np.array([140 + 70j, 0, 0]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[0, 1],
                          conn_type=Connection.Delta))

    b738.add_load(LoadSIY('S738a', S=np.array([126 + 62j, 0, 0]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[0, 1],
                          conn_type=Connection.Delta))

    b740.add_load(LoadSIY('S740c', S=np.array([0, 0, 85 + 40j]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[0, 2],
                          conn_type=Connection.Delta))

    b741.add_load(LoadSIY('S741c', S=np.array([0, 0, 42 + 21j]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[0, 2],
                          conn_type=Connection.Delta))

    b742.add_load(LoadSIY('S742a', S=np.array([8 + 4j, 0, 0]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[0, 1],
                          conn_type=Connection.Delta))

    b742.add_load(LoadSIY('S742b', S=np.array([0, 85 + 40j, 0]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[1, 2],
                          conn_type=Connection.Delta))

    b744.add_load(LoadSIY('S744a', S=np.array([42 + 21j, 0, 0]) / 1000, I=np.array([0, 0, 0]), Y=np.array([0, 0, 0]), conn=[0, 1],
                          conn_type=Connection.Delta))

    # line types #######################################################################################################

    lt721 = LineTypeABC(name="Line type 721", phases=3,
                        zABC=np.array(
                            [[0.055416667 + 0.037367424j, 0.012746212 - 0.006969697j, 0.006382576 - 0.007897727j],
                             [0.012746212 - 0.006969697j, 0.050113636 + 0.035984848j, 0.012746212 - 0.006969697j],
                             [0.006382576 - 0.007897727j, 0.012746212 - 0.006969697j, 0.055416667 + 0.037367424j]]),
                        ysh_ABC=np.array([[80.27484728, 0, 0],
                                          [0, 80.27484728, 0],
                                          [0, 0, 80.27484728]]) * 1e-9 * w * 1j)

    lt722 = LineTypeABC(name="Line type 722", phases=3,
                        zABC=np.array(
                            [[0.089981061 + 0.056306818j,  0.030852273 - 0.006174242j,  0.023371212 - 0.011496212j],
                             [0.030852273 - 0.006174242j,  0.085000000 + 0.050719697j,  0.030852273 - 0.006174242j],
                             [0.023371212 - 0.011496212j,  0.030852273 - 0.006174242j,  0.089981061 + 0.056306818j]]),
                        ysh_ABC=np.array([[64.2184109, 0, 0],
                                          [0, 64.2184109, 0],
                                          [0, 0, 64.2184109]]) * 1e-9 * w * 1j)

    lt723 = LineTypeABC(name="Line type 723", phases=3,
                        zABC=np.array(
                            [[0.245000000 + 0.127140152j, 0.092253788 + 0.039981061j, 0.086837121 + 0.028806818j],
                             [0.092253788 + 0.039981061j, 0.246628788 + 0.119810606j, 0.092253788 + 0.039981061j],
                             [0.086837121 + 0.028806818j, 0.092253788 + 0.039981061j, 0.245000000 + 0.127140152j]]),
                        ysh_ABC=np.array([[37.5977112, 0, 0],
                                          [0, 37.5977112, 0],
                                          [0, 0, 37.5977112]]) * 1e-9 * w * 1j)

    lt724 = LineTypeABC(name="Line type 724", phases=3,
                        zABC=np.array(
                            [[0.396818182 + 0.146931818j, 0.098560606 + 0.051856061j, 0.093295455 + 0.040208333j],
                             [0.098560606 + 0.051856061j, 0.399015152 + 0.140113636j, 0.098560606 + 0.051856061j],
                             [0.093295455 + 0.040208333j, 0.098560606 + 0.051856061j, 0.396818182 + 0.146931818j]]),
                        ysh_ABC=np.array([[46.9685, 0, 0],
                                          [0, 46.9685, 0],
                                          [0, 0, 46.9685]]) * 1e-9 * w * 1j)

    # Lines ############################################################################################################

    L1 = Line('L1', line_type=lt722, bus_from=b701, bus_to=b702, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.96)
    L2 = Line('L2', line_type=lt724, bus_from=b702, bus_to=b705, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.4)
    L3 = Line('L3', line_type=lt723, bus_from=b702, bus_to=b713, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.36)
    L4 = Line('L4', line_type=lt722, bus_from=b702, bus_to=b703, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=1.32)
    L5 = Line('L5', line_type=lt724, bus_from=b703, bus_to=b727, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.24)
    L6 = Line('L6', line_type=lt723, bus_from=b703, bus_to=b730, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.6)
    L7 = Line('L7', line_type=lt724, bus_from=b704, bus_to=b714, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.08)
    L8 = Line('L8', line_type=lt723, bus_from=b704, bus_to=b720, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.8)
    L9 = Line('L9', line_type=lt724, bus_from=b705, bus_to=b742, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.32)
    L10 = Line('L10', line_type=lt724, bus_from=b705, bus_to=b712, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.24)
    L11 = Line('L11', line_type=lt724, bus_from=b706, bus_to=b725, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.28)
    L12 = Line('L12', line_type=lt724, bus_from=b707, bus_to=b724, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.76)
    L13 = Line('L13', line_type=lt724, bus_from=b707, bus_to=b722, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.12)
    L14 = Line('L14', line_type=lt723, bus_from=b708, bus_to=b733, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.32)
    L15 = Line('L15', line_type=lt724, bus_from=b708, bus_to=b732, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.32)
    L16 = Line('L16', line_type=lt723, bus_from=b709, bus_to=b731, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.6)
    L17 = Line('L17', line_type=lt723, bus_from=b709, bus_to=b708, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.32)
    L18 = Line('L18', line_type=lt724, bus_from=b710, bus_to=b735, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.2)
    L19 = Line('L19', line_type=lt724, bus_from=b710, bus_to=b736, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=1.28)
    L20 = Line('L20', line_type=lt723, bus_from=b711, bus_to=b741, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.4)
    L21 = Line('L21', line_type=lt724, bus_from=b711, bus_to=b740, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.2)
    L22 = Line('L22', line_type=lt723, bus_from=b713, bus_to=b704, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.52)
    L23 = Line('L23', line_type=lt724, bus_from=b714, bus_to=b718, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.52)
    L24 = Line('L24', line_type=lt724, bus_from=b720, bus_to=b707, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.92)
    L25 = Line('L25', line_type=lt723, bus_from=b720, bus_to=b706, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.6)
    L26 = Line('L26', line_type=lt723, bus_from=b727, bus_to=b744, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.28)
    L27 = Line('L27', line_type=lt723, bus_from=b730, bus_to=b709, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.2)
    L28 = Line('L28', line_type=lt723, bus_from=b733, bus_to=b734, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.56)
    L29 = Line('L29', line_type=lt723, bus_from=b734, bus_to=b737, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.64)
    L30 = Line('L30', line_type=lt724, bus_from=b734, bus_to=b710, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.52)
    L31 = Line('L31', line_type=lt723, bus_from=b737, bus_to=b738, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.4)
    L32 = Line('L32', line_type=lt723, bus_from=b738, bus_to=b711, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.4)
    L33 = Line('L33', line_type=lt724, bus_from=b744, bus_to=b728, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.2)
    L34 = Line('L34', line_type=lt724, bus_from=b744, bus_to=b729, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=0.28)
    L35 = Line('L35', line_type=lt721, bus_from=b799, bus_to=b701, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=1.85)

    # define transformers ##############################################################################################

    Ttype1 = TransformerType3p("Transformer type 1", conn_f=Connection.Delta, conn_t=Connection.Delta,
                               r=0.01, x=0.08, Vf_rate=230, Vt_rate=4.8, rating=2.5)
    T1 = Transformer("T1", transformer_type=Ttype1, bus_from=source, bus_to=b799)

    Ttype2 = TransformerType3p("Transformer type 2", conn_f=Connection.Delta, conn_t=Connection.Delta,
                               r=0.00045, x=0.0181, Vf_rate=4.8, Vt_rate=0.48, rating=0.5)
    T2 = Transformer("T2", transformer_type=Ttype2, bus_from=b709, bus_to=b775)

    # assemble circuit #################################################################################################
    circuit = Circuit(Sbase=100)

    circuit.buses = [source, b701, b702, b703, b704, b705, b706, b707, b708, b709, b710, b711, b712, b713, b714, b718,
                     b720, b722, b724, b725, b727, b728, b729, b730, b731, b732, b733, b734, b735, b736, b737,
                     b738, b740, b741, b742, b744, b775, b799]

    circuit.branches = [L1, L2, L3, L4, L5, L6, L7, L8, L9, L10, L11, L12, L13, L14, L15, L16, L17, L18, L19, L20,
                        L21, L22, L23, L24, L25, L26, L27, L28, L29, L30, L31, L32, L33, L34, L35, T1, T2]

    data = circuit.compile()

    data.print()

    from scipy.sparse.linalg import spsolve
    # ##################################################################################################################
    np.set_printoptions(suppress=True)
    power_flow = PowerFlow(circuit)
    results = power_flow.run(method=PowerFlowMethods.ZMatrix, verbose=False, max_iter=10)

    print('\nVoltage solution')
    print('converged', results.converged, ', err:', results.error)
    print(np.abs(results.V))

    print('\nPacked voltages per bus')
    Vpack = circuit.pack_node_solution(results.V)
    for i in range(len(circuit.buses)):
        print(str(circuit.buses[i]), ':', abs(Vpack[i]), '<', np.angle(Vpack[i], True), 'º p.u. ->\t', abs(Vpack[i]) * circuit.buses[i].Vnom, 'kV')

    # print('\nPacked power per bus')
    # Spack = circuit.pack_node_solution(results.Sbus)
    # for i in range(len(circuit.buses)):
    #     print(str(circuit.buses[i]), ':', Spack[i].real, ' p.u. ->\t', Spack[i].real * circuit.Sbase, 'MW')
    #
    # print('\nPacked branch power')
    # Sbr = circuit.pack_branch_solution(results.Sbranch)
    # for i in range(len(circuit.branches)):
    #     print(str(circuit.branches[i]), ':', Sbr[i].real, ' p.u. ->\t', Sbr[i].real * circuit.Sbase, 'MW')

    # circuit.plot()
