import pytest
import numpy as np
import os
import VeraGridEngine.api as gce

# Define the path to the test grid file
TEST_GRID_FILENAME = os.path.join(os.path.dirname(__file__), 'data', 'grids', 'switch_try.gridcal')

EXPECTED_PF_REDUCIBLE_FALSE = np.array([
    [10.000000, 10.000000, 10.000000],
    [11.000000, 11.000000, 11.000000],
    [12.000000, 12.000000, 12.000000],
    [13.000000, 13.000000, 13.000000],
    [ 0.000000, 14.000000,  0.000000],
    [15.000000, 15.000000, 15.000000],
    [16.000000, 16.000000, 16.000000],
    [17.000000, 17.000000, 17.000000],
    [18.000000, 18.000000, 18.000000],
    [19.000000, 19.000000, 19.000000]
])

# When reducible=True, the switch column (index 2) should be all zeros
EXPECTED_PF_REDUCIBLE_TRUE = np.array([
    [10.000000, 10.000000, 0.0],
    [11.000000, 11.000000, 0.0],
    [12.000000, 12.000000, 0.0],
    [13.000000, 13.000000, 0.0],
    [ 0.000000, 14.000000, 0.0],
    [15.000000, 15.000000, 0.0],
    [16.000000, 16.000000, 0.0],
    [17.000000, 17.000000, 0.0],
    [18.000000, 18.000000, 0.0],
    [19.000000, 19.000000, 0.0]
])


def find_switch(grid):
    """Helper function to find the first switch in the grid."""
    for switch in grid.switch_devices:
        return switch
    return None

def run_ts_pf_and_get_sf(grid):
    """Runs the time series power flow and returns the Sf results."""
    pf_ts_driver = gce.PowerFlowTimeSeriesDriver(grid)
    pf_ts_driver.run()
    # Order: [Line 1, Line 2, Switch]
    return pf_ts_driver.results.Sf

def test_switch_ts_pf_reducible_false():
    """
    Tests the time series power flow with a non-reducible switch.
    Compares the calculated 'from' power flow (Sf) against expected values.
    """
    grid = gce.open_file(TEST_GRID_FILENAME)
    switch = find_switch(grid)
    if switch is None:
        pytest.fail("No switch found in the test grid.")

    # Set the switch reducible property
    switch.reducible = False

    # Run the time series power flow
    calculated_sf = run_ts_pf_and_get_sf(grid).real

    # Compare the results
    assert np.allclose(calculated_sf, EXPECTED_PF_REDUCIBLE_FALSE, rtol=1e-5, atol=1e-6)


def test_switch_ts_pf_reducible_true():
    """
    Tests the time series power flow with a reducible switch.
    Compares the calculated 'from' power flow (Sf) against expected values.
    """
    grid = gce.open_file(TEST_GRID_FILENAME)
    switch = find_switch(grid)
    if switch is None:
        pytest.fail("No switch found in the test grid.")

    # Set the switch reducible property
    switch.reducible = True

    # Run the time series power flow
    calculated_sf = run_ts_pf_and_get_sf(grid).real

    # Compare the results
    assert np.allclose(calculated_sf, EXPECTED_PF_REDUCIBLE_TRUE, rtol=1e-5, atol=1e-6)

        
if __name__ == "__main__":
    test_switch_ts_pf_reducible_false()
    test_switch_ts_pf_reducible_true()