from pathlib import Path

from GridCal.Engine.IO.file_handler import FileOpen
from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import \
    PowerFlowOptions, ReactivePowerControlMode, SolverType
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver


def test_power_flow():
    fname = Path(__file__).parent.parent.parent / \
            'Grids_and_profiles' / 'grids' / 'IEEE 30 Bus with storage.xlsx'

    print('Reading...')
    main_circuit = FileOpen(fname).open()
    options = PowerFlowOptions(SolverType.NR, verbose=False,
                               initialize_with_existing_solution=False,
                               multi_core=False, dispatch_storage=True,
                               control_q=ReactivePowerControlMode.NoControl,
                               control_p=True)
    # grid.export_profiles('ppppppprrrrroooofiles.xlsx')
    # exit()
    ####################################################################################################################
    # PowerFlowDriver
    ####################################################################################################################
    print('\n\n')
    power_flow = PowerFlowDriver(main_circuit, options)
    power_flow.run()
    print('\n\n', main_circuit.name)
    print('\t|V|:', abs(power_flow.results.voltage))
    print('\t|Sbranch|:', abs(power_flow.results.Sbranch))
    print('\t|loading|:', abs(power_flow.results.loading) * 100)
    print('\tReport')
    print(power_flow.results.get_report_dataframe())


if __name__ == '__main__':
    test_power_flow()
