from GridCal.Engine import PowerFlowOptions, PowerFlowDriver, FileOpen, SolverType, ReactivePowerControlMode, \
    TapsControlMode, BranchImpedanceMode


def run(fname):

    circuit = FileOpen(fname).open()

    options = PowerFlowOptions(solver_type=SolverType.NR,
                               retry_with_other_methods=False,
                               verbose=False,
                               initialize_with_existing_solution=False,
                               tolerance=1e-4,
                               max_iter=5,
                               max_outer_loop_iter=10,
                               control_q=ReactivePowerControlMode.NoControl,
                               control_taps=TapsControlMode.NoControl,
                               multi_core=False,
                               dispatch_storage=False,
                               control_p=False,
                               apply_temperature_correction=False,
                               branch_impedance_tolerance_mode=BranchImpedanceMode.Specified,
                               q_steepness_factor=30,
                               distributed_slack=False,
                               ignore_single_node_islands=False,
                               correction_parameter=1e-4)

    driver = PowerFlowDriver(circuit, options)

    driver.run()

    print(abs(driver.results.voltage))
    print(driver.results.error)
    for r in driver.results.convergence_reports:
        print(r)


if __name__ == '__main__':

    # run('/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/lynn5buspv.xlsx')
    run('/home/santi/Descargas/Equivalent.gridcal')