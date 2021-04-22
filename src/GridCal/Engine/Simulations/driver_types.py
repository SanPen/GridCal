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


class SimulationTypes(Enum):
    PowerFlow_run = 'power flow'
    ShortCircuit_run = 'Short circuit'
    MonteCarlo_run = 'Monte Carlo'
    TimeSeries_run = 'Time series power flow'
    ClusteringTimeSeries_run = 'Clustering Time series power flow'
    ContinuationPowerFlow_run = 'Voltage collapse'
    LatinHypercube_run = 'Latin Hypercube'
    StochasticPowerFlow = 'Stochastic Power Flow'
    Cascade_run = 'Cascade'
    OPF_run = 'Optimal power flow'
    OPFTimeSeries_run = 'OPF Time series'
    TransientStability_run = 'Transient stability'
    TopologyReduction_run = 'Topology reduction'
    PTDF_run = 'PTDF'
    PTDF_TS_run = 'PTDF_TS'
    OTDF_run = 'OTDF'
    OTDF_TS_run = 'OTDF_TS'
    Delete_and_reduce_run = 'Delete and reduce'
