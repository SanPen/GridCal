import numpy as np
from scipy.sparse import csc_matrix

from GridCalEngine.Simulations.StateEstimation.observability_analysis import \
    check_for_observability_and_return_unobservable_buses, add_pseudo_measurements_for_unobservable_buses
from GridCalEngine.Simulations.StateEstimation.pseudo_measurements_augmentation import build_neighbors, \
    add_pseudo_measurements, PseudoMeasurement


class DummyLogger:
    def __init__(self):
        self.logs = []
    def add_info(self, *args, **kwargs):
        self.logs.append(("INFO", args, kwargs))
    def add_warning(self, *args, **kwargs):
        self.logs.append(("WARN", args, kwargs))

# --- Dummy SE input structure ---
class DummyMeasurementList:
    def __init__(self):
        self.p_inj = []
        self.q_inj = []
        self.pg_inj = []
        self.qg_inj = []
        self.pf_value = []
        self.pt_value = []
        self.qf_value = []
        self.qt_value = []
        self.if_value = []
        self.it_value = []
        self.vm_value = []
        self.va_value = []

        # Indices for SE code
        self.p_idx = []
        self.q_idx = []
        self.pg_idx = []
        self.qg_idx = []
        self.pf_idx = []
        self.pt_idx = []
        self.qf_idx = []
        self.qt_idx = []
        self.if_idx = []
        self.it_idx = []
        self.vm_idx = []
        self.va_idx = []
    def slice(self, **kwargs):
        return self

# --- Test ---
def test_observability_and_pseudo_measurements():
    logger = DummyLogger()

    # 3-bus system
    n_bus = 3
    Ybus = np.array([[10-30j, -5+15j, -5+15j],
                     [-5+15j, 5-15j, 0+0j],
                     [-5+15j, 0+0j, 5-15j]], dtype=complex)
    Ybus_sparse = csc_matrix(Ybus)

    # Branch connectivity matrices
    Cf = csc_matrix([[1,0,0],
                     [0,1,0]])
    Ct = csc_matrix([[0,1,0],
                     [0,0,1]])

    # Construct simple Yf and Yt for each branch (3-bus, 2 branches)
    # These are diagonal matrices with branch admittances
    branch_adm = np.array([5-15j, 5-15j])  # from Ybus off-diagonal magnitudes
    n_br = len(branch_adm)
    # Yf[i, j] = branch i from bus j admittance
    Yf_data = np.array(branch_adm)
    Yt_data = np.array(branch_adm)

    Yf = csc_matrix((Yf_data, (np.arange(n_br), [0, 1])), shape=(n_br, n_bus))
    Yt = csc_matrix((Yt_data, (np.arange(n_br), [1, 2])), shape=(n_br, n_bus))

    V = np.array([1+0j, 1+0j, 1+0j])
    no_slack = [1, 2]

    se_input = DummyMeasurementList()

    # --- Observability check ---
    class DummyNC:
        bus_data = type("BD", (), {"Vbus": V})
        load_data = type("LD", (), {"get_injections_per_bus": lambda: np.array([1.0,1.0,1.0])})
        Sbase = 1.0

    unobservable_buses, V,bus_contrib = check_for_observability_and_return_unobservable_buses(
        nc=DummyNC(),
        Ybus=Ybus_sparse,
        Yf=Yf,
        Yt=Yt,
        no_slack = [1, 2],
        F=np.array([0, 1]),
        T=np.array([1, 2]),
        Cf=Cf,
        Ct=Ct,
        se_input=DummyMeasurementList(),
        fixed_slack=True,
        logger=logger
    )

    assert isinstance(unobservable_buses, list)

    # --- Add pseudo-measurements ---
    se_input_island = add_pseudo_measurements_for_unobservable_buses(unobservable_buses, V=V,
                                                  Ybus=Ybus_sparse,
                                                  Cf=Cf,
                                                  Ct=Ct,
                                                  se_input=se_input,
                                                  sigma_pseudo_meas_value=1,
                                                  logger=logger)

    # Check that pseudo-measurements were added
    for bus in unobservable_buses:
        p_exists = any(isinstance(m, PseudoMeasurement) and m.bus == bus for m in se_input.p_inj)
        q_exists = any(isinstance(m, PseudoMeasurement) and m.bus == bus for m in se_input.q_inj)
        assert p_exists and q_exists, f"Pseudo-measurements missing for bus {bus}"

    print("Test passed: Observability, pseudo-measurements, and measurement integration successful.")

if __name__ == "__main__":
    test_observability_and_pseudo_measurements()