# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
import math
import numpy as np
from datetime import datetime
from collections.abc import Mapping
from typing import Dict
import pyproj
from GridCalEngine.Devices.Injections.battery import Battery
from GridCalEngine.Devices.Injections.shunt import Shunt
from GridCalEngine.Devices.Aggregation.branch_group import BranchGroup
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Devices.Branches.transformer import TransformerType, Transformer2W
from GridCalEngine.Devices.Branches.hvdc_line import HvdcLine
from GridCalEngine.enumerations import BuildStatus
from GridCalEngine.Devices.Branches.line import SequenceLineType, Line
from GridCalEngine.Devices.Injections.load import Load
from GridCalEngine.Devices.Injections.generator import Generator
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Aggregation.country import Country
from GridCalEngine.Devices.multi_circuit import MultiCircuit

try:
    import pypsa

    PYPSA_AVAILABLE = True
except ImportError:
    PYPSA_AVAILABLE = False


class PyPSAParser:
    """
    PyPSAParser
    """

    def __init__(self, pypsa_grid: 'pypsa.Network', logger: Logger):
        """

        :param pypsa_grid:
        :param logger:
        """
        self.pypsa_grid = pypsa_grid
        self.grid = MultiCircuit(pypsa_grid.name)  # todo: PyPSA doesn't provide f_base
        self.logger = logger

        self.nt = len(pypsa_grid.snapshots)
        start_time = self._parse_date(pypsa_grid.meta['snapshots']['start'])
        self.grid.create_profiles(self.nt, 1, 'h', start_time)  # todo: don't assume hourly intervals

        self.srid = self.pypsa_grid.srid  # EPSG number

        # geo_crs: EPSG:4326  # general geographic projection, not used for metric measures. "EPSG:4326" is the standard used by OSM and google maps
        # distance_crs: EPSG:3857  # projection for distance measurements only. Possible recommended values are "EPSG:3857" (used by OSM and Google Maps)
        # area_crs: ESRI:54009  # projection for area measurements only. Possible recommended values are Global Mollweide "ESRI:54009"
        self.to_latlon_converter = pyproj.Transformer.from_crs(self.srid, 4326, always_xy=False)
        self.to_xy_converter = pyproj.Transformer.from_crs(self.srid, 3857, always_xy=False)

        self.countries = self._parse_countries()
        self.buses = self._parse_buses()
        self.line_types = self._parse_line_types()
        self.transformer_types = self._parse_transformer_types()

    @staticmethod
    def _parse_date(raw: str) -> datetime:
        return datetime.strptime(raw, '%Y-%m-%d')

    @staticmethod
    def _is_active(data) -> bool:
        """
        Returns whether the given component is active. This feature is only
        supported by some PyPSA networks, e.g. those in the PyPSA-Eur models.
        :param data: the component data.
        """
        try:
            return not data['under_construction']
        except KeyError:
            return True

    def _parse_countries(self) -> "Mapping[str, Country]":
        """
        Parses the country data from the PyPSA network.
        :return: a mapping from country name to GridCal `Country` objects.
        """
        by_name = {}
        for name in self.pypsa_grid.meta['countries']:
            country = Country(name)
            self.grid.add_country(country)
            by_name[name] = country
        return by_name

    def _parse_buses(self) -> Dict[str, Bus]:
        """
        Parses the bus data from the PyPSA network.
        :return: a mapping from bus name to GridCal `Bus` objects.
        """

        by_name: Dict[str, Bus] = dict()
        for ix, data in self.pypsa_grid.buses.iterrows():
            active = self._is_active(data)
            is_slack = data['control'] == 'Slack'  # otherwise 'PQ' or 'PV'
            is_dc = data['carrier'] == 'DC'
            country = self.countries[data['country']]

            # the longitude and latitude come stored in x, y depending on the projection (self.srid)
            x = data['x']
            y = data['y']
            lon, lat = self.to_latlon_converter.transform(xx=x, yy=y)
            x2, y2 = self.to_xy_converter.transform(xx=x, yy=y)

            bus = Bus(name=ix,
                      Vnom=data['v_nom'],
                      vmin=data['v_mag_pu_min'],
                      vmax=data['v_mag_pu_max'],
                      xpos=x2,
                      ypos=y2,
                      longitude=lon,
                      latitude=lat,
                      active=active,
                      is_slack=is_slack,
                      is_dc=is_dc,
                      country=country)
            self.grid.add_bus(bus)
            by_name[ix] = bus

        return by_name

    def _parse_generators(self):
        """
        Parses the generator row from the PyPSA network.
        """

        """
        'bus'
        'control'
        'type'
        'p_nom'
        'p_nom_mod'
        'p_nom_extendable'
        'p_nom_min'
        'p_nom_max'
        'p_min_pu'
        'p_max_pu'
        'p_set'
        'e_sum_min'
        'e_sum_max'
        'q_set'
        'sign'
        'carrier'
        'marginal_cost'
        'marginal_cost_quadratic'
        'active'
        'build_year'
        'lifetime'
        'capital_cost'
        'efficiency'
        'committable'
        'start_up_cost'
        'shut_down_cost'
        'stand_by_cost'
        'min_up_time'
        'min_down_time'
        'up_time_before'
        'down_time_before'
        'ramp_limit_up'
        'ramp_limit_down'
        'ramp_limit_start_up'
        'ramp_limit_shut_down'
        'weight'
        'p_nom_opt'        
        """

        for name, row in self.pypsa_grid.generators.iterrows():

            bus = self.buses[row['bus']]

            if row['q_set'] > 0 or row['p_set'] > 0:
                power_factor = row['p_set'] / math.sqrt(row['q_set'] ** 2 + row['p_set'] ** 2)
            else:
                power_factor = 0.8

            is_controlled = row['control'] == 'PV'

            Pmin = row['p_nom_min']
            if Pmin == -np.inf:
                Pmin = -1e20

            Pmax = row['p_nom_max']
            if Pmax == np.inf:
                Pmax = 1e20

            elm = Generator(
                name=name,
                P=row['p_set'] * row['sign'],
                power_factor=power_factor,
                is_controlled=is_controlled,
                active=row['active'],
                Snom=row['p_nom'],
                Pmin=Pmin,
                Pmax=Pmax,
                opex=row['marginal_cost'],
                Cost=row['marginal_cost'],
                Cost2=row['marginal_cost_quadratic'],
                capex=row['capital_cost'] * row['p_nom'],
                enabled_dispatch=bool(row['committable']),
            )

            elm.Cost2 = row.get('marginal_cost_quadratic', 0.0)
            elm.StartupCost = row.get('start_up_cost', 0.0)
            elm.ShutdownCost = row.get('shut_down_cost', 0.0)
            elm.MinTimeUp = row.get('min_up_time', 0.0)
            elm.MinTimeDown = row.get('min_down_time', 0.0)
            elm.RampUp = row.get('ramp_limit_up', 1e20)
            elm.RampDown = row.get('ramp_limit_down', 1e20)

            self.grid.add_generator(bus=bus, api_obj=elm)

            try:
                P_prof = self.pypsa_grid.generators_t.p_max_pu[name].to_numpy()
                elm.active_prof.set(np.ones(self.nt, dtype=bool))
                elm.Pmax_prof.set(P_prof * elm.Snom)

            except KeyError:  # missing p_max_pu[ix]
                self.logger.add_warning(msg="No Generator P profile",
                                        device=name)

    def _parse_storage_units(self):
        """
        Parses the storage units data from the PyPSA network.
        """

        for name, row in self.pypsa_grid.storage_units.iterrows():

            bus = self.buses[row['bus']]

            if row['q_set'] > 0 or row['p_set'] > 0:
                power_factor = row['p_set'] / math.sqrt(row['q_set'] ** 2 + row['p_set'] ** 2)
            else:
                power_factor = 0.8

            is_controlled = row['control'] == 'PV'

            Pmin = row['p_nom_min']
            if Pmin == -np.inf:
                Pmin = -1e20

            Pmax = row['p_nom_max']
            if Pmax == np.inf:
                Pmax = 1e20

            elm = Battery(
                name=name,
                P=row['p_set'] * row['sign'],
                power_factor=power_factor,
                is_controlled=is_controlled,
                Snom=row['p_nom'],
                active=row['active'],
                Pmin=Pmin,
                Pmax=Pmax,
                opex=row['marginal_cost'],
                Cost=row['marginal_cost'],
                capex=row['capital_cost'] * row['p_nom'],
                enabled_dispatch=bool(row.get('p_dispatch', True)),
            )

            elm.Enom = row.get('e_nom', 9999.0)
            elm.Cost2 = row.get('marginal_cost_quadratic', 0.0)
            elm.StartupCost = row.get('start_up_cost', 0.0)
            elm.ShutdownCost = row.get('shut_down_cost', 0.0)
            elm.MinTimeUp = row.get('min_up_time', 0.0)
            elm.MinTimeDown = row.get('min_down_time', 0.0)
            elm.RampUp = row.get('ramp_limit_up', 1e20)
            elm.RampDown = row.get('ramp_limit_down', 1e20)

            self.grid.add_battery(bus=bus, api_obj=elm)

            try:
                P_prof = self.pypsa_grid.generators_t.p_max_pu[name].to_numpy()
                elm.active_prof.set(np.ones(self.nt, dtype=bool))
                elm.Pmax_prof.set(P_prof * elm.Snom)

            except KeyError:  # missing p_max_pu[ix]
                self.logger.add_warning(msg="No Generator P profile",
                                        device=name)

    def _parse_stores(self):
        """
        Parses the stores data from the PyPSA network.
        """
        if len(self.pypsa_grid.stores) > 0:
            self.logger.add_warning('Shunt impedances not currently supported')

    def _parse_loads(self):
        """
        Parses the load data from the PyPSA network.
        """
        for ix, data in self.pypsa_grid.loads.iterrows():
            bus = self.buses[data['bus']]
            active = self._is_active(data)
            load = Load(name=ix, P=data['p_set'], Q=data['q_set'], active=active)
            self.grid.add_load(bus, load)
            try:
                P_prof = self.pypsa_grid.loads_t.p_set[ix].to_numpy()
                load.active_prof = np.ones(self.nt, dtype=bool)
                load.P_prof = P_prof
            except KeyError:
                pass

    def _parse_line_types(self) -> Dict[str, SequenceLineType]:
        """
        Parses the line type data from the PyPSA network.
        :return: a mapping from type name to GridCal `SequenceLineType` objects.
        """
        by_name: Dict[str, SequenceLineType] = dict()
        for ix, data in self.pypsa_grid.line_types.iterrows():
            # Compute shunt susceptance in S/km from shunt capacitance in nF/km.
            omega = 2 * math.pi * data['f_nom']  # Hz
            b = data['c_per_length'] * omega * 1e-3  # in uS
            kind = SequenceLineType(name=ix, Imax=data['i_nom'], R=data['r_per_length'], X=data['x_per_length'], B=b)
            self.grid.add_sequence_line(kind)
            by_name[ix] = kind
        return by_name

    def _parse_lines(self):
        """
        Parses the line data from the PyPSA network.
        """
        w = 2.0 * np.pi * self.grid.fBase
        for ix, row in self.pypsa_grid.lines.iterrows():
            from_bus = self.buses[row['bus0']]
            to_bus = self.buses[row['bus1']]
            copy_count = int(row['num_parallel'])
            length = row['length']
            status = BuildStatus.Commissioned
            name = row.get('name', ix)

            if copy_count > 1:
                # More than onle line, make a group for later...
                group = BranchGroup(name=name)
                self.grid.add_branch_group(group)

                rate = row['s_nom'] / copy_count
            else:
                group = None
                rate = row['s_nom']

            for i in range(copy_count if copy_count > 1 else 1):
                elm = Line(
                    bus_from=from_bus,
                    bus_to=to_bus,
                    name=name,
                    code=name,
                    active=bool(row['active']),
                    length=length,
                    rate=rate,
                    opex=row['capital_cost'],
                    build_status=status
                )

                if group is not None:
                    elm.group = group

                template = self.line_types.get(row['type'], None)
                if template is None:
                    elm.R = row['r']
                    elm.X = row['x']
                    elm.B = row['b']
                    elm.fill_design_properties(
                        r_ohm=row['r'],
                        x_ohm=row['x'],
                        c_nf=row['b'] / w * 1e9,
                        freq=self.grid.fBase,
                        length=length,
                        Imax=0,
                        Sbase=self.grid.Sbase,
                    )
                    elm.rate = rate
                else:
                    elm.apply_template(obj=template, Sbase=self.grid.Sbase, freq=self.grid.fBase)

                self.grid.add_line(elm)

    def _parse_hvdc(self):
        """
        Parses the HVDC data from the PyPSA network.
        """
        for ix, data in self.pypsa_grid.links.iterrows():
            from_bus = self.buses[data['bus0']]
            to_bus = self.buses[data['bus1']]
            active = self._is_active(data)
            self.grid.add_hvdc(
                HvdcLine(bus_from=from_bus,
                         bus_to=to_bus,
                         name=ix,
                         active=active,
                         rate=data['p_nom'] * data['p_max_pu'],
                         Pset=data['p_set'],
                         opex=data['capital_cost'],
                         length=data['length'])
            )

    def _parse_transformer_types(self) -> Dict[str, TransformerType]:
        """
        Parses the transformer type data from the PyPSA network.
        :return: a mapping from type name to GridCal `TransformerType` objects.
        """
        by_name: Dict[str, TransformerType] = dict()
        for ix, data in self.pypsa_grid.transformer_types.iterrows():
            kind = TransformerType(name=str(ix),
                                   hv_nominal_voltage=data['v_nom_0'],
                                   lv_nominal_voltage=data['v_nom_1'],
                                   nominal_power=data['s_nom'],
                                   iron_losses=data['pfe'],
                                   no_load_current=data['i0'],
                                   short_circuit_voltage=data['vsc'])
            self.grid.add_transformer_type(kind)
            by_name[ix] = kind
        return by_name

    def _parse_transformers(self):
        """
        Parses the transformer data from the PyPSA network.
        """
        for ix, data in self.pypsa_grid.transformers.iterrows():
            from_bus = self.buses[data['bus0']]
            to_bus = self.buses[data['bus1']]
            proto = Transformer2W(bus_from=from_bus,
                                  bus_to=to_bus,
                                  name=f'{ix}-proto',
                                  tap_module=data['tap_ratio'],
                                  tap_phase=data['phase_shift'])

            copy_count = int(data['num_parallel'])

            template = self.transformer_types.get(data['type'], None)

            if template is not None:
                proto.apply_template(obj=template, Sbase=self.grid.Sbase, logger=self.logger)
            else:
                proto.R = data['r']
                proto.X = data['x']
                proto.G = data['g']
                proto.B = data['b']
                if copy_count:
                    proto.rate = data['s_nom'] / copy_count

            assert math.isclose(proto.rate, 2e3, abs_tol=1e-6)  # todo: handle other types of transformers
            for i in range(copy_count):
                transformer = proto.copy()
                transformer.name = f'{ix}-{i}'
                self.grid.add_transformer2w(transformer)

    def _parse_shunts(self):
        """
        Parses the shunt impedances row from the PyPSA network.
        """
        for name, row in self.pypsa_grid.shunt_impedances.iterrows():
            bus = self.buses[row['bus']]
            V2 = (bus.Vnom * 1e3) ** 2
            g = row['g']  # in Siemens
            b = row['b']  # in Siemens
            G = V2 * g * 1e-6  # in MW
            B = V2 * b * 1e-6  # in MVAr

            elm = Shunt(
                name=row['name'],
                G=G,
                B=B,
                active=bool(row["active"])
            )
            self.grid.add_shunt(bus=bus, api_obj=elm)

    def parse(self) -> MultiCircuit:
        """
        Parses the PyPSA network.
        :return: the GridCal circuit object.
        """
        self._parse_generators()
        self._parse_storage_units()
        self._parse_stores()
        self._parse_loads()
        self._parse_lines()
        self._parse_hvdc()
        self._parse_transformers()
        self._parse_shunts()
        return self.grid


def pypsa2gridcal(network: 'pypsa.Network', logger: Logger) -> MultiCircuit:
    """

    :param network:
    :param logger:
    :return:
    """
    parser = PyPSAParser(network, logger)
    return parser.parse()


def parse_pypsa_netcdf(file_path: str, logger: Logger) -> MultiCircuit:
    """
    Parses the netCDF file using the PyPSA library.
    :param file_path: the file path
    :param logger: a logger to produce warnings and/or errors.
    :return: the GridCal circuit object
    """
    if not PYPSA_AVAILABLE:
        logger.add_error(f'PyPSA not installed, try pip install pypsa')
        return MultiCircuit('')
    else:
        network = pypsa.Network()
        network.import_from_netcdf(file_path)
        return pypsa2gridcal(network, logger)


def parse_pypsa_hdf5(file_path: str, logger: Logger) -> MultiCircuit:
    """
    Parses the HDF5 store file using the PyPSA library.
    :param file_path: the file path
    :param logger: a logger to produce warnings and/or errors.
    :return: the GridCal circuit object
    """
    if not PYPSA_AVAILABLE:
        logger.add_error(f'PyPSA not installed, try pip install pypsa')
        return MultiCircuit('')
    else:
        network = pypsa.Network()
        network.import_from_hdf5(file_path)
        return pypsa2gridcal(network, logger)
