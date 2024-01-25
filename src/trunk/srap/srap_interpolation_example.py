import numpy as np
from matplotlib import pyplot as plt

p_available = np.array([80, 30, 50, 80, 30, 50])
sensitivities = np.array([0.1, 0.09, 0.07, -0.1, -0.09, -0.07])

overload = -10
srap_pmax_mw = 100  # srap_limit

if overload > 0:

    positives = np.where(sensitivities >= 0)[0]
    p_available2 = p_available[positives]
    sensitivities2 = sensitivities[positives]

    idx = np.argsort(-sensitivities2)  # more positive first

    p_available3 = p_available2[idx]
    sensitivities3 = sensitivities2[idx]

    xp = np.cumsum(p_available3)
    fp = np.cumsum(p_available3 * sensitivities3)

    max_srap_power = np.interp(srap_pmax_mw, xp, fp)

    plt.plot(xp, fp)
    plt.axhline(y=overload, c='b')
    plt.axvline(x=srap_pmax_mw, c='g')

    solved = max_srap_power >= overload

else:

    negatives = np.where(sensitivities <= 0)[0]
    p_available2 = p_available[negatives]
    sensitivities2 = sensitivities[negatives]

    idx = np.argsort(sensitivities2)  # more positive first

    p_available3 = p_available2[idx]
    sensitivities3 = sensitivities2[idx]

    xp = np.cumsum(p_available3)
    fp = np.cumsum(p_available3 * sensitivities3)

    max_srap_power = np.interp(srap_pmax_mw, xp, fp)

    plt.plot(xp, fp)
    plt.axhline(y=overload, c='b')
    plt.axvline(x=srap_pmax_mw, c='g')

    solved = max_srap_power <= overload

print(max_srap_power, solved)

plt.show()
