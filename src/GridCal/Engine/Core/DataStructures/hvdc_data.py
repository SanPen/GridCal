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
import scipy.sparse as sp
import GridCal.Engine.Core.topology as tp


class HvdcData:

    def __init__(self, nhvdc, nbus, ntime=1):
        """

        :param nhvdc:
        :param nbus:
        """
        self.nhvdc = nhvdc
        self.ntime = ntime

        self.names = np.zeros(nhvdc, dtype=object)

        self.loss_factor = np.zeros(nhvdc)

        self.active = np.zeros((nhvdc, ntime), dtype=bool)
        self.rate = np.zeros((nhvdc, ntime))
        self.Pf = np.zeros((nhvdc, ntime))
        self.Pt = np.zeros((nhvdc, ntime))
        self.Vset_f = np.zeros((nhvdc, ntime))
        self.Vset_t = np.zeros((nhvdc, ntime))

        self.Qmin_f = np.zeros(nhvdc)
        self.Qmax_f = np.zeros(nhvdc)
        self.Qmin_t = np.zeros(nhvdc)
        self.Qmax_t = np.zeros(nhvdc)

        self.C_hvdc_bus_f = sp.lil_matrix((nhvdc, nbus), dtype=int)  # this ons is just for splitting islands
        self.C_hvdc_bus_t = sp.lil_matrix((nhvdc, nbus), dtype=int)  # this ons is just for splitting islands

    def slice(self, elm_idx, bus_idx, time_idx=None):
        """

        :param elm_idx:
        :param bus_idx:
        :param time_idx:
        :return:
        """

        if time_idx is None:
            tidx = elm_idx
        else:
            tidx = np.ix_(elm_idx, time_idx)

        data = HvdcData(nhvdc=len(elm_idx), nbus=len(bus_idx))

        data.names = self.names[elm_idx]
        data.active = self.active[elm_idx]

        data.rate = self.rate[tidx]
        data.Pf = self.Pf[tidx]
        data.Pt = self.Pt[tidx]
        data.Vset_f = self.Vset_f[tidx]
        data.Vset_t = self.Vset_t[tidx]

        data.loss_factor = self.loss_factor[elm_idx]
        data.Qmin_f = self.Qmin_f[elm_idx]
        data.Qmax_f = self.Qmax_f[elm_idx]
        data.Qmin_t = self.Qmin_t[elm_idx]
        data.Qmax_t = self.Qmax_t[elm_idx]

        data.C_hvdc_bus_f = self.C_hvdc_bus_f[np.ix_(elm_idx, bus_idx)]
        data.C_hvdc_bus_t = self.C_hvdc_bus_t[np.ix_(elm_idx, bus_idx)]

        return data

    def get_island(self, bus_idx):
        """
        Get HVDC indices of the island given by the bus indices
        :param bus_idx: list of bus indices
        :return: list of HVDC lines indices
        """
        return tp.get_elements_of_the_island(self.C_hvdc_bus_f + self.C_hvdc_bus_t, bus_idx)

    def get_injections_per_bus(self):
        F = self.C_hvdc_bus_f.T * (self.active * self.Pf)
        T = self.C_hvdc_bus_t.T * (self.active * self.Pt)
        return F + T

    @property
    def Pbus(self):
        return self.get_injections_per_bus()

    def get_qmax_from_per_bus(self):
        """
        Max reactive power in the From Bus
        :return: (nbus, nt) Qmax From
        """
        return self.C_hvdc_bus_f.T * (self.Qmax_f * self.active.T).T

    def get_qmin_from_per_bus(self):
        """
        Min reactive power in the From Bus
        :return: (nbus, nt) Qmin From
        """
        return self.C_hvdc_bus_f.T * (self.Qmin_f * self.active.T).T

    def get_qmax_to_per_bus(self):
        """
        Max reactive power in the To Bus
        :return: (nbus, nt) Qmax To
        """
        return self.C_hvdc_bus_t.T * (self.Qmax_t * self.active.T).T

    def get_qmin_to_per_bus(self):
        """
        Min reactive power in the To Bus
        :return: (nbus, nt) Qmin To
        """
        return self.C_hvdc_bus_t.T * (self.Qmin_t * self.active.T).T

    def get_loading(self):
        return self.Pf / self.rate

    def get_losses(self):
        return (self.Pf.T * self.loss_factor).T

    def __len__(self):
        return self.nhvdc
