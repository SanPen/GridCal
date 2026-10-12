# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import pandas as pd
from typing import Dict, Union, Tuple
import numpy as np
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Branches.underground_line_type import UndergroundLineType
from VeraGridEngine.Devices.Parents.branch_parent import BranchParent
from VeraGridEngine.Devices.Profiles import ProfileFloat
from VeraGridEngine.enumerations import DeviceType, BuildStatus, SubObjectType, PrpCat, ParamPowerFlowReferenceType
from VeraGridEngine.Devices.Branches.line_locations import LineLocations
from VeraGridEngine.Devices.Parents.editable_device import GCProp


class DcLine(BranchParent):
    __slots__ = (
        'measurements',
        '_length',
        'tolerance',
        '_r_fault',
        '_fault_pos',
        '_R',
        'template',
        'dc_conductor',
        '_locations',
    )

    LOCAL_PROPERTY_DECLARATIONS: Tuple[GCProp, ...] = (
        GCProp(prop_name='dc_conductor', units='', tpe=int,
               definition='Global conductor number in the Cable System (one-based).',
               cat=[PrpCat.TP]),
        GCProp(
            prop_name='R',
            units='p.u.',
            tpe=float,
            definition='Total positive sequence resistance.',
            cat=[PrpCat.PF],
            dyn_ref=ParamPowerFlowReferenceType.dc_line_r_pu,
        ),
        GCProp(
            prop_name='length',
            units='km',
            tpe=float,
            definition='Length of the line (not used for calculation)',
            cat=[PrpCat.TP],
            dyn_ref=ParamPowerFlowReferenceType.dc_line_length_km,
        ),
        GCProp(
            prop_name='r_fault',
            units='p.u.',
            tpe=float,
            definition='Resistance of the mid-line fault.Used in short circuit studies.',
            cat=[PrpCat.SC],
        ),
        GCProp(
            prop_name='fault_pos',
            units='p.u.',
            tpe=float,
            definition='Per-unit positioning of the fault:0 would be at the "from" side,1 would '
                                 'be at the "to" side,therefore 0.5 is at the middle.',
            cat=[PrpCat.SC],
        ),
        GCProp(
            prop_name='template',
            units='',
            tpe=DeviceType.UnderGroundLineDevice,
            definition='Cable System applied to this DC line.',
            editable=False,
            cat=[PrpCat.TP],
        ),
        GCProp(
            prop_name='locations',
            units='',
            tpe=SubObjectType.LineLocations,
            definition='',
            editable=False,
            cat=[PrpCat.TP],
        ),
    )

    def __init__(self,
                 bus_from: Union[Bus, None] = None,
                 bus_to: Union[Bus, None] = None,
                 name: str = 'Dc Line',
                 idtag: Union[str, None] = None,
                 code: str = '',
                 r=1e-20,
                 design_rate: float = 9999,
                 rate=9999.0,
                 active=True,
                 tolerance=0,
                 cost=0.0,
                 mttf=0,
                 mttr=0,
                 r_fault=0.0,
                 fault_pos=0.5,
                 length=1,
                 temp_base=20,
                 temp_oper=20,
                 alpha=0.00330,
                 template: UndergroundLineType | None = None,
                 contingency_factor=1.0,
                 protection_rating_factor: float = 1.4,
                 contingency_enabled=True,
                 monitor_loading=True,
                 capex=0,
                 opex=0,
                 build_status: BuildStatus = BuildStatus.Commissioned,
                 dc_conductor: int = 1):
        """
        DC current line
        :param bus_from: Bus from
        :param bus_to: Bus to
        :param name: Name of the branch
        :param idtag: UUID code
        :param code: secondary ID
        :param r: resistance in p.u.
        :param design_rate: Design rate (MW)
        :param rate: Branch rating (MW)
        :param active: is it active?
        :param tolerance: Tolerance specified for the branch impedance in %
        :param cost: Cost of overload (e/MW)
        :param mttf: Mean time too failure
        :param mttr: Mean time to repair
        :param r_fault: Fault resistance
        :param fault_pos: Fault position
        :param length: Length (km)
        :param temp_base: base temperature (i.e 25º °C)
        :param temp_oper: Operational temperature (°C)
        :param alpha: Thermal constant of the material (°C)
        :param template: Cable System supplying the DC equivalent
        :param dc_conductor: One-based global conductor number in the Cable System
        :param contingency_factor: Rating factor in case of contingency
        :param contingency_enabled: enabled for contingencies (Legacy)
        :param monitor_loading: monitor the loading (used in OPF)
        :param capex: Cost of investment (e/MW)
        :param opex: Cost of operation (e/MWh)
        :param build_status: build status (now time)
        """

        BranchParent.__init__(self,
                              name=name,
                              idtag=idtag,
                              code=code,
                              bus_from=bus_from,
                              bus_to=bus_to,
                              active=active,
                              reducible=False,
                              design_rate=design_rate,
                              rate=rate,
                              contingency_factor=contingency_factor,
                              protection_rating_factor=protection_rating_factor,
                              contingency_enabled=contingency_enabled,
                              monitor_loading=monitor_loading,
                              mttf=mttf,
                              mttr=mttr,
                              build_status=build_status,
                              capex=capex,
                              opex=opex,
                              cost=cost,
                              temp_base=temp_base,
                              temp_oper=temp_oper,
                              alpha=alpha,
                              device_type=DeviceType.DCLineDevice)

        # List of measurements
        self.measurements = list()

        # line length in km
        self._length = float(length)

        # line impedance tolerance
        self.tolerance = float(tolerance)

        # short circuit impedance
        self.r_fault = float(r_fault)
        self.fault_pos = float(fault_pos)

        # total impedance and admittance in p.u.
        self.R = float(r) if r is not None else 0.0001

        # type template
        self.template: UndergroundLineType | None = template
        self.dc_conductor = int(dc_conductor)

        # Line locations
        self._locations: LineLocations = LineLocations()



    @property
    def temp_oper_prof(self) -> ProfileFloat:
        """
        Cost profile
        :return: Profile
        """
        return self._temp_oper_prof

    @temp_oper_prof.setter
    def temp_oper_prof(self, val: Union[ProfileFloat, np.ndarray]):
        if isinstance(val, ProfileFloat):
            self._temp_oper_prof = val
        elif isinstance(val, np.ndarray):
            self._temp_oper_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a temp_oper_prof')

    @property
    def locations(self) -> LineLocations:
        """
        Cost profile
        :return: Profile
        """
        return self._locations

    @locations.setter
    def locations(self, val: Union[LineLocations, np.ndarray]):
        if isinstance(val, LineLocations):
            self._locations = val
        elif isinstance(val, np.ndarray):
            self._locations.set(data=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a locations')

    @property
    def R_corrected(self):
        """
        Returns a temperature corrected resistance based on a formula provided by:
        NFPA 70-2005, National Electrical Code, Table 8, footnote #2; and
        https://en.wikipedia.org/wiki/Electrical_resistivity_and_conductivity#Linear_approximation
        (version of 2019-01-03 at 15:20 EST).
        """
        return self.R * (1 + self.alpha * (self.temp_oper - self.temp_base))

    @property
    def length(self) -> float:
        """
        Line length in km
        :return: float
        """
        return self._length

    @length.setter
    def length(self, val: float):
        val = float(val)
        if isinstance(val, float):
            if val > 0.0:

                if self._length != 0 and self.auto_update_enabled:
                    factor = np.round(val / self._length, 6)  # new length / old length

                    self.R *= factor

                self._length = val
            else:
                # print('The length cannot be zero, ignoring value')
                pass
        else:
            raise Exception('The length must be a float value')

    def change_base(self, Sbase_old, Sbase_new):
        """

        :param Sbase_old:
        :param Sbase_new:
        """
        b = Sbase_new / Sbase_old

        self.R *= b

    def get_weight(self) -> float:
        """

        :return:
        """
        return self.R

    def apply_template(self,
                       obj: UndergroundLineType,
                       Sbase: float,
                       logger: Logger | None = None) -> None:
        """
        Apply one Cable System to this line atomically.

        The resistance copied to ``DcLine`` is the static per-unit value used
        by network compilation. Inductance and capacitance remain canonical in
        ``UndergroundLineType`` and are converted on demand by the dynamic consumers.
        The branch rating is intentionally preserved until the public DC pole
        voltage convention is defined.

        :param obj: Cable System to apply.
        :param Sbase: System power base in MVA.
        :param logger: Optional logger receiving validation failures.
        :return: None.
        """
        if logger is None:
            calculation_logger: Logger = Logger()
        else:
            calculation_logger = logger

        line_voltage: float = self.get_max_bus_nominal_voltage()
        try:
            if not isinstance(obj, UndergroundLineType):
                raise ValueError('Select a Cable System')
            if not np.isfinite(obj.Vnom) or obj.Vnom <= 0.0 or not np.isfinite(obj.Imax) or obj.Imax < 0.0:
                raise ValueError('Invalid Cable System rating')
            resistance_pu, _, _ = obj.get_dc_values(
                Sbase=Sbase, length=self.length, line_Vnom=line_voltage,
                conductor=self.dc_conductor,
            )
        except ValueError as error:
            calculation_logger.add_error('DC cable template could not be applied',
                                         device=self.name, value=str(error))
            return

        # Conversion succeeds before changing the branch; preserve its rating.
        self.R = resistance_pu
        self.template = obj
        self.rms_template, self.emt_template = obj.get_branch_dynamic_templates(
            device_type=self.device_type, logger=calculation_logger)

    def get_applied_dynamic_values_pu_seconds(self,
                                              Sbase: float) -> Tuple[float, float] | None:
        """
        Convert the associated physical cable data for dynamic consumers.

        This method returns ``None`` when the line has no physical cable
        evidence. It does not apply a simulation fallback or write a log.

        :param Sbase: System power base in MVA.
        :return: Total series inductance and shunt capacitance in p.u. seconds,
                 or ``None`` when no physical cable type is associated.
        """
        if self.template is not None:
            line_voltage: float = self.get_max_bus_nominal_voltage()
            resistance_pu: float
            inductance_pu_seconds: float
            capacitance_pu_seconds: float
            resistance_pu, inductance_pu_seconds, capacitance_pu_seconds = self.template.get_dc_values(
                Sbase=Sbase,
                length=self.length,
                line_Vnom=line_voltage,
                conductor=self.dc_conductor,
            )
            return inductance_pu_seconds, capacitance_pu_seconds
        else:
            return None

    def get_dynamic_values_pu_seconds(self,
                                      Sbase: float,
                                      logger: Logger) -> Tuple[float, float]:
        """
        Get the physical cable coefficients required by a dynamic simulation.

        A line without a physical cable template remains usable as a purely
        resistive branch. The missing optional dynamics are reported instead
        of stopping the simulation.

        :param Sbase: System power base in MVA.
        :param logger: Simulation logger receiving the resistive-fallback warning.
        :return: Total series inductance and shunt capacitance in p.u. seconds.
        """
        physical_values: Tuple[float, float] | None = self.get_applied_dynamic_values_pu_seconds(
            Sbase=Sbase,
        )
        if physical_values is not None:
            return physical_values
        else:
            # No physical L/C default exists for a DC cable. Returning zero
            # selects the existing resistive simulation reduction without
            # creating a fictitious physical UndergroundLineType.
            logger.add_warning(
                msg='DC line has no cable template; using the resistive fallback',
                device=self.name,
                value='L=0, C=0',
            )
            return 0.0, 0.0

    def copy(self,
             bus_dict: Dict[Bus, Bus] | None = None) -> 'DcLine':
        """
        Copy the DC line and keep its physical span.

        :param bus_dict: Optional mapping from source buses to copied buses.
        :return: New DC line with the same electrical data and cable template.
        """

        if bus_dict is None:
            bus_from: Bus | None = self.bus_from
            bus_to: Bus | None = self.bus_to
        else:
            bus_from = bus_dict[self.bus_from]
            bus_to = bus_dict[self.bus_to]

        copied_line: DcLine = DcLine(
            bus_from=bus_from,
            bus_to=bus_to,
            name=self.name,
            r=self.R,
            rate=self.rate,
            active=self.active,
            mttf=self.mttf,
            mttr=self.mttr,
            length=self.length,
            temp_base=self.temp_base,
            temp_oper=self.temp_oper,
            alpha=self.alpha,
            template=self.template,
            dc_conductor=self.dc_conductor,
        )

        copied_line.measurements = self.measurements

        copied_line.active_prof = self.active_prof
        copied_line.rate_prof = self.rate_prof

        return copied_line

    # def get_save_data(self):
    #     """
    #     Return the data that matches the edit_headers
    #     :return:
    #     """
    #     data = list()
    #     for name, properties in self.registered_properties.items():
    #         obj = getattr(self, name)
    #
    #         if obj is None:
    #             data.append("")
    #         else:
    #
    #             if hasattr(obj, 'idtag'):
    #                 obj = obj.idtag
    #             else:
    #                 if properties.tpe not in [str, float, int, bool]:
    #                     obj = str(obj)
    #                 else:
    #                     obj = str(obj)
    #
    #             data.append(obj)
    #     return data


    def get_coordinates(self):
        """
        Get the branch defining coordinates
        """
        return [self.bus_from.get_coordinates(), self.bus_to.get_coordinates()]

    # Scalar property accessors coerce assignments to the declared schema types.

    @property
    def R(self) -> float:
        """
        Get ``R``.

        :return: float
        """
        return self._R

    @R.setter
    def R(self, val: float) -> None:
        """
        Set ``R``.

        :param val: Value to assign.
        :return: None
        """
        self._R = float(val)

    @property
    def r_fault(self) -> float:
        """
        Get ``r_fault``.

        :return: float
        """
        return self._r_fault

    @r_fault.setter
    def r_fault(self, val: float) -> None:
        """
        Set ``r_fault``.

        :param val: Value to assign.
        :return: None
        """
        self._r_fault = float(val)

    @property
    def fault_pos(self) -> float:
        """
        Get ``fault_pos``.

        :return: float
        """
        return self._fault_pos

    @fault_pos.setter
    def fault_pos(self, val: float) -> None:
        """
        Set ``fault_pos``.

        :param val: Value to assign.
        :return: None
        """
        self._fault_pos = float(val)

