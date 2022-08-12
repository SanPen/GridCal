import numpy as np
from matplotlib import pyplot as plt
from scipy.integrate import quad


def W(x):
    return x / np.power(1 + np.power(x, 2), 2)


def metropolis_step(func, x0, d=1.0, metropolis_hastings=False):
    """
    Metropolis jump
    This utilizes the normal distribution to compute the proposed jumps
    :param func: function to sample
    :param x0: current markov point
    :param d: maximum jump size from the current markov state to the next (AKA Sigma)
    :return: next markov point, accepted?
    """
    if metropolis_hastings:
        # metropolis-hastings
        xp = np.random.normal(loc=x0, scale=d)
    else:
        # simple metropolis
        xp = x0 + d * np.random.uniform(low=-1, high=1)

    if func(xp) / func(x0) > np.random.uniform(low=0, high=1):
        return xp, 1  # accepted the sample
    return x0, 0  # rejected the sample


def metropolis(func, x0, d, n_samples=100000, metropolis_hastings=True):
    """
    Metropolis sampling algorithm
    (an MCMC algorithm)
    :param func: unction to sample from
    :param x0: starting point (should be around the high probability area)
    :param d: maximum jump size from the current state to the next
    :param n_samples: number of samples
    :param metropolis_hastings: Use the Metropolis-Hastings strategy? else the Metropolis strategy
    :return: samples array, sample acceptance rate
    """
    # compute the metropolis algorithm
    samples = np.empty(n_samples)
    samples[0] = x0
    total_accepted = 0
    for i in range(1, n_samples):
        samples[i], accepted = metropolis_step(func=func,
                                               x0=samples[i - 1],
                                               d=d,
                                               metropolis_hastings=metropolis_hastings)
        total_accepted += accepted

    acceptance_rate = total_accepted / (n_samples - 1)

    return samples, acceptance_rate

# compute the integral of the function so that we can normalize it
# (this is a condition of the method)
norm = quad(W, 0, np.infty)[0]
x = np.linspace(0, 10, 100)
fx = W(x) / norm  # normalized function

# plot the normalized function
plt.plot(x, fx)

samples_, acceptance_rate_ = metropolis(func=W,
                                        x0=3.0,
                                        d=2.,
                                        n_samples=int(1e5),
                                        metropolis_hastings=False)

# the acceptance rate should be as close to 0.5 as possible
# that ensures that we've been sampling correctly
print('Acceptance rate:', acceptance_rate_)

n_burning_in = 100  # number of samples after which we consider that we are actually sampling correctly
plt.hist(samples_[n_burning_in:], bins=100, density=True)

plt.show()
