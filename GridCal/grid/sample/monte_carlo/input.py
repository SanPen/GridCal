from numpy.core.multiarray import zeros
from pyDOE import lhs


class MonteCarloInput:

    def __init__(self, n, Scdf, Icdf, Ycdf):
        """

        @param Scdf: Power cumulative density function
        @param Icdf: Current cumulative density function
        @param Ycdf: Admittances cumulative density function
        """
        self.n = n

        self.Scdf = Scdf

        self.Icdf = Icdf

        self.Ycdf = Ycdf

    def __call__(self, samples=0, use_latin_hypercube=False):

        if use_latin_hypercube:

            lhs_points = lhs(self.n, samples=samples, criterion='center')

            if samples > 0:
                S = zeros((samples, self.n), dtype=complex)
                I = zeros((samples, self.n), dtype=complex)
                Y = zeros((samples, self.n), dtype=complex)

                for i in range(self.n):
                    if self.Scdf[i] is not None:
                        S[:, i] = self.Scdf[i].get_at(lhs_points[:, i])

        else:
            if samples > 0:
                S = zeros((samples, self.n), dtype=complex)
                I = zeros((samples, self.n), dtype=complex)
                Y = zeros((samples, self.n), dtype=complex)

                for i in range(self.n):
                    if self.Scdf[i] is not None:
                        S[:, i] = self.Scdf[i].get_sample(samples)
            else:
                S = zeros(self.n, dtype=complex)
                I = zeros(self.n, dtype=complex)
                Y = zeros(self.n, dtype=complex)

                for i in range(self.n):
                    if self.Scdf[i] is not None:
                        S[i] = complex(self.Scdf[i].get_sample()[0])

        time_series_input = TimeSeriesInput()
        time_series_input.S = S
        time_series_input.I = I
        time_series_input.Y = Y
        time_series_input.valid = True

        return time_series_input

    def get_at(self, x):
        """
        Get samples at x
        Args:
            x: values in [0, 1+ to sample the CDF

        Returns:

        """
        S = zeros((1, self.n), dtype=complex)
        I = zeros((1, self.n), dtype=complex)
        Y = zeros((1, self.n), dtype=complex)

        for i in range(self.n):
            if self.Scdf[i] is not None:
                S[:, i] = self.Scdf[i].get_at(x[i])

        time_series_input = TimeSeriesInput()
        time_series_input.S = S
        time_series_input.I = I
        time_series_input.Y = Y
        time_series_input.valid = True

        return time_series_input
