Linear example
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    """
    IEEE14 example with linear OPF
    """
    cwd = os.getcwd()
    fname = os.path.join('data', 'grids', 'IEEE 14 zip costs.gridcal')
    grid = gce.FileOpen(fname).open()

    # Linear OPF
    res = run_linear_opf_ts(grid=grid,
                            optimize_nodal_capacity=True,
                            time_indices=None,
                            nodal_capacity_sign=-1.0,
                            capacity_nodes_idx=np.array([10, 11]))

    print('P linear nodal capacity: ', res.nodal_capacity_vars.P)
    print('')


Non-linear example
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    """
    IEEE14 example with non-linear OPF
    """
    cwd = os.getcwd()
    fname = os.path.join('data', 'grids', 'IEEE 14 zip costs.gridcal')
    grid = gce.FileOpen(fname).open()

    # Nonlinear OPF
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=0)
    opf_options = gce.OptimalPowerFlowOptions(solver=gce.SolverType.NONLINEAR_OPF, ips_tolerance=1e-8,
                                              ips_iterations=50, verbose=0, acopf_mode=AcOpfMode.ACOPFstd)
    res = run_nonlinear_opf(grid=grid, pf_options=pf_options, opf_options=opf_options, plot_error=False, pf_init=True,
                            optimize_nodal_capacity=True,
                            nodal_capacity_sign=-1.0,
                            capacity_nodes_idx=np.array([10, 11]))

    print('P non-linear nodal capacity: ', res.nodal_capacity)
    print('')


Results
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Linear nodal capacity power, in MW**

P linear nodal capacity: [4.85736901, 1.52653874]

**Non-linear nodal capacity power, in MW**

P non-linear nodal capacity: [5.0114640, 1.693406]

