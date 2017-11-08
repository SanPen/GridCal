import pandas as pd
from numpy.core.multiarray import zeros


class TimeSeriesInput:

    def __init__(self, s_profile: pd.DataFrame=None, i_profile: pd.DataFrame=None, y_profile: pd.DataFrame=None):
        """
        Time series input
        @param s_profile: DataFrame with the profile of the injected power at the buses
        @param i_profile: DataFrame with the profile of the injected current at the buses
        @param y_profile: DataFrame with the profile of the shunt admittance at the buses
        """

        # master time array. All the profiles must match its length
        self.time_array = None

        self.Sprof = s_profile
        self.Iprof = i_profile
        self.Yprof = y_profile

        # Array of load admittances (shunt)
        self.Y = None

        # Array of load currents
        self.I = None

        # Array of aggregated bus power (loads, generators, storage, etc...)
        self.S = None

        # is this timeSeriesInput valid? typically it is valid after compiling it
        self.valid = False

    def compile(self):
        """
        Generate time-consistent arrays
        @return:
        """
        cols = list()
        self.valid = False
        merged = None
        for p in [self.Sprof, self.Iprof, self.Yprof]:
            if p is None:
                cols.append(None)
            else:
                if merged is None:
                    merged = p
                else:
                    merged = pd.concat([merged, p], axis=1)
                cols.append(p.columns)
                self.valid = True

        # by merging there could have been time inconsistencies that would produce NaN
        # to solve it we "interpolate" by replacing the NaN by the nearest value
        if merged is not None:
            merged.interpolate(method='nearest', axis=0, inplace=True)

            t, n = merged.shape

            # pick the merged series time
            self.time_array = merged.index.values

            # Array of aggregated bus power (loads, generators, storage, etc...)
            if cols[0] is not None:
                self.S = merged[cols[0]].values
            else:
                self.S = zeros((t, n), dtype=complex)

            # Array of load currents
            if cols[1] is not None:
                self.I = merged[cols[1]].values
            else:
                self.I = zeros((t, n), dtype=complex)

            # Array of load admittances (shunt)
            if cols[2] is not None:
                self.Y = merged[cols[2]].values
            else:
                self.Y = zeros((t, n), dtype=complex)

    def get_at(self, t):
        """
        Returns the necessary values
        @param t: time index
        @return:
        """
        return self.Y[t, :], self.I[t, :], self.S[t, :]

    def get_from_buses(self, bus_idx):
        """

        @param bus_idx:
        @return:
        """
        ts = TimeSeriesInput()
        ts.S = self.S[:, bus_idx]
        ts.I = self.I[:, bus_idx]
        ts.Y = self.Y[:, bus_idx]
        ts.valid = True
        return ts

    def apply_from_island(self, res, bus_original_idx, branch_original_idx, nbus_full, nbranch_full):
        """

        :param res:
        :param bus_original_idx:
        :param branch_original_idx:
        :param nbus_full:
        :param nbranch_full:
        :return:
        """

        if self.Sprof is None:
            self.time_array = res.time_array
            t = len(self.time_array)
            self.Sprof = pd.DataFrame()  # zeros((t, nbus_full), dtype=complex)
            self.Iprof = pd.DataFrame()  # zeros((t, nbranch_full), dtype=complex)
            self.Yprof = pd.DataFrame()  # zeros((t, nbus_full), dtype=complex)

        self.Sprof[res.Sprof.columns.values] = res.Sprof
        self.Iprof[res.Iprof.columns.values] = res.Iprof
        self.Yprof[res.Yprof.columns.values] = res.Yprof
