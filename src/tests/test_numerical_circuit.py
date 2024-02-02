import os
from GridCalEngine.api import *


def test_numerical_cicuit_generator_contingencies():
    """
    Check whether the generator contingency present on the gridcal file is applied correctly
    :return: Nothing if ok, fails if not
    """
    for i, fname in enumerate([
        os.path.join('data', 'grids', 'IEEE14-gen120.gridcal'),
        os.path.join('data', 'grids', 'IEEE14-gen80.gridcal')
    ]):
        main_circuit = FileOpen(fname).open()
        nc = compile_numerical_circuit_at(main_circuit, t_idx=None)

        # for cnt in main_circuit.contingencies:
        #
        #     nc.set_contingency_status(contingencies_list=[cnt])

        cnt = main_circuit.contingencies[0]  # yo sé que la primera contingencia es cambiar el generador del bus 1 en 120%

        p_prev = nc.generator_data.p[1]  # P del primer generador antes del cambio
        nc.set_contingency_status(contingencies_list=[cnt])
        p_post = nc.generator_data.p[1]
        change = 1.2 if i == 0 else 0.8

        assert p_prev * change == p_post

def test_numerical_cicuit_branch_contingencies():
    """
    Check whether the generator contingency present on the gridcal file is applied correctly
    :return: Nothing if ok, fails if not
    """
    for i, fname in enumerate([
        os.path.join('data', 'grids', 'IEEE14-gen120.gridcal'),
        os.path.join('data', 'grids', 'IEEE14-gen80.gridcal')
    ]):
        main_circuit = FileOpen(fname).open()
        nc = compile_numerical_circuit_at(main_circuit, t_idx=None)

        # for cnt in main_circuit.contingencies:
        #
        #     nc.set_contingency_status(contingencies_list=[cnt])

        cnt = main_circuit.contingencies[0]  # yo sé que la primera contingencia es cambiar el generador del bus 1 en 120%

        p_prev = nc.generator_data.p[1]  # P del primer generador antes del cambio
        nc.set_contingency_status(contingencies_list=[cnt])
        p_post = nc.generator_data.p[1]
        change = 1.2 if i == 0 else 0.8

        assert p_prev * change == p_post


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
