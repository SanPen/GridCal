
from GridCal.Engine.All import *
from matplotlib import pyplot as plt

if __name__ == '__main__':

    main_circuit = MultiCircuit()
    # fname = '/Data/Doctorado/spv_phd/GridCal_project/GridCal/IEEE_300BUS.xls'
    # fname = 'Pegasus 89 Bus.xlsx'
    # fname = 'Illinois200Bus.xlsx'
    # fname = 'IEEE_30_new.xlsx'
    # fname = 'lynn5buspq.xlsx'
    # fname = 'D:\\GitHub\\GridCal\\Grids_and_profiles\\grids\\Europe winter 2009 model.xlsx'
    # fname = "C:\\Users\\spenate\\Documents\\PROYECTOS\\Sensible\\Evora reduced (no switchs, corrected, profiles 1W@15T).xlsx"
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE_30_new.xlsx'
    # fname = 'D:\\GitHub\\GridCal\\Grids_and_profiles\\grids\\IEEE_30_new.xlsx'
    # fname = 'D:\\GitHub\\GridCal\\Grids_and_profiles\\grids\\IEEE 30 Bus with storage.xlsx'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 30 Bus with storage.xlsx'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39.xlsx'
    # fname = '/Data/Doctorado/spv_phd/GridCal_project/GridCal/IEEE_14.xls'
    # fname = '/Data/Doctorado/spv_phd/GridCal_project/GridCal/IEEE_39Bus(Islands).xls'

    print('Reading...')
    main_circuit.load_file(fname)
    options = PowerFlowOptions(SolverType.NR, verbose=False,
                               initialize_with_existing_solution=False,
                               multi_core=False, dispatch_storage=True,
                               control_q=ReactivePowerControlMode.NoControl,
                               control_p=True)

    # grid.export_profiles('ppppppprrrrroooofiles.xlsx')
    # exit()

    ####################################################################################################################
    # PowerFlow
    ####################################################################################################################
    print('\n\n')
    power_flow = PowerFlow(main_circuit, options)
    power_flow.run()

    print('\n\n', main_circuit.name)
    print('\t|V|:', abs(power_flow.results.voltage))
    print('\t|Sbranch|:', abs(power_flow.results.Sbranch))
    print('\t|loading|:', abs(power_flow.results.loading) * 100)
    print('\tReport')
    print(power_flow.results.get_report_dataframe())