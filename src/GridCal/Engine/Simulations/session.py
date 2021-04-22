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
from uuid import uuid4

# Module imports
import GridCal.Engine.Simulations.Stochastic.blackout_driver as blkout
import GridCal.Engine.Simulations.OPF.opf_driver as opfdrv
import GridCal.Engine.Simulations.LinearFactors.analytic_ptdf_driver as ptdfdrv
import GridCal.Engine.Simulations.LinearFactors.ptdf_ts_driver as ptdftsdrv
import GridCal.Engine.Simulations.ShortCircuitStudies.short_circuit_driver as scdrv
import GridCal.Engine.Simulations.NK.n_minus_k_driver as nmkdrv
import GridCal.Engine.Simulations.NK.n_minus_k_ts_driver as nmktsdrv
import GridCal.Engine.Simulations.OPF.opf_ts_driver as opftsdrv
import GridCal.Engine.Simulations.PowerFlow.power_flow_driver as pfdrv
import GridCal.Engine.Simulations.Stochastic.stochastic_power_flow_driver as mcdrv
import GridCal.Engine.Simulations.PowerFlow.time_series_driver as pftsdrv
import GridCal.Engine.Simulations.PowerFlow.time_series_clustring_driver as clpftsdrv
import GridCal.Engine.Simulations.ContinuationPowerFlow.continuation_power_flow_driver as cpfdrv
import GridCal.Engine.Simulations.Topology.topology_driver as tpdrv


class SimulationSession:

    def __init__(self, name: str = 'Session', idtag: str = None):

        self.idtag: str = uuid4().hex if idtag is None else idtag

        self.name: str = name

        self.power_flow: pfdrv.PowerFlowDriver = None
        self.short_circuit: scdrv.ShortCircuitDriver = None
        self.stochastic_pf: mcdrv.StochasticPowerFlowDriver = None
        self.time_series: pftsdrv.TimeSeries = None
        self.clustering_time_series: clpftsdrv.TimeSeriesClustering = None
        self.continuation_power_flow: cpfdrv.ContinuationPowerFlowDriver = None
        self.cascade: blkout.Cascading = None
        self.optimal_power_flow: opfdrv.OptimalPowerFlow = None
        self.optimal_power_flow_time_series: opftsdrv.OptimalPowerFlowTimeSeries = None
        self.topology_reduction: tpdrv.TopologyReduction = None
        self.ptdf_analysis: ptdfdrv.LinearAnalysisDriver = None
        self.ptdf_ts_analysis: ptdftsdrv.PtdfTimeSeries = None
        self.otdf_analysis: ptdfdrv.LinearAnalysisDriver = None
        self.otdf_ts_analysis: nmkdrv.NMinusK = None

        self.drivers = dict()

    def register_driver(self, driver):
        """
        Register driver
        :param driver:
        :return:
        """
        self.drivers[driver.name] = driver


