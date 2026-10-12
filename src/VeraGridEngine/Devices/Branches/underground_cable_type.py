# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import math
from typing import Any, Tuple

from VeraGridEngine.Devices.Parents.editable_device import EditableDevice, GCProp
from VeraGridEngine.enumerations import CableResistanceInput, DeviceType, PrpCat


class UndergroundCableType(EditableDevice):
    """Single-core cable construction with a core and a metallic sheath."""

    __slots__ = (
        '_nominal_voltage',
        '_resistance_input',
        '_core_dc_resistance',
        '_sheath_dc_resistance',
        '_core_diameter',
        '_core_internal_diameter',
        '_cable_diameter',
        '_sheath_thickness',
        '_main_insulation_thickness',
        '_core_resistivity',
        '_sheath_resistivity',
        '_core_filling_factor',
        '_sheath_filling_factor',
        '_main_insulation_permittivity',
        '_outer_insulation_permittivity',
        '_main_insulation_loss_tangent',
        '_outer_insulation_loss_tangent',
        '_core_relative_permeability',
        '_sheath_relative_permeability',
        '_skin_effect_factor',
        '_proximity_effect_factor',
    )

    # Descriptive property names also supply GUI headers, as for Wire.
    # Keep the previous names as file aliases so existing catalogues still load.
    LOCAL_PROPERTY_DECLARATIONS: Tuple[GCProp, ...] = (
        GCProp(prop_name='nominal_voltage', old_names=('Vnom',), units='kV', tpe=float,
               definition='Rated cable voltage (PowerFactory uline)',
               cat=(PrpCat.TP,)),
        GCProp(prop_name='resistance_input', old_names=('core_resistance_input',), units='', tpe=CableResistanceInput,
               definition='Choose the resistance inputs for both core and sheath at 20 degrees Celsius: DC resistances, or resistivities and filling factors',
               cat=(PrpCat.TP,)),
        GCProp(prop_name='core_dc_resistance', old_names=('rpha',), units='Ohm/km', tpe=float,
               definition='Core DC resistance at 20 degrees Celsius: input in DC resistance mode, otherwise calculated from resistivity, filling factor and diameter',
               cat=(PrpCat.TP,)),
        GCProp(prop_name='sheath_dc_resistance', units='Ohm/km', tpe=float,
               definition='Sheath DC resistance at 20 degrees Celsius: input in DC resistance mode, otherwise calculated from resistivity, filling factor and annular area',
               cat=(PrpCat.TP,)),
        GCProp(prop_name='core_diameter', old_names=('diaCon',), units='mm', tpe=float,
               definition='Core outer diameter',
               cat=(PrpCat.TP,)),
        GCProp(prop_name='core_internal_diameter', old_names=('diaTube',), units='mm', tpe=float,
               definition='Core inner diameter',
               cat=(PrpCat.TP,)),
        GCProp(prop_name='cable_diameter', old_names=('diaCab',), units='mm', tpe=float,
               definition='Overall cable diameter, including outer insulation',
               cat=(PrpCat.TP,)),
        GCProp(prop_name='sheath_thickness', old_names=('thSht',), units='mm', tpe=float,
               definition='Metallic sheath thickness',
               cat=(PrpCat.TP,)),
        GCProp(prop_name='main_insulation_thickness', old_names=('thIns',), units='mm', tpe=float,
               definition='Core-to-sheath insulation thickness (PowerFactory thIns[0]); outer insulation is derived from cable_diameter',
               cat=(PrpCat.TP,)),
        GCProp(prop_name='core_resistivity', old_names=('crho_core',), units='uOhm*cm', tpe=float,
               definition='Core resistivity at 20 degrees Celsius (PowerFactory crho[0]); inactive in DC resistance mode',
               cat=(PrpCat.TP,)),
        GCProp(prop_name='sheath_resistivity', old_names=('crho_sheath',), units='uOhm*cm', tpe=float,
               definition='Sheath resistivity at 20 degrees Celsius (PowerFactory crho[1]); inactive in DC resistance mode',
               cat=(PrpCat.TP,)),
        GCProp(prop_name='core_filling_factor', old_names=('Cf_core',), units='%', tpe=float,
               definition='Core conducting filling factor (PowerFactory Cf[0]); inactive in DC resistance mode',
               cat=(PrpCat.TP,)),
        GCProp(prop_name='sheath_filling_factor', old_names=('Cf_sheath',), units='%', tpe=float,
               definition='Sheath conducting filling factor (PowerFactory Cf[1]); inactive in DC resistance mode',
               cat=(PrpCat.TP,)),
        GCProp(prop_name='main_insulation_permittivity', old_names=('cepsr_core_sheath',), units='', tpe=float,
               definition='Core-to-sheath insulation relative permittivity (PowerFactory cepsr[0])',
               cat=(PrpCat.TP,)),
        GCProp(prop_name='outer_insulation_permittivity', old_names=('cepsr_outer',), units='', tpe=float,
               definition='Outer insulation relative permittivity (PowerFactory cepsr[1])',
               cat=(PrpCat.TP,)),
        GCProp(prop_name='main_insulation_loss_tangent', old_names=('ctand_core_sheath',), units='', tpe=float,
               definition='Core-to-sheath insulation dielectric loss factor (PowerFactory ctand[0])',
               cat=(PrpCat.TP,)),
        GCProp(prop_name='outer_insulation_loss_tangent', old_names=('ctand_outer',), units='', tpe=float,
               definition='Outer insulation dielectric loss factor (PowerFactory ctand[1])',
               cat=(PrpCat.TP,)),
        GCProp(prop_name='core_relative_permeability', old_names=('my_core',), units='', tpe=float,
               definition='Core relative magnetic permeability (PowerFactory my[0])',
               cat=(PrpCat.TP,)),
        GCProp(prop_name='sheath_relative_permeability', old_names=('my_sheath',), units='', tpe=float,
               definition='Sheath relative magnetic permeability (PowerFactory my[1])',
               cat=(PrpCat.TP,)),
        GCProp(prop_name='skin_effect_factor', old_names=('ks',), units='', tpe=float,
               definition='Core skin-effect factor',
               cat=(PrpCat.TP,)),
        GCProp(prop_name='proximity_effect_factor', old_names=('kp',), units='', tpe=float,
               definition='Imported core proximity-effect factor; informational, not used by this calculation',
               editable=False, cat=(PrpCat.TP,)),
    )

    def __init__(self,
                 name: str = 'Underground cable',
                 idtag: str | None = None,
                 code: str = '',
                 nominal_voltage: float = 1.0,
                 core_dc_resistance: float = 0.0,
                 core_diameter: float = 10.0,
                 core_internal_diameter: float = 0.0,
                 cable_diameter: float = 30.0,
                 sheath_thickness: float = 1.0,
                 main_insulation_thickness: float = 5.0,
                 core_resistivity: float = 1.7241,
                 sheath_resistivity: float = 1.7241,
                 core_filling_factor: float = 100.0,
                 sheath_filling_factor: float = 100.0,
                 main_insulation_permittivity: float = 2.3,
                 outer_insulation_permittivity: float = 2.5,
                 main_insulation_loss_tangent: float = 0.0,
                 outer_insulation_loss_tangent: float = 0.0,
                 core_relative_permeability: float = 1.0,
                 sheath_relative_permeability: float = 1.0,
                 skin_effect_factor: float = 1.0,
                 proximity_effect_factor: float = 1.0,
                 core_resistance_input: CableResistanceInput | None = None,
                 resistance_input: CableResistanceInput | None = None,
                 sheath_dc_resistance: float | None = None) -> None:
        """Create one physical cable using scalar inputs for its two conducting layers.

        :param name: Cable catalogue name.
        :param idtag: Persistent VeraGrid identifier.
        :param code: Optional user code.
        :param nominal_voltage: Rated cable voltage (PowerFactory uline) in kV.
        :param core_dc_resistance: Core DC resistance at 20 degrees Celsius in Ohm/km, used only in DC resistance mode.
        :param core_resistance_input: Deprecated alias of the shared resistance_input selector.
        :param resistance_input: Select DC resistances or material inputs for both core and sheath; defaults to material inputs.
        :param sheath_dc_resistance: Sheath DC resistance at 20 degrees Celsius in Ohm/km, required in DC resistance mode.
        :param core_diameter: Core outer diameter in mm.
        :param core_internal_diameter: Core inner diameter in mm.
        :param cable_diameter: Overall cable diameter, including outer insulation in mm.
        :param sheath_thickness: Metallic sheath thickness in mm.
        :param main_insulation_thickness: Core-to-sheath insulation thickness (PowerFactory thIns[0]); outer insulation is derived from cable_diameter in mm.
        :param core_resistivity: Core resistivity at 20 degrees Celsius (PowerFactory crho[0]) in uOhm*cm.
        :param sheath_resistivity: Sheath resistivity at 20 degrees Celsius (PowerFactory crho[1]) in uOhm*cm.
        :param core_filling_factor: Core conducting filling factor (PowerFactory Cf[0]) in %.
        :param sheath_filling_factor: Sheath conducting filling factor (PowerFactory Cf[1]) in %.
        :param main_insulation_permittivity: Core-to-sheath insulation relative permittivity (PowerFactory cepsr[0]).
        :param outer_insulation_permittivity: Outer insulation relative permittivity (PowerFactory cepsr[1]).
        :param main_insulation_loss_tangent: Core-to-sheath insulation dielectric loss factor (PowerFactory ctand[0]).
        :param outer_insulation_loss_tangent: Outer insulation dielectric loss factor (PowerFactory ctand[1]).
        :param core_relative_permeability: Core relative magnetic permeability (PowerFactory my[0]).
        :param sheath_relative_permeability: Sheath relative magnetic permeability (PowerFactory my[1]).
        :param skin_effect_factor: Core skin-effect factor.
        :param proximity_effect_factor: Imported core proximity-effect factor; informational, not used by this calculation.
        :return: None.
        """
        EditableDevice.__init__(
            self,
            name=name,
            idtag=idtag,
            code=code,
            device_type=DeviceType.UndergroundCableTypeDevice,
        )

        # Store only the supported layers; the DGS parser maps the PowerFactory vectors.
        self.nominal_voltage = nominal_voltage
        if (core_resistance_input is not None and resistance_input is not None
                and CableResistanceInput(core_resistance_input) != CableResistanceInput(resistance_input)):
            raise ValueError('Specify one common resistance input method for core and sheath')
        self.resistance_input = (resistance_input if resistance_input is not None else
                                 core_resistance_input if core_resistance_input is not None else
                                 CableResistanceInput.Resistivity)
        self.core_dc_resistance = core_dc_resistance
        self.sheath_dc_resistance = 0.0 if sheath_dc_resistance is None else sheath_dc_resistance
        self.core_diameter = core_diameter
        self.core_internal_diameter = core_internal_diameter
        self.cable_diameter = cable_diameter
        self.sheath_thickness = sheath_thickness
        self.main_insulation_thickness = main_insulation_thickness
        self.core_resistivity = core_resistivity
        self.sheath_resistivity = sheath_resistivity
        self.core_filling_factor = core_filling_factor
        self.sheath_filling_factor = sheath_filling_factor
        self.main_insulation_permittivity = main_insulation_permittivity
        self.outer_insulation_permittivity = outer_insulation_permittivity
        self.main_insulation_loss_tangent = main_insulation_loss_tangent
        self.outer_insulation_loss_tangent = outer_insulation_loss_tangent
        self.core_relative_permeability = core_relative_permeability
        self.sheath_relative_permeability = sheath_relative_permeability
        self.skin_effect_factor = skin_effect_factor
        self.proximity_effect_factor = proximity_effect_factor
        if (core_resistance_input is not None and resistance_input is None
                and sheath_dc_resistance is None):
            # Preserve the former core-only constructor's sheath definition.
            self.sheath_dc_resistance = self.get_sheath_dc_resistance_from_material()

    @property
    def nominal_voltage(self) -> float:
        """Read the nominal_voltage input.

        :return: Rated cable voltage (PowerFactory uline) in kV.
        """
        return self._nominal_voltage

    @nominal_voltage.setter
    def nominal_voltage(self, value: float) -> None:
        """Store the nominal_voltage input.

        :param value: Rated cable voltage (PowerFactory uline) in kV.
        :return: None.
        """
        self._nominal_voltage = float(value)

    @property
    def resistance_input(self) -> CableResistanceInput:
        """Return the common resistance input method for core and sheath."""
        return self._resistance_input

    @resistance_input.setter
    def resistance_input(self, value: CableResistanceInput | str) -> None:
        """Store the selector without reinterpreting other inputs during file loading."""
        self._resistance_input = CableResistanceInput(value)

    @property
    def core_resistance_input(self) -> CableResistanceInput:
        """Compatibility alias; this selector now controls both conducting layers."""
        return self.resistance_input

    @core_resistance_input.setter
    def core_resistance_input(self, value: CableResistanceInput | str) -> None:
        self.resistance_input = value

    def get_sheath_area_m2(self) -> float:
        """Return the tubular sheath area, excluding the core and insulation."""
        inner_radius_m = (self.core_diameter / 2.0 + self.main_insulation_thickness) * 1e-3
        thickness_m = self.sheath_thickness * 1e-3
        return math.pi * thickness_m * (2.0 * inner_radius_m + thickness_m)

    def get_sheath_dc_resistance_from_material(self) -> float:
        """Derive sheath resistance from its material data, also for legacy migration."""
        conducting_area_m2 = self.get_sheath_area_m2() * self.sheath_filling_factor / 100.0
        if conducting_area_m2 <= 0.0:
            return float('nan')
        return self.sheath_resistivity * 1e-5 / conducting_area_m2

    def get_core_material_properties(self) -> tuple[float, float]:
        """Return effective calculation inputs in micro-ohm cm and percent.

        A directly specified resistance determines effective resistivity over
        the solid core section; a 100 percent factor avoids applying it twice.
        The material-input path is unchanged for legacy files and DGS imports.
        """
        if self.resistance_input == CableResistanceInput.DcResistance:
            area_m2 = math.pi * (self.core_diameter * 0.5e-3) ** 2
            return self._core_dc_resistance * area_m2 * 1.0e5, 100.0
        return self.core_resistivity, self.core_filling_factor

    def get_sheath_material_properties(self) -> tuple[float, float]:
        """Return the active sheath calculation inputs in micro-ohm cm and percent."""
        if self.resistance_input == CableResistanceInput.DcResistance:
            return self.sheath_dc_resistance * self.get_sheath_area_m2() * 1e5, 100.0
        return self.sheath_resistivity, self.sheath_filling_factor

    def validate_resistance_inputs(self) -> None:
        """Reject invalid active inputs before calculating an impedance matrix."""
        if not math.isfinite(self.core_diameter) or self.core_diameter <= 0.0:
            raise ValueError('Core diameter must be finite and positive')
        if (not math.isfinite(self.sheath_thickness) or self.sheath_thickness <= 0.0
                or not math.isfinite(self.main_insulation_thickness) or self.main_insulation_thickness <= 0.0
                or not math.isfinite(self.get_sheath_area_m2()) or self.get_sheath_area_m2() <= 0.0):
            raise ValueError('Sheath annular area and its defining dimensions must be finite and positive')
        for layer in ('core', 'sheath'):
            if self.resistance_input == CableResistanceInput.DcResistance:
                resistance = getattr(self, f'{layer}_dc_resistance')
                if not math.isfinite(resistance) or resistance <= 0.0:
                    raise ValueError(f'{layer.capitalize()} DC resistance must be finite and positive')
            else:
                resistivity = getattr(self, f'{layer}_resistivity')
                factor = getattr(self, f'{layer}_filling_factor')
                if not math.isfinite(resistivity) or resistivity <= 0.0:
                    raise ValueError(f'{layer.capitalize()} resistivity must be finite and positive')
                if not math.isfinite(factor) or not 0.0 < factor <= 100.0:
                    raise ValueError(f'{layer.capitalize()} filling factor must be greater than zero and at most 100 percent')

    def is_property_editable(self, prop: GCProp) -> bool:
        """Allow only the selected resistance representation to be edited."""
        if prop.name in ('core_dc_resistance', 'sheath_dc_resistance'):
            return self.resistance_input == CableResistanceInput.DcResistance
        if prop.name in ('core_resistivity', 'core_filling_factor', 'sheath_resistivity', 'sheath_filling_factor'):
            return self.resistance_input == CableResistanceInput.Resistivity
        return super().is_property_editable(prop)

    def set_value(self, prop: GCProp, t_idx: int | None, value: Any) -> None:
        """Apply GUI edits, preserving resistance when switching input method.

        Snapshot setters used by file loading deliberately bypass this UI
        transition so saved inputs are restored independently of field order.
        """
        if not self.is_property_editable(prop):
            raise ValueError(f'{prop.name} is not an active input')
        if prop.name == 'resistance_input':
            mode = CableResistanceInput(value)
            if mode != self.resistance_input:
                self.validate_resistance_inputs()
                if mode == CableResistanceInput.DcResistance:
                    self._core_dc_resistance = self.core_dc_resistance
                    self._sheath_dc_resistance = self.sheath_dc_resistance
                else:
                    # Preserve each layer's R when returning to material inputs.
                    for layer, properties in (('core', self.get_core_material_properties()),
                                               ('sheath', self.get_sheath_material_properties())):
                        factor = getattr(self, f'{layer}_filling_factor')
                        if not math.isfinite(factor) or not 0.0 < factor <= 100.0:
                            factor = 100.0
                        setattr(self, f'{layer}_resistivity', properties[0] * factor / 100.0)
                        setattr(self, f'{layer}_filling_factor', factor)
                self.resistance_input = mode
            return
        if prop.name in ('core_dc_resistance', 'core_resistivity', 'core_filling_factor', 'core_diameter',
                         'sheath_dc_resistance', 'sheath_resistivity', 'sheath_filling_factor',
                         'sheath_thickness', 'main_insulation_thickness'):
            number = float(value)
            if not math.isfinite(number) or number <= 0.0:
                raise ValueError(f'{prop.name} must be finite and positive')
            if prop.name in ('core_filling_factor', 'sheath_filling_factor') and number > 100.0:
                raise ValueError('Filling factor cannot exceed 100 percent')
        super().set_value(prop=prop, t_idx=t_idx, value=value)

    @property
    def core_dc_resistance(self) -> float:
        """Return the active or derived core DC resistance at 20 C in Ohm/km."""
        if self.resistance_input == CableResistanceInput.DcResistance:
            return self._core_dc_resistance
        area_m2 = math.pi * (self.core_diameter * 0.5e-3) ** 2
        conducting_area_m2 = area_m2 * self.core_filling_factor / 100.0
        if conducting_area_m2 <= 0.0:
            return float('nan')
        return self.core_resistivity * 1.0e-5 / conducting_area_m2

    @core_dc_resistance.setter
    def core_dc_resistance(self, value: float) -> None:
        """Store the core_dc_resistance input.

        :param value: Core DC resistance at 20 degrees Celsius in Ohm/km; active only in DC resistance mode.
        :return: None.
        """
        self._core_dc_resistance = float(value)

    @property
    def sheath_dc_resistance(self) -> float:
        """Return the active or derived sheath DC resistance at 20 C in Ohm/km."""
        if self.resistance_input == CableResistanceInput.DcResistance:
            return self._sheath_dc_resistance
        return self.get_sheath_dc_resistance_from_material()

    @sheath_dc_resistance.setter
    def sheath_dc_resistance(self, value: float) -> None:
        """Store the sheath resistance input; used only in DC resistance mode."""
        self._sheath_dc_resistance = float(value)

    @property
    def core_diameter(self) -> float:
        """Read the core_diameter input.

        :return: Core outer diameter in mm.
        """
        return self._core_diameter

    @core_diameter.setter
    def core_diameter(self, value: float) -> None:
        """Store the core_diameter input.

        :param value: Core outer diameter in mm.
        :return: None.
        """
        self._core_diameter = float(value)

    @property
    def core_internal_diameter(self) -> float:
        """Read the core_internal_diameter input.

        :return: Core inner diameter in mm.
        """
        return self._core_internal_diameter

    @core_internal_diameter.setter
    def core_internal_diameter(self, value: float) -> None:
        """Store the core_internal_diameter input.

        :param value: Core inner diameter in mm.
        :return: None.
        """
        self._core_internal_diameter = float(value)

    @property
    def cable_diameter(self) -> float:
        """Read the cable_diameter input.

        :return: Overall cable diameter, including outer insulation in mm.
        """
        return self._cable_diameter

    @cable_diameter.setter
    def cable_diameter(self, value: float) -> None:
        """Store the cable_diameter input.

        :param value: Overall cable diameter, including outer insulation in mm.
        :return: None.
        """
        self._cable_diameter = float(value)

    @property
    def sheath_thickness(self) -> float:
        """Read the sheath_thickness input.

        :return: Metallic sheath thickness in mm.
        """
        return self._sheath_thickness

    @sheath_thickness.setter
    def sheath_thickness(self, value: float) -> None:
        """Store the sheath_thickness input.

        :param value: Metallic sheath thickness in mm.
        :return: None.
        """
        self._sheath_thickness = float(value)

    @property
    def main_insulation_thickness(self) -> float:
        """Read the main_insulation_thickness input.

        :return: Core-to-sheath insulation thickness (PowerFactory thIns[0]); outer insulation is derived from cable_diameter in mm.
        """
        return self._main_insulation_thickness

    @main_insulation_thickness.setter
    def main_insulation_thickness(self, value: float) -> None:
        """Store the main_insulation_thickness input.

        :param value: Core-to-sheath insulation thickness (PowerFactory thIns[0]); outer insulation is derived from cable_diameter in mm.
        :return: None.
        """
        self._main_insulation_thickness = float(value)

    @property
    def core_resistivity(self) -> float:
        """Read the core_resistivity input.

        :return: Core resistivity at 20 degrees Celsius (PowerFactory crho[0]) in uOhm*cm.
        """
        return self._core_resistivity

    @core_resistivity.setter
    def core_resistivity(self, value: float) -> None:
        """Store the core_resistivity input.

        :param value: Core resistivity at 20 degrees Celsius (PowerFactory crho[0]) in uOhm*cm.
        :return: None.
        """
        self._core_resistivity = float(value)

    @property
    def sheath_resistivity(self) -> float:
        """Read the sheath_resistivity input.

        :return: Sheath resistivity at 20 degrees Celsius (PowerFactory crho[1]) in uOhm*cm.
        """
        return self._sheath_resistivity

    @sheath_resistivity.setter
    def sheath_resistivity(self, value: float) -> None:
        """Store the sheath_resistivity input.

        :param value: Sheath resistivity at 20 degrees Celsius (PowerFactory crho[1]) in uOhm*cm.
        :return: None.
        """
        self._sheath_resistivity = float(value)

    @property
    def core_filling_factor(self) -> float:
        """Read the core_filling_factor input.

        :return: Core conducting filling factor (PowerFactory Cf[0]) in %.
        """
        return self._core_filling_factor

    @core_filling_factor.setter
    def core_filling_factor(self, value: float) -> None:
        """Store the core_filling_factor input.

        :param value: Core conducting filling factor (PowerFactory Cf[0]) in %.
        :return: None.
        """
        self._core_filling_factor = float(value)

    @property
    def sheath_filling_factor(self) -> float:
        """Read the sheath_filling_factor input.

        :return: Sheath conducting filling factor (PowerFactory Cf[1]) in %.
        """
        return self._sheath_filling_factor

    @sheath_filling_factor.setter
    def sheath_filling_factor(self, value: float) -> None:
        """Store the sheath_filling_factor input.

        :param value: Sheath conducting filling factor (PowerFactory Cf[1]) in %.
        :return: None.
        """
        self._sheath_filling_factor = float(value)

    @property
    def main_insulation_permittivity(self) -> float:
        """Read the main_insulation_permittivity input.

        :return: Core-to-sheath insulation relative permittivity (PowerFactory cepsr[0]).
        """
        return self._main_insulation_permittivity

    @main_insulation_permittivity.setter
    def main_insulation_permittivity(self, value: float) -> None:
        """Store the main_insulation_permittivity input.

        :param value: Core-to-sheath insulation relative permittivity (PowerFactory cepsr[0]).
        :return: None.
        """
        self._main_insulation_permittivity = float(value)

    @property
    def outer_insulation_permittivity(self) -> float:
        """Read the outer_insulation_permittivity input.

        :return: Outer insulation relative permittivity (PowerFactory cepsr[1]).
        """
        return self._outer_insulation_permittivity

    @outer_insulation_permittivity.setter
    def outer_insulation_permittivity(self, value: float) -> None:
        """Store the outer_insulation_permittivity input.

        :param value: Outer insulation relative permittivity (PowerFactory cepsr[1]).
        :return: None.
        """
        self._outer_insulation_permittivity = float(value)

    @property
    def main_insulation_loss_tangent(self) -> float:
        """Read the main_insulation_loss_tangent input.

        :return: Core-to-sheath insulation dielectric loss factor (PowerFactory ctand[0]).
        """
        return self._main_insulation_loss_tangent

    @main_insulation_loss_tangent.setter
    def main_insulation_loss_tangent(self, value: float) -> None:
        """Store the main_insulation_loss_tangent input.

        :param value: Core-to-sheath insulation dielectric loss factor (PowerFactory ctand[0]).
        :return: None.
        """
        self._main_insulation_loss_tangent = float(value)

    @property
    def outer_insulation_loss_tangent(self) -> float:
        """Read the outer_insulation_loss_tangent input.

        :return: Outer insulation dielectric loss factor (PowerFactory ctand[1]).
        """
        return self._outer_insulation_loss_tangent

    @outer_insulation_loss_tangent.setter
    def outer_insulation_loss_tangent(self, value: float) -> None:
        """Store the outer_insulation_loss_tangent input.

        :param value: Outer insulation dielectric loss factor (PowerFactory ctand[1]).
        :return: None.
        """
        self._outer_insulation_loss_tangent = float(value)

    @property
    def core_relative_permeability(self) -> float:
        """Read the core_relative_permeability input.

        :return: Core relative magnetic permeability (PowerFactory my[0]).
        """
        return self._core_relative_permeability

    @core_relative_permeability.setter
    def core_relative_permeability(self, value: float) -> None:
        """Store the core_relative_permeability input.

        :param value: Core relative magnetic permeability (PowerFactory my[0]).
        :return: None.
        """
        self._core_relative_permeability = float(value)

    @property
    def sheath_relative_permeability(self) -> float:
        """Read the sheath_relative_permeability input.

        :return: Sheath relative magnetic permeability (PowerFactory my[1]).
        """
        return self._sheath_relative_permeability

    @sheath_relative_permeability.setter
    def sheath_relative_permeability(self, value: float) -> None:
        """Store the sheath_relative_permeability input.

        :param value: Sheath relative magnetic permeability (PowerFactory my[1]).
        :return: None.
        """
        self._sheath_relative_permeability = float(value)

    @property
    def skin_effect_factor(self) -> float:
        """Read the skin_effect_factor input.

        :return: Core skin-effect factor.
        """
        return self._skin_effect_factor

    @skin_effect_factor.setter
    def skin_effect_factor(self, value: float) -> None:
        """Store the skin_effect_factor input.

        :param value: Core skin-effect factor.
        :return: None.
        """
        self._skin_effect_factor = float(value)

    @property
    def proximity_effect_factor(self) -> float:
        """Read the proximity_effect_factor input.

        :return: Imported core proximity-effect factor; informational, not used by this calculation.
        """
        return self._proximity_effect_factor

    @proximity_effect_factor.setter
    def proximity_effect_factor(self, value: float) -> None:
        """Store the proximity_effect_factor input.

        :param value: Imported core proximity-effect factor; informational, not used by this calculation.
        :return: None.
        """
        self._proximity_effect_factor = float(value)
