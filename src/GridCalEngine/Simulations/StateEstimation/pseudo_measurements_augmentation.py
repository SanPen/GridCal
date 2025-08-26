import numpy as np


class PseudoMeasurement:
    def __init__(self, value, sigma, bus, mtype="p_inj"):
        """
        Parameters
        ----------
        value : float
            Per-unit value of pseudo measurement
        sigma : float
            Per-unit standard deviation (large → low weight)
        bus : int
            Bus index this pseudo measurement belongs to
        mtype : str
            Measurement type, e.g. "p_inj", "q_inj"
        """
        self.value = value
        self.sigma = sigma
        self.bus = bus
        self.mtype = mtype

    def get_value_pu(self, Sbase: float):
        return self.value / Sbase

    def get_standard_deviation_pu(self, Sbase: float):
        return self.sigma / Sbase


def build_neighbors(Cf, Ct):
    """
    Build neighbor list per bus from connectivity matrices.
    Cf, Ct: sparse branch-to-bus incidence matrices
    """
    n_buses = Cf.shape[1]
    neighbors = [[] for _ in range(n_buses)]

    # convert sparse matrices to COO for fast iteration
    Cf_coo, Ct_coo = Cf.tocoo(), Ct.tocoo()

    for br in range(Cf_coo.shape[0]):
        i = Cf_coo.col[br]
        j = Ct_coo.col[br]
        if i != j:
            neighbors[i].append(j)
            neighbors[j].append(i)

    return neighbors
def compute_power_injection(bus, V, Ybus, neighbors):
    """
    Compute AC active and reactive power injection for a bus using neighbors.
    neighbors: prebuilt list of lists, neighbors[i] = list of neighbor bus indices
    """
    Vi = abs(V[bus])
    thetai = np.angle(V[bus])
    Pi, Qi = 0.0, 0.0

    for nb in neighbors[bus]:
        Vj = abs(V[nb])
        thetaj = np.angle(V[nb])
        Gij = Ybus[bus, nb].real
        Bij = Ybus[bus, nb].imag

        Pi += Vi * Vj * (Gij * np.cos(thetai - thetaj) +
                         Bij * np.sin(thetai - thetaj))
        Qi += Vi * Vj * (Gij * np.sin(thetai - thetaj) -
                         Bij * np.cos(thetai - thetaj))

    # self-admittance part
    Yii = Ybus[bus, bus]
    Pi += Vi ** 2 * Yii.real
    Qi -= Vi ** 2 * Yii.imag

    return Pi, Qi


def add_pseudo_measurements(se_input, unobservable_buses, V, Ybus, neighbors,
                            sigma_pseudo=1.0, logger=None):
    """
    Extend se_input with pseudo-measurements for unobservable buses.
    neighbors: prebuilt neighbor list per bus
    """
    for bus in unobservable_buses:
        Pi, Qi = compute_power_injection(bus, V, Ybus, neighbors)

        pm_p = PseudoMeasurement(Pi, sigma_pseudo, bus, mtype="p_inj")
        pm_q = PseudoMeasurement(Qi, sigma_pseudo, bus, mtype="q_inj")

        se_input.p_inj.append(pm_p)
        se_input.q_inj.append(pm_q)

        if logger:
            logger.add_info(
                f"Pseudo-measurement added at bus {bus}",
                device="pseudo",
                device_class="virtual",
                device_property="P, Q",
                value=(Pi, Qi),
                sigma=sigma_pseudo
            )

    return se_input
