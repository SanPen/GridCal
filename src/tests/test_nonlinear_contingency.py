from GridCal.Engine import *


def test_ptdf():
    fname = os.path.join('src', 'tests', 'data', 'grids', 'IEEE 30 bus.raw')
    main_circuit = FileOpen(fname).open()

    options = LinearAnalysisOptions(distribute_slack=False, correct_values=False)
    simulation = LinearAnalysisDriver(grid=main_circuit, options=options)
    simulation.run()

    print('Finished!')

    # lodf: open a line and save the pu variation of P in the lines
    # ptdf: open a line and save the pu variation of P in the buses

    # 1: solve power flow with all lines OK
    # 2: compute the new voltages with HELM
    # 3: post-process to get the powers: V(YV)* for ptdf, Vf(Yf V)* for lodf (check power_flow_post_process)
    # 4: also store the voltages


    return True


if __name__ == '__main__':
    test_ptdf()

