

from GridCalEngine.Devices.Branches.tap_changer import TapChanger, TapChangerTypes


def test_tap_changer1():

    tc = TapChanger(total_positions=13,
                    neutral_position=6,
                    dV=0.01,
                    asymmetry_angle=0,
                    tpe=TapChangerTypes.Asymmetrical90)

    print(tc.steps)

    ndu = tc.ndu()
    a = tc.get_tap_phase()
    r = tc.get_tap_module()
    print(a, r)

    tc.tap_up()
    tc.tap_up()
    tc.tap_up()
    tc.tap_up()

    ndu = tc.ndu()
    a = tc.get_tap_phase()
    r = tc.get_tap_module()
    print(a, r)

    tc.reset()
    tc.tap_down()
    tc.tap_down()
    tc.tap_down()
    tc.tap_down()

    ndu = tc.ndu()
    a = tc.get_tap_phase()
    r = tc.get_tap_module()
    print(a, r)

    print()
