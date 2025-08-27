# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Union, List

import numpy as np

import VeraGridEngine.Devices as gcdev
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Devices import MultiCircuit
from VeraGridEngine.Devices.Parents.branch_parent import BranchParent
from VeraGridEngine.IO.cim.cgmes.base import get_new_rdfid, form_rdfid
import VeraGridEngine.IO.cim.cgmes.cgmes_assets.cgmes_2_4_15_assets as cgmes24
import VeraGridEngine.IO.cim.cgmes.cgmes_assets.cgmes_3_0_0_assets as cgmes30
from VeraGridEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from VeraGridEngine.IO.cim.cgmes.cgmes_typing import CGMES_ASSETS, is_term
from VeraGridEngine.IO.cim.cgmes.cgmes_create_instances import (create_cgmes_dc_tp_node, create_cgmes_terminal,
                                                                create_cgmes_load_response_char,
                                                                create_cgmes_current_limit,
                                                                create_cgmes_location, create_cgmes_generating_unit,
                                                                create_cgmes_regulating_control,
                                                                create_cgmes_tap_changer_control,
                                                                create_sv_power_flow, create_cgmes_vsc_converter,
                                                                create_cgmes_dc_line_segment, create_cgmes_dc_line,
                                                                create_cgmes_dc_node,
                                                                create_cgmes_acdc_converter_terminal,
                                                                create_cgmes_conform_load_group,
                                                                create_cgmes_operational_limit_type,
                                                                create_cgmes_sub_load_area,
                                                                create_cgmes_non_conform_load_group,
                                                                create_cgmes_nonlinear_sc_point,
                                                                create_sv_shunt_compensator_sections)
from VeraGridEngine.IO.cim.cgmes.cgmes_enums import (RegulatingControlModeKind,
                                                     TransformerControlMode)
from VeraGridEngine.IO.cim.cgmes.cgmes_enums import (SynchronousMachineOperatingMode,
                                                     SynchronousMachineKind,
                                                     LimitTypeKind, OperationalLimitDirectionKind)
from VeraGridEngine.IO.cim.cgmes.cgmes_utils import (find_object_by_uuid,
                                                     find_object_by_vnom,
                                                     find_object_by_cond_eq_uuid,
                                                     get_ohm_values_power_transformer,
                                                     find_object_by_attribute)
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.common_functions import compute_zip_power
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.data_logger import DataLogger
from VeraGridEngine.enumerations import CGMESVersions
from VeraGridEngine.enumerations import (TapChangerTypes, TapPhaseControl, TapModuleControl)


def get_cgmes_geograpical_regions(multi_circuit_model: MultiCircuit,
                                  cgmes_model: CgmesCircuit,
                                  ver: CGMESVersions,
                                  logger: DataLogger):
    """

    :param multi_circuit_model:
    :param cgmes_model:
    :param ver:
    :param logger:
    :return:
    """
    for mc_class in [multi_circuit_model.countries, multi_circuit_model.areas]:
        for mc_elm in mc_class:

            if ver == CGMESVersions.v2_4_15:
                geo_region = cgmes24.GeographicalRegion(rdfid=form_rdfid(mc_elm.idtag))
            elif ver == CGMESVersions.v3_0_0:
                geo_region = cgmes30.GeographicalRegion(rdfid=form_rdfid(mc_elm.idtag))
            else:
                raise NotImplemented()

            geo_region.name = mc_elm.name
            geo_region.description = mc_elm.code
            cgmes_model.add(geo_region)

    if len(cgmes_model.cgmes_assets.GeographicalRegion_list) == 0:
        logger.add_error(
            msg='Country or Area is not defined and GeographicalRegion cannot be exported',
            device_class="GeographicalRegion",
            comment="The CGMES export will not be valid!")


def get_cgmes_sub_geographical_regions(multi_circuit_model: MultiCircuit,
                                       cgmes_model: CgmesCircuit,
                                       ver: CGMESVersions,
                                       logger: DataLogger):
    """

    :param multi_circuit_model:
    :param cgmes_model:
    :param ver:
    :param logger:
    :return:
    """

    for mc_class in [multi_circuit_model.communities,
                     multi_circuit_model.zones]:
        for mc_elm in mc_class:
            # object_template = cgmes_model.get_class_type("SubGeographicalRegion")
            # sub_geo_region = object_template(rdfid=form_rdfid(mc_elm.idtag))

            if ver == CGMESVersions.v2_4_15:
                sub_geo_region = cgmes24.SubGeographicalRegion(rdfid=form_rdfid(mc_elm.idtag))
            elif ver == CGMESVersions.v3_0_0:
                sub_geo_region = cgmes30.SubGeographicalRegion(rdfid=form_rdfid(mc_elm.idtag))
            else:
                raise NotImplemented()

            sub_geo_region.name = mc_elm.name
            sub_geo_region.description = mc_elm.code

            region_id = ""
            if hasattr(mc_elm, "country"):
                if mc_elm.country:
                    region_id = mc_elm.country.idtag
            elif hasattr(mc_elm, "area"):
                if mc_elm.area:
                    region_id = mc_elm.area.idtag

            region = find_object_by_uuid(
                cgmes_model=cgmes_model,
                object_list=cgmes_model.cgmes_assets.GeographicalRegion_list,
                target_uuid=region_id
            )
            if isinstance(region, cgmes_model.assets.GeographicalRegion):
                sub_geo_region.Region = region
            else:
                if len(cgmes_model.cgmes_assets.GeographicalRegion_list) > 0:
                    sub_geo_region.Region = cgmes_model.cgmes_assets.GeographicalRegion_list[0]
                else:
                    sub_geo_region.Region = None

                logger.add_warning(msg='GeographicalRegion not found for SubGeographicalRegion',
                                   device_class="SubGeographicalRegion")

            cgmes_model.add(sub_geo_region)

    if len(cgmes_model.cgmes_assets.SubGeographicalRegion_list) == 0:
        logger.add_error(
            msg='Community or Zone is not defined and SubGeographicalRegion cannot be exported',
            device_class="SubGeographicalRegion",
            comment="The CGMES export will not be valid!")


def get_base_voltage_from_boundary(cgmes_model: CgmesCircuit,
                                   vnom: float,
                                   ver: CGMESVersions, ):
    """

    :param cgmes_model:
    :param vnom:
    :param ver:
    :return:
    """
    bv_list = cgmes_model.elements_by_type_boundary.get("BaseVoltage")
    if bv_list is not None:
        for bv in bv_list:
            if bv.nominalVoltage == vnom:
                return bv
    return None


def get_cgmes_base_voltages(multi_circuit_model: MultiCircuit,
                            cgmes_model: CgmesCircuit,
                            ver: CGMESVersions,
                            logger: DataLogger) -> None:
    """

    :param multi_circuit_model:
    :param cgmes_model:
    :param ver:
    :param logger:
    :return:
    """
    base_volt_set = set()
    for bus in multi_circuit_model.buses:

        if bus.Vnom not in base_volt_set and get_base_voltage_from_boundary(cgmes_model, bus.Vnom, ver) is None:
            base_volt_set.add(bus.Vnom)

            new_rdf_id = get_new_rdfid()
            # object_template = cgmes_model.get_class_type("BaseVoltage")
            # base_volt = object_template(rdfid=new_rdf_id)

            if ver == CGMESVersions.v2_4_15:
                base_volt = cgmes24.BaseVoltage(rdfid=new_rdf_id)
            elif ver == CGMESVersions.v3_0_0:
                base_volt = cgmes30.BaseVoltage(rdfid=new_rdf_id)
            else:
                raise NotImplemented()

            base_volt.name = f'_BV_{int(bus.Vnom)}'
            base_volt.nominalVoltage = bus.Vnom

            cgmes_model.add(base_volt)
    return


def get_cgmes_substations(multi_circuit_model: MultiCircuit,
                          cgmes_model: CgmesCircuit,
                          ver: CGMESVersions,
                          logger: DataLogger) -> None:
    """

    :param multi_circuit_model:
    :param cgmes_model:
    :param ver:
    :param logger:
    :return:
    """
    for mc_elm in multi_circuit_model.substations:
        # object_template = cgmes_model.get_class_type("Substation")
        # substation = object_template(rdfid=form_rdfid(mc_elm.idtag))

        if ver == CGMESVersions.v2_4_15:
            substation = cgmes24.Substation(rdfid=form_rdfid(mc_elm.idtag))
        elif ver == CGMESVersions.v3_0_0:
            substation = cgmes30.Substation(rdfid=form_rdfid(mc_elm.idtag))
        else:
            raise NotImplemented()

        substation.name = mc_elm.name
        region = find_object_by_uuid(
            cgmes_model=cgmes_model,
            object_list=cgmes_model.cgmes_assets.SubGeographicalRegion_list,
            target_uuid=mc_elm.community.idtag if mc_elm.community is not None else ""
            # TODO Community.idtag!
        )

        if isinstance(region, cgmes_model.assets.GeographicalRegion):
            substation.Region = region
        else:
            if len(cgmes_model.cgmes_assets.SubGeographicalRegion_list) > 0:
                substation.Region = cgmes_model.cgmes_assets.SubGeographicalRegion_list[0]
            else:
                substation.Region = None
                logger.add_warning(msg='Region not found for Substation',
                                   device_class="SubGeographicalRegion")

        create_cgmes_location(cgmes_model=cgmes_model,
                              device=substation,
                              longitude=mc_elm.longitude,
                              latitude=mc_elm.latitude,
                              ver=ver,
                              logger=logger)

        cgmes_model.add(substation)


def get_cgmes_voltage_levels(multi_circuit_model: MultiCircuit,
                             cgmes_model: CgmesCircuit,
                             ver: CGMESVersions,
                             logger: DataLogger) -> None:
    """

    :param multi_circuit_model:
    :param cgmes_model:
    :param ver:
    :param logger:
    :return:
    """
    for mc_elm in multi_circuit_model.voltage_levels:

        # object_template = cgmes_model.get_class_type("VoltageLevel")
        # vl = object_template(rdfid=form_rdfid(mc_elm.idtag))

        if ver == CGMESVersions.v2_4_15:
            vl = cgmes24.VoltageLevel(rdfid=form_rdfid(mc_elm.idtag))
        elif ver == CGMESVersions.v3_0_0:
            vl = cgmes30.VoltageLevel(rdfid=form_rdfid(mc_elm.idtag))
        else:
            raise NotImplemented()

        vl.name = mc_elm.name
        vl.BaseVoltage = find_object_by_vnom(
            cgmes_model=cgmes_model,
            object_list=cgmes_model.cgmes_assets.BaseVoltage_list,
            target_vnom=mc_elm.Vnom
        )
        # vl.Bays = later
        # vl.TopologicalNode added at tn_nodes func

        if mc_elm.substation is not None:
            substation = find_object_by_uuid(
                cgmes_model=cgmes_model,
                object_list=cgmes_model.cgmes_assets.Substation_list,
                target_uuid=mc_elm.substation.idtag
            )

            if isinstance(substation, cgmes_model.assets.VoltageLevel):
                vl.Substation = substation

                # link back
                if substation.VoltageLevels is None:
                    substation.VoltageLevels = list()

                substation.VoltageLevels.append(vl)

            else:
                logger.add_error(
                    msg=f'Substation not found for VoltageLevel',
                    device=mc_elm.device_type.value,
                    device_class=gcdev.Bus,
                    comment=f"{vl.name}"
                )
        cgmes_model.add(vl)


def get_cgmes_tp_nodes(multi_circuit_model: MultiCircuit,
                       cgmes_model: CgmesCircuit,
                       ver: CGMESVersions,
                       logger: DataLogger) -> None:
    """
    Convert gcdev Buses to CGMES Topological Nodes

    :param multi_circuit_model:
    :param cgmes_model:
    :param ver:
    :param logger:
    :return:
    """
    for bus in multi_circuit_model.buses:

        if bus.is_dc:
            create_cgmes_dc_tp_node(tp_name=bus.name,
                                    tp_description=bus.code,
                                    cgmes_model=cgmes_model,
                                    ver=ver,
                                    logger=logger)

        else:
            if not bus.internal:

                tn = find_object_by_uuid(
                    cgmes_model=cgmes_model,
                    object_list=cgmes_model.cgmes_assets.TopologicalNode_list,
                    target_uuid=bus.idtag
                )
                if tn is not None:
                    # Skipping already added buses
                    continue

                # object_template = cgmes_model.get_class_type("TopologicalNode")
                # tn = object_template(rdfid=form_rdfid(bus.idtag))

                if ver == CGMESVersions.v2_4_15:
                    tn = cgmes24.TopologicalNode(rdfid=form_rdfid(bus.idtag))
                elif ver == CGMESVersions.v3_0_0:
                    tn = cgmes30.TopologicalNode(rdfid=form_rdfid(bus.idtag))
                else:
                    raise NotImplemented()

                tn.name = bus.name
                tn.shortName = bus.name
                tn.description = bus.code
                tn.BaseVoltage = find_object_by_vnom(
                    cgmes_model=cgmes_model,
                    object_list=cgmes_model.cgmes_assets.BaseVoltage_list,
                    target_vnom=bus.Vnom
                )

                if bus.voltage_level is not None and cgmes_model.cgmes_assets.VoltageLevel_list:  # VoltageLevel
                    vl = find_object_by_uuid(
                        cgmes_model=cgmes_model,
                        object_list=cgmes_model.cgmes_assets.VoltageLevel_list,
                        target_uuid=bus.voltage_level.idtag
                    )

                    if isinstance(vl, cgmes_model.assets.VoltageLevel):
                        tn.ConnectivityNodeContainer = vl
                        vl.TopologicalNode = tn  # link back

                else:
                    logger.add_error(
                        msg=f'No Voltage Level found',
                        device=bus.idtag,
                        device_class=bus.device_type.value,
                        device_property="Bus.voltage_level.idtag",
                        value=bus.voltage_level,
                        comment="get_cgmes_tn_nodes()")

                    create_cgmes_location(cgmes_model=cgmes_model,
                                          device=tn,
                                          longitude=bus.longitude,
                                          latitude=bus.latitude,
                                          ver=ver,
                                          logger=logger)

                cgmes_model.add(tn)

    return


def get_cgmes_cn_nodes_from_tp_nodes(multi_circuit_model: MultiCircuit,
                                     cgmes_model: CgmesCircuit,
                                     ver: CGMESVersions,
                                     logger: DataLogger) -> None:
    """
    Export one ConnectivityNode for every TopologicalNode

    :param multi_circuit_model:
    :param cgmes_model:
    :param ver:
    :param logger:
    :return:
    """
    for tn in cgmes_model.cgmes_assets.TopologicalNode_list:
        new_rdf_id = get_new_rdfid()

        # object_template = cgmes_model.get_class_type("ConnectivityNode")
        # cn = object_template(rdfid=new_rdf_id)

        if ver == CGMESVersions.v2_4_15:
            cn = cgmes24.ConnectivityNode(rdfid=new_rdf_id)
        elif ver == CGMESVersions.v3_0_0:
            cn = cgmes30.ConnectivityNode(rdfid=new_rdf_id)
        else:
            raise NotImplemented()

        cn.name = tn.name
        cn.shortName = tn.shortName
        cn.description = tn.description
        cn.BaseVoltage = tn.BaseVoltage

        tn.ConnectivityNodes = cn
        cn.TopologicalNode = tn

        if tn.ConnectivityNodeContainer:
            tn.ConnectivityNodeContainer.ConnectivityNodes = cn
            cn.ConnectivityNodeContainer = tn.ConnectivityNodeContainer
        else:
            logger.add_error(
                msg=f'TN has no ConnectivityNodeContainer, so cannot be assigned to CN',
                device=tn.rdfid,
                device_class=tn.tpe,
                device_property="Bus.voltage_level.idtag",
                value="None",
                comment="get_cgmes_cn_nodes_from_tp_nodes()"
            )

        cgmes_model.add(cn)


def get_cgmes_loads(multicircuit_model: MultiCircuit,
                    cgmes_model: CgmesCircuit,
                    ver: CGMESVersions,
                    logger: DataLogger):
    """
    Converts every Multi Circuit load into CGMES ConformLoad.

    :param multicircuit_model: MultiCircuit model in VeraGrid
    :param cgmes_model:
    :param ver:
    :param logger:
    :return:
    """

    create_cgmes_sub_load_area(cgmes_model, ver, logger)
    c_load_group = create_cgmes_conform_load_group(cgmes_model, ver, logger)
    nc_load_group = create_cgmes_non_conform_load_group(cgmes_model, ver, logger)

    for mc_elm in multicircuit_model.loads:

        if mc_elm.scalable:
            # object_template = cgmes_model.get_class_type("ConformLoad")
            # load = object_template(rdfid=form_rdfid(mc_elm.idtag))

            if ver == CGMESVersions.v2_4_15:
                load = cgmes24.ConformLoad(rdfid=form_rdfid(mc_elm.idtag))
            elif ver == CGMESVersions.v3_0_0:
                load = cgmes30.ConformLoad(rdfid=form_rdfid(mc_elm.idtag))
            else:
                raise NotImplemented()


        else:
            # object_template = cgmes_model.get_class_type("NonConformLoad")
            # load = object_template(rdfid=form_rdfid(mc_elm.idtag))

            if ver == CGMESVersions.v2_4_15:
                load = cgmes24.NonConformLoad(rdfid=form_rdfid(mc_elm.idtag))
            elif ver == CGMESVersions.v3_0_0:
                load = cgmes30.NonConformLoad(rdfid=form_rdfid(mc_elm.idtag))
            else:
                raise NotImplemented()

        load.Terminals = create_cgmes_terminal(mc_elm.bus, None, load, cgmes_model, ver, logger)
        load.name = mc_elm.name

        if mc_elm.bus.voltage_level:

            vl = find_object_by_uuid(
                cgmes_model=cgmes_model,
                object_list=cgmes_model.cgmes_assets.VoltageLevel_list,
                target_uuid=mc_elm.bus.voltage_level.idtag
            )
            if isinstance(vl, cgmes_model.assets.VoltageLevel):
                load.EquipmentContainer = vl

        load.BaseVoltage = find_object_by_vnom(cgmes_model=cgmes_model,
                                               object_list=cgmes_model.cgmes_assets.BaseVoltage_list,
                                               target_vnom=mc_elm.bus.Vnom)

        if mc_elm.Ii != 0.0:
            load.LoadResponse = create_cgmes_load_response_char(load=mc_elm,
                                                                cgmes_model=cgmes_model,
                                                                ver=ver)
            load.p = mc_elm.P / load.LoadResponse.pConstantPower
            load.q = mc_elm.Q / load.LoadResponse.qConstantPower
        else:
            load.p = mc_elm.P
            load.q = mc_elm.Q

        load.description = mc_elm.code

        if mc_elm.scalable:
            load.LoadGroup = c_load_group
            c_load_group.EnergyConsumers.append(load)
        else:
            load.LoadGroup = nc_load_group
            nc_load_group.EnergyConsumers.append(load)

        cgmes_model.add(load)


def get_cgmes_equivalent_injections(multicircuit_model: MultiCircuit,
                                    cgmes_model: CgmesCircuit,
                                    ver: CGMESVersions,
                                    logger: DataLogger):
    """
    Converts every Multi Circuit external grid
    into CGMES equivalent injection.

    :param multicircuit_model: MultiCircuit model in VeraGrid
    :param cgmes_model:
    :param ver:
    :param logger:
    :return:
    """

    for mc_elm in multicircuit_model.external_grids:

        # object_template = cgmes_model.get_class_type("EquivalentInjection")
        # ei = object_template(rdfid=form_rdfid(mc_elm.idtag))

        if ver == CGMESVersions.v2_4_15:
            ei = cgmes24.EquivalentInjection(rdfid=form_rdfid(mc_elm.idtag))
        elif ver == CGMESVersions.v3_0_0:
            ei = cgmes30.EquivalentInjection(rdfid=form_rdfid(mc_elm.idtag))
        else:
            raise NotImplemented()

        ei.description = mc_elm.code
        ei.name = mc_elm.name
        ei.p = mc_elm.P
        ei.q = mc_elm.Q
        ei.BaseVoltage = find_object_by_vnom(cgmes_model=cgmes_model,
                                             object_list=cgmes_model.cgmes_assets.BaseVoltage_list,
                                             target_vnom=mc_elm.bus.Vnom)

        ei.Terminals = create_cgmes_terminal(mc_elm.bus, None, ei, cgmes_model, ver, logger)
        ei.regulationCapability = False

        cgmes_model.add(ei)


def get_cgmes_ac_line_segments(multicircuit_model: MultiCircuit,
                               cgmes_model: CgmesCircuit,
                               op_lim_types: List,
                               ver: CGMESVersions,
                               logger: DataLogger):
    """
    Converts every Multi Circuit line
    into CGMES AC line segment.

    :param multicircuit_model: MultiCircuit model in VeraGrid
    :param cgmes_model: CgmesModel
    :param op_lim_types: Operational Limit types like PATL and TATL900, TATL60
    :param ver:
    :param logger: DataLogger
    :return:
    """
    sbase = multicircuit_model.Sbase
    for mc_elm in multicircuit_model.lines:

        # object_template = cgmes_model.get_class_type("ACLineSegment")
        # line = object_template(rdfid=form_rdfid(mc_elm.idtag))

        if ver == CGMESVersions.v2_4_15:
            line = cgmes24.ACLineSegment(rdfid=form_rdfid(mc_elm.idtag))
        elif ver == CGMESVersions.v3_0_0:
            line = cgmes30.ACLineSegment(rdfid=form_rdfid(mc_elm.idtag))
        else:
            raise NotImplemented()

        line.description = mc_elm.code
        line.name = mc_elm.name
        line.BaseVoltage = find_object_by_vnom(
            cgmes_model=cgmes_model,
            object_list=cgmes_model.cgmes_assets.BaseVoltage_list,
            target_vnom=mc_elm.get_max_bus_nominal_voltage()
        )  # which Vnom we need?

        # Terminals
        line.Terminals = [
            create_cgmes_terminal(mc_bus=mc_elm.bus_from,
                                  seq_num=1,
                                  cond_eq=line,
                                  cgmes_model=cgmes_model,
                                  ver=ver,
                                  logger=logger),
            create_cgmes_terminal(mc_bus=mc_elm.bus_to,
                                  seq_num=2,
                                  cond_eq=line,
                                  cgmes_model=cgmes_model,
                                  ver=ver,
                                  logger=logger)
        ]
        line.length = mc_elm.length

        # RATES
        get_cgmes_current_limits(cgmes_model=cgmes_model,
                                 cgmes_elm=line,
                                 mc_elm=mc_elm,
                                 op_lim_types=op_lim_types,
                                 ver=ver,
                                 logger=logger)

        vnom = line.BaseVoltage.nominalVoltage

        if vnom is not None:
            # Calculate Zbase
            zbase = (vnom * vnom) / sbase
            ybase = 1.0 / zbase

            line.r = mc_elm.R * zbase
            line.x = mc_elm.X * zbase
            # line.gch = mc_elm.G * Ybase
            line.bch = mc_elm.B * ybase
            line.r0 = mc_elm.R0 * zbase
            line.x0 = mc_elm.X0 * zbase
            # line.g0ch = mc_elm.G0 * Ybase
            line.b0ch = mc_elm.B0 * ybase

        cgmes_model.add(line)


def get_cgmes_generators(multicircuit_model: MultiCircuit,
                         cgmes_model: CgmesCircuit,
                         ver: CGMESVersions,
                         logger: DataLogger):
    """
    Converts Multi Circuit generators
    into appropriate CGMES Generating Unit.

    :param multicircuit_model: MultiCircuit model in VeraGrid
    :param cgmes_model:
    :param ver:
    :param logger:
    :return:
    """

    for mc_elm in multicircuit_model.generators:
        # Generating Units ---------------------------------------------------
        cgmes_gen = create_cgmes_generating_unit(gen=mc_elm, cgmes_model=cgmes_model, ver=ver)
        cgmes_gen.name = mc_elm.name
        cgmes_gen.description = mc_elm.code

        # cgmes_gen.EquipmentContainer: cgmes.Substation
        if cgmes_model.cgmes_assets.Substation_list and mc_elm.bus.substation:
            subs = find_object_by_uuid(
                cgmes_model=cgmes_model,
                object_list=cgmes_model.cgmes_assets.Substation_list,
                target_uuid=mc_elm.bus.substation.idtag
            )

            if isinstance(subs, cgmes_model.assets.Substation):

                cgmes_gen.EquipmentContainer = subs
                # link back
                if isinstance(subs.Equipments, list):
                    subs.Equipment.append(cgmes_gen)
                else:
                    subs.Equipment = [cgmes_gen]
            else:
                logger.add_error(
                    msg=f'No substation found for generator',
                    device=mc_elm.idtag,
                    device_class=mc_elm.device_type.value,
                    device_property="Substation",
                    value=subs,
                    comment=f"get_cgmes_generators() - {mc_elm.name}")
        else:
            logger.add_error(
                msg=f'No substations in the model',
                device_property="Substation list",
                comment=f"get_cgmes_generators()")

        cgmes_gen.initialP = mc_elm.P
        cgmes_gen.maxOperatingP = mc_elm.Pmax
        cgmes_gen.minOperatingP = mc_elm.Pmin

        # Synchronous Machine ------------------------------------------------
        # object_template = cgmes_model.get_class_type("SynchronousMachine")
        # cgmes_syn = object_template(rdfid=form_rdfid(mc_elm.idtag))

        if ver == CGMESVersions.v2_4_15:
            cgmes_syn = cgmes24.SynchronousMachine(rdfid=form_rdfid(mc_elm.idtag))
        elif ver == CGMESVersions.v3_0_0:
            cgmes_syn = cgmes30.SynchronousMachine(rdfid=form_rdfid(mc_elm.idtag))
        else:
            raise NotImplemented()

        cgmes_syn.description = mc_elm.code
        cgmes_syn.name = mc_elm.name
        # cgmes_syn.aggregate is optional, not exported
        if mc_elm.bus.is_slack:
            cgmes_syn.referencePriority = 1
            cgmes_gen.normalPF = 1  # in veragrid the participation factor is the cost
        else:
            cgmes_syn.referencePriority = 0
            cgmes_gen.normalPF = 0

        # TODO cgmes_syn.EquipmentContainer: VoltageLevel

        cgmes_syn.Terminals = create_cgmes_terminal(mc_bus=mc_elm.bus,
                                                    seq_num=1,
                                                    cond_eq=cgmes_syn,
                                                    cgmes_model=cgmes_model,
                                                    ver=ver,
                                                    logger=logger)

        # CONTROL : has_control: do we have control?
        # control_type: voltage or power control, ..
        # is_controlled: enabling flag (already have)
        if mc_elm.is_controlled:
            cgmes_syn.RegulatingControl = (
                create_cgmes_regulating_control(cgmes_syn, mc_elm, cgmes_model, ver, logger))
            cgmes_syn.controlEnabled = True
        else:
            cgmes_syn.controlEnabled = False

        # Todo cgmes_syn.ratedPowerFactor = 1.0
        cgmes_syn.ratedS = mc_elm.Snom
        cgmes_syn.GeneratingUnit = cgmes_gen  # linking them together
        cgmes_gen.RotatingMachine = cgmes_syn  # linking them together
        cgmes_syn.maxQ = mc_elm.Qmax
        cgmes_syn.minQ = mc_elm.Qmin
        cgmes_syn.r = mc_elm.R1 if mc_elm.R1 != 1e-20 else None  # default value not exported
        cgmes_syn.p = -mc_elm.P  # negative sign!
        cgmes_syn.q = -mc_elm.P * np.tan(np.arccos(mc_elm.Pf))
        # TODO cgmes_syn.qPercent =
        if mc_elm.q_curve is not None:
            pMin = mc_elm.q_curve.get_Pmin()
        else:
            pMin = mc_elm.Pmin
        if cgmes_syn.p < 0:
            cgmes_syn.operatingMode = SynchronousMachineOperatingMode.generator
            if pMin < 0:
                cgmes_syn.type = SynchronousMachineKind.generatorOrMotor
            elif pMin == 0:
                cgmes_syn.type = SynchronousMachineKind.generatorOrCondenser
            else:
                cgmes_syn.type = SynchronousMachineKind.generator
        elif cgmes_syn.p == 0:
            cgmes_syn.operatingMode = SynchronousMachineOperatingMode.condenser
            if pMin < 0:  # TODO We don't have all the types
                cgmes_syn.type = SynchronousMachineKind.motorOrCondenser
            elif pMin == 0:
                cgmes_syn.type = SynchronousMachineKind.generatorOrCondenser
            else:
                cgmes_syn.type = SynchronousMachineKind.generatorOrCondenser
        else:
            cgmes_syn.operatingMode = SynchronousMachineOperatingMode.motor
            if pMin < 0:
                cgmes_syn.type = SynchronousMachineKind.generatorOrMotor
            elif pMin == 0:
                cgmes_syn.type = SynchronousMachineKind.motorOrCondenser
            else:
                cgmes_syn.type = SynchronousMachineKind.generatorOrMotor

        # generatorOrCondenser = 'generatorOrCondenser'
        # generator = 'generator'
        # generatorOrMotor = 'generatorOrMotor'
        # motor = 'motor'
        # motorOrCondenser = 'motorOrCondenser'
        # generatorOrCondenserOrMotor = 'generatorOrCondenserOrMotor'
        # condenser = 'condenser'

        if mc_elm.bus.voltage_level:
            vl = find_object_by_uuid(
                cgmes_model=cgmes_model,
                object_list=cgmes_model.cgmes_assets.VoltageLevel_list,
                target_uuid=mc_elm.bus.voltage_level.idtag
            )
            cgmes_syn.EquipmentContainer = vl

        cgmes_syn.BaseVoltage = find_object_by_vnom(cgmes_model=cgmes_model,
                                                    object_list=cgmes_model.cgmes_assets.BaseVoltage_list,
                                                    target_vnom=mc_elm.bus.Vnom)
        cgmes_model.add(cgmes_syn)


def get_cgmes_power_transformers(grid: MultiCircuit,
                                 cgmes_model: CgmesCircuit,
                                 op_lim_types: List,
                                 ver: CGMESVersions,
                                 logger: DataLogger):
    """
    Creates all transformer related CGMES classes from VeraGrid transformer.

    :param grid: MultiCircuit model in VeraGrid
    :param cgmes_model: CgmesModel
    :param op_lim_types:
    :param ver:
    :param logger: DataLogger
    :return:
    """
    for mc_elm in grid.transformers2w:

        # object_template = cgmes_model.get_class_type("PowerTransformer")
        # cm_transformer = object_template(rdfid=form_rdfid(mc_elm.idtag))

        if ver == CGMESVersions.v2_4_15:
            cm_transformer = cgmes24.PowerTransformer(rdfid=form_rdfid(mc_elm.idtag))
        elif ver == CGMESVersions.v3_0_0:
            cm_transformer = cgmes30.PowerTransformer(rdfid=form_rdfid(mc_elm.idtag))
        else:
            raise NotImplemented()

        cm_transformer.uuid = mc_elm.idtag
        cm_transformer.description = mc_elm.code
        cm_transformer.name = mc_elm.name
        cm_transformer.Terminals = [
            create_cgmes_terminal(mc_elm.bus_from, 1, cm_transformer, cgmes_model, ver, logger),
            create_cgmes_terminal(mc_elm.bus_to, 2, cm_transformer, cgmes_model, ver, logger)
        ]
        cm_transformer.aggregate = False  # what is this?
        if mc_elm.bus_from.substation:
            substation = find_object_by_uuid(
                cgmes_model=cgmes_model,
                object_list=cgmes_model.cgmes_assets.Substation_list,
                target_uuid=mc_elm.bus_from.substation.idtag
            )

            if isinstance(substation, cgmes_model.assets.Substation):
                cm_transformer.EquipmentContainer = substation

        cm_transformer.PowerTransformerEnd = list()
        # Winding 1 ---------------------------------------------------------

        if ver == CGMESVersions.v2_4_15:
            pte1 = cgmes24.PowerTransformerEnd()
            pte2 = cgmes24.PowerTransformerEnd()

        elif ver == CGMESVersions.v3_0_0:
            pte1 = cgmes30.PowerTransformerEnd()
            pte2 = cgmes24.PowerTransformerEnd()

        else:
            raise NotImplemented()

        pte1.name = f"Winding 1 - {mc_elm.name}"
        pte1.PowerTransformer = cm_transformer
        pte1.Terminal = cm_transformer.Terminals[0]
        pte1.BaseVoltage = find_object_by_vnom(
            cgmes_model=cgmes_model,
            object_list=cgmes_model.cgmes_assets.BaseVoltage_list,
            target_vnom=mc_elm.bus_from.Vnom
        )

        # RATES
        get_cgmes_current_limits(cgmes_model=cgmes_model,
                                 cgmes_elm=cm_transformer,
                                 mc_elm=mc_elm,
                                 op_lim_types=op_lim_types,
                                 ver=ver,
                                 logger=logger)

        (pte1.r,
         pte1.x,
         pte1.g,
         pte1.b,
         pte1.r0,
         pte1.x0,
         pte1.g0,
         pte1.b0) = get_ohm_values_power_transformer(r=mc_elm.R,
                                                     x=mc_elm.X,
                                                     g=mc_elm.G,
                                                     b=mc_elm.B,
                                                     r0=mc_elm.R0,
                                                     x0=mc_elm.X0,
                                                     g0=mc_elm.G0,
                                                     b0=mc_elm.B0,
                                                     nominal_power=mc_elm.Sn,
                                                     rated_voltage=mc_elm.HV,
                                                     Sbase=grid.Sbase)

        pte1.ratedU = mc_elm.HV
        pte1.ratedS = mc_elm.Sn
        pte1.endNumber = 1

        # Winding 2 ---------------------------------------------------------
        pte2.name = f"Winding 2 - {mc_elm.name}"
        pte2.PowerTransformer = cm_transformer
        pte2.Terminal = cm_transformer.Terminals[1]
        pte2.BaseVoltage = find_object_by_vnom(
            cgmes_model=cgmes_model,
            object_list=cgmes_model.cgmes_assets.BaseVoltage_list,
            target_vnom=mc_elm.bus_to.Vnom
        )

        # TODO: Shouldn't this be half?
        pte2.r = 0.0
        pte2.x = 0.0
        pte2.g = 0.0
        pte2.b = 0.0
        pte2.r0 = 0.0
        pte2.x0 = 0.0
        pte2.g0 = 0.0
        pte2.b0 = 0.0
        pte2.ratedU = mc_elm.LV
        pte2.ratedS = mc_elm.Sn
        pte2.endNumber = 2

        # -------------------- RATIO TAP  & PHASE TAP -----------------------
        # RatioTapChanger (tcc: voltage, disabled)	<--	-->	NoRegulation
        # RatioTapChanger (tcc: voltage, enabled)	<--	-->	Voltage
        # PhaseTapChangerSymmetrical	<--	-->	Symmetrical
        # PhaseTapChangerAsymmetrical	<--	-->	Asymmetrical
        #                         TAP Changer EQ

        tcc_mode = RegulatingControlModeKind.voltage
        tcc_enabled = False

        if mc_elm.tap_changer.tc_type == TapChangerTypes.NoRegulation:
            if ver == CGMESVersions.v2_4_15:
                tap_changer = cgmes24.RatioTapChanger(rdfid=get_new_rdfid())
            elif ver == CGMESVersions.v3_0_0:
                tap_changer = cgmes30.RatioTapChanger(rdfid=get_new_rdfid())
            else:
                raise NotImplemented()

        elif mc_elm.tap_changer.tc_type == TapChangerTypes.VoltageRegulation:
            if ver == CGMESVersions.v2_4_15:
                tap_changer = cgmes24.RatioTapChanger(rdfid=get_new_rdfid())
            elif ver == CGMESVersions.v3_0_0:
                tap_changer = cgmes30.RatioTapChanger(rdfid=get_new_rdfid())
            else:
                raise NotImplemented()

            if mc_elm.tap_module_control_mode != TapModuleControl.fixed:
                # if fixed, it should be disabled
                tcc_enabled = True

        elif mc_elm.tap_changer.tc_type == TapChangerTypes.Symmetrical:
            if ver == CGMESVersions.v2_4_15:
                tap_changer = cgmes24.PhaseTapChangerSymmetrical(rdfid=get_new_rdfid())
            elif ver == CGMESVersions.v3_0_0:
                tap_changer = cgmes30.PhaseTapChangerSymmetrical(rdfid=get_new_rdfid())
            else:
                raise NotImplemented()

            if mc_elm.tap_phase_control_mode != TapPhaseControl.fixed:
                # if fixed, it should be disabled
                tcc_enabled = True
            tcc_mode = RegulatingControlModeKind.activePower

        elif mc_elm.tap_changer.tc_type == TapChangerTypes.Asymmetrical:
            if ver == CGMESVersions.v2_4_15:
                tap_changer = cgmes24.PhaseTapChangerAsymmetrical(rdfid=get_new_rdfid())
            elif ver == CGMESVersions.v3_0_0:
                tap_changer = cgmes30.PhaseTapChangerAsymmetrical(rdfid=get_new_rdfid())
            else:
                raise NotImplemented()

            if (mc_elm.tap_module_control_mode != TapModuleControl.fixed or
                    mc_elm.tap_phase_control_mode != TapPhaseControl.fixed):
                # if fixed, it should be disabled
                tcc_enabled = True
            tcc_mode = RegulatingControlModeKind.activePower

        else:
            tap_changer = None
            logger.add_error(msg='No TapChangerType found for TapChanger',
                             device=mc_elm.tap_changer,
                             device_class=mc_elm.device_type.value,
                             value=mc_elm.tap_changer)

        if tap_changer is not None:
            tap_changer.name = f'_tc_{mc_elm.name}'
            tap_changer.shortName = f'_tc_{mc_elm.name}'
            tap_changer.neutralU = pte1.ratedU
            tap_changer.TransformerEnd = pte1

            # STEPs
            tap_changer.total_pos = mc_elm.tap_changer.total_positions

            (tap_changer.lowStep,
             tap_changer.highStep,
             tap_changer.normalStep,
             tap_changer.neutralStep,
             voltageIncr,
             tap_changer.step) = mc_elm.tap_changer.get_cgmes_values()

            if isinstance(tap_changer, (cgmes24.RatioTapChanger, cgmes30.RatioTapChanger)):

                tap_changer.stepVoltageIncrement = voltageIncr

            elif isinstance(tap_changer, (cgmes24.PhaseTapChangerNonLinear, cgmes30.PhaseTapChangerNonLinear)):

                # PhaseTapChangerSymmetrical or PhaseTapChangerAsymmetrical
                tap_changer.voltageStepIncrement = voltageIncr
                tap_changer.xMin = mc_elm.X
                # TODO tap_changer.xMax from Impedance corr table
                tap_changer.xMax = mc_elm.X  # just to have it in the export

            else:
                logger.add_error(
                    msg='stepVoltageIncrement cannot be filled for TapChanger',
                    device=mc_elm,
                    device_class=mc_elm.device_type.value,
                    value=mc_elm.idtag,
                    comment="get_cgmes_power_transformers")

            if isinstance(tap_changer, (cgmes24.PhaseTapChangerAsymmetrical, cgmes30.PhaseTapChangerAsymmetrical)):
                tap_changer.windingConnectionAngle = mc_elm.tap_changer.asymmetry_angle

            # CONTROL
            tap_changer.ltcFlag = True  # load tap changing capability
            tap_changer.TapChangerControl = create_cgmes_tap_changer_control(
                tap_changer=tap_changer,
                tcc_mode=tcc_mode,
                tcc_enabled=tcc_enabled,
                mc_trafo=mc_elm,
                cgmes_model=cgmes_model,
                ver=ver,
                logger=logger
            )
            # tculControlMode not used, but has to be set to something: volt/react ..
            tap_changer.tculControlMode = TransformerControlMode.volt
            #                   TAP Changer SSH
            tap_changer.controlEnabled = tcc_enabled
            # Specifies the regulation status of the equipment.  True is regulating, false is not regulating.
            # why, why not?

            #                   TAP Changer SV

            # object_template = cgmes_model.get_class_type("SvTapStep")
            # sv_tap_step = object_template(rdfid=new_rdf_id, tpe="SvTapStep")
            if ver == CGMESVersions.v2_4_15:
                sv_tap_step = cgmes24.SvTapStep(rdfid=get_new_rdfid(), tpe="SvTapStep")
            elif ver == CGMESVersions.v3_0_0:
                sv_tap_step = cgmes30.SvTapStep(rdfid=get_new_rdfid(), tpe="SvTapStep")
            else:
                raise NotImplemented()

            # TODO def EA same as step? should it come from the results?
            # PowerFlowResults: tap_module, tap_angle (for SvTapStep), get the closest tap pos for the object.
            sv_tap_step.position = mc_elm.tap_changer.tap_position
            sv_tap_step.TapChanger = tap_changer

            # -----------------------------------------------------------------
            cgmes_model.add(tap_changer)
            cgmes_model.add(sv_tap_step)
        else:
            # No tap changer
            pass

        cm_transformer.PowerTransformerEnd.append(pte1)
        cgmes_model.add(pte1)
        cm_transformer.PowerTransformerEnd.append(pte2)
        cgmes_model.add(pte2)
        cgmes_model.add(cm_transformer)

    # ------------------------------------------------------------------------------------------------------------------
    # Create the 3W transformers
    # ------------------------------------------------------------------------------------------------------------------

    for mc_elm in grid.transformers3w:

        # object_template = cgmes_model.get_class_type("PowerTransformer")
        # cm_transformer = object_template(rdfid=form_rdfid(mc_elm.idtag))
        if ver == CGMESVersions.v2_4_15:
            cm_transformer = cgmes24.PowerTransformer(rdfid=form_rdfid(mc_elm.idtag))
        elif ver == CGMESVersions.v3_0_0:
            cm_transformer = cgmes30.PowerTransformer(rdfid=form_rdfid(mc_elm.idtag))
        else:
            raise NotImplemented()

        cm_transformer.uuid = mc_elm.idtag
        cm_transformer.description = mc_elm.code
        cm_transformer.name = mc_elm.name
        cm_transformer.Terminals = [
            create_cgmes_terminal(mc_elm.bus1, 1, cm_transformer, cgmes_model, ver, logger),
            create_cgmes_terminal(mc_elm.bus2, 2, cm_transformer, cgmes_model, ver, logger),
            create_cgmes_terminal(mc_elm.bus3, 3, cm_transformer, cgmes_model, ver, logger)
        ]

        if mc_elm.bus1.substation:
            substation = find_object_by_uuid(
                cgmes_model=cgmes_model,
                object_list=cgmes_model.cgmes_assets.Substation_list,
                target_uuid=mc_elm.bus1.substation.idtag
            )

            if isinstance(substation, cgmes_model.assets.Substation):
                cm_transformer.EquipmentContainer = substation

        # TODO tr3w rates?
        # current_rate = mc_elm.rate * 1e3 / (mc_elm.get_max_bus_nominal_voltage() * 1.73205080756888)
        # current_rate = np.round(current_rate, 4)
        # create_cgmes_current_limit(cm_transformer.Terminals[0], current_rate, cgmes_model, logger)
        # create_cgmes_current_limit(cm_transformer.Terminals[1], current_rate, cgmes_model, logger)

        cm_transformer.PowerTransformerEnd = []
        if ver == CGMESVersions.v2_4_15:
            pte1 = cgmes24.PowerTransformerEnd()
            pte2 = cgmes24.PowerTransformerEnd()
            pte3 = cgmes24.PowerTransformerEnd()
        elif ver == CGMESVersions.v3_0_0:
            pte1 = cgmes30.PowerTransformerEnd()
            pte2 = cgmes30.PowerTransformerEnd()
            pte3 = cgmes30.PowerTransformerEnd()
        else:
            raise NotImplemented()

        # Winding 1 ---------------------------------------------------------
        pte1.name = mc_elm.name
        pte1.PowerTransformer = cm_transformer
        pte1.Terminal = cm_transformer.Terminals[0]
        pte1.BaseVoltage = find_object_by_vnom(
            cgmes_model=cgmes_model,
            object_list=cgmes_model.cgmes_assets.BaseVoltage_list,
            target_vnom=mc_elm.bus1.Vnom
        )
        pte1.ratedU = mc_elm.V1
        pte1.ratedS = mc_elm.rate1
        pte1.endNumber = 1

        (pte1.r,
         pte1.x,
         pte1.g,
         pte1.b,
         pte1.r0,
         pte1.x0,
         pte1.g0,
         pte1.b0) = get_ohm_values_power_transformer(r=mc_elm.winding1.R,
                                                     x=mc_elm.winding1.X,
                                                     g=mc_elm.winding1.G,
                                                     b=mc_elm.winding1.B,
                                                     r0=mc_elm.winding1.R0,
                                                     x0=mc_elm.winding1.X0,
                                                     g0=mc_elm.winding1.G0,
                                                     b0=mc_elm.winding1.B0,
                                                     nominal_power=mc_elm.winding1.rate,
                                                     rated_voltage=mc_elm.winding1.HV,
                                                     Sbase=grid.Sbase)

        # Winding 2 ---------------------------------------------------------
        pte2.name = mc_elm.name
        pte2.PowerTransformer = cm_transformer
        pte2.Terminal = cm_transformer.Terminals[1]
        pte2.BaseVoltage = find_object_by_vnom(
            cgmes_model=cgmes_model,
            object_list=cgmes_model.cgmes_assets.BaseVoltage_list,
            target_vnom=mc_elm.bus2.Vnom
        )
        pte2.ratedU = mc_elm.V2
        pte2.ratedS = mc_elm.rate2
        pte2.endNumber = 2

        (pte2.r,
         pte2.x,
         pte2.g,
         pte2.b,
         pte2.r0,
         pte2.x0,
         pte2.g0,
         pte2.b0) = get_ohm_values_power_transformer(r=mc_elm.winding2.R,
                                                     x=mc_elm.winding2.X,
                                                     g=mc_elm.winding2.G,
                                                     b=mc_elm.winding2.B,
                                                     r0=mc_elm.winding2.R0,
                                                     x0=mc_elm.winding2.X0,
                                                     g0=mc_elm.winding2.G0,
                                                     b0=mc_elm.winding2.B0,
                                                     nominal_power=mc_elm.winding2.rate,
                                                     rated_voltage=mc_elm.winding2.HV,
                                                     Sbase=grid.Sbase)

        # Winding 3 ---------------------------------------------------------
        pte3.name = mc_elm.name
        pte3.PowerTransformer = cm_transformer
        pte3.Terminal = cm_transformer.Terminals[2]
        pte3.BaseVoltage = find_object_by_vnom(
            cgmes_model=cgmes_model,
            object_list=cgmes_model.cgmes_assets.BaseVoltage_list,
            target_vnom=mc_elm.bus3.Vnom
        )
        pte3.ratedU = mc_elm.V3
        pte3.ratedS = mc_elm.rate3
        pte3.endNumber = 3

        (pte3.r,
         pte3.x,
         pte3.g,
         pte3.b,
         pte3.r0,
         pte3.x0,
         pte3.g0,
         pte3.b0) = get_ohm_values_power_transformer(r=mc_elm.winding3.R,
                                                     x=mc_elm.winding3.X,
                                                     g=mc_elm.winding3.G,
                                                     b=mc_elm.winding3.B,
                                                     r0=mc_elm.winding3.R0,
                                                     x0=mc_elm.winding3.X0,
                                                     g0=mc_elm.winding3.G0,
                                                     b0=mc_elm.winding3.B0,
                                                     nominal_power=mc_elm.winding3.rate,
                                                     rated_voltage=mc_elm.winding3.HV,
                                                     Sbase=grid.Sbase)

        # compose transformer ------------------------------------------------------------------------------------------
        cm_transformer.PowerTransformerEnd.append(pte1)
        cgmes_model.add(pte1)
        cm_transformer.PowerTransformerEnd.append(pte2)
        cgmes_model.add(pte2)
        cm_transformer.PowerTransformerEnd.append(pte3)
        cgmes_model.add(pte3)

        cgmes_model.add(cm_transformer)


def get_cgmes_current_limits(cgmes_model: CgmesCircuit,
                             cgmes_elm: CGMES_ASSETS,
                             mc_elm: BranchParent,
                             op_lim_types: List,
                             ver: CGMESVersions,
                             logger: DataLogger):
    """
    Export Current Limits to CGMES for Branches.

    :param cgmes_model: CgmesCircuit
    :param mc_elm: GcDev Transformer 2W/3W or ACLineSegment
    :param cgmes_elm: CGMES Transformer 2W or ACLineSegment
    :param op_lim_types: list of used OperationalLimitTypes
    :param ver:
    :param logger: DataLogger
    :return: None
    """

    def create_limits_for_terminal(termnl, rate_and_type):
        """
        Helper function to create current limits for a terminal.

        :param termnl: The terminal object
        :param rate_and_type: List of (rate_mw, op_limit_type) tuples
        """
        for rate_mw, op_limit_type in rate_and_type:

            if rate_mw != 0.0:
                create_cgmes_current_limit(
                    terminal=termnl,
                    rate_mw=rate_mw,
                    op_limit_type=op_limit_type,
                    cgmes_model=cgmes_model,
                    ver=ver,
                    logger=logger
                )

    # Get operational limit types
    patl, tatl_900, tatl_60 = op_lim_types

    # Rate and Type Mapping
    rates = [
        (mc_elm.rate, patl),
        # Normal rate
        (mc_elm.contingency_factor * mc_elm.rate, tatl_900),
        # Contingency rate - TATL 900
        (mc_elm.protection_rating_factor * mc_elm.rate, tatl_60)
        # Contingency rate - TATL 60
    ]

    # Apply current limits to each terminal: 2 for TR2W/Lines, 3 for TR3W
    for terminal in cgmes_elm.Terminals:
        if terminal is not None:  # Skip if the terminal does not exist
            create_limits_for_terminal(terminal, rates)


def get_cgmes_operational_limit_types(cgmes_model: CgmesCircuit, ver: CGMESVersions):
    """
    Creates three kind of Operational limit type for Cgmes Export.

    :param cgmes_model: CgmesModel
    :param ver:
    :return:
    """
    # PATL      -----
    patl = create_cgmes_operational_limit_type(cgmes_model, ver)
    patl.name = "Normal rating"
    patl.shortName = "PATL"
    patl.description = "Permanent Admissible Transmission Loading"
    patl.acceptableDuration = None  # unlimited

    patl.limitType = LimitTypeKind.patl
    patl.direction = OperationalLimitDirectionKind.absoluteValue

    # TATL 900  ------
    tatl_900 = create_cgmes_operational_limit_type(cgmes_model, ver)
    tatl_900.name = "Contingency rating in VeraGrid"
    tatl_900.shortName = "TATL"
    tatl_900.description = "Temporarily Admissible Transmission Loading"
    tatl_900.acceptableDuration = 900

    tatl_900.limitType = LimitTypeKind.tatl
    tatl_900.direction = OperationalLimitDirectionKind.absoluteValue

    # TATL 60   ------
    tatl_60 = create_cgmes_operational_limit_type(cgmes_model, ver)
    tatl_60.name = "Protection rating in VeraGrid"
    tatl_60.shortName = "TATL"
    tatl_60.description = "Temporarily Admissible Transmission Loading"
    tatl_60.acceptableDuration = 60

    tatl_60.limitType = LimitTypeKind.tatl
    tatl_60.direction = OperationalLimitDirectionKind.absoluteValue

    return [patl, tatl_900, tatl_60]


def get_cgmes_equivalent_shunts(multicircuit_model: MultiCircuit,
                                cgmes_model: CgmesCircuit,
                                ver: CGMESVersions,
                                logger: DataLogger):
    """
    Converts Multi Circuit shunts
    into CGMES EquivalentShunt.
    No control, like FixShunt in RAW.

    :param multicircuit_model: MultiCircuit model in VeraGrid
    :param cgmes_model:
    :param ver:
    :param logger:
    :return:
    """

    for mc_elm in multicircuit_model.shunts:

        if ver == CGMESVersions.v2_4_15:
            eq_shunt = cgmes24.EquivalentShunt(rdfid=form_rdfid(mc_elm.idtag))
        elif ver == CGMESVersions.v3_0_0:
            eq_shunt = cgmes30.EquivalentShunt(rdfid=form_rdfid(mc_elm.idtag))
        else:
            raise NotImplemented()

        eq_shunt.name = mc_elm.name
        eq_shunt.description = mc_elm.code

        if mc_elm.bus.voltage_level:

            vl = find_object_by_uuid(
                cgmes_model=cgmes_model,
                object_list=cgmes_model.cgmes_assets.VoltageLevel_list,
                target_uuid=mc_elm.bus.voltage_level.idtag
            )

            if isinstance(vl, cgmes_model.assets.VoltageLevel):
                eq_shunt.EquipmentContainer = vl

        base_voltage = find_object_by_vnom(
            cgmes_model=cgmes_model,
            object_list=cgmes_model.cgmes_assets.BaseVoltage_list,
            target_vnom=mc_elm.bus.Vnom)
        if base_voltage is not None:
            eq_shunt.BaseVoltage = base_voltage

        eq_shunt.b = mc_elm.B / (mc_elm.bus.Vnom ** 2)
        eq_shunt.g = mc_elm.G / (mc_elm.bus.Vnom ** 2)

        create_cgmes_terminal(mc_bus=mc_elm.bus,
                              seq_num=1,
                              cond_eq=eq_shunt,
                              cgmes_model=cgmes_model,
                              ver=ver,
                              logger=logger)

        cgmes_model.add(eq_shunt)


def get_cgmes_linear_and_non_linear_shunts(multicircuit_model: MultiCircuit,
                                           cgmes_model: CgmesCircuit,
                                           ver: CGMESVersions,
                                           logger: DataLogger):
    """
    Converts Multi Circuit Controllable Shunts
    into CGMES Linear or Non-Linear shunt compensators
    (depending on is_linear flag)

    :param multicircuit_model: MultiCircuit model in VeraGrid
    :param cgmes_model: CgmesModel
    :param ver:
    :param logger: DataLogger
    :return:
    """

    for mc_elm in multicircuit_model.controllable_shunts:

        if mc_elm.is_nonlinear:

            if ver == CGMESVersions.v2_4_15:
                non_lin_sc = cgmes24.NonlinearShuntCompensator(rdfid=form_rdfid(mc_elm.idtag))
            elif ver == CGMESVersions.v3_0_0:
                non_lin_sc = cgmes30.NonlinearShuntCompensator(rdfid=form_rdfid(mc_elm.idtag))
            else:
                raise NotImplemented()

            non_lin_sc.name = mc_elm.name
            non_lin_sc.description = mc_elm.code
            if mc_elm.bus.voltage_level:
                vl = find_object_by_uuid(
                    cgmes_model=cgmes_model,
                    object_list=cgmes_model.cgmes_assets.VoltageLevel_list,
                    target_uuid=mc_elm.bus.voltage_level.idtag
                )
                if isinstance(vl, cgmes_model.assets.VoltageLevel):
                    non_lin_sc.EquipmentContainer = vl

            non_lin_sc.BaseVoltage = find_object_by_vnom(
                cgmes_model=cgmes_model,
                object_list=cgmes_model.cgmes_assets.BaseVoltage_list,
                target_vnom=mc_elm.bus.Vnom)

            non_lin_sc.Terminals = (
                create_cgmes_terminal(mc_bus=mc_elm.bus,
                                      seq_num=1,
                                      cond_eq=non_lin_sc,
                                      cgmes_model=cgmes_model,
                                      ver=ver,
                                      logger=logger)
            )

            # CONTROL
            # control_type: voltage or power control, ..
            # is_controlled: enabling flag (already have)
            if mc_elm.is_controlled:
                non_lin_sc.RegulatingControl = (
                    create_cgmes_regulating_control(non_lin_sc, mc_elm, cgmes_model, ver, logger)
                )
                non_lin_sc.controlEnabled = True
            else:
                non_lin_sc.controlEnabled = False

            # SSH: sections: Shunt compensator sections in use.
            if mc_elm.active:
                non_lin_sc.sections = mc_elm.step + 1
            else:
                non_lin_sc.sections = 0

            # EQ
            non_lin_sc.nomU = mc_elm.bus.Vnom
            b_points_mva, g_points_mva = mc_elm.get_block_points()
            b_points = [b / (non_lin_sc.nomU ** 2) for b in b_points_mva]
            g_points = [g / (non_lin_sc.nomU ** 2) for g in g_points_mva]
            for i in range(len(b_points)):
                create_cgmes_nonlinear_sc_point(
                    section_num=i + 1,
                    b=b_points[i],
                    g=g_points[i],
                    nl_sc=non_lin_sc,
                    cgmes_model=cgmes_model,
                    ver=ver
                )
            non_lin_sc.normalSections = non_lin_sc.sections
            non_lin_sc.maximumSections = len(b_points)
            if non_lin_sc.maximumSections < non_lin_sc.sections:
                logger.add_error(
                    msg="Number or sections is out of range",
                    device=non_lin_sc,
                    device_class=non_lin_sc.tpe,
                    value=non_lin_sc.sections,
                    expected_value=non_lin_sc.maximumSections,
                    comment="maxSections < sections"
                )
            non_lin_sc.aggregate = False

            cgmes_model.add(non_lin_sc)

        else:  # LINEAR controllable shunts

            # object_template = cgmes_model.get_class_type("LinearShuntCompensator")
            if ver == CGMESVersions.v2_4_15:
                lsc = cgmes24.LinearShuntCompensator(rdfid=form_rdfid(mc_elm.idtag))
            elif ver == CGMESVersions.v3_0_0:
                lsc = cgmes30.LinearShuntCompensator(rdfid=form_rdfid(mc_elm.idtag))
            else:
                raise NotImplemented()

            lsc.name = mc_elm.name
            lsc.description = mc_elm.code
            if mc_elm.bus.voltage_level:
                vl = find_object_by_uuid(
                    cgmes_model=cgmes_model,
                    object_list=cgmes_model.cgmes_assets.VoltageLevel_list,
                    target_uuid=mc_elm.bus.voltage_level.idtag
                )

                if isinstance(vl, cgmes_model.assets.VoltageLevel):
                    lsc.EquipmentContainer = vl

            base_voltage = find_object_by_vnom(cgmes_model=cgmes_model,
                                               object_list=cgmes_model.cgmes_assets.BaseVoltage_list,
                                               target_vnom=mc_elm.bus.Vnom)

            if isinstance(base_voltage, cgmes_model.assets.BaseVoltage):
                lsc.BaseVoltage = base_voltage

            if mc_elm.active:
                lsc.sections = mc_elm.step + 1
            else:
                lsc.sections = 0

            # EQ
            lsc.nomU = mc_elm.bus.Vnom
            lsc.bPerSection = mc_elm.get_linear_b_steps()[0] / (lsc.nomU ** 2)
            lsc.gPerSection = mc_elm.get_linear_g_steps()[0] / (lsc.nomU ** 2)
            lsc.normalSections = lsc.sections
            lsc.maximumSections = len(mc_elm.b_steps)
            if lsc.maximumSections < lsc.sections:
                logger.add_error(
                    msg="Number or sections is out of range",
                    device=lsc,
                    device_class=lsc.tpe,
                    value=lsc.sections,
                    expected_value=lsc.maximumSections,
                    comment="maxSections < sections"
                )
            lsc.aggregate = False

            lsc.Terminals = (
                create_cgmes_terminal(mc_bus=mc_elm.bus,
                                      seq_num=1,
                                      cond_eq=lsc,
                                      cgmes_model=cgmes_model,
                                      ver=ver,
                                      logger=logger)
            )

            # CONTROL
            if mc_elm.is_controlled:
                lsc.RegulatingControl = (
                    create_cgmes_regulating_control(lsc, mc_elm, cgmes_model, ver, logger)
                )
                lsc.controlEnabled = True
            else:
                lsc.controlEnabled = False

            cgmes_model.add(lsc)


def get_cgmes_breakers(multicircuit_model: MultiCircuit,
                       cgmes_model: CgmesCircuit,
                       ver: CGMESVersions,
                       logger: DataLogger):
    """
    Converts every Multi Circuit Switch into CGMES Breaker.

    :param multicircuit_model: MultiCircuit model in VeraGrid
    :param cgmes_model:
    :param ver:
    :param logger:
    :return:
    """

    for mc_elm in multicircuit_model.switch_devices:
        if ver == CGMESVersions.v2_4_15:
            br = cgmes24.Breaker(rdfid=form_rdfid(mc_elm.idtag))
        elif ver == CGMESVersions.v3_0_0:
            br = cgmes30.Breaker(rdfid=form_rdfid(mc_elm.idtag))
        else:
            raise NotImplemented()

        br.Terminals = [
            create_cgmes_terminal(mc_elm.bus_from, None, br, cgmes_model, ver, logger),
            create_cgmes_terminal(mc_elm.bus_to, None, br, cgmes_model, ver, logger)
        ]

        br.name = mc_elm.name
        br.description = mc_elm.code
        br.BaseVoltage = find_object_by_vnom(cgmes_model=cgmes_model,
                                             object_list=cgmes_model.cgmes_assets.BaseVoltage_list,
                                             target_vnom=mc_elm.get_max_bus_nominal_voltage())

        if mc_elm.get_voltage_level_from():
            vl = find_object_by_uuid(
                cgmes_model=cgmes_model,
                object_list=cgmes_model.cgmes_assets.VoltageLevel_list,
                target_uuid=mc_elm.bus_from.voltage_level.idtag
            )
            br.EquipmentContainer = vl

        br.open = not mc_elm.active
        br.retained = mc_elm.retained
        br.normalOpen = mc_elm.normal_open
        br.aggregate = False

        # .ratedCurrent is optional attr, not sure is it in Amps or an enum
        # if br.BaseVoltage is not None:
        #     br.ratedCurrent = np.round(
        #         (mc_elm.rated_current * 1000.0) / (br.BaseVoltage.nominalVoltage * 1.73205080756888),
        #         4)
        # else:
        #     logger.add_warning(msg="Couldn't calculate rated current as BaseVoltage missing")

        cgmes_model.add(br)


def get_cgmes_sv_voltages(
        multi_circuit_model: MultiCircuit,
        cgmes_model: CgmesCircuit,
        pf_results: PowerFlowResults,
        ver: CGMESVersions,
        logger: DataLogger) -> None:
    """
    Creates a CgmesCircuit SvVoltage_list
    from PowerFlow results of the numerical circuit.

    :param multi_circuit_model:
    :param cgmes_model:
    :param pf_results:
    :param ver:
    :param logger:
    :return:
    """
    # SvVoltage: v, a, TopologicalNode

    for bus, voltage in zip(multi_circuit_model.buses, pf_results.voltage):

        if not bus.is_dc and not bus.internal:

            tp_node = find_object_by_uuid(
                cgmes_model=cgmes_model,
                object_list=cgmes_model.cgmes_assets.TopologicalNode_list,
                target_uuid=bus.idtag
            )

            if isinstance(tp_node, cgmes_model.assets.TopologicalNode):

                if ver == CGMESVersions.v2_4_15:
                    sv_voltage = cgmes24.SvVoltage(rdfid=get_new_rdfid(), tpe='SvVoltage')
                elif ver == CGMESVersions.v3_0_0:
                    sv_voltage = cgmes30.SvVoltage(rdfid=get_new_rdfid(), tpe='SvVoltage')
                else:
                    raise NotImplemented()

                sv_voltage.TopologicalNode = tp_node

                # as the ORDER of the results is the same as the order of buses (=tn)
                bv = tp_node.BaseVoltage
                sv_voltage.v = np.abs(voltage) * bv.nominalVoltage
                sv_voltage.angle = np.angle(voltage, deg=True)

                # Add the SvVoltage instance to the SvVoltage_list
                cgmes_model.add(sv_voltage)

            else:
                logger.add_info(
                    msg="TP Node not found for bus",
                    value=tp_node,
                    expected_value=bus.idtag,
                )

        else:
            logger.add_info(
                msg="SvVoltage is not exported for internal (TR3W) buses and DC buses",
                value=voltage,
            )


def get_cgmes_sv_power_flow_1(multi_circuit: MultiCircuit,
                              nc: NumericalCircuit,
                              cgmes_model: CgmesCircuit,
                              pf_results: PowerFlowResults,
                              ver: CGMESVersions,
                              logger: DataLogger) -> None:
    """
    For single-terminal devices:
    Creates a CgmesCircuit SvPowerFlow_list from PowerFlow results of the numerical circuit.

    :param multi_circuit:
    :param nc:
    :param cgmes_model:
    :param pf_results:
    :param ver:
    :param logger:
    :return: SvVoltage_list is populated in CgmesCircuit.
    """
    # SVPowerFlow: p, q -> Terminals
    # SvPowerFlow class is required to be instantiated for the following classes:
    # subclasses of the RotatingMachine,
    # subclasses of the EnergyConsumer,
    # EquivalentInjection,
    # ShuntCompensator,
    # StaticVarCompensator and
    # EnergySource.

    # Generators ------------------------------------------------------------
    gen_objects = multi_circuit.generators

    gen_ps = nc.generator_data.p
    gen_qs = pf_results.gen_q

    for (gen, gen_p, gen_q) in zip(gen_objects, gen_ps, gen_qs):

        term = find_object_by_cond_eq_uuid(
            object_list=cgmes_model.cgmes_assets.Terminal_list,
            cond_eq_target_uuid=gen.idtag
        )

        if is_term(term):

            create_sv_power_flow(
                cgmes_model=cgmes_model,
                p=gen_p,
                q=gen_q,
                terminal=term,
                ver=ver
            )

        else:
            logger.add_error(msg='No Terminal found for Generator',
                             device=gen,
                             device_class=gen.device_type.value,
                             value=gen.idtag)

    # Load-like devices -----------------------------------------------------
    # loads, static_generators, external_grids, current_injections
    load_objects = multi_circuit.get_load_like_devices()

    load_power = compute_zip_power(
        S0=nc.load_data.S,
        I0=nc.load_data.I,
        Y0=nc.load_data.Y,
        Vm=np.abs(pf_results.voltage[nc.load_data.get_bus_indices()])
    )

    for (mc_load_like, load_power) in zip(load_objects, load_power):

        term = find_object_by_cond_eq_uuid(
            object_list=cgmes_model.cgmes_assets.Terminal_list,
            cond_eq_target_uuid=mc_load_like.idtag  # missing Load uuid
        )

        if is_term(term):

            create_sv_power_flow(
                cgmes_model=cgmes_model,
                p=load_power.real,
                q=load_power.imag,
                terminal=term,
                ver=ver
            )

        else:
            logger.add_error(msg='No Terminal found for Load-like device',
                             device=mc_load_like,
                             device_class=mc_load_like.device_type.value,
                             value=mc_load_like.idtag)

    # Shunts ----------------------------------------------------------------
    # shunts, controllable shunts
    shunt_objects = multi_circuit.get_shunt_like_devices()

    shunt_qs = pf_results.shunt_q

    for (mc_shunt_like, shunt_q) in zip(shunt_objects, shunt_qs):

        term = find_object_by_cond_eq_uuid(
            object_list=cgmes_model.cgmes_assets.Terminal_list,
            cond_eq_target_uuid=mc_shunt_like.idtag  # missing Load uuid
        )
        if is_term(term):

            create_sv_power_flow(
                cgmes_model=cgmes_model,
                p=0.0,
                q=shunt_q,
                terminal=term,
                ver=ver
            )

        else:
            logger.add_error(msg='No Terminal found for Shunt-like device',
                             device=mc_shunt_like,
                             device_class=mc_shunt_like.device_type.value,
                             value=mc_shunt_like.idtag,
                             comment="SvPowerFlow is not exported.")


def get_cgmes_sv_power_flow_2(multi_circuit: MultiCircuit,
                              nc: NumericalCircuit,
                              cgmes_model: CgmesCircuit,
                              pf_results: PowerFlowResults,
                              ver: CGMESVersions,
                              logger: DataLogger) -> None:
    """
    For Branches:
    Creates a CgmesCircuit SvPowerFlow_list from PowerFlow results of the numerical circuit.

    :param multi_circuit:
    :param nc:
    :param cgmes_model:
    :param pf_results:
    :param ver:
    :param logger:
    :return: SvVoltage_list is populated in CgmesCircuit.
    """
    # SVPowerFlow: p, q -> Terminals
    # RuleDescription:
    # 	Branches shall have cim:SvPowerFlow instantiated at its cim:Terminals for
    # 	the following branch classes:
    # 	- cim:SeriesCompensator
    # 	- cim:ACLineSegment
    # 	- cim:PowerTransformer
    # 	- cim:EquivalentBranch
    # 	- cim:Switch where cim:Switch.retained is true.

    # Branches ------------------------------------------------------------
    branch_objects = multi_circuit.get_branches(add_vsc=False, add_hvdc=False, add_switch=True)

    for (branch, pf_res_from, pf_res_to) in zip(branch_objects, pf_results.Sf, pf_results.St):

        term = find_object_by_cond_eq_uuid(
            object_list=cgmes_model.cgmes_assets.Terminal_list,
            cond_eq_target_uuid=branch.idtag
        )
        if is_term(term[0]):

            create_sv_power_flow(
                cgmes_model=cgmes_model,
                p=pf_res_from.real,
                q=pf_res_from.imag,
                terminal=term,
                ver=ver
            )

        else:
            logger.add_error(msg='No Terminal found for Branch',
                             device=branch,
                             device_class=branch.device_type.value,
                             value=branch.idtag,
                             comment="get_cgmes_sv_power_flow_2()")


def get_cgmes_sv_tap_step(multi_circuit: MultiCircuit,
                          nc: NumericalCircuit,
                          cgmes_model: CgmesCircuit,
                          pf_results: PowerFlowResults,
                          ver: CGMESVersions,
                          logger: DataLogger) -> None:
    """

    :param multi_circuit:
    :param nc:
    :param cgmes_model:
    :param pf_results:
    :param ver:
    :param logger:
    :return:
    """
    branch_objects = multi_circuit.get_branches(add_vsc=False, add_hvdc=False, add_switch=True)

    tap_modules = pf_results.tap_module

    for (branch, t_m) in zip(branch_objects, tap_modules):

        if isinstance(branch, gcdev.Transformer2W):
            pass
            # branch.tap_changer.h

    pass


def get_cgmes_sv_shunt_compensator_sections(cgmes_model: CgmesCircuit,
                                            ver: CGMESVersions) -> None:
    """

    :param cgmes_model:
    :param ver:
    :return:
    """

    for shunts in [cgmes_model.cgmes_assets.LinearShuntCompensator_list,
                   cgmes_model.cgmes_assets.NonlinearShuntCompensator_list]:

        for shunt in shunts:
            create_sv_shunt_compensator_sections(
                cgmes_model=cgmes_model,
                sections=shunt.sections if shunt.sections is not None else 0,
                cgmes_shunt_compensator=shunt,
                ver=ver,
            )


def get_cgmes_topological_island(multicircuit_model: MultiCircuit,
                                 nc: NumericalCircuit,
                                 cgmes_model: CgmesCircuit,
                                 ver: CGMESVersions,
                                 logger: DataLogger):
    """

    :param multicircuit_model:
    :param nc:
    :param cgmes_model:
    :param ver:
    :param logger:
    :return:
    """
    nc_islands = nc.split_into_islands()

    i = 0
    for nc_i in nc_islands:
        i = i + 1

        if ver == CGMESVersions.v2_4_15:
            new_island = cgmes24.TopologicalIsland(get_new_rdfid())
        elif ver == CGMESVersions.v3_0_0:
            new_island = cgmes30.TopologicalIsland(get_new_rdfid())
        else:
            raise NotImplemented()

        new_island.name = "TopologicalIsland" + str(i)
        new_island.TopologicalNodes = []
        bus_idtags = nc_i.bus_data.idtag
        mc_buses = []
        for tn_idtag in bus_idtags:
            tn = find_object_by_uuid(cgmes_model=cgmes_model,
                                     object_list=cgmes_model.cgmes_assets.TopologicalNode_list,
                                     target_uuid=tn_idtag)

            if isinstance(tn, cgmes_model.assets.TopologicalNode):
                new_island.TopologicalNodes.append(tn)
                mc_bus = find_object_by_attribute(multicircuit_model.buses, "idtag", tn_idtag)
                mc_buses.append(mc_bus)
            else:
                logger.add_warning(msg="TopologicalNode missing from TopologicalIsland!",
                                   device=new_island.name,
                                   device_property="TopologicalNode")
        if mc_buses:
            slack_bus = find_object_by_attribute(mc_buses, "is_slack", True)
            if slack_bus:
                slack_tn = find_object_by_uuid(cgmes_model,
                                               cgmes_model.cgmes_assets.TopologicalNode_list,
                                               slack_bus.idtag)

                if isinstance(slack_tn, cgmes_model.assets.TopologicalNode):
                    new_island.AngleRefTopologicalNode = slack_tn
                    for tn in new_island.TopologicalNodes:
                        tn.AngleRefTopologicalIsland = slack_tn
            else:
                logger.add_warning(
                    msg="AngleRefTopologicalNode missing from TopologicalIsland!",
                    device=new_island.name,
                    device_property="AngleRefTopologicalNode")
        else:
            logger.add_error(
                msg="All TopologicalNodes are missing from TopologicalIsland!",
                device=new_island.name,
                device_property="TopologicalNode")
        cgmes_model.add(new_island)


def make_coordinate_system(cgmes_model: CgmesCircuit,
                           ver: CGMESVersions,
                           logger: DataLogger):
    """

    :param cgmes_model:
    :param ver:
    :param logger:
    :return:
    """
    if ver == CGMESVersions.v2_4_15:
        coo_sys = cgmes24.CoordinateSystem(rdfid=get_new_rdfid())
    elif ver == CGMESVersions.v3_0_0:
        coo_sys = cgmes30.CoordinateSystem(rdfid=get_new_rdfid())
    else:
        raise NotImplemented()

    coo_sys.name = "EPSG4326"
    coo_sys.crsUrn = "urn:ogc:def:crs:EPSG::4326"
    coo_sys.Locations = []

    cgmes_model.add(coo_sys)


def convert_hvdc_line_to_cgmes(multicircuit_model: MultiCircuit,
                               cgmes_model: CgmesCircuit,
                               ver: CGMESVersions,
                               logger: DataLogger):
    """
    Converts simplified HVDC line to two VSConverters inside DCConverterUnits,
    connected with a DCLineSegment, contained in a DCLine
    DCGround?
    DCNodes, DCTopologicalNodes are also created here from scratch
    as there is no DC part in the simplified modelling.

    :param multicircuit_model: MultiCircuit model in VeraGrid
    :param cgmes_model:
    :param ver:
    :param logger:
    :return:
    """

    for hvdc_line in multicircuit_model.hvdc_lines:
        # FROM side
        vsc_1, dc_conv_unit_1 = create_cgmes_vsc_converter(
            cgmes_model=cgmes_model,
            gc_vsc=None,
            p_set=hvdc_line.Pset,
            v_set=hvdc_line.Vset_f,
            ver=ver,
            logger=logger
        )
        dc_tp_1 = create_cgmes_dc_tp_node(
            tp_name=f'DC_side_{hvdc_line.bus_from.name}',
            tp_description=f'DC_for_{hvdc_line.bus_from.code}',
            cgmes_model=cgmes_model,
            ver=ver,
            logger=logger
        )
        dc_node_1 = create_cgmes_dc_node(cn_name='DC_node_name',
                                         cn_description='DC_node_VSC_1',
                                         cgmes_model=cgmes_model,
                                         dc_tp=dc_tp_1,
                                         dc_ec=dc_conv_unit_1,
                                         ver=ver,
                                         logger=logger)

        create_cgmes_acdc_converter_terminal(
            cgmes_model=cgmes_model,
            mc_dc_bus=None,
            seq_num=2,
            dc_node=dc_node_1,
            dc_cond_eq=vsc_1,
            ver=ver,
            logger=logger
        )

        create_cgmes_terminal(
            cgmes_model=cgmes_model,
            mc_bus=hvdc_line.bus_from,
            seq_num=None,
            cond_eq=vsc_1,
            ver=ver,
            logger=logger
        )

        # TO side
        vsc_2, dc_conv_unit_2 = create_cgmes_vsc_converter(
            cgmes_model=cgmes_model,
            gc_vsc=None,
            p_set=-hvdc_line.Pset,
            v_set=hvdc_line.Vset_t,
            ver=ver,
            logger=logger
        )
        dc_tp_2 = create_cgmes_dc_tp_node(
            tp_name=f'DC_side_{hvdc_line.bus_to.name}',
            tp_description=f'DC_for_{hvdc_line.bus_to.code}',
            cgmes_model=cgmes_model,
            ver=ver,
            logger=logger
        )
        dc_node_2 = create_cgmes_dc_node(cn_name='DC_node_name_2',
                                         cn_description='DC_node_VSC_2',
                                         cgmes_model=cgmes_model,
                                         dc_tp=dc_tp_2,
                                         dc_ec=dc_conv_unit_2,
                                         ver=ver,
                                         logger=logger)

        create_cgmes_acdc_converter_terminal(
            cgmes_model=cgmes_model,
            mc_dc_bus=None,
            seq_num=2,
            dc_node=dc_node_2,
            dc_cond_eq=vsc_2,
            ver=ver,
            logger=logger
        )

        create_cgmes_terminal(
            cgmes_model=cgmes_model,
            mc_bus=hvdc_line.bus_to,
            seq_num=None,
            cond_eq=vsc_2,
            ver=ver,
            logger=logger
        )

        # DC Line
        dc_line = create_cgmes_dc_line(cgmes_model=cgmes_model, ver=ver, logger=logger)
        create_cgmes_dc_line_segment(cgmes_model=cgmes_model,
                                     mc_elm=hvdc_line,
                                     dc_tp_1=dc_tp_1,
                                     dc_node_1=dc_node_1,
                                     dc_tp_2=dc_tp_2,
                                     dc_node_2=dc_node_2,
                                     eq_cont=dc_line,
                                     ver=ver,
                                     logger=logger)

    return


# endregion


def veragrid_to_cgmes(gc_model: MultiCircuit,
                      num_circ: NumericalCircuit,
                      pf_results: Union[None, PowerFlowResults],
                      cgmes_model: CgmesCircuit,
                      logger: DataLogger) -> CgmesCircuit:
    """
    Converts the input Multi circuit to a new CGMES Circuit.

    :param gc_model: Multi circuit object
    :param num_circ: Numerical circuit complied from MC
    :param cgmes_model: CGMES circuit object
    :param pf_results: power flow results from VeraGrid
    :param logger: Logger object
    :return: CGMES circuit (as a new object)
    """
    ver = cgmes_model.cgmes_version

    get_cgmes_geograpical_regions(gc_model, cgmes_model, ver, logger)
    get_cgmes_sub_geographical_regions(gc_model, cgmes_model, ver, logger)

    make_coordinate_system(cgmes_model, ver, logger)

    get_cgmes_base_voltages(gc_model, cgmes_model, ver, logger)

    get_cgmes_substations(gc_model, cgmes_model, ver, logger)
    get_cgmes_voltage_levels(gc_model, cgmes_model, ver, logger)

    get_cgmes_tp_nodes(gc_model, cgmes_model, ver, logger)
    get_cgmes_cn_nodes_from_tp_nodes(gc_model, cgmes_model, ver, logger)

    # TODO BusbarSection
    # get_cgmes_cn_nodes_from_cns(gc_model, cgmes_model, logger)

    get_cgmes_loads(gc_model, cgmes_model, ver, logger)
    get_cgmes_equivalent_injections(gc_model, cgmes_model, ver, logger)
    get_cgmes_generators(gc_model, cgmes_model, ver, logger)

    # Get operational limit types
    operational_limit_type_list = get_cgmes_operational_limit_types(cgmes_model, ver)
    # patl, tatl_900, tatl_60

    # BRANCHES
    # lines
    get_cgmes_ac_line_segments(gc_model, cgmes_model, operational_limit_type_list, ver, logger)
    # transformers, windings
    get_cgmes_power_transformers(gc_model, cgmes_model, operational_limit_type_list, ver, logger)

    # SHUNTS
    get_cgmes_equivalent_shunts(gc_model, cgmes_model, ver, logger)
    get_cgmes_linear_and_non_linear_shunts(gc_model, cgmes_model, ver, logger)

    # Switches (Breakers)
    get_cgmes_breakers(gc_model, cgmes_model, ver, logger)

    # DC elements
    convert_hvdc_line_to_cgmes(gc_model, cgmes_model, ver, logger)
    # TODO get_cgmes_vsc_from_vsc()
    # TODO get_dc_line_from_dc_line()

    # RESULTS: sv classes
    if pf_results:
        # if converged == True...

        # SvVoltage for every TopoNode
        get_cgmes_sv_voltages(gc_model, cgmes_model, pf_results, ver, logger)

        # PowerFlow: P, Q results for every terminal
        get_cgmes_sv_power_flow_1(gc_model, num_circ, cgmes_model, pf_results, ver, logger)
        # get_cgmes_sv_power_flow_2(gc_model, num_circ, cgmes_model, pf_results,
        #                           logger)

        # SV Status: for ConductingEquipment
        # TODO create_sv_status() elements.active parameter

        # SVTapStep: handled at transformer function
        # TODO get it from results
        get_cgmes_sv_tap_step(gc_model, num_circ, cgmes_model, pf_results, ver, logger)

        # SvShuntCompensatorSections:
        get_cgmes_sv_shunt_compensator_sections(cgmes_model, ver)

        # Topological Islands
        get_cgmes_topological_island(gc_model, num_circ, cgmes_model, ver, logger)

    else:
        logger.add_error(msg="Missing power flow result for CGMES export.")

    if logger.has_logs():
        print("\nLogger is not empty! (cgmes export)")

    return cgmes_model
