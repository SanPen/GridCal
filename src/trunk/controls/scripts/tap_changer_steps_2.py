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

tap_changer = gci.TapChanger()
tap_changer.init_from_cgmes(
    low=low,
    high=high,
    normal=normal,
    neutral=neutral,
    stepVoltageIncrement=sVI,
    step=step
)
print(tap_changer.total_positions, tap_changer.tap_position)
print(f'{tap_changer.get_cgmes_values()}')

low_2, high_2, normal_2, neutral_2, sVI_2, step_2 = tap_changer.get_cgmes_values()

# df = pd.DataFrame(data={'idx': np.arange(len(tap_changer._m_array)),
#                         'm': tap_changer._m_array,
#                         'tau': tap_changer._tau_array
#                         })
#
# print(tap_changer.get_tap_module())
# print(df)

assert low == low_2
assert high == high_2
assert normal == normal_2
assert neutral == neutral_2
assert sVI == sVI_2
assert step == step_2
