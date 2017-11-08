from PyQt5.QtCore import QRunnable
from PyQt5.QtCore import QRunnable
from numpy.core.umath import conj, maximum
from numpy.linalg import inv
from numpy.ma import zeros

from GridCal.grid.calculate.short_circuit.options import ShortCircuitOptions
from GridCal.grid.calculate.short_circuit.results import ShortCircuitResults
from GridCal.grid.calculate.short_circuit.sc3p import short_circuit_3p
from GridCal.grid.model.circuit import MultiCircuit
from GridCal.grid.model.circuit.circuit import Circuit


class ShortCircuitRunnable(QRunnable):
    # progress_signal = pyqtSignal(float)
    # progress_text = pyqtSignal(str)
    # done_signal = pyqtSignal()

    def __init__(self, grid: MultiCircuit, options: ShortCircuitOptions):
        """
        PowerFlow class constructor
        @param grid: MultiCircuit Object
        """
        QRunnable.__init__(self)

        # Grid to run a power flow in
        self.grid = grid

        # Options to use
        self.options = options

        # compile the buses short circuit impedance array
        n = len(self.grid.buses)
        self.Zf = zeros(n, dtype=complex)
        for i in range(n):
            self.Zf[i] = self.grid.buses[i].Zf

        self.results = None

        self.__cancel__ = False

    def single_short_circuit(self, circuit: Circuit):
        """
        Run a power flow simulation for a single circuit
        @param circuit:
        @return:
        """

        assert(circuit.power_flow_results is not None)

        # compute Zbus if needed
        if circuit.power_flow_input.Zbus is None:
            circuit.power_flow_input.Zbus = inv(circuit.power_flow_input.Ybus).toarray()  # is dense, so no need to store it as sparse

        # Compute the short circuit
        V, SCpower = short_circuit_3p(bus_idx=self.options.bus_index,
                                      Zbus=circuit.power_flow_input.Zbus,
                                      Vbus=circuit.power_flow_results.voltage,
                                      Zf=self.Zf, baseMVA=circuit.Sbase)

        # Compute the branches power
        Sbranch, Ibranch, loading, losses = self.compute_branch_results(circuit=circuit, V=V)

        # voltage, Sbranch, loading, losses, error, converged, Qpv
        results = ShortCircuitResults(Sbus=circuit.power_flow_input.Sbus,
                                      voltage=V,
                                      Sbranch=Sbranch,
                                      Ibranch=Ibranch,
                                      loading=loading,
                                      losses=losses,
                                      SCpower=SCpower,
                                      error=0,
                                      converged=True,
                                      Qpv=None)

        # # check the limits
        # sum_dev = results.check_limits(circuit.power_flow_input)
        # print('dev sum: ', sum_dev)

        return results

    @staticmethod
    def compute_branch_results(circuit: Circuit, V):
        """
        Compute the power flows trough the branches
        @param circuit: instance of Circuit
        @param V: Voltage solution array for the circuit buses
        @return: Sbranch, Ibranch, loading, losses
        """
        If = circuit.power_flow_input.Yf * V
        It = circuit.power_flow_input.Yt * V
        Sf = V[circuit.power_flow_input.F] * conj(If)
        St = V[circuit.power_flow_input.T] * conj(It)
        losses = Sf - St
        Ibranch = maximum(If, It)
        Sbranch = maximum(Sf, St)
        loading = Sbranch * circuit.Sbase / circuit.power_flow_input.branch_rates

        # idx = where(abs(loading) == inf)[0]
        # loading[idx] = 9999

        return Sbranch, Ibranch, loading, losses

    def run(self):
        """
        Run a power flow for every circuit
        @return:
        """
        print('Short circuit at ', self.grid.name)
        # self.progress_signal.emit(0.0)

        n = len(self.grid.buses)
        m = len(self.grid.branches)
        results = ShortCircuitResults()  # yes, reuse this class
        results.initialize(n, m)
        k = 0
        for circuit in self.grid.circuits:
            if self.options.verbose:
                print('Solving ' + circuit.name)

            circuit.short_circuit_results = self.single_short_circuit(circuit)
            results.apply_from_island(circuit.short_circuit_results, circuit.bus_original_idx, circuit.branch_original_idx)

            # self.progress_signal.emit((k+1) / len(self.grid.circuits))
            k += 1

        self.results = results
        self.grid.short_circuit_results = results

        # self.progress_signal.emit(0.0)
        # self.done_signal.emit()

    def cancel(self):
        self.__cancel__ = True


