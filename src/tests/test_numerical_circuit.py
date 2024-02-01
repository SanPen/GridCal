import os
from GridCalEngine.api import *


def test_numerical_cicuit():
    """
    Compare the PSSE PTDF and the GridCal PTDF for IEEE14, IEEE30, IEEE118 and REE networks
    """
    fname_cont = os.path.join('data', 'grids', 'IEEE14-gen120.gridcal')

    main_circuit = FileOpen(fname_cont).open()

    # DC power flow method
    pf_options = PowerFlowOptions(SolverType.DC,
                                  verbose=False,
                                  initialize_with_existing_solution=False,
                                  dispatch_storage=True,
                                  control_q=ReactivePowerControlMode.NoControl,
                                  control_p=False)
    options1 = ContingencyAnalysisOptions(pf_options=pf_options, engine=ContingencyMethod.PowerFlow)
    cont_analysis_driver1 = ContingencyAnalysisDriver(grid=main_circuit, options=options1,
                                                      linear_multiple_contingencies=None)

    cont_analysis_driver1.run()
    # nc = compile_numerical_circuit_at(main_circuit, t_idx=None)

    fnames = os.path.join('data', 'grids', 'RAW', 'IEEE 14 bus.raw')

    main_circuit = FileOpen(fnames).open()
    main_circuit.buses[1].generators[0].P *= 1.2  # Increase 20%

    # run the linear analysis
    pf_options = PowerFlowOptions()
    power_flow = PowerFlowDriver(grid=main_circuit, options=pf_options)
    power_flow.run()

    assert np.allclose(cont_analysis_driver1.results.Sf, power_flow.results.Sf)


def test_numerical_cicuit_spv():
    """
    Check that the numerical circuit does apply a generator contingency correctly
    """
    fname_cont = os.path.join('data', 'grids', 'IEEE14-gen120.gridcal')

    main_circuit = FileOpen(fname_cont).open()
    nc = compile_numerical_circuit_at(main_circuit, t_idx=None)

    # for cnt in main_circuit.contingencies:
    #
    #     nc.set_contingency_status(contingencies_list=[cnt])

    cnt = main_circuit.contingencies[0]  # yo sé que la primera contingencia es cambiar el generador del bus 1 en 120%

    p_antes = nc.generator_data.p[1]  # P del primer generador antes del cambio
    nc.set_contingency_status(contingencies_list=[cnt])
    p_despues = nc.generator_data.p[1]

    assert p_antes * 1.20 == p_despues






