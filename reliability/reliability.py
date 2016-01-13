from numpy.random import exponential, normal
from enum import Enum
from matplotlib import pyplot as plt


class States(int):
    Failed = 0
    Working = 1
    Maintenance = 2


class ElementTypes(Enum):
    Generic = 100
    Bus = 0
    Gen = 1
    Branch = 2
    Switch = 3
    Load = 4
    Grid = 5
    SlackGen = 6


class EventList(list):

    def __init__(self, value = []): # Constructor
        list.__init__([]) # Customizes list
        self.concat(value) # Copies mutable defaults

    def __getitem__(self, index):
        return super(EventList, self).__getitem__(index)

    def __setitem__(self, key, value):
        super(EventList, self).__setitem__(key, value)

    def concat(self, value): # value: list, Set...
        for x in value: # Removes duplicates
            if not x in self:
                self.append(x)

    def add(self, event):
        self.append(event)

    def size(self):
        return len(self)

    def remove_redundant(self):
        # Remove the redundant events
        n = self.size()
        i = n-2
        while i > 0:
            if self[i][1] == self[i-1][1]:
                del self[i]
            i -= 1

    def merge_events(self, event_list, remove_redundant=True):
        """
        Add another list of events to this list.
        It can also remove the redundant events
        """
        self += event_list
        # print(self)
        self.sort()
        # print(self)
        # set the final event state as the previous event state
        n = self.size()
        self[n-1] = (self[n-1][0], self[n-2][1])
        # print(self)
        # remove redundant events
        if remove_redundant:
            self.remove_redundant()

    def merge_series_component_events(self, events_list):
        """
        Composes the series events list of a number of components

        Args:
            events_list: list of EventList objects corresponding to a number of components in series
        """
        c_num = len(events_list)  # number of components

        for k in range(c_num):
            for evt in events_list[k]:
                if evt[1] == States.Failed:
                    self.add(evt)  # a down-event is always added
                else:
                    all_working = True
                    i = 0
                    while i < c_num and all_working:
                        t = evt[0]
                        if not events_list[i].state_at(t + 1e-6):
                            all_working = False
                        i += 1

                    # up-events are added only if all the components are up for the examined up-event time
                    if all_working:
                        self.add(evt)

        self.sort()
        self.remove_redundant()

    def merge_parallel_component_events(self, events_list):
        """
        Composes the series events list of a number of components

        Args:
            events_list: list of EventList objects corresponding to a number of components in series
        """
        c_num = len(events_list)  # number of components

        for k in range(c_num):
            for evt in events_list[k]:
                if evt[1] == States.Working:
                    self.add(evt)  # a down-event is always added
                else:
                    all_failed = True
                    i = 0
                    while i < c_num and all_failed:
                        t = evt[0]
                        if events_list[i].state_at(t + 1e-6):
                            all_failed = False
                        i += 1

                    # up-events are added only if all the components are up for the examined up-event time
                    if all_failed:
                        self.add(evt)

        self.sort()
        self.remove_redundant()

    def state_at(self, t):
        """
        Returns the state at any given time
        """
        n = self.size()
        s0 = self[0]
        sn = self[n-1]

        if t <= s0[0]:
            return s0[1]

        elif t >= sn[0]:
            return sn[1]

        else:  # look for it
            for i in range(1, n):
                if t >= self[i-1][0] and t <= self[i][0]:
                    # t is found
                    return self[i-1][1]

    def get_up_and_down_time(self):
        """
        Computes the up and down time of the stored events list
        """
        n = self.size()
        upt = 0.0
        dwt = 0.0
        for i in range(1, n):
            if self[i-1][1] == States.Working:
                upt += self[i][0] - self[i-1][0]  # increase the up-time
            else:
                dwt += self[i][0] - self[i-1][0]  # increase the down-time
        return upt, dwt

    def plot(self, ylab=''):
        n = len(self)
        for i in range(n-1):
            #print(str(self[i][0]) + ", " + str(self[i+1][0]) + '->' + str(str(self[i][1])))
            plt.plot((self[i][0], self[i+1][0]), (self[i][1], self[i][1]), 'k-')
            plt.plot((self[i][0], self[i][0]), (0, 1), 'k-')
            plt.plot((self[i+1][0], self[i+1][0]), (0, 1), 'k-')
            if self[i][1] == States.Failed:
                color = 'r'
            else:
                color = 'g'
            plt.axvspan(ymin=0, ymax=1, xmin=self[i][0], xmax=self[i+1][0], facecolor=color, alpha=0.5)
        plt.ylabel(ylab)
        plt.xlim((0, self[n-1][0]+10))


class Element(object):
    """
    This class represents the system element.
    In a graph it is given by a node element, regardless of the element's nature
    """

    def __init__(self, name, element_type, MTTF, MTTR, DEVTR=None, state=States.Working, weight=0, online=True):
        """
        Class constructor

        Args:
            name = name of the element

            element_type = type of element given by the class ElementTypes

            MTTF = mean time to failure

            MTTR = mean time to repair

            DEVTR = deviation from time to repair

            state = initial state of the element, given by the possible states enumerated by the class States

            weight = possible weight of the element

            online = flag denoting if the element is active or not.
        """

        self.name = name
        self.type = element_type
        self.MTTF = MTTF
        self.MTTR = MTTR
        self.DEVTR = DEVTR
        self.current_state = state
        self.weight = weight
        self.is_on_line = online

        self.events = EventList([])

        self.time_based_maintenance_events = EventList([])

        self.use_normal_recovery_law = False
        if DEVTR is not None:
            self.use_normal_recovery_law = True

    def generate_states(self, simulation_time):
        """
        Generate the system events randomly.

        Once failed, a component is accounted to be replaced (as good as new)

        Args:

            simulation_time: simulation time limit (typically the expected life of the system)
        """
        events = EventList()

        self.events.clear()
        # append the initial state event
        self.events.append((0, self.current_state * self.is_on_line))
        # append the last state event
        self.events.append((simulation_time, -1 * self.is_on_line))

        mttf = self.MTTF
        mttr = self.MTTR

        # generate failure-repair events
        t = 0
        last_state = self.current_state
        while t < simulation_time:  # simulate failures and recoveries until the time is reached
            if (not last_state) == States.Failed:  # if the state to set is failed, get the time of the failure
                t_evt = t + exponential(mttf)
                last_state = States.Failed
            else:  # the element is failed, calculate its recovery time
                if self.use_normal_recovery_law:
                    t_evt = t + normal(mttr, self.DEVTR)
                else:
                    t_evt = t + exponential(mttr)
                last_state = States.Working

            if t_evt <= simulation_time:
                events.append((t_evt, last_state * self.is_on_line))
            t = t_evt

        self.events.merge_events(events + self.time_based_maintenance_events)

if __name__ == '__main__':
    simulation_time = 172000
    name = 'element'
    type = ElementTypes.Generic
    MTTF = 36402.64
    MTTR = 6500.30

    plt.subplot(5, 1, 1)
    elm1 = Element(name, type, MTTF, MTTR)
    elm1.generate_states(simulation_time)
    print(elm1.events)
    elm1.events.plot('system 1')

    plt.subplot(5, 1, 2)
    elm2 = Element(name, type, MTTF, MTTR)
    elm2.generate_states(simulation_time)
    print(elm2.events)
    elm2.events.plot('system 2')

    plt.subplot(5, 1, 3)
    elm3 = Element(name, type, MTTF, MTTR)
    elm3.generate_states(simulation_time)
    print(elm3.events)
    elm3.events.plot('system 3')

    # series aggregation
    plt.subplot(5, 1, 4)
    system_events = EventList()
    system_events.merge_series_component_events([elm1.events, elm2.events, elm3.events])
    upt, dwt = system_events.get_up_and_down_time()
    print('up-time:' + str(upt) + ', down-time:' + str(dwt))
    system_events.plot('series')
    print(system_events)

    # parallel aggregation
    plt.subplot(5, 1, 5)
    system_events = EventList()
    system_events.merge_parallel_component_events([elm1.events, elm2.events, elm3.events])
    upt, dwt = system_events.get_up_and_down_time()
    print('up-time:' + str(upt) + ', down-time:' + str(dwt))
    system_events.plot('parallel')
    print(system_events)


    plt._show()
    #input()