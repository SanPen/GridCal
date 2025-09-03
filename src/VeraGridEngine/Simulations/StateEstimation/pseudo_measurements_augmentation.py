

import numpy as np

from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.measurement import MeasurementTemplate
from VeraGridEngine.enumerations import DeviceType

class PseudoMeasurement(MeasurementTemplate):
    def __init__(self, value, sigma, api_obj: Bus, name="",
                 idtag = None):
        # If this has to be injected in DB it has to get a object instance of class Device. In order
        # to persist it in DB it should be saved in Asset class !
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
        MeasurementTemplate.__init__(self,
                                     value=value,
                                     uncertainty=sigma,
                                     api_obj=api_obj,
                                     name=name,
                                     idtag=idtag,
                                     device_type=DeviceType.NoDevice)
        self.value = value
        self.sigma = sigma
        self.bus = api_obj


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


def add_pseudo_measurements(se_input, unobservable_buses, V, Ybus, neighbors,bus_dict,
                            sigma_pseudo=1.0,Sbase=100,logger=None, ):
    """
    Extend se_input with pseudo-measurements for unobservable buses.
    neighbors: prebuilt neighbor list per bus
    """
    for bus_idx in unobservable_buses:
        Pi, Qi = compute_power_injection(bus_idx, V, Ybus, neighbors)

        # Fallback for zero pseudo-measurements
        if abs(Pi) < 1e-6:
            # Use average of neighboring line flows (approximation)
            if neighbors[bus_idx]:
                Pi = sum(abs(Ybus[bus_idx, nb]) * abs(V[bus_idx]) * abs(V[nb]) for nb in neighbors[bus_idx]) / len(neighbors[bus_idx])
            else:
                Pi = 0.1  # small default non-zero value

        if abs(Qi) < 1e-6:
            Qi = 0.0  # often reactive load is unknown; can keep 0 or small value

        # Get the Bus object for this bus_idx
        bus_obj = bus_dict[bus_idx]
        pm_p = PseudoMeasurement(Pi*Sbase, sigma_pseudo, bus_obj,"pseudo")
        pm_q = PseudoMeasurement(Qi*Sbase, sigma_pseudo, bus_obj, "pseudo",)# converted later to pu in get_measurements
        se_input.p_idx.append(bus_idx)  # or appropriate index mapping
        se_input.p_inj.append(pm_p)

        se_input.q_idx.append(bus_idx)
        se_input.q_inj.append(pm_q)

        if logger:
            logger.add_info(
                f"Pseudo-measurement added at bus {bus_obj}",
                device="pseudo",
                device_class="virtual",
                device_property="P, Q",
                value=(Pi, Qi)
            )

    return se_input
