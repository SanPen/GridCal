import math
import numpy as np
from datetime import datetime
from collections.abc import Mapping

try:
    import pypsa
    PYPSA_AVAILABLE = True
except ImportError:
    # print('Could not find PyPSA library; some grid file formats may not be supported')
    PYPSA_AVAILABLE = False

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

BUS_X_SCALE_FACTOR = 720
BUS_Y_SCALE_FACTOR = -900


class PyPSAParser:
    def __init__(self, src: 'pypsa.Network', logger: Logger):
        self.src = src
        self.dest = MultiCircuit(src.name)  # todo: PyPSA doesn't provide f_base
        self.logger = logger

        self.nt = len(src.snapshots)
        start_time = self._parse_date(src.meta['snapshots']['start'])
        self.dest.create_profiles(self.nt, 1, 'h', start_time)  # todo: don't assume hourly intervals

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
        for name in self.src.meta['countries']:
            country = Country(name)
            self.dest.add_country(country)
            by_name[name] = country
        return by_name

    def _parse_buses(self) -> "Mapping[str, Bus]":
        """
        Parses the bus data from the PyPSA network.
        :return: a mapping from bus name to GridCal `Bus` objects.
        """
        by_name = {}
        for ix, data in self.src.buses.iterrows():
            active = self._is_active(data)
            is_slack = data['control'] == 'Slack'  # otherwise 'PQ' or 'PV'
            is_dc = data['carrier'] == 'DC'
            country = self.countries[data['country']]
            bus = Bus(ix, Vnom=data['v_nom'], vmin=data['v_mag_pu_min'], vmax=data['v_mag_pu_max'],
                      xpos=data['x'] * BUS_X_SCALE_FACTOR, ypos=data['y'] * BUS_Y_SCALE_FACTOR,
                      active=active, is_slack=is_slack, is_dc=is_dc, country=country)
            self.dest.add_bus(bus)
            by_name[ix] = bus
        return by_name

    def _parse_generators(self):
        """
        Parses the generator data from the PyPSA network.
        """
        for ix, data in self.src.generators.iterrows():
            bus = self.buses[data['bus']]
            power_factor = data['p_set'] / math.sqrt(data['q_set'] ** 2 + data['p_set'] ** 2)
            is_controlled = data['control'] == 'PV'
            generator = Generator(ix, P=data['p_set'] * data['sign'],
                                  power_factor=power_factor,
                                  is_controlled=is_controlled,
                                  Pmin=data['p_nom_min'],
                                  Pmax=data['p_nom_max'],
                                  opex=data['marginal_cost'],
                                  Cost=data['marginal_cost'],
                                  capex=data['capital_cost'] * data['p_nom'])
            self.dest.add_generator(bus, generator)
            try:
                P_prof = self.src.generators_t.p_max_pu[ix].to_numpy()
                generator.active_prof = np.ones(self.nt, dtype=bool)
                generator.P_prof = P_prof
            except KeyError:  # missing p_max_pu[ix]
                pass

    def _parse_storage_units(self):
        """
        Parses the storage units data from the PyPSA network.
        """
        if len(self.src.storage_units) > 0:
            self.logger.add_warning('Storage units not currently supported')

    def _parse_stores(self):
        """
        Parses the stores data from the PyPSA network.
        """
        if len(self.src.stores) > 0:
            self.logger.add_warning('Shunt impedances not currently supported')

    def _parse_loads(self):
        """
        Parses the load data from the PyPSA network.
        """
        for ix, data in self.src.loads.iterrows():
            bus = self.buses[data['bus']]
            active = self._is_active(data)
            load = Load(name=ix, P=data['p_set'], Q=data['q_set'], active=active)
            self.dest.add_load(bus, load)
            try:
                P_prof = self.src.loads_t.p_set[ix].to_numpy()
                load.active_prof = np.ones(self.nt, dtype=bool)
                load.P_prof = P_prof
            except KeyError:
                pass

    def _parse_line_types(self) -> "Mapping[str, SequenceLineType]":
        """
        Parses the line type data from the PyPSA network.
        :return: a mapping from type name to GridCal `SequenceLineType` objects.
        """
        by_name = {}
        for ix, data in self.src.line_types.iterrows():
            # Compute shunt susceptance in S/km from shunt capacitance in nF/km.
            omega = 2 * math.pi * data['f_nom']  # Hz
            b = data['c_per_length'] * omega * 1e-9
            kind = SequenceLineType(name=ix, Imax=data['i_nom'], R=data['r_per_length'], X=data['x_per_length'], B=b)
            self.dest.add_sequence_line(kind)
            by_name[ix] = kind
        return by_name

    def _apply_template(self, types, ix, data, proto):
        kind = types[data['type']]
        proto.apply_template(kind, self.dest.Sbase)
        expected_rate = proto.rate * int(data['num_parallel'])
        if not math.isclose(expected_rate, data['s_nom'], abs_tol=1e-6):
            self.logger.add_warning(f'Components {ix}-* have incorrect rate', value=data['s_nom'],
                                    expected_value=expected_rate)

    def _parse_lines(self):
        """
        Parses the line data from the PyPSA network.
        """
        for ix, data in self.src.lines.iterrows():
            from_bus = self.buses[data['bus0']]
            to_bus = self.buses[data['bus1']]

            length = data['length']
            is_active = self._is_active(data)
            status = BuildStatus.Commissioned if is_active else BuildStatus.Planned
            proto = Line(from_bus, to_bus, name=f'{ix}-proto', active=is_active, length=length,
                         opex=data['capital_cost'], build_status=status)

            copy_count = int(data['num_parallel'])
            if data['type']:
                self._apply_template(self.line_types, ix, data, proto)
            else:
                proto.R = data['r']
                proto.X = data['x']
                proto.B = data['b']
                if copy_count:
                    proto.rate = data['s_nom'] / copy_count

            for i in range(copy_count):
                line = proto.copy()
                line.name = f'{ix}-{i}'
                self.dest.add_line(line)

    def _parse_hvdc(self):
        """
        Parses the HVDC data from the PyPSA network.
        """
        for ix, data in self.src.links.iterrows():
            from_bus = self.buses[data['bus0']]
            to_bus = self.buses[data['bus1']]
            active = self._is_active(data)
            self.dest.add_hvdc(
                HvdcLine(from_bus, to_bus, name=ix, active=active, rate=data['p_nom'] * data['p_max_pu'],
                         Pset=data['p_set'], opex=data['capital_cost'], length=data['length']))

    def _parse_transformer_types(self) -> "Mapping[str, TransformerType]":
        """
        Parses the transformer type data from the PyPSA network.
        :return: a mapping from type name to GridCal `TransformerType` objects.
        """
        by_name = {}
        for ix, data in self.src.transformer_types.iterrows():
            kind = TransformerType(name=ix, hv_nominal_voltage=data['v_nom_0'], lv_nominal_voltage=data['v_nom_1'],
                                   nominal_power=data['s_nom'], iron_losses=data['pfe'], no_load_current=data['i0'],
                                   short_circuit_voltage=data['vsc'])
            self.dest.add_transformer_type(kind)
            by_name[ix] = kind
        return by_name

    def _parse_transformers(self):
        """
        Parses the transformer data from the PyPSA network.
        """
        for ix, data in self.src.transformers.iterrows():
            from_bus = self.buses[data['bus0']]
            to_bus = self.buses[data['bus1']]
            proto = Transformer2W(from_bus, to_bus, name=f'{ix}-proto', tap_module=data['tap_ratio'],
                                  tap_phase=data['phase_shift'])

            copy_count = int(data['num_parallel'])
            if data['type']:
                self._apply_template(self.transformer_types, ix, data, proto)
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
                self.dest.add_transformer2w(transformer)

    def _parse_shunts(self):
        """
        Parses the shunt impedances data from the PyPSA network.
        """
        if len(self.src.shunt_impedances) > 0:
            self.logger.add_warning('Shunt impedances not currently supported')

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
        return self.dest


def _log_pypsa_unavailable(logger: Logger, file_format: str):
    logger.add_error(f'{file_format} not supported since the PyPSA library could not be found')


def _parse_network(network: 'pypsa.Network', logger: Logger) -> MultiCircuit:
    parser = PyPSAParser(network, logger)
    return parser.parse()


def parse_netcdf(file_path: str, logger: Logger) -> MultiCircuit:
    """
    Parses the netCDF file using the PyPSA library.
    :param file_path: the file path
    :param logger: a logger to produce warnings and/or errors.
    :return: the GridCal circuit object
    """
    if not PYPSA_AVAILABLE:
        _log_pypsa_unavailable(logger, 'NetCDF')
        return MultiCircuit('')

    network = pypsa.Network()
    network.import_from_netcdf(file_path)
    return _parse_network(network, logger)


def parse_hdf5(file_path: str, logger: Logger) -> MultiCircuit:
    """
    Parses the HDF5 store file using the PyPSA library.
    :param file_path: the file path
    :param logger: a logger to produce warnings and/or errors.
    :return: the GridCal circuit object
    """
    if not PYPSA_AVAILABLE:
        _log_pypsa_unavailable(logger, 'HDF5 store')
        return MultiCircuit('')

    network = pypsa.Network()
    network.import_from_hdf5(file_path)
    return _parse_network(network, logger)
