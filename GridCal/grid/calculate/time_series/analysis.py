from numpy.core.multiarray import zeros

from GridCal.grid.calculate.time_series.results import TimeSeriesResults


class TimeSeriesResultsAnalysis:

    def __init__(self, results: TimeSeriesResults):
        self.res = results

        self.branch_overload_frequency = None
        self.bus_undervoltage_frequency = None
        self.bus_overvoltage_frequency = None

        self.branch_overload_accumulated = None
        self.bus_undervoltage_accumulated = None
        self.bus_overvoltage_accumulated = None

        self.buses_selected_for_storage_frequency = None

        self.__run__()

    def __run__(self):
        self.branch_overload_frequency = zeros(self.res.m)
        self.bus_undervoltage_frequency = zeros(self.res.n)
        self.bus_overvoltage_frequency = zeros(self.res.n)

        self.branch_overload_accumulated = zeros(self.res.m, dtype=complex)
        self.bus_undervoltage_accumulated = zeros(self.res.n, dtype=complex)
        self.bus_overvoltage_accumulated = zeros(self.res.n, dtype=complex)

        self.buses_selected_for_storage_frequency = zeros(self.res.n)

        for i in range(self.res.nt):
            self.branch_overload_frequency[self.res.overloads_idx[i]] += 1
            self.bus_undervoltage_frequency[self.res.undervoltage_idx[i]] += 1
            self.bus_overvoltage_frequency[self.res.overvoltage_idx[i]] += 1

            self.branch_overload_accumulated[self.res.overloads_idx[i]] += self.res.overloads[i]
            self.bus_undervoltage_accumulated[self.res.undervoltage_idx[i]] += self.res.undervoltage[i]
            self.bus_overvoltage_accumulated[self.res.overvoltage_idx[i]] += self.res.overvoltage[i]

            self.buses_selected_for_storage_frequency[self.res.buses_useful_for_storage[i]] += 1
