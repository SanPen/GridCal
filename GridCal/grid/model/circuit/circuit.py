import networkx as nx
import pandas as pd
from numpy import nan, ones, r_, sqrt, where, array
from warnings import warn

from GridCal.grid.calculate.power_flow.input import PowerFlowInput
from GridCal.grid.calculate.time_series.input import TimeSeriesInput
from GridCal.grid.sample.monte_carlo.input import MonteCarloInput
from GridCal.grid.statistics.statistics import CDF
from scripts.research.levmar_pf import Jacobian


class Circuit:

    def __init__(self, name='Circuit'):
        """
        Circuit constructor
        @param name: Name of the circuit
        """

        self.name = name

        # Base power (MVA)
        self.Sbase = 100

        # Should be able to accept Branches, Lines and Transformers alike
        self.branches = list()

        # array of branch indices in the master circuit
        self.branch_original_idx = list()

        # Should accept buses
        self.buses = list()

        # array of bus indices in the master circuit
        self.bus_original_idx = list()

        # Object with the necessary inputs for a power flow study
        self.power_flow_input = None

        #  containing the power flow results
        self.power_flow_results = None

        # containing the short circuit results
        self.short_circuit_results = None

        # Object with the necessary inputs for th time series simulation
        self.time_series_input = None

        # Object with the time series simulation results
        self.time_series_results = None

        # Monte Carlo input object
        self.monte_carlo_input = None

        # Monte Carlo time series batch
        self.mc_time_series = None

        # Bus-Branch graph
        self.graph = None

    def clear(self):
        """
        Delete the Circuit content
        @return:
        """
        self.Sbase = 100
        self.branches = list()
        self.branch_original_idx = list()
        self.buses = list()
        self.bus_original_idx = list()

    def compile(self):
        """
        Compile the circuit into all the needed arrays:
            - Ybus matrix
            - Sbus vector
            - Vbus vector
            - etc...
        """
        n = len(self.buses)
        m = len(self.branches)

        self.graph = nx.Graph()

        # declare power flow results
        power_flow_input = PowerFlowInput(n, m)

        # time series inputs
        Sprofile = pd.DataFrame()
        Iprofile = pd.DataFrame()
        Yprofile = pd.DataFrame()
        Scdf_ = [None] * n
        Icdf_ = [None] * n
        Ycdf_ = [None] * n
        time_series_input = None
        monte_carlo_input = None

        are_cdfs = False

        # Dictionary that helps referencing the nodes
        buses_dict = dict()

        # declare the square root of 3 to do it only once
        sqrt3 = sqrt(3.0)

        # Compile the buses
        for i in range(n):

            # Add buses dictionary entry
            buses_dict[self.buses[i]] = i

            # set the name
            power_flow_input.bus_names[i] = self.buses[i].name

            # assign the nominal voltage value
            power_flow_input.Vnom[i] = self.buses[i].Vnom

            # Determine the bus type
            self.buses[i].determine_bus_type()

            # compute the bus magnitudes
            Y, I, S, V, Yprof, Iprof, Sprof, Ycdf, Icdf, Scdf = self.buses[i].get_YISV()
            power_flow_input.Vbus[i] = V  # set the bus voltages
            power_flow_input.Sbus[i] += S  # set the bus power
            power_flow_input.Ibus[i] += I  # set the bus currents

            power_flow_input.Ybus[i, i] += Y  # set the bus shunt impedance in per unit
            power_flow_input.Yshunt[i] += Y  # copy the shunt impedance

            power_flow_input.types[i] = self.buses[i].type.value[0]  # set type

            power_flow_input.Vmin[i] = self.buses[i].Vmin
            power_flow_input.Vmax[i] = self.buses[i].Vmax
            power_flow_input.Qmin[i] = self.buses[i].Qmin_sum
            power_flow_input.Qmax[i] = self.buses[i].Qmax_sum

            # compute the time series arrays  ##############################################

            # merge the individual profiles. The profiles are Pandas DataFrames
            # ttt, nnn = Sprof.shape
            if Sprof is not None:
                k = where(Sprof.values == nan)
                Sprofile = pd.concat([Sprofile, Sprof], axis=1)
            else:
                nn = len(Sprofile)
                Sprofile['Sprof@Bus' + str(i)] = pd.Series(ones(nn) * S, index=Sprofile.index)  # append column of zeros

            if Iprof is not None:
                Iprofile = pd.concat([Iprofile, Iprof], axis=1)
            else:
                Iprofile['Iprof@Bus' + str(i)] = pd.Series(ones(len(Iprofile)) * I, index=Iprofile.index)

            if Yprof is not None:
                Yprofile = pd.concat([Yprofile, Yprof], axis=1)
            else:
                Yprofile['Iprof@Bus' + str(i)] = pd.Series(ones(len(Yprofile)) * Y, index=Yprofile.index)

            # Store the CDF's form Monte Carlo ##############################################

            if Scdf is None and S != complex(0, 0):
                Scdf = CDF(array([S]))

            if Icdf is None and I != complex(0, 0):
                Icdf = CDF(array([I]))

            if Ycdf is None and Y != complex(0, 0):
                Ycdf = CDF(array([Y]))

            if Scdf is not None or Icdf is not None or Ycdf is not None:
                are_cdfs = True

            Scdf_[i] = Scdf
            Icdf_[i] = Icdf
            Ycdf_[i] = Ycdf

        # normalize the power array
        power_flow_input.Sbus /= self.Sbase

        # normalize the currents array (I was given in MVA at v=1 p.u.)
        power_flow_input.Ibus /= self.Sbase

        # normalize the admittances array (Y was given in MVA at v=1 p.u.)
        power_flow_input.Ybus /= self.Sbase
        power_flow_input.Yshunt /= self.Sbase

        # normalize the reactive power limits array (Q was given in MVAr)
        power_flow_input.Qmax /= self.Sbase
        power_flow_input.Qmin /= self.Sbase

        if Sprofile is not None:
            Sprofile /= self.Sbase
            Sprofile.columns = ['Sprof@Bus' + str(i) for i in range(Sprofile.shape[1])]

        if Iprofile is not None:
            Iprofile /= self.Sbase
            Iprofile.columns = ['Iprof@Bus' + str(i) for i in range(Iprofile.shape[1])]

        if Yprofile is not None:
            Yprofile /= self.Sbase
            Yprofile.columns = ['Yprof@Bus' + str(i) for i in range(Yprofile.shape[1])]

        time_series_input = TimeSeriesInput(Sprofile, Iprofile, Yprofile)
        time_series_input.compile()

        if are_cdfs:
            monte_carlo_input = MonteCarloInput(n, Scdf_, Icdf_, Ycdf_)

        # Compile the branches
        for i in range(m):

            if self.branches[i].active:
                # Set the branch impedance

                f = buses_dict[self.branches[i].bus_from]
                t = buses_dict[self.branches[i].bus_to]

                f, t = self.branches[i].apply_to(Ybus=power_flow_input.Ybus,
                                                 Yseries=power_flow_input.Yseries,
                                                 Yshunt=power_flow_input.Yshunt,
                                                 Yf=power_flow_input.Yf,
                                                 Yt=power_flow_input.Yt,
                                                 B1=power_flow_input.B1,
                                                 B2=power_flow_input.B2,
                                                 i=i, f=f, t=t)
                # add the bus shunts
                # power_flow_input.Yf[i, f] += power_flow_input.Yshunt[f, f]
                # power_flow_input.Yt[i, t] += power_flow_input.Yshunt[t, t]

                # Add graph edge (automatically adds the vertices)
                self.graph.add_edge(f, t)

                # Set the active flag in the active branches array
                power_flow_input.active_branches[i] = 1

                # Arrays with the from and to indices per bus
                power_flow_input.F[i] = f
                power_flow_input.T[i] = t

            # fill rate
            if self.branches[i].rate > 0:
                power_flow_input.branch_rates[i] = self.branches[i].rate
            else:
                power_flow_input.branch_rates[i] = 1e-6
                warn('The branch ' + str(i) + ' has no rate. Setting 1e-6 to avoid zero division.')

        # Assign the power flow inputs  button
        power_flow_input.compile()
        self.power_flow_input = power_flow_input
        self.time_series_input = time_series_input
        self.monte_carlo_input = monte_carlo_input

    def set_at(self, t, mc=False):
        """
        Set the current values given by the profile step of index t
        @param t: index of the profiles
        @param mc: Is this being run from MonteCarlo?
        @return: Nothing
        """
        if self.time_series_input is not None:
            if mc:

                if self.mc_time_series is None:
                    warn('No monte carlo inputs in island!!!')
                else:
                    self.power_flow_input.Sbus = self.mc_time_series.S[t, :] / self.Sbase
            else:
                self.power_flow_input.Sbus = self.time_series_input.S[t, :] / self.Sbase
        else:
            warn('No time series values')

    def sample_monte_carlo_batch(self, batch_size, use_latin_hypercube=False):
        """
        Samples a monte carlo batch as a time series object
        @param batch_size: size of the batch (integer)
        @return:
        """
        self.mc_time_series = self.monte_carlo_input(batch_size, use_latin_hypercube)

    def sample_at(self, x):
        """
        Get samples at x
        Args:
            x: values in [0, 1+ to sample the CDF

        Returns:

        """
        self.mc_time_series = self.monte_carlo_input.get_at(x)

    def get_loads(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.loads:
                elm.bus = bus
            lst = lst + bus.loads
        return lst

    def get_static_generators(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.static_generators:
                elm.bus = bus
            lst = lst + bus.static_generators
        return lst

    def get_shunts(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.shunts:
                elm.bus = bus
            lst = lst + bus.shunts
        return lst

    def get_controlled_generators(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.controlled_generators:
                elm.bus = bus
            lst = lst + bus.controlled_generators
        return lst

    def get_batteries(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.batteries:
                elm.bus = bus
            lst = lst + bus.batteries
        return lst

    def get_Jacobian(self, sparse=False):
        """
        Returns the Grid Jacobian matrix
        Returns:
            Grid Jacobian Matrix in CSR sparse format or as full matrix
        """

        # Initial magnitudes
        pvpq = r_[self.power_flow_input.pv, self.power_flow_input.pq]

        J = Jacobian(Ybus=self.power_flow_input.Ybus,
                     V=self.power_flow_input.Vbus,
                     Ibus=self.power_flow_input.Ibus,
                     pq=self.power_flow_input.pq,
                     pvpq=pvpq)

        if sparse:
            return J
        else:
            return J.todense()
