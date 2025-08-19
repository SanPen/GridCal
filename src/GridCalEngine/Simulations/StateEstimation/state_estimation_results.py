import numpy as np
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowResults


class StateEstimationResults(PowerFlowResults):

    def __init__(self, n=0, m=0, bus_names=None, branch_names=None, hvdc_names=None, bus_types=None,
                 V=None, Scalc=None, m_values=None, tau=None, Sf=None, St=None, If=None, It=None,
                 loading=None, losses=None, Pf_vsc=None, St_vsc=None, If_vsc=None, It_vsc=None,
                 losses_vsc=None, loading_vsc=None, Sf_hvdc=None, St_hvdc=None, losses_hvdc=None,
                 loading_hvdc=None, norm_f=50.0, converged=False, iterations=0, elapsed=0.0,
                 bad_data_detected=False):
        """
        State Estimation Results constructor with optional parameters
        """
        """
        State Estimation Results constructor

        :param n: number of buses
        :param m: number of branches
        :param bus_names: bus names array
        :param branch_names: branch names array
        :param hvdc_names: HVDC names array
        :param bus_types: bus types array
        :param V: voltage results
        :param Scalc: calculated power injections
        :param m_values: tap module values
        :param tau: tap angle values
        :param Sf: power flow at from bus
        :param St: power flow at to bus
        :param If: current at from bus
        :param It: current at to bus
        :param loading: branch loading
        :param losses: branch losses
        :param Pf_vsc: VSC active power
        :param St_vsc: VSC apparent power
        :param If_vsc: VSC current at from bus
        :param It_vsc: VSC current at to bus
        :param losses_vsc: VSC losses
        :param loading_vsc: VSC loading
        :param Sf_hvdc: HVDC power flow at from bus
        :param St_hvdc: HVDC power flow at to bus
        :param losses_hvdc: HVDC losses
        :param loading_hvdc: HVDC loading
        :param norm_f: norm value
        :param converged: convergence flag
        :param iterations: number of iterations
        :param elapsed: elapsed time
        :param bad_data_detected: bad data detection flag
        """
        # Handle array defaults properly to avoid dimension issues
        if bus_names is None:
            bus_names = np.array([], dtype=object)
        if branch_names is None:
            branch_names = np.array([], dtype=object)
        if hvdc_names is None:
            hvdc_names = np.array([], dtype=object)
        if bus_types is None:
            bus_types = np.array([], dtype=int)
        if Pf_vsc is None:
            Pf_vsc = np.array([], dtype=float)
        # Initialize the parent class with defaults if needed
        PowerFlowResults.__init__(self,
                                  n=n,
                                  m=m,
                                  n_hvdc=len(hvdc_names),
                                  n_vsc=len(Pf_vsc),
                                  n_gen=0,
                                  n_batt=0,
                                  n_sh=0,
                                  bus_names=bus_names,
                                  branch_names=branch_names,
                                  hvdc_names=hvdc_names,
                                  vsc_names=np.array([], dtype=object),
                                  gen_names=np.array([], dtype=object),
                                  batt_names=np.array([], dtype=object),
                                  sh_names=np.array([], dtype=object),
                                  bus_types=bus_types)

        # Store state estimation specific results with proper array initialization
        self.V = np.array(V, dtype=complex) if V is not None else np.array([], dtype=complex)
        self.Scalc = np.array(Scalc, dtype=complex) if Scalc is not None else np.array([], dtype=complex)
        self.m = np.array(m_values, dtype=float) if m_values is not None else np.array([], dtype=float)
        self.tau = np.array(tau, dtype=float) if tau is not None else np.array([], dtype=float)
        self.Sf = np.array(Sf, dtype=complex) if Sf is not None else np.array([], dtype=complex)
        self.St = np.array(St, dtype=complex) if St is not None else np.array([], dtype=complex)
        self.If = np.array(If, dtype=complex) if If is not None else np.array([], dtype=complex)
        self.It = np.array(It, dtype=complex) if It is not None else np.array([], dtype=complex)
        self.loading = np.array(loading, dtype=float) if loading is not None else np.array([], dtype=float)
        self.losses = np.array(losses, dtype=complex) if losses is not None else np.array([], dtype=complex)
        self.Pf_vsc = np.array(Pf_vsc, dtype=float) if Pf_vsc is not None else np.array([], dtype=float)
        self.St_vsc = np.array(St_vsc, dtype=complex) if St_vsc is not None else np.array([], dtype=complex)
        self.If_vsc = np.array(If_vsc, dtype=float) if If_vsc is not None else np.array([], dtype=float)
        self.It_vsc = np.array(It_vsc, dtype=complex) if It_vsc is not None else np.array([], dtype=complex)
        self.losses_vsc = np.array(losses_vsc, dtype=float) if losses_vsc is not None else np.array([], dtype=float)
        self.loading_vsc = np.array(loading_vsc, dtype=float) if loading_vsc is not None else np.array([], dtype=float)
        self.Sf_hvdc = np.array(Sf_hvdc, dtype=complex) if Sf_hvdc is not None else np.array([], dtype=complex)
        self.St_hvdc = np.array(St_hvdc, dtype=complex) if St_hvdc is not None else np.array([], dtype=complex)
        self.losses_hvdc = np.array(losses_hvdc, dtype=complex) if losses_hvdc is not None else np.array([], dtype=complex)
        self.loading_hvdc = np.array(loading_hvdc, dtype=complex) if loading_hvdc is not None else np.array([], dtype=complex)
        self.norm_f = norm_f
        self._converged = converged
        self._iterations = iterations
        self._elapsed = elapsed
        self.bad_data_detected = bad_data_detected
