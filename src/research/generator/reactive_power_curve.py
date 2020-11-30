import numpy as np
from matplotlib import pyplot as plt


def make_default_q_curve(Snom, Qmin, Qmax, n=3):
    """
    Compute the generator capability curve
    :param Snom: Nominal power
    :param Qmin: Minimum reactive power
    :param Qmax: Maximum reactive power
    :param n: number of points, at least 3
    :return: Array of points [(P1, Qmin1, Qmax1), (P2, Qmin2, Qmax2), ...]
    """
    assert(n > 2)

    pts = np.zeros((n, 3))
    s2 = Snom * Snom

    # Compute the intersections of the Qlimits with the natural curve
    p0_max = np.sqrt(s2 - Qmax * Qmax)
    p0_min = np.sqrt(s2 - Qmin * Qmin)
    p0 = min(p0_max, p0_min)  # pick the lower limit as the starting point for sampling

    pts[1:, 0] = np.linspace(p0, Snom, n - 1)
    pts[0, 0] = 0
    pts[0, 1] = Qmin
    pts[0, 2] = Qmax

    for i in range(1, n):
        p2 = pts[i, 0] * pts[i, 0]  # P^2
        q = np.sqrt(s2 - p2)  # point that naturally matches Q = sqrt(S^2 - P^2)

        # assign the natural point if it does not violates the limits imposes, else set the limit
        qmin = -q if -q > Qmin else Qmin
        qmax = q if q < Qmax else Qmax

        # Enforce that Qmax > Qmin
        if qmax < qmin:
            qmax = qmin
        if qmin > qmax:
            qmin = qmax

        # Assign the points
        pts[i, 1] = qmin
        pts[i, 2] = qmax

    return pts


def get_q_limits(q_points, p):
    """
    Get the reactive power limits
    :param q_points: Array of points [(P1, Qmin1, Qmax1), (P2, Qmin2, Qmax2), ...]
    :param p: active power value (or array)
    :return:
    """
    all_p = q_points[:, 0]
    all_qmin = q_points[:, 1]
    all_qmax = q_points[:, 2]

    qmin = np.interp(p, all_p, all_qmin)
    qmax = np.interp(p, all_p, all_qmax)

    return qmin, qmax


Snom = 650
points = make_default_q_curve(Snom=Snom, Qmin=-100, Qmax=300)

# plot the capability curve
p = points[:, 0]
qmin = points[:, 1]
qmax = points[:, 2]
plt.plot(qmax, p, 'x-')
plt.plot(qmin, p, 'x-')

# generate random points and interpolate the curve to get the reactive power limits
p2 = np.random.random(10) * Snom
qmin2, qmax2 = get_q_limits(q_points=points, p=p2)
plt.plot(qmax2, p2, 'o')
plt.plot(qmin2, p2, 'o')

plt.show()
