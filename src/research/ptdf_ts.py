from GridCal.Engine import PowerFlowOptions, PowerFlowDriver, FileOpen, SolverType, ReactivePowerControlMode, \
    TapsControlMode, BranchImpedanceMode, TimeSeries, PTDF, PTDFOptions


def run(fname):

    circuit = FileOpen(fname).open()

    pf_options = PowerFlowOptions(solver_type=SolverType.NR,
                                  retry_with_other_methods=False,
                                  verbose=False,
                                  initialize_with_existing_solution=False,
                                  tolerance=1e-6,
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

    ts_driver = TimeSeries(circuit, pf_options)
    ts_driver.run()

    ptdf_options = PTDFOptions(group_mode=Ptd,
                               power_increment=10.0,
                               use_multi_threading=False)
    ptdf_driver = PTDF(circuit, ptdf_options, pf_options)



if __name__ == '__main__':

    run(r'C:\Users\PENVERSA\OneDrive - Red Eléctrica Corporación\Escritorio\IEEE cases\WSCC 9 bus.gridcal')