from GridCal.Engine.Simulations.PowerFlow.steady_state.reactive_control_mode \
    import ReactivePowerControlMode
from GridCal.Engine.Simulations.PowerFlow.steady_state.solver_type import \
    SolverType
from GridCal.Engine.Simulations.PowerFlow.steady_state.taps_control_mode \
    import TapsControlMode
from GridCal.Engine.basic_structures import BranchImpedanceMode


class PowerFlowOptions:
    """
    Power flow options class; its object is used as an argument for the
    :ref:`PowerFlowMP<pf_mp>` constructor.

    Arguments:

        **solver_type** (:ref:`SolverType<solver_type>`, SolverType.NR): Solver type

        **retry_with_other_methods** (bool, True): Use a battery of methods to tackle
        the problem if the main solver fails

        **verbose** (bool, False): Print additional details in the logger

        **initialize_with_existing_solution** (bool, True): *To be detailed*

        **tolerance** (float, 1e-6): Solution tolerance for the power flow numerical
        methods

        **max_iter** (int, 25): Maximum number of iterations for the power flow
        numerical method

        **max_outer_loop_iter** (int, 100): Maximum number of iterations for the
        controls outer loop

        **control_q** (:ref:`ReactivePowerControlMode<q_control>`,
        ReactivePowerControlMode.NoControl): Control mode for the PV nodes reactive
        power limits

        **control_taps** (:ref:`TapsControlMode<taps_control>`,
        TapsControlMode.NoControl): Control mode for the transformer taps equipped with
        a voltage regulator (as part of the outer loop)

        **multi_core** (bool, False): Use multi-core processing? applicable for time
        series

        **dispatch_storage** (bool, False): Dispatch storage?

        **control_p** (bool, False): Control active power (optimization dispatch)

        **apply_temperature_correction** (bool, False): Apply the temperature
        correction to the resistance of the branches?

        **branch_impedance_tolerance_mode** (BranchImpedanceMode,
        BranchImpedanceMode.Specified): Type of modification of the branches impedance

        **q_steepness_factor** (float, 30): Steepness factor :math:`k` for the
        :ref:`ReactivePowerControlMode<q_control>` iterative control

    """

    def __init__(self,
                 solver_type: SolverType = SolverType.NR,
                 retry_with_other_methods=True,
                 verbose=False,
                 initialize_with_existing_solution=True,
                 tolerance=1e-6,
                 max_iter=25,
                 max_outer_loop_iter=100,
                 control_q=ReactivePowerControlMode.NoControl,
                 control_taps=TapsControlMode.NoControl,
                 multi_core=False,
                 dispatch_storage=False,
                 control_p=False,
                 apply_temperature_correction=False,
                 branch_impedance_tolerance_mode=BranchImpedanceMode.Specified,
                 q_steepness_factor=30,
                 ):

        self.solver_type = solver_type

        self.retry_with_other_methods = retry_with_other_methods

        self.tolerance = tolerance

        self.max_iter = max_iter

        self.max_outer_loop_iter = max_outer_loop_iter

        self.control_Q = control_q

        self.control_P = control_p

        self.verbose = verbose

        self.initialize_with_existing_solution = initialize_with_existing_solution

        self.multi_thread = multi_core

        self.dispatch_storage = dispatch_storage

        self.control_taps = control_taps

        self.apply_temperature_correction = apply_temperature_correction

        self.branch_impedance_tolerance_mode = branch_impedance_tolerance_mode

        self.q_steepness_factor = q_steepness_factor