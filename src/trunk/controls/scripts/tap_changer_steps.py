import pandas as pd
import numpy as np
import GridCalEngine.api as gci

# CGMES data 1
low = -20
high = 20
normal = -2
neutral = 0
sVI = 0.8
step = -2
# # CGMES data 2
# low = 0
# high = 33
# normal = 17
# neutral = 17
# sVI = 0.625
# step = 17

negative_low = low < 0

if negative_low:
    tap_changer = gci.TapChanger(total_positions=high-low,
                                 neutral_position=neutral-low+1,
                                 normal_position=normal-low+1,
                                 dV=sVI/100,
                                 asymmetry_angle=90,
                                 tc_type=gci.TapChangerTypes.VoltageRegulation)
    tap_changer.tap_position = tap_changer.neutral_position + step

else:
    tap_changer = gci.TapChanger(total_positions=high-low,
                                 neutral_position=neutral,
                                 normal_position=normal,
                                 dV=sVI/100,
                                 asymmetry_angle=90,
                                 tc_type=gci.TapChangerTypes.VoltageRegulation)
    tap_changer.tap_position = step

df = pd.DataFrame(data={'idx': np.arange(len(tap_changer._m_array)),
                        'm': tap_changer._m_array,
                        'tau': tap_changer._tau_array
                        })

print(tap_changer.get_tap_module())
print(df)

print('CGMES export')

m = tap_changer.total_positions
if negative_low:
    low_2 = -tap_changer.neutral_position + 1
    high_2 = m-tap_changer.neutral_position + 1
    normal_2 = tap_changer.normal_position + low_2 - 1
    neutral_2 = tap_changer.neutral_position + low_2 - 1
    sVI_2 = tap_changer.dV * 100
    step_2 = tap_changer.tap_position + low_2 - 1
else:
    low_2 = 0
    high_2 = m
    normal_2 = tap_changer.normal_position
    neutral_2 = tap_changer.neutral_position
    sVI_2 = tap_changer.dV * 100
    step_2 = tap_changer.tap_position

assert low == low_2
assert high == high_2
assert normal == normal_2
assert neutral == neutral_2
assert sVI == sVI_2
assert step == step_2
