from GridCal.grid.calculate.solver_type import SolverType


class PowerFlowOptions:

    def __init__(self, solver_type: SolverType = SolverType.NR, aux_solver_type: SolverType = SolverType.HELM,
                 verbose=False, robust=False, initialize_with_existing_solution=True, dispatch_storage=True,
                 tolerance=1e-6, max_iter=25, control_q=True):
        """
        Power flow execution options
        @param solver_type:
        @param aux_solver_type:
        @param verbose:
        @param robust:
        @param initialize_with_existing_solution:
        @param dispatch_storage:
        @param tolerance:
        @param max_iter:
        @param control_q:
        """
        self.solver_type = solver_type

        self.auxiliary_solver_type = aux_solver_type

        self.tolerance = tolerance

        self.max_iter = max_iter

        self.control_Q = control_q

        self.dispatch_storage = dispatch_storage

        self.verbose = verbose

        self.robust = robust

        self.initialize_with_existing_solution = initialize_with_existing_solution

        self.dispatch_storage = dispatch_storage
