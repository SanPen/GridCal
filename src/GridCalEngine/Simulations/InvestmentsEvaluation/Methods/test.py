import numpy as np
import matplotlib.pyplot as plt

class ProblemMock:
    def __init__(self, xl, xu):
        self.xl = xl
        self.xu = xu

class SkewedIntegerSampling:
    """
    SkewedIntegerSampling generates samples skewed toward the lower bounds
    but spread across the full lb–ub range. Works for integer variables.
    """
    def _do(self, problem, n_samples, **kwargs):
        xl = np.asarray(problem.xl, dtype=int)
        xu = np.asarray(problem.xu, dtype=int)

        n_var = len(xl)
        X = np.zeros((n_samples, n_var), dtype=int)

        # Generate skewed samples per variable
        for j in range(n_var):
            # Create skewed samples in [0, 1]
            skewed = (np.linspace(0, 1, n_samples) ** 4)

            # Scale to range [xl[j], xu[j]]
            range_j = xu[j] - xl[j]
            values = (skewed * range_j + xl[j]).astype(int)

            # Shuffle for diversity
            np.random.shuffle(values)
            X[:, j] = values

        return X

# Testing setup
if __name__ == "__main__":
    problem = ProblemMock(xl=[0], xu=[100])  # Two variables
    sampler = SkewedIntegerSampling()
    n_samples = 1000

    samples = sampler._do(problem, n_samples)

    # Plot histograms for each variable
    n_var = samples.shape[1]
    fig, axs = plt.subplots(1, n_var, figsize=(5 * n_var, 4))

    if n_var == 1:
        axs = [axs]

    for i in range(n_var):
        axs[i].hist(samples[:, i], bins=20, edgecolor='black')
        axs[i].set_title(f'Variable {i}')
        axs[i].set_xlabel('Value')
        axs[i].set_ylabel('Frequency')

    plt.tight_layout()
    plt.show()
