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
import numpy as np
import pandas as pd
from warnings import warn
from enum import Enum


class TimeFrame(Enum):
    Continuous = 'Continuous'


class DeviceType(Enum):
    BusDevice = 'Bus'
    BranchDevice = 'Branch'
    BatteryDevice = 'Battery'
    LoadDevice = 'Load'
    GeneratorDevice = 'Generator'
    StaticGeneratorDevice = 'Static Generator'
    ShuntDevice = 'Shunt'
    WireDevice = 'Wire'
    SequenceLineDevice = 'Sequence line'
    UnderGroundLineDevice = 'Underground line'
    TowerDevice = 'Tower'
    TransformerTypeDevice = 'Transformer type'


class GCProp:

    def __init__(self, units, tpe, definition, profile_name=''):

        self.units = units

        self.tpe = tpe

        self.definition = definition

        self.profile_name = profile_name


class EditableDevice:

    def __init__(self, name, active, device_type: DeviceType,
                 editable_headers,
                 non_editable_attributes=list(),
                 properties_with_profile=dict()):
        """
        Class to generalize any editable device
        :param name: Asset's name
        :param active: is active
        :param editable_headers: dictionary of header properties {'magnitude': (unit, type)}
        :param device_type: DeviceType instance
        :param non_editable_attributes: list of non editable magnitudes
        :param properties_with_profile: dictionary of profile properties {'magnitude': profile_magnitude}
        """

        self.name = name

        self.active = active

        self.active_prof = None

        self.type_name = device_type.value

        self.device_type = device_type

        # associated graphic object
        self.graphic_obj = None

        self.editable_headers = editable_headers

        self.non_editable_attributes = non_editable_attributes

        self.properties_with_profile = properties_with_profile

        self.properties_with_profile['active'] = 'active_prof'

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """

        data = list()
        for name, properties in self.editable_headers.items():
            obj = getattr(self, name)
            if properties.tpe not in [str, float, int, bool]:
                obj = str(obj)
            data.append(obj)
        return data

    def get_headers(self):
        """
        Return a list of headers
        """
        return list(self.editable_headers.keys())

    def __str__(self):
        return self.name

    def create_profiles(self, index):
        """
        Create the load object default profiles
        Args:
        :param index: pandas time index
        """
        for magnitude, values in self.properties_with_profile.items():
            self.create_profile(magnitude=magnitude, index=index)

    def resize_profiles(self, index, time_frame: TimeFrame):
        """
        Resize the profiles in this object
        :param index: pandas time index
        :param time_frame: Time frame to use (Short term, Long term)
        """
        n1 = index.shape[0]
        for magnitude, values in self.properties_with_profile.items():
            if values[1] == time_frame:
                # get the current profile
                val = getattr(self, self.properties_with_profile[magnitude]).values[:, 0]
                n2 = val.shape[0]

                if n1 > n2:
                    # extend the values
                    extension = np.ones(n1 - n2, dtype=val.dtype) * getattr(self, magnitude)  # copy the current value
                    val2 = np.r_[val, extension]
                else:
                    # curtail the values
                    val2 = val[:n1]

                df = pd.DataFrame(data=val2, index=index, columns=[self.name])
                setattr(self, self.properties_with_profile[magnitude], df)

    def create_profile(self, magnitude, index, arr=None, arr_in_pu=False):
        """
        Create power profile based on index
        :param magnitude: name of the property
        :param index: pandas time index
        :param arr: array of values to set
        :param arr_in_pu: is the array in per-unit?
        """
        # get the value of the magnitude
        x = getattr(self, magnitude)
        tpe = self.editable_headers[magnitude].tpe
        if arr_in_pu:
            val = arr * x
        else:
            val = np.ones(len(index), dtype=tpe) * x if arr is None else arr

        # set the profile variable associated with the magnitude
        df = pd.DataFrame(data=val, index=index, columns=[self.name])
        setattr(self, self.properties_with_profile[magnitude], df)

    def ensure_profiles_exist(self, index):
        """
        It might be that when loading the GridCal Model has properties that the file has not.
        Those properties must be initialized as well
        :param index: Time series index (timestamps)
        """
        for magnitude in self.properties_with_profile.keys():

            if index is not None:
                prof_attr = self.properties_with_profile[magnitude]

                df = getattr(self, prof_attr)

                if df is None:
                    # there is no profile, create a new one with the default values
                    print(self.name, ': created profile for ' + prof_attr)
                    self.create_profile(magnitude=magnitude, index=index)
                else:
                    if df.shape[0] != len(index):
                        # the length of the profile is different from the length of the master profile
                        print(self.name, ': created profile for ' + prof_attr)
                        self.create_profile(magnitude=magnitude, index=index)
                    else:
                        # all ok
                        pass

            else:
                warn('The time index is None')

    def delete_profiles(self):
        """
        Delete the object profiles (set all to None)
        """
        for magnitude in self.properties_with_profile.keys():
            setattr(self, self.properties_with_profile[magnitude], None)

    def set_profile_values(self, t):
        """
        Set the profile values at t
        :param t: time index (integer)
        """
        for magnitude in self.properties_with_profile.keys():
            df = getattr(self, self.properties_with_profile[magnitude])
            setattr(self, magnitude, df.values[t])


# class ReliabilityDevice(EditableDevice):
#
#     def __init__(self, name, active, type_name, editable_headers, mttf, mttr):
#         """
#         Class to provide reliability derived functionality
#         :param editable_headers: dictionary of header properties {'magnitude': (unit, type)}
#         :param mttf: Mean Time To Failure (h)
#         :param mttr: Mean Time To Repair (h)
#         """
#
#         # name, active, type_name, editable_headers, device_type, non_editable_attributes, properties_with_profile
#         EditableDevice.__init__(self, name=name, active=active, type_name=type_name, editable_headers=editable_headers)
#
#         self.mttf = mttf
#
#         self.mttr = mttr
#
#     def get_failure_time(self, n_samples):
#         """
#         Get an array of possible failure times
#         :param n_samples: number of samples to draw
#         :return: Array of times in hours
#         """
#         return -1.0 * self.mttf * np.log(np.random.rand(n_samples))
#
#     def get_repair_time(self, n_samples):
#         """
#         Get an array of possible repair times
#         :param n_samples: number of samples to draw
#         :return: Array of times in hours
#         """
#         return -1.0 * self.mttr * np.log(np.random.rand(n_samples))
#
#     def get_reliability_events(self, horizon, n_samples):
#         """
#         Get random fail-repair events until a given time horizon in hours
#         :param horizon: maximum horizon in hours
#         :return: list of events
#         """
#         t = np.zeros(n_samples)
#         events = list()
#         while t.any() < horizon:  # if all event get to the horizon, finnish the sampling
#
#             # simulate failure
#             te = self.get_failure_time(n_samples)
#             if (t + te).any() <= horizon:
#                 t += te
#                 events.append(t)
#
#             # simulate repair
#             te = self.get_repair_time(n_samples)
#             if (t + te).any() <= horizon:
#                 t += te
#                 events.append(t)
#
#         return events

#
# class InjectionDevice(ReliabilityDevice):
#
#     def __init__(self, name, bus, active, type_name, editable_headers, mttf, mttr, properties_with_profile):
#         """
#         InjectionDevice constructor
#         :param editable_headers: dictionary of header properties {'magnitude': (unit, type)}
#         :param mttf: Mean Time To Failure (h)
#         :param mttr: Mean Time To Repair (h)
#         :param properties_with_profile: dictionary with the properties with profiles {'magnitude': ('profile magnitude')}
#         """
#         ReliabilityDevice.__init__(self, name, active=active, type_name=type_name,
#                                    editable_headers=editable_headers, mttf=mttf, mttr=mttr)
#         # connection bus
#         self.bus = bus
#
#         # dictionary relating the property with the associated profile property
#         self.properties_with_profile = properties_with_profile
#
#     def create_profiles(self, index):
#         """
#         Create the load object default profiles
#         Args:
#             index: dataFrame index
#         """
#         for magnitude in self.properties_with_profile.keys():
#             self.create_profile(magnitude=magnitude, index=index)
#
#     def create_profile(self, magnitude, index, arr=None, arr_in_pu=False):
#         """
#         Create power profile based on index
#         :param magnitude: name of the property
#         :param index: pandas index
#         :param arr: array of values to set
#         :param arr_in_pu: is the array in per-unit?
#         """
#         # get the value of the magnitude
#         x = getattr(self, magnitude)
#
#         if arr_in_pu:
#             val = arr * x
#         else:
#             val = np.ones(len(index)) * x if arr is None else arr
#
#         # set the profile variable associated with the magnitude
#         df = pd.DataFrame(data=val, index=index, columns=[self.name])
#         setattr(self, self.properties_with_profile[magnitude], df)
#
#     def delete_profiles(self):
#         """
#         Delete the object profiles (set all to None)
#         """
#         for magnitude in self.properties_with_profile.keys():
#             setattr(self, self.properties_with_profile[magnitude], None)
#
#     def set_profile_values(self, t):
#         """
#         Set the profile values at t
#         :param t: time index (integer)
#         """
#         for magnitude in self.properties_with_profile.keys():
#             df = getattr(self, self.properties_with_profile[magnitude])
#             setattr(self, magnitude, df.values[t])
#
#     def ensure_profiles_exist(self, index):
#         """
#         It might be that when loading the Ordena Model has properties that the file has not.
#         Those properties must be initialized as well
#         :param index: dataFrame index
#         """
#         if index is not None:
#             for magnitude in self.properties_with_profile.keys():
#                 prof_attr = self.properties_with_profile[magnitude]
#                 df = getattr(self, prof_attr)
#                 if df is None:
#                     print(self.name, ': created profile for ' + prof_attr)
#                     self.create_profile(magnitude=magnitude, index=index)
#                 elif df.shape[0] != len(index):
#                     print(self.name, ': created profile for ' + prof_attr)
#                     self.create_profile(magnitude=magnitude, index=index)
#                 else:
#                     pass
#         else:
#             warn('the time idex is None')
