# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from typing import List, Any, Dict, Union
from enum import Enum
import pandas as pd
import numpy as np
import datetime
import nptyping as npt
from scipy.sparse import csc_matrix, csr_matrix

IntList = List[int]
Numeric = Union[int, float, bool, complex]
NumericVec = npt.NDArray[npt.Shape['*'], npt.Double]
DateVec = npt.NDArray[npt.Shape['*'], npt.Datetime64]
IntVec = npt.NDArray[npt.Shape['*'], npt.Int]
BoolVec = npt.NDArray[npt.Shape['*'], npt.Bool]
Vec = npt.NDArray[npt.Shape['*'], npt.Double]
CxVec = npt.NDArray[npt.Shape['*'], npt.Complex]
StrVec = npt.NDArray[npt.Shape['*'], npt.String]
ObjVec = npt.NDArray[npt.Shape['*'], npt.Object]
Mat = npt.NDArray[npt.Shape['*, *'], npt.Double]
CxMat = npt.NDArray[npt.Shape['*, *'], npt.Complex]
IntMat = npt.NDArray[npt.Shape['*, *'], npt.Int]
StrMat = npt.NDArray[npt.Shape['*, *'], npt.String]
ObjMat = npt.NDArray[npt.Shape['*, *'], npt.Object]
CscMat = csc_matrix
CsrMat = csr_matrix


class BusMode(Enum):
    """
    Emumetarion of bus modes
    """
    PQ = 1
    PV = 2
    Slack = 3
    NONE = 4
    STO_DISPATCH = 5  # Storage dispatch, in practice it is the same as REF
    PVB = 6

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return BusMode[s]
        except KeyError:
            return s


class ExternalGridMode(Enum):
    """
    Modes of operation of external grids
    """
    PQ = "PQ"
    PV = "PV"
    VD = "VD"

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return ExternalGridMode[s]
        except KeyError:
            return s


class InvestmentEvaluationMethod(Enum):
    """
    Investment evaluation methods
    """
    Independent = "Independent"
    Hyperopt = "Hyperopt"
    MVRSM = "MVRSM"

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return InvestmentEvaluationMethod[s]
        except KeyError:
            return s


class BranchImpedanceMode(Enum):
    """
    Enumeration of branch impedance modes
    """
    Specified = 0
    Upper = 1
    Lower = 2

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return BranchImpedanceMode[s]
        except KeyError:
            return s


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
    AC_OPF = 'Nonlinear AC OPF'
    Simple_OPF = 'Simple dispatch'
    Proportional_OPF = 'Proportional OPF'
    NRI = 'Newton-Raphson in current'
    DYCORS_OPF = 'DYCORS OPF'
    GA_OPF = 'Genetic Algorithm OPF'
    NELDER_MEAD_OPF = 'Nelder Mead OPF'
    BFS = 'Backwards-Forward substitution'
    BFS_linear = 'Backwards-Forward substitution (linear)'
    Constant_Impedance_linear = 'Constant impedance linear'
    NoSolver = 'No Solver'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return SolverType[s]
        except KeyError:
            return s


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

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return TapsControlMode[s]
        except KeyError:
            return s


class SyncIssueType(Enum):
    """
    Sync issues enumeration
    """
    Added = 'Added'
    Deleted = 'Deleted'
    Conflict = 'Conflict'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return SyncIssueType[s]
        except KeyError:
            return s


class EngineType(Enum):
    """
    Available engines enumeration
    """
    GridCal = 'GridCal'
    Bentayga = 'Bentayga'
    NewtonPA = 'Newton Power Analytics'
    PGM = 'Power Grid Model'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return EngineType[s]
        except KeyError:
            return s


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

    def plot(self, plt, LINEWIDTH, ax=None):
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


class MIPSolvers(Enum):
    """
    MIP solvers enumeration
    """
    GLOP = "GLOP"
    CBC = 'CBC'
    HIGHS = 'HIGHS'
    SCIP = 'SCIP'
    CPLEX = 'CPLEX'
    GUROBI = 'GUROBI'
    XPRESS = 'XPRESS'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return MIPSolvers[s]
        except KeyError:
            return s


class TimeGrouping(Enum):
    """
    Time groupings enumeration
    """
    NoGrouping = 'No grouping'
    Monthly = 'Monthly'
    Weekly = 'Weekly'
    Daily = 'Daily'
    Hourly = 'Hourly'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return TimeGrouping[s]
        except KeyError:
            return s


class ZonalGrouping(Enum):
    """
    Zonal groupings enumeration
    """
    NoGrouping = 'No grouping'
    Area = 'Area'
    All = 'All (copper plate)'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return ZonalGrouping[s]
        except KeyError:
            return s


class ContingencyEngine(Enum):
    """
    Enumeratio of contingency calculation engines
    """
    PowerFlow = 'Power flow'
    HELM = 'HELM'
    PTDF = 'PTDF'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return ZonalGrouping[s]
        except KeyError:
            return s


def classify_by_hour(t: pd.DatetimeIndex) -> List[List[int]]:
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


def classify_by_day(t: pd.DatetimeIndex) -> list[list[Any]]:
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


def get_time_groups(t_array: pd.DatetimeIndex, grouping: TimeGrouping) -> List[int]:
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
    """
    Enumeration of logs severities
    """
    Error = 'Error'
    Warning = 'Warning'
    Information = 'Information'
    Divergence = 'Divergence'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return LogSeverity[s]
        except KeyError:
            return s


class LogEntry:
    """
    Logger entry
    """

    def __init__(self, msg="", severity: LogSeverity = LogSeverity.Information, device="", value="", expected_value=""):
        self.time = "{date:%H:%M:%S}".format(date=datetime.datetime.now())  # might use %Y/%m/%d %H:%M:%S
        self.msg = str(msg)
        self.severity = severity
        self.device = device
        self.value = value
        self.expected_value = str(expected_value)

    def to_list(self) -> List[Any]:
        """
        Get list representation of this entry
        :return:
        """
        return [self.time, self.severity.value, self.msg, self.device, self.value, self.expected_value]

    def __str__(self):
        return "{0} {1}: {2} {3} {4} {5}".format(self.time,
                                                 self.severity.value,
                                                 self.msg,
                                                 self.device,
                                                 self.value,
                                                 self.expected_value)


class Logger:
    """
    Logger class
    """

    def __init__(self):

        self.entries: List[LogEntry] = list()

        self.debug_entries: List[str] = list()

    def add_debug(self, *args):
        """
        Add debug entry
        :param args:
        :return:
        """
        self.debug_entries.append(" ".join([str(x) for x in args]))

    def append(self, txt: str):
        """
        simple text log
        :param txt: some message text
        """
        self.entries.append(LogEntry(txt))

    def has_logs(self):
        """
        Are there any logs?
        :return: True / False
        """
        return len(self.entries) > 0

    def add_info(self, msg: str, device="", value="", expected_value="", device_class='', comment='', device_property=''):
        """
        Add info entry
        :param msg:
        :param device:
        :param value:
        :param expected_value:
        :param device_class:
        :param comment:
        :return:
        """
        self.entries.append(LogEntry(msg, LogSeverity.Information, device, str(value), str(expected_value)))

    def add_warning(self, msg, device="", value="", expected_value="", device_class='', comment='', device_property=''):
        """
        Add warning entry
        :param msg:
        :param device:
        :param value:
        :param expected_value:
        :param device_class:
        :param comment:
        :return:
        """
        self.entries.append(LogEntry(msg, LogSeverity.Warning, device, str(value), str(expected_value)))

    def add_error(self, msg, device="", value="", expected_value="", device_class='', comment='', device_property=''):
        """
        Add error entry
        :param msg:
        :param device:
        :param value:
        :param expected_value:
        :param device_class:
        :param comment:
        :return:
        """
        self.entries.append(LogEntry(msg, LogSeverity.Error, device, str(value), str(expected_value)))

    def add_divergence(self, msg, device="", value=0, expected_value=0, tol=1e-6):
        """
        Add divergence entry
        :param msg:
        :param device:
        :param value:
        :param expected_value:
        :param tol:
        :return:
        """

        if abs(value - expected_value) > tol:
            self.entries.append(LogEntry(msg, LogSeverity.Divergence, device, str(value), str(expected_value)))

    def add(self, msg, severity: LogSeverity = LogSeverity.Error, device="", value="", expected_value=""):
        """
        Add general entry
        :param msg:
        :param severity:
        :param device:
        :param value:
        :param expected_value
        :return:
        """
        self.entries.append(LogEntry(msg, severity, device, str(value), str(expected_value)))

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
        """
        Save to CSV
        :param fname: file name
        """
        self.to_df().to_csv(fname)

    def to_xlsx(self, fname):
        """
        To Excel
        :param fname: file name
        """
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

    def size(self) -> int:
        """
        Number of logs
        :return: size
        """
        return len(self.entries)


class ConvergenceReport:
    """
    Convergence report
    """

    def __init__(self):
        self.methods_ = list()
        self.converged_ = list()
        self.error_ = list()
        self.elapsed_ = list()
        self.iterations_ = list()

    def add(self, method, converged, error, elapsed, iterations):
        """

        :param method:
        :param converged:
        :param error:
        :param elapsed:
        :param iterations:
        :return:
        """
        self.methods_.append(method)
        self.converged_.append(converged)
        self.error_.append(error)
        self.elapsed_.append(elapsed)
        self.iterations_.append(iterations)

    def converged(self):
        """

        :return:
        """
        if len(self.converged_) > 0:
            return self.converged_[-1]
        else:
            return False

    def error(self):
        """

        :return:
        """
        if len(self.error_) > 0:
            return self.error_[-1]
        else:
            return 0

    def elapsed(self):
        """

        :return:
        """
        if len(self.elapsed_) > 0:
            return self.elapsed_[-1]
        else:
            return 0

    def to_dataframe(self):
        """

        :return:
        """
        data = {'Method': self.methods_,
                'Converged?': self.converged_,
                'Error': self.error_,
                'Elapsed (s)': self.elapsed_,
                'Iterations': self.iterations_}

        df = pd.DataFrame(data)

        return df


def get_list_dim(a: List[Any]) -> int:
    """
    Get the dimensions of a List, this is for the case were a matrix is represented by lists of lists
    :param a: some List
    :return: Dimensions
    """
    if not type(a) == list:
        return 0
    else:
        if len(a) > 0:
            if type(a[0]) == list:
                return 2
            else:
                return 1
        else:
            return 1


class CompressedJsonStruct:
    """
    Compressed json block
    """

    def __init__(self, fields: List[str] = None, data: List[Any] = None):
        self.__fields: List[str] = list()
        self.__data: List[Any] = list() if data is None else data

        if fields is not None:
            self.__fields = fields

        if data is not None:
            self.set_data(data)

        self.__fields_pos_dict: Dict[str, int] = self.get_position_dict()

    def get_position_dict(self):
        """

        :return:
        """
        return {val: i for i, val in enumerate(self.__fields)}

    def set_fields(self, fields: List[str]):
        """
        Set the block fields and initialize the reverse index lookup
        :param fields: list of property names
        :return:
        """
        self.__fields = fields
        self.__fields_pos_dict = self.get_position_dict()

    def set_data(self, dta: List[Any]):
        """
        Set the data and check its consistency
        :param dta: list of lists
        :return: Nothing
        """
        if type(dta) == list:
            if len(dta) > 0:

                dim = get_list_dim(dta)

                if dim == 2:
                    self.__data = dta
                elif dim == 1:
                    self.__data = [dta]
                else:
                    raise Exception('The list has the wrong number of dimensions: ' + str(dim))

                if len(self.__data[0]) != len(self.__fields):
                    raise Exception("Data length does not match the fields length")

    def get_data(self):
        """

        :return:
        """
        return self.__data

    def get_row_number(self):
        """

        :return:
        """
        return len(self.__data)

    def get_col_index(self, prop):
        """

        :param prop:
        :return:
        """
        return self.__fields_pos_dict[prop]

    def get_final_dict(self):
        """

        :return:
        """
        return {'fields': self.__fields,
                'data': self.__data[0] if len(self.__data) == 1 else self.__data}

    def get_dict_at(self, i):
        """

        :param i:
        :return:
        """
        return {f: val for f, val in zip(self.__fields, self.__data[i])}

    def declare_n_entries(self, n):
        """
        Add n entries to the data
        :param n:
        :return:
        """
        nf = len(self.__fields)
        self.__data = [[None] * nf for i in range(n)]

    def set_at(self, i, col_name, val):
        """
        Set value at a position, counts that the data has been declared
        :param i: column index (object index)
        :param col_name: name of the property
        :param val: value to set
        """
        j = self.get_col_index(prop=col_name)
        self.__data[i][j] = val
