# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

from enum import Enum
import pandas as pd
import numpy as np
import datetime
from typing import List, Dict

from GridCal.Engine.plot_config import LINEWIDTH, plt


class BusMode(Enum):
    PQ = 1
    PV = 2
    Slack = 3
    NONE = 4
    STO_DISPATCH = 5  # Storage dispatch, in practice it is the same as REF
    PVB = 6


class BranchImpedanceMode(Enum):
    Specified = 0
    Upper = 1
    Lower = 2


class SolverType(Enum):
    """
    Refer to the :ref:`Power Flow section<power_flow>` for details about the different
    algorithms supported by **GridCal**.
    """

    NR = 'Newton Raphson'
    NRD = 'Newton Raphson Decoupled'
    NRFD_XB = 'Fast decoupled XB'
    NRFD_BX = 'Fast decoupled BX'
    GAUSS = 'Gauss-Seidel'
    DC = 'Linear DC'
    HELM = 'Holomorphic Embedding'
    ZBUS = 'Z-Gauss-Seidel'
    IWAMOTO = 'Iwamoto-Newton-Raphson'
    CONTINUATION_NR = 'Continuation-Newton-Raphson'
    HELMZ = 'HELM-Z'
    LM = 'Levenberg-Marquardt'
    FASTDECOUPLED = 'Fast decoupled'
    LACPF = 'Linear AC'
    DC_OPF = 'Linear DC OPF'
    AC_OPF = 'Linear AC OPF'
    Simple_OPF = 'Simple dispatch'
    Proportional_OPF = 'Proportional OPF'
    NRI = 'Newton-Raphson in current'
    DYCORS_OPF = 'DYCORS OPF'
    GA_OPF = 'Genetic Algorithm OPF'
    NELDER_MEAD_OPF = 'Nelder Mead OPF'


class ReactivePowerControlMode(Enum):
    """
    The :ref:`ReactivePowerControlMode<q_control>` offers 3 modes to control how
    :ref:`Generator<generator>` objects supply reactive power:

    **NoControl**: In this mode, the :ref:`generators<generator>` don't try to regulate
    the voltage at their :ref:`bus<bus>`.

    **Direct**: In this mode, the :ref:`generators<generator>` try to regulate the
    voltage at their :ref:`bus<bus>`. **GridCal** does so by applying the following
    algorithm in an outer control loop. For grids with numerous
    :ref:`generators<generator>` tied to the same system, for example wind farms, this
    control method sometimes fails with some :ref:`generators<generator>` not trying
    hard enough*. In this case, the simulation converges but the voltage controlled
    :ref:`buses<bus>` do not reach their target voltage, while their
    :ref:`generator(s)<generator>` haven't reached their reactive power limit. In this
    case, the slower **Iterative** control mode may be used (see below).

        ON PV-PQ BUS TYPE SWITCHING LOGIC IN POWER FLOW COMPUTATION
        Jinquan Zhao

        1) Bus i is a PQ bus in the previous iteration and its
           reactive power was fixed at its lower limit:

            If its voltage magnitude Vi >= Viset, then

                it is still a PQ bus at current iteration and set Qi = Qimin .

                If Vi < Viset , then

                    compare Qi with the upper and lower limits.

                    If Qi >= Qimax , then
                        it is still a PQ bus but set Qi = Qimax .
                    If Qi <= Qimin , then
                        it is still a PQ bus and set Qi = Qimin .
                    If Qimin < Qi < Qi max , then
                        it is switched to PV bus, set Vinew = Viset.

        2) Bus i is a PQ bus in the previous iteration and
           its reactive power was fixed at its upper limit:

            If its voltage magnitude Vi <= Viset , then:
                bus i still a PQ bus and set Q i = Q i max.

                If Vi > Viset , then

                    Compare between Qi and its upper/lower limits

                    If Qi >= Qimax , then
                        it is still a PQ bus and set Q i = Qimax .
                    If Qi <= Qimin , then
                        it is still a PQ bus but let Qi = Qimin in current iteration.
                    If Qimin < Qi < Qimax , then
                        it is switched to PV bus and set Vinew = Viset

        3) Bus i is a PV bus in the previous iteration.

            Compare Q i with its upper and lower limits.

            If Qi >= Qimax , then
                it is switched to PQ and set Qi = Qimax .
            If Qi <= Qimin , then
                it is switched to PQ and set Qi = Qimin .
            If Qi min < Qi < Qimax , then
                it is still a PV bus.

    **Iterative**: As mentioned above, the **Direct** control mode may not yield
    satisfying results in some isolated cases. The **Direct** control mode tries to
    jump to the final solution in a single or few iterations, but in grids where a
    significant change in reactive power at one :ref:`generator<generator>` has a
    significant impact on other :ref:`generators<generator>`, additional iterations may
    be required to reach a satisfying solution.

    Instead of trying to jump to the final solution, the **Iterative** mode raises or
    lowers each :ref:`generator's<generator>` reactive power incrementally. The
    increment is determined using a logistic function based on the difference between
    the current :ref:`bus<bus>` voltage its target voltage. The steepness factor
    :code:`k` of the logistic function was determined through trial and error, with the
    intent of reducing the number of iterations while avoiding instability. Other
    values may be specified in :ref:`PowerFlowOptions<pf_options>`.

    The :math:`Q_{Increment}` in per unit is determined by:

    .. math::

        Q_{Increment} = 2 * \\left[\\frac{1}{1 + e^{-k|V_2 - V_1|}}-0.5\\right]

    Where:

        k = 30 (by default)

    """
    NoControl = "NoControl"
    Direct = "Direct"
    Iterative = "Iterative"


class TapsControlMode(Enum):
    """
    The :ref:`TapsControlMode<taps_control>` offers 3 modes to control how
    :ref:`transformers<transformer>`' :ref:`tap changer<tap_changer>` regulate
    voltage on their regulated :ref:`bus<bus>`:

    **NoControl**: In this mode, the :ref:`transformers<transformer>` don't try to
    regulate the voltage at their :ref:`bus<bus>`.

    **Direct**: In this mode, the :ref:`transformers<transformer>` try to regulate
    the voltage at their bus. **GridCal** does so by jumping straight to the tap that
    corresponds to the desired transformation ratio, or the highest or lowest tap if
    the desired ratio is outside of the tap range.

    This behavior may fail in certain cases, especially if both the
    :ref:`TapControlMode<taps_control>` and :ref:`ReactivePowerControlMode<q_control>`
    are set to **Direct**. In this case, the simulation converges but the voltage
    controlled :ref:`buses<bus>` do not reach their target voltage, while their
    :ref:`generator(s)<generator>` haven't reached their reactive power limit. When
    this happens, the slower **Iterative** control mode may be used (see below).

    **Iterative**: As mentioned above, the **Direct** control mode may not yield
    satisfying results in some isolated cases. The **Direct** control mode tries to
    jump to the final solution in a single or few iterations, but in grids where a
    significant change of tap at one :ref:`transformer<transformer>` has a
    significant impact on other :ref:`transformers<transformer>`, additional
    iterations may be required to reach a satisfying solution.

    Instead of trying to jump to the final solution, the **Iterative** mode raises or
    lowers each :ref:`transformer's<transformer>` tap incrementally.
    """

    NoControl = "NoControl"
    Direct = "Direct"
    Iterative = "Iterative"


class SyncIssueType(Enum):
    Added = 'Added'
    Deleted = 'Deleted'
    Conflict = 'Conflict'


class CDF:
    """
    Inverse Cumulative density function of a given array of data
    """

    def __init__(self, data):
        """
        Constructor
        @param data: Array (list or numpy array)
        """
        # Create the CDF of the data
        # sort the data:
        if type(data) is pd.DataFrame:
            self.arr = np.sort(np.ndarray.flatten(data.values))

        else:
            self.arr = np.sort(data, axis=0)

        self.iscomplex = np.iscomplexobj(self.arr)

        # calculate the proportional values of samples
        n = len(data)
        if n > 1:
            self.prob = np.arange(n, dtype=float) / (n - 1)
        else:
            self.prob = np.arange(n, dtype=float)

        # iterator index
        self.idx = 0

        # array length
        self.len = len(self.arr)

    def __call__(self):
        """
        Call this as CDF()
        @return:
        """
        return self.arr

    def __iter__(self):
        """
        Iterator constructor
        @return:
        """
        self.idx = 0
        return self

    def __next__(self):
        """
        Iterator next element
        @return:
        """
        if self.idx == self.len:
            raise StopIteration

        self.idx += 1
        return self.arr[self.idx - 1]

    def __add__(self, other):
        """
        Sum of two CDF
        @param other:
        @return: A CDF object with the sum of other CDF to this CDF
        """
        return CDF(np.array([a + b for a in self.arr for b in other]))

    def __sub__(self, other):
        """
        Subtract of two CDF
        @param other:
        @return: A CDF object with the subtraction a a CDF to this CDF
        """
        return CDF(np.array([a - b for a in self.arr for b in other]))

    def get_sample(self, npoints=1):
        """
        Samples a number of uniform distributed points and
        returns the corresponding probability values given the CDF.
        @param npoints: Number of points to sample, 1 by default
        @return: Corresponding probabilities
        """
        pt = np.random.uniform(0, 1, npoints)
        if self.iscomplex:
            a = np.interp(pt, self.prob, self.arr.real)
            b = np.interp(pt, self.prob, self.arr.imag)
            return a + 1j * b
        else:
            return np.interp(pt, self.prob, self.arr)

    def get_at(self, prob):
        """
        Samples a number of uniform distributed points and
        returns the corresponding probability values given the CDF.
        @param prob: probability from 0 to 1
        @return: Corresponding CDF value
        """
        if self.iscomplex:
            a = np.interp(prob, self.prob, self.arr.real)
            b = np.interp(prob, self.prob, self.arr.imag)
            return a + 1j * b
        else:
            return np.interp(prob, self.prob, self.arr)

    def plot(self, ax=None):
        """
        Plots the CFD
        @param ax: MatPlotLib axis to plot into
        @return:
        """
        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)
        ax.plot(self.prob, self.arr, linewidth=LINEWIDTH)
        ax.set_xlabel('$p(x)$')
        ax.set_ylabel('$x$')
        # ax.plot(self.norm_points, self.values, 'x')


class StatisticalCharacterization:
    """
    Object to store the statistical characterization
    It is useful because the statistical characterizations can be:
    - not grouped
    - grouped by day
    - grouped by hour
    """

    def __init__(self, gen_P, load_P, load_Q):
        """
        Constructor
        @param gen_P: 2D array with the active power generation profiles (time, generator)
        @param load_P: 2D array with the active power load profiles (time, load)
        @param load_Q: 2D array with the reactive power load profiles time, load)
        @return:
        """
        # Arrays where to store the statistical laws for sampling
        self.gen_P_laws = list()  # List[CDF]
        self.load_P_laws = list()  # List[CDF]
        self.load_Q_laws = list()  # List[CDF]

        # Create a CDF for every profile
        rows, cols = np.shape(gen_P)
        for i in range(cols):
            cdf = CDF(gen_P[:, i])
            self.gen_P_laws.append(cdf)

        rows, cols = np.shape(load_P)
        for i in range(cols):
            cdf = CDF(load_P[:, i])
            self.load_P_laws.append(cdf)

        rows, cols = np.shape(load_Q)
        for i in range(cols):
            cdf = CDF(load_Q[:, i])
            self.load_Q_laws.append(cdf)

    def get_sample(self, load_enabled_idx, gen_enabled_idx, npoints=1):
        """
        Returns a 2D array containing for load and generation profiles, shape (time, load)
        The profile is sampled from the original data CDF functions

        @param npoints: number of sampling points
        @return:
        PG: generators profile
        S: loads profile
        """
        # nlp = len(self.load_P_laws)
        # nlq = len(self.load_Q_laws)
        # ngp = len(self.gen_P_laws)
        nlp = len(load_enabled_idx)
        ngp = len(gen_enabled_idx)

        if len(self.load_P_laws) != len(self.load_Q_laws):
            raise Exception('Different number of elements in the load active and reactive profiles.')

        P = [None] * nlp
        Q = [None] * nlp
        PG = [None] * ngp

        k = 0
        for i in load_enabled_idx:
            P[k] = self.load_P_laws[i].get_sample(npoints)
            Q[k] = self.load_Q_laws[i].get_sample(npoints)
            k += 1

        k = 0
        for i in gen_enabled_idx:
            PG[k] = self.gen_P_laws[i].get_sample(npoints)
            k += 1

        P = np.array(P)
        Q = np.array(Q)
        S = P + 1j * Q

        PG = np.array(PG)

        return PG.transpose(), S.transpose()

    def plot(self, ax):
        """
        Plot this statistical characterization
        @param ax:  matplotlib index
        @return:
        """
        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        for cdf in self.gen_P_laws:
            ax.plot(cdf.prob, cdf.arr, color='r', marker='x')
        for cdf in self.load_P_laws:
            ax.plot(cdf.prob, cdf.arr, color='g', marker='x')
        for cdf in self.load_Q_laws:
            ax.plot(cdf.prob, cdf.arr, color='b', marker='x')

        ax.set_xlabel('$p(x)$')
        ax.set_ylabel('$x$')


class MIPSolvers(Enum):
    CBC = 'CBC'
    SCIP = 'SCIP'
    CPLEX = 'CPLEX'
    GUROBI = 'Gurobi'
    XPRESS = 'Xpress'


class TimeGrouping(Enum):
    NoGrouping = 'No grouping'
    Monthly = 'Monthly'
    Weekly = 'Weekly'
    Daily = 'Daily'
    Hourly = 'Hourly'


def classify_by_hour(t: pd.DatetimeIndex):
    """
    Passes an array of TimeStamps to an array of arrays of indices
    classified by hour of the year
    @param t: Pandas time Index array
    @return: list of lists of integer indices
    """
    n = len(t)

    offset = t[0].hour * t[0].dayofyear
    mx = t[n - 1].hour * t[n - 1].dayofyear

    arr = list()

    for i in range(mx - offset + 1):
        arr.append(list())

    for i in range(n):
        hourofyear = t[i].hour * t[i].dayofyear
        arr[hourofyear - offset].append(i)

    return arr


def classify_by_day(t: pd.DatetimeIndex):
    """
    Passes an array of TimeStamps to an array of arrays of indices
    classified by day of the year
    @param t: Pandas time Index array
    @return: list of lists of integer indices
    """
    n = len(t)

    offset = t[0].dayofyear
    mx = t[n - 1].dayofyear

    arr = list()

    for i in range(mx - offset + 1):
        arr.append(list())

    for i in range(n):
        hourofyear = t[i].dayofyear
        arr[hourofyear - offset].append(i)

    return arr


def get_time_groups(t_array: pd.DatetimeIndex, grouping: TimeGrouping):
    """
    Get the indices delimiting a number of groups
    :param t_array: DatetimeIndex object containing dates
    :param grouping: TimeGrouping value
    :return: list of indices that determine the partitions
    """
    groups = list()

    last = -1

    i = 0
    for i, t in enumerate(t_array):

        if grouping == TimeGrouping.Monthly:
            if t.month != last:
                last = t.month
                groups.append(i)

        elif grouping == TimeGrouping.Weekly:
            if t.week != last:
                last = t.week
                groups.append(i)

        elif grouping == TimeGrouping.Daily:
            if t.day != last:
                last = t.day
                groups.append(i)

        elif grouping == TimeGrouping.Hourly:
            if t.hour != last:
                last = t.hour
                groups.append(i)

    # add the last index if it is not already there
    if len(t_array) > 0:
        if i != groups[len(groups) - 1]:
            groups.append(i)

    return groups


class LogSeverity(Enum):
    Error = 'Error'
    Warning = 'Warning'
    Information = 'Information'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return LogSeverity[s]
        except KeyError:
            return s


class LogEntry:

    def __init__(self, msg="", severity: LogSeverity = LogSeverity.Information, device="", value="", expected_value=""):

        self.time = "{date:%H:%M:%S}".format(date=datetime.datetime.now())  # might use %Y/%m/%d %H:%M:%S
        self.msg = str(msg)
        self.severity = severity
        self.device = device
        self.value = value
        self.expected_value = str(expected_value)

    def to_list(self):
        return [self.time, self.severity.value, self.msg, self.device, self.value, self.expected_value]

    def __str__(self):
        return "{0} {1}: {2} {3} {4} {5}".format(self.time,
                                                 self.severity.value,
                                                 self.msg,
                                                 self.device,
                                                 self.value,
                                                 self.expected_value)


class Logger:

    def __init__(self):

        self.entries = list()  # List[LogEntry]

    def append(self, txt):
        """

        :param txt:
        :return:
        """
        self.entries.append(LogEntry(txt))

    def has_logs(self):
        return len(self.entries) > 0

    def add_info(self, msg, device="", value="", expected_value=""):
        """

        :param msg:
        :param device:
        :param value:
        :param expected_value
        :return:
        """
        self.entries.append(LogEntry(msg, LogSeverity.Information, device, value, expected_value))

    def add_warning(self, msg, device="", value="", expected_value=""):
        """

        :param msg:
        :param device:
        :param value:
        :param expected_value
        :return:
        """
        self.entries.append(LogEntry(msg, LogSeverity.Warning, device, value, expected_value))

    def add_error(self, msg, device="", value="", expected_value=""):
        """

        :param msg:
        :param device:
        :param value:
        :param expected_value
        :return:
        """
        self.entries.append(LogEntry(msg, LogSeverity.Error, device, value, expected_value))

    def add(self, msg, severity: LogSeverity = LogSeverity.Error, device="", value="", expected_value=""):
        """

        :param msg:
        :param severity:
        :param device:
        :param value:
        :param expected_value
        :return:
        """
        self.entries.append(LogEntry(msg, severity, device, value, expected_value))

    def to_dict(self):
        """
        Get the logs sorted by severity and message
        :return: Dictionary[Dictionary[List[time, device, value, expected value]]]
        """
        by_severity = dict()

        for e in self.entries:

            if e.severity.value not in by_severity.keys():
                by_severity[e.severity.value] = dict()

            by_msg = by_severity[e.severity.value]

            if e.msg in by_msg.keys():
                # add msg to existing msg list
                by_msg[e.msg].append((e.time, e.device, e.value, e.expected_value))
            else:
                # add msg entry for the first time
                by_msg[e.msg] = [(e.time, e.device, e.value, e.expected_value)]

        return by_severity

    def to_df(self):
        """
        Get DataFrame
        :return:
        """
        data = [e.to_list() for e in self.entries]
        df = pd.DataFrame(data=data, columns=['Time', 'Severity', 'Message', 'Device', 'Value', 'Expected value'])
        df.set_index('Time', inplace=True)
        return df

    def to_csv(self, fname):
        self.to_df().to_csv(fname)

    def to_xlsx(self, fname):
        self.to_df().to_excel(fname)

    def __str__(self):

        val = ''
        for e in self.entries:
            val += str(e) + '\n'
        return val

    def __getitem__(self, key):
        """
        get [index] implementation
        :param key: integer
        :return: message, severity
        """
        return self.entries[key]

    def __setitem__(self, idx, value):
        """
        set [index] implementation
        :param idx: integer
        :param value: string message
        :return: Nothing
        """
        self.entries[idx] = value

    def __iadd__(self, other: "Logger"):
        """
        += implementation
        :param other:
        :return:
        """

        if other is not None:
            self.entries += other.entries
        return self

    def __len__(self):
        return len(self.entries)


if __name__ == '__main__':
    from GridCal.Engine.IO.file_handler import FileOpen

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39.gridcal'

    main_circuit = FileOpen(fname).open()

    get_time_groups(t_array=main_circuit.time_profile, grouping=TimeGrouping.Monthly)

    get_time_groups(t_array=main_circuit.time_profile, grouping=TimeGrouping.Weekly)

    get_time_groups(t_array=main_circuit.time_profile, grouping=TimeGrouping.Daily)

    get_time_groups(t_array=main_circuit.time_profile, grouping=TimeGrouping.Hourly)
