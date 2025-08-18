
import pandapower

from GridCalEngine.IO.others.pandapower_parser import Panda2GridCal
from GridCalEngine.Simulations.StateEstimation.state_stimation_driver import StateEstimation

def test_state_estimation():
    breakpoint()
    net_wns = pandapower.from_json(
            f"src/tests/data/grids/state-estimation /small_grid_gb_hv_estimate_raw_expected.json"
        )
    g = Panda2GridCal(net_wns)
    grid = g.get_multicircuit()
    se = StateEstimation(circuit=grid)
    se.run()