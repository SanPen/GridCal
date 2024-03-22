
import pandas as pd
from GridCalEngine.Devices.Branches.tap_changer import TapChanger, TapChangerTypes


def test_tap_changer1():
    """
    Test the TapChanger 1
    :return:
    """
    tc = TapChanger(total_positions=13,
                    neutral_position=6,
                    dV=0.01,  # p.u.
                    asymmetry_angle=90,  # deg
                    tc_type=TapChangerTypes.VoltageRegulation)

    print(tc.to_df())

    tc.tap_position = 0
    a = tc.get_tap_phase()
    r = tc.get_tap_module()

    tc.tap_position = 3
    a = tc.get_tap_phase()
    r = tc.get_tap_module()

    tc.tap_position = -3
    a = tc.get_tap_phase()
    r = tc.get_tap_module()

    print()
