# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
from typing import Tuple
from VeraGridEngine.Devices.Parents.physical_device import PhysicalDevice, GCProp
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.fmu_template import FmuTemplate
from VeraGridEngine.enumerations import (DeviceType, BuildStatus, SubObjectType, FmuTemplateDomain, FmuTemplateMode,
                                         PrpCat)
from VeraGridEngine.Utils.Symbolic.symbolic_io import duplicate_block

from VeraGridEngine.Utils.Symbolic.templates_common_functions import connect_bus_variables_rms, \
    connect_bus_variables_emt


class DynamicDevice(PhysicalDevice):
    """
    Parent class for devices with dynamic models
    """
    __slots__ = (
        '_var_factory',
        '_rms_model',
        '_emt_model',
        '_rms_template',
        '_emt_template',
        '_rms_fmu_template',
        '_emt_fmu_template',
        '_rms_fmu_import_config',
        '_emt_fmu_import_config',
        '_rms_fmu_me_import_config',
        '_emt_fmu_me_import_config',
    )

    LOCAL_PROPERTY_DECLARATIONS: Tuple[GCProp, ...] = (
        GCProp(
            prop_name='rms_model',
            units='',
            tpe=SubObjectType.DaeBlockType,
            definition='RMS dynamic model',
            display=False,
            cat=[PrpCat.RMS],
        ),
        GCProp(
            prop_name='emt_model',
            units='',
            tpe=SubObjectType.DaeBlockType,
            definition='EMT dynamic model',
            display=False,
            cat=[PrpCat.EMT],
        ),
        GCProp(
            prop_name='rms_template',
            units='',
            tpe=DeviceType.RmsModelTemplateDevice,
            definition='Native RMS template used. Assigning it clears rms_fmu_template.',
            display=True,
            cat=[PrpCat.RMS],
        ),
        GCProp(
            prop_name='emt_template',
            units='',
            tpe=DeviceType.EmtModelTemplateDevice,
            definition='Native EMT template used. Assigning it clears emt_fmu_template.',
            display=True,
            cat=[PrpCat.EMT],
        ),
        GCProp(
            prop_name='rms_fmu_template',
            units='',
            tpe=DeviceType.FmuTemplateDevice,
            definition='RMS FMU template used only by RMS simulations. Assigning it clears rms_template.',
            display=True,
            cat=[PrpCat.RMS],
        ),
        GCProp(
            prop_name='emt_fmu_template',
            units='',
            tpe=DeviceType.FmuTemplateDevice,
            definition='EMT FMU template used only by EMT simulations. Assigning it clears emt_template.',
            display=True,
            cat=[PrpCat.EMT],
        ),
        GCProp(
            prop_name='rms_fmu_import_config',
            units='',
            tpe=str,
            definition='Serialized FMU Co-Simulation RMS configuration',
            display=False,
            cat=[PrpCat.RMS],
        ),
        GCProp(
            prop_name='emt_fmu_import_config',
            units='',
            tpe=str,
            definition='Serialized FMU Co-Simulation EMT configuration',
            display=False,
            cat=[PrpCat.EMT],
        ),
        GCProp(
            prop_name='rms_fmu_me_import_config',
            units='',
            tpe=str,
            definition='Serialized FMU Model Exchange RMS configuration',
            display=False,
            cat=[PrpCat.RMS],
        ),
        GCProp(
            prop_name='emt_fmu_me_import_config',
            units='',
            tpe=str,
            definition='Serialized FMU Model Exchange EMT configuration',
            display=False,
            cat=[PrpCat.EMT],
        ),
    )

    def __init__(self,
                 name: str,
                 idtag: str | None,
                 code: str,
                 device_type: DeviceType,
                 build_status: BuildStatus = BuildStatus.Commissioned):
        """
        Build one dynamic-capable device shell.

        :param name: Device display name.
        :param idtag: Persistent identifier or ``None``.
        :param code: Short device code.
        :param device_type: Concrete device type.
        :param build_status: Build lifecycle state.
        :return: None.
        """

        # The physical-device parent owns the common metadata required by every
        # network element, so it must be initialized before any dynamic state is
        # attached to this object.
        PhysicalDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=device_type,
                                build_status=build_status)

        # The variable factory is injected later because the editor/circuit owns
        # the shared symbol namespace and devices must reuse it consistently.
        self._var_factory: VarFactory | None = None

        # RMS state is always present as a block shell so callers can interact
        # with a concrete object even before a template is assigned.
        self._rms_model: Block = Block()
        self._rms_template: RmsModelTemplate | None = None
        self._rms_fmu_template: FmuTemplate | None = None
        self._rms_fmu_import_config: str = ""
        self._rms_fmu_me_import_config: str = ""

        # EMT state mirrors the RMS structure so both domains can be managed
        # independently while exposing the same lifecycle to callers.
        self._emt_model: Block = Block()
        self._emt_template: EmtModelTemplate | None = None
        self._emt_fmu_template: FmuTemplate | None = None
        self._emt_fmu_import_config: str = ""
        self._emt_fmu_me_import_config: str = ""

    def _clear_rms_fmu_config(self) -> None:
        """
        Clear all serialized RMS FMU runtime configurations.

        :return: None.
        """

        # Clearing both serialized forms prevents stale runtime settings from
        # surviving after the assigned FMU source changes.
        self._rms_fmu_import_config = ""
        self._rms_fmu_me_import_config = ""

    def _clear_emt_fmu_config(self) -> None:
        """
        Clear all serialized EMT FMU runtime configurations.

        :return: None.
        """

        # Clearing both serialized forms prevents stale runtime settings from
        # surviving after the assigned FMU source changes.
        self._emt_fmu_import_config = ""
        self._emt_fmu_me_import_config = ""

    def _apply_rms_fmu_template(self, template: FmuTemplate) -> None:
        """
        Copy the symbolic RMS shell and serialized FMU configuration from a reusable template.

        :param template: Reusable FMU template.
        :return: None.
        """

        # Native templates and FMU templates are mutually exclusive sources for
        # the runtime model, so assigning one must clear the other.
        self._rms_template = None
        self._clear_rms_fmu_config()
        if self.auto_update_enabled:
            # The template block is normalized before duplication so the device
            # receives a self-contained shell with consistent symbolic wiring.
            template.block.unify_blocks()
            self.rms_model = duplicate_block(template.block, self._var_factory)
        else:
            pass

        if template.mode == FmuTemplateMode.CO_SIMULATION:
            # The serialized configuration is routed to the field that matches
            # the FMU execution mode so downstream import code can stay explicit.
            self._rms_fmu_import_config = template.serialized_config
        else:
            if template.mode == FmuTemplateMode.MODEL_EXCHANGE:
                self._rms_fmu_me_import_config = template.serialized_config
            else:
                raise ValueError(f"Unsupported FMU template mode {template.mode}")

    def _apply_emt_fmu_template(self, template: FmuTemplate) -> None:
        """
        Copy the symbolic EMT shell and serialized FMU configuration from a reusable template.

        :param template: Reusable FMU template.
        :return: None.
        """

        # Native templates and FMU templates are mutually exclusive sources for
        # the runtime model, so assigning one must clear the other.
        self._emt_template = None
        self._clear_emt_fmu_config()
        if self.auto_update_enabled:
            # The template block is normalized before duplication so the device
            # receives a self-contained shell with consistent symbolic wiring.
            template.block.unify_blocks()
            self.emt_model = duplicate_block(template.block, self._var_factory)
        else:
            pass

        if template.mode == FmuTemplateMode.CO_SIMULATION:
            # The serialized configuration is routed to the field that matches
            # the FMU execution mode so downstream import code can stay explicit.
            self._emt_fmu_import_config = template.serialized_config
        else:
            if template.mode == FmuTemplateMode.MODEL_EXCHANGE:
                self._emt_fmu_me_import_config = template.serialized_config
            else:
                raise ValueError(f"Unsupported FMU template mode {template.mode}")

    def set_var_factory(self, val: VarFactory) -> None:
        """
        Store the shared variable factory used by RMS and EMT symbolic blocks.

        :param val: Shared variable factory.
        :return: None.
        """

        if isinstance(val, VarFactory):
            self._var_factory = val
        else:
            raise ValueError(f"VarFactory cannot accept {val}")

    @property
    def rms_model(self) -> Block:
        """
        Return the RMS symbolic model.

        :return: RMS symbolic block.
        """
        return self._rms_model

    @rms_model.setter
    def rms_model(self, val: Block) -> None:
        """
        Store the RMS symbolic model.

        :param val: RMS symbolic block.
        :return: None.
        """

        if isinstance(val, Block):
            self._rms_model = val
        else:
            raise ValueError(f"RMS model cannot accept {val}")

    @property
    def emt_model(self) -> Block:
        """
        Return the EMT symbolic model.

        :return: EMT symbolic block.
        """
        return self._emt_model

    @emt_model.setter
    def emt_model(self, val: Block) -> None:
        """
        Store the EMT symbolic model.

        :param val: EMT symbolic block.
        :return: None.
        """

        if isinstance(val, Block):
            self._emt_model = val
        else:
            raise ValueError(f"EMT model cannot accept {val}")

    @property
    def rms_template(self) -> RmsModelTemplate | None:
        """
        Return the assigned native RMS template.

        :return: RMS template or ``None``.
        """
        return self._rms_template

    @rms_template.setter
    def rms_template(self, val: RmsModelTemplate | None) -> None:
        if isinstance(val, RmsModelTemplate):
            # Native template assignment clears any FMU assignment because the
            # device must derive its RMS model from exactly one template source.
            self._rms_template = val
            self._rms_fmu_template = None
            self._clear_rms_fmu_config()

            if self.auto_update_enabled:
                # Duplicating the template avoids mutating shared library blocks,
                # and bus variables are rebound to this specific device instance.
                rms_mdl = duplicate_block(val.block, self._var_factory,
                                           preserve_external_network_connections=True)
                rms_mdl.name = val.name
                connect_bus_variables_rms(self, rms_mdl, self._var_factory)
                self.rms_model = rms_mdl

        elif val is None:
            # Clearing the native template removes the editor-facing assignment
            # and resets the runtime block to an empty shell.
            self._rms_template = None
            # self.rms_model = Block()
        else:
            raise ValueError(f"RMS template cannot accept {val}")

    @property
    def emt_template(self) -> EmtModelTemplate | None:
        """
        Return the assigned native EMT template.

        :return: EMT template or ``None``.
        """
        return self._emt_template

    @emt_template.setter
    def emt_template(self, val: EmtModelTemplate | None) -> None:
        if isinstance(val, EmtModelTemplate):
            # Native template assignment clears any FMU assignment because the
            # device must derive its EMT model from exactly one template source.
            self._emt_template = val
            self._emt_fmu_template = None
            self._clear_emt_fmu_config()

            if self.auto_update_enabled:
                # Duplicating the template avoids mutating shared library blocks,
                # and bus variables are rebound to this specific device instance.
                # The attachment normalizers read ``self.emt_model`` while they
                # rebuild the saved root contract, so publish the new block
                # before attaching it to the buses.
                emt_mdl: Block = duplicate_block(val.block, self._var_factory)
                emt_mdl.name = val.name
                self.emt_model = emt_mdl
                connect_bus_variables_emt(self,
                                          emt_mdl,
                                          self._var_factory,
                                          allow_deferred_connection=True)
        elif val is None:
            # Clearing the template makes any previously registered bus endpoint
            # stale because the device no longer guarantees that its current EMT
            # model remains valid for bus-driven rebinding.
            # unregister_connected_emt_model_from_attached_buses(device=self)
            self._emt_template = None
        else:
            raise ValueError(f"EMT template cannot accept {val}")

    @property
    def rms_fmu_template(self) -> FmuTemplate | None:
        """
        Get the reusable FMU template assigned to the RMS domain.

        :return: RMS FMU template when available.
        """

        return self._rms_fmu_template

    @rms_fmu_template.setter
    def rms_fmu_template(self, val: FmuTemplate | None) -> None:
        """
        Set the reusable FMU template assigned to the RMS domain.

        :param val: RMS FMU template or ``None``.
        :return: None.
        """

        if isinstance(val, FmuTemplate):
            if val.domain == FmuTemplateDomain.RMS:
                self._rms_fmu_template = val
                self._apply_rms_fmu_template(val)
            else:
                raise ValueError(f"RMS FMU template must declare the RMS domain, got {val.domain}")
        else:
            if val is None:
                self._rms_fmu_template = None
                self._clear_rms_fmu_config()
            else:
                raise ValueError(f"RMS FMU template cannot accept {val}")

    @property
    def emt_fmu_template(self) -> FmuTemplate | None:
        """
        Get the reusable FMU template assigned to the EMT domain.

        :return: EMT FMU template when available.
        """

        return self._emt_fmu_template

    @emt_fmu_template.setter
    def emt_fmu_template(self, val: FmuTemplate | None) -> None:
        """
        Set the reusable FMU template assigned to the EMT domain.

        :param val: EMT FMU template or ``None``.
        :return: None.
        """

        if isinstance(val, FmuTemplate):
            if val.domain == FmuTemplateDomain.EMT:
                self._emt_fmu_template = val
                self._apply_emt_fmu_template(val)
            else:
                raise ValueError(f"EMT FMU template must declare the EMT domain, got {val.domain}")
        else:
            if val is None:
                self._emt_fmu_template = None
                self._clear_emt_fmu_config()
            else:
                raise ValueError(f"EMT FMU template cannot accept {val}")

    @property
    def rms_fmu_import_config(self) -> str:
        """
        Get the serialized RMS FMU Co-Simulation configuration.

        :return: Serialized configuration text.
        """

        return self._rms_fmu_import_config

    @rms_fmu_import_config.setter
    def rms_fmu_import_config(self, val: str) -> None:
        """
        Store the serialized RMS FMU Co-Simulation configuration.

        :param val: Serialized configuration text.
        :return: None.
        """

        self._rms_fmu_import_config = str(val)

    @property
    def emt_fmu_import_config(self) -> str:
        """
        Get the serialized EMT FMU Co-Simulation configuration.

        :return: Serialized configuration text.
        """

        return self._emt_fmu_import_config

    @emt_fmu_import_config.setter
    def emt_fmu_import_config(self, val: str) -> None:
        """
        Store the serialized EMT FMU Co-Simulation configuration.

        :param val: Serialized configuration text.
        :return: None.
        """

        self._emt_fmu_import_config = str(val)

    @property
    def rms_fmu_me_import_config(self) -> str:
        """
        Get the serialized RMS FMU Model Exchange configuration.

        :return: Serialized configuration text.
        """

        return self._rms_fmu_me_import_config

    @rms_fmu_me_import_config.setter
    def rms_fmu_me_import_config(self, val: str) -> None:
        """
        Store the serialized RMS FMU Model Exchange configuration.

        :param val: Serialized configuration text.
        :return: None.
        """

        self._rms_fmu_me_import_config = str(val)

    @property
    def emt_fmu_me_import_config(self) -> str:
        """
        Get the serialized EMT FMU Model Exchange configuration.

        :return: Serialized configuration text.
        """

        return self._emt_fmu_me_import_config

    @emt_fmu_me_import_config.setter
    def emt_fmu_me_import_config(self, val: str) -> None:
        """
        Store the serialized EMT FMU Model Exchange configuration.

        :param val: Serialized configuration text.
        :return: None.
        """

        self._emt_fmu_me_import_config = str(val)
