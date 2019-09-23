from GridCal.Engine import *


def test():
    fname = os.path.join('..', '..', 'Grids_and_profiles', 'grids', 'IEEE39.gridcal')
    print('Reading...')
    main_circuit = FileOpen(fname).open()
    options = PowerFlowOptions(SolverType.NR, verbose=False,
                               initialize_with_existing_solution=False,
                               multi_core=False, dispatch_storage=True,
                               control_q=ReactivePowerControlMode.NoControl,
                               control_p=True)

    ############################################################
    # Time Series
    ############################################################
    print('Running TS...', '')
    start = time.time()

    ts = TimeSeries(grid=main_circuit, options=options)
    ts.run()

    end = time.time()
    dt = end - start
    print('  total', dt, 's')

if __name__ == '__main__':
    # import cProfile
    # cProfile.runctx('test()', None, locals())
    test()