from matplotlib import pyplot as plt
from warnings import warn

from GridCal.grid.model.node_type import NodeType
from GridCal.grid.statistics.statistics import CDF


class Bus:

    def __init__(self, name="Bus", vnom=10, vmin=0.9, vmax=1.1, xpos=0, ypos=0, active=True):
        """
        Bus  constructor
        """

        self.name = name

        self.type_name = 'Bus'

        self.properties_with_profile = None

        # Nominal voltage (kV)
        self.Vnom = vnom

        self.Vmin = vmin

        self.Vmax = vmax

        self.Qmin_sum = 0

        self.Qmax_sum = 0

        self.Zf = 0

        self.active = active

        # List of load s attached to this bus
        self.loads = list()

        # List of Controlled generators attached to this bus
        self.controlled_generators = list()

        # List of shunt s attached to this bus
        self.shunts = list()

        # List of batteries attached to this bus
        self.batteries = list()

        # List of static generators attached tot this bus
        self.static_generators = list()

        # Bus type
        self.type = NodeType.NONE

        # Flag to determine if the bus is a slack bus or not
        self.is_slack = False

        # if true, the presence of storage devices turn the bus into a Reference bus in practice
        # So that P +jQ are computed
        self.dispatch_storage = False

        self.x = xpos

        self.y = ypos

        self.graphic_obj = None

        self.edit_headers = ['name', 'active', 'is_slack', 'Vnom', 'Vmin', 'Vmax', 'Zf', 'x', 'y']

        self.units = ['', '', '', 'kV', 'p.u.', 'p.u.', 'p.u.', '', '']

        self.edit_types = {'name': str,
                           'active': bool,
                           'is_slack': bool,
                           'Vnom': float,
                           'Vmin': float,
                           'Vmax': float,
                           'Zf': complex,
                           'x': float,
                           'y': float}

    def determine_bus_type(self):
        """
        Infer the bus type from the devices attached to it
        @return: Nothing
        """
        if len(self.controlled_generators) > 0:

            if self.is_slack:  # If contains generators and is marked as REF, then set it as REF
                self.type = NodeType.REF
            else:  # Otherwise set as PV
                self.type = NodeType.PV

        elif len(self.batteries) > 0:

            if self.dispatch_storage:
                # If there are storage devices and the dispatchable flag is on, set the bus as dispatchable
                self.type = NodeType.STO_DISPATCH
            else:
                # Otherwise a storage device shall be marked as a voltage controlld bus
                self.type = NodeType.PV
        else:
            if self.is_slack:  # If there is no device but still is marked as REF, then set as REF
                self.type = NodeType.REF
            else:
                # Nothing special; set it as PQ
                self.type = NodeType.PQ

    def get_YISV(self, index=None):
        """
        Compose the
            - Z: Impedance attached to the bus
            - I: Current attached to the bus
            - S: Power attached to the bus
            - V: Voltage of the bus
        All in complex values
        @return: Y, I, S, V, Yprof, Iprof, Sprof
        """
        Y = complex(0, 0)
        I = complex(0, 0)  # Positive Generates, negative consumes
        S = complex(0, 0)  # Positive Generates, negative consumes
        V = complex(1, 0)

        y_profile = None
        i_profile = None  # Positive Generates, negative consumes
        s_profile = None  # Positive Generates, negative consumes

        y_cdf = None
        i_cdf = None   # Positive Generates, negative consumes
        s_cdf = None   # Positive Generates, negative consumes

        self.Qmin_sum = 0
        self.Qmax_sum = 0

        is_v_controlled = False

        # Loads
        for elm in self.loads:

            if elm.active:

                if elm.Z != 0:
                    Y += 1 / elm.Z
                I -= elm.I  # Reverse sign convention in the load
                S -= elm.S  # Reverse sign convention in the load

                # Add the profiles
                elm_s_prof, elm_i_prof, elm_z_prof = elm.get_profiles(index)
                if elm_z_prof is not None:
                    if elm_z_prof.values.sum(axis=0) != complex(0):
                        if y_profile is None:
                            y_profile = 1 / elm_z_prof
                            y_cdf = CDF(y_profile)
                        else:
                            pr = 1 / elm_z_prof
                            y_profile = y_profile.add(pr, fill_value=0)
                            y_cdf = y_cdf + CDF(pr)

                if elm_i_prof is not None:
                    if elm_i_prof.values.sum(axis=0) != complex(0):
                        if i_profile is None:
                            i_profile = -elm_i_prof  # Reverse sign convention in the load
                            i_cdf = CDF(i_profile)
                        else:
                            pr = -elm_i_prof
                            i_profile = i_profile.add(pr, fill_value=0)  # Reverse sign convention in the load
                            i_cdf = i_cdf + CDF(pr)

                if elm_s_prof is not None:
                    if elm_s_prof.values.sum(axis=0) != complex(0):
                        if s_profile is None:
                            s_profile = -elm_s_prof  # Reverse sign convention in the load
                            s_cdf = CDF(s_profile)
                        else:
                            pr = -elm_s_prof
                            s_profile = s_profile.add(pr, fill_value=0)  # Reverse sign convention in the load
                            s_cdf = s_cdf + CDF(pr)
            else:
                warn(elm.name + ' is not active')

        # controlled gen and batteries
        for elm in self.controlled_generators + self.batteries:

            if elm.active:
                # Add the generator active power
                S = complex(S.real + elm.P, S.imag)

                self.Qmin_sum += elm.Qmin
                self.Qmax_sum += elm.Qmax

                # Voltage of the bus
                if not is_v_controlled:
                    V = complex(elm.Vset, 0)
                    is_v_controlled = True
                else:
                    if elm.Vset != V.real:
                        raise Exception("Different voltage controlled generators try to control " +
                                        "the same bus with different voltage set points")
                    else:
                        pass

                # add the power profile
                elm_p_prof, elm_vset_prof = elm.get_profiles(index)
                if elm_p_prof is not None:
                    if s_profile is None:
                        s_profile = elm_p_prof  # Reverse sign convention in the load
                        s_cdf = CDF(s_profile)
                    else:
                        s_profile = s_profile.add(elm_p_prof, fill_value=0)
                        s_cdf = s_cdf + CDF(elm_p_prof)
            else:
                warn(elm.name + ' is not active')

        # set maximum reactive power limits
        if self.Qmin_sum == 0:
            self.Qmin_sum = -999900
        if self.Qmax_sum == 0:
            self.Qmax_sum = 999900

        # Shunts
        for elm in self.shunts:
            if elm.active:
                Y += elm.Y
            else:
                warn(elm.name + ' is not active')

        # Static generators
        for elm in self.static_generators:

            if elm.active:
                S += elm.S

                if elm.Sprof is not None:
                    if s_profile is None:
                        s_profile = elm.Sprof  # Reverse sign convention in the load
                        s_cdf = CDF(s_profile)
                    else:
                        s_profile = s_profile.add(elm.Sprof, fill_value=0)
                        s_cdf = s_cdf + CDF(elm.Pprof)
            else:
                warn(elm.name + ' is not active')

        # Align profiles into a common column sum based on the time axis
        if s_profile is not None:
            s_profile = s_profile.sum(axis=1)

        if i_profile is not None:
            i_profile = i_profile.sum(axis=1)

        if y_profile is not None:
            y_profile = y_profile.sum(axis=1)

        return Y, I, S, V, y_profile, i_profile, s_profile, y_cdf, i_cdf, s_cdf

    def plot_profiles(self, ax=None):
        """

        @param time_idx: Master time profile: usually stored in the circuit
        @param ax: Figure axis, if not provided one will be created
        @return:
        """

        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)
            show_fig = True
        else:
            show_fig = False

        for elm in self.loads:
            ax.plot(elm.Sprof.index, elm.Sprof.values.real, label=elm.name)

        for elm in self.controlled_generators + self.batteries:
            ax.plot(elm.Pprof.index, elm.Pprof.values, label=elm.name)

        for elm in self.static_generators:
            ax.plot(elm.Sprof.index, elm.Sprof.values.real, label=elm.name)

        plt.legend()
        plt.title(self.name)
        plt.ylabel('MW')
        if show_fig:
            plt.show()

    def copy(self):
        """

        :return:
        """
        bus = Bus()
        bus.name = self.name

        # Nominal voltage (kV)
        bus.Vnom = self.Vnom

        bus.vmin = self.Vmin

        bus.Vmax = self.Vmax

        bus.Zf = self.Zf

        bus.Qmin_sum = self.Qmin_sum

        bus.Qmax_sum = self.Qmax_sum

        bus.active = self.active

        # List of load s attached to this bus
        for elm in self.loads:
            bus.loads.append(elm.copy())

        # List of Controlled generators attached to this bus
        for elm in self.controlled_generators:
            bus.controlled_generators.append(elm.copy())

        # List of shunt s attached to this bus
        for elm in self.shunts:
            bus.shunts.append(elm.copy())

        # List of batteries attached to this bus
        for elm in self.batteries:
            bus.batteries.append(elm.copy())

        # List of static generators attached tot this bus
        for g in self.static_generators:
            bus.static_generators.append(g.copy())

        # Bus type
        bus.type = self.type

        # Flag to determine if the bus is a slack bus or not
        bus.is_slack = self.is_slack

        # if true, the presence of storage devices turn the bus into a Reference bus in practice
        # So that P +jQ are computed
        bus.dispatch_storage = self.dispatch_storage

        bus.x = self.x

        bus.y = self.y

        # self.graphic_obj = None

        return bus

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        self.retrieve_graphic_position()
        return [self.name, self.active, self.is_slack, self.Vnom, self.Vmin, self.Vmax, self.Zf, self.x, self.y]

    def set_state(self, t):
        """
        Set the profiles state of the objects in this bus to the value given in the profiles at the index t
        :param t: index of the profile
        :return:
        """
        for elm in self.loads:
            elm.S = elm.Sprof.values[t, 0]
            elm.I = elm.Iprof.values[t, 0]
            elm.Z = elm.Zprof.values[t, 0]

        for elm in self.static_generators:
            elm.S = elm.Sprof.values[t, 0]

        for elm in self.batteries:
            elm.P = elm.Pprof.values[t, 0]
            elm.Vset = elm.Vsetprof.values[t, 0]

        for elm in self.controlled_generators:
            elm.P = elm.Pprof.values[t, 0]
            elm.Vset = elm.Vsetprof.values[t, 0]

        for elm in self.shunts:
            elm.Y = elm.Yprof.values[t, 0]

    def retrieve_graphic_position(self):
        """
        Get the position set by the graphic object
        :return:
        """
        if self.graphic_obj is not None:
            self.x = self.graphic_obj.pos().x()
            self.y = self.graphic_obj.pos().y()
