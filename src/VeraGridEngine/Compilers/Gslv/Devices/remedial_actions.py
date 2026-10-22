# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from VeraGridEngine.Compilers.Gslv.activation import (
    contingency_ops_type_dict, pg, remedial_action_property_dict,
)
from VeraGridEngine.Devices.multi_circuit import MultiCircuit


def bind_event_devices(circuit: MultiCircuit, gslv_grid: "pg.MultiCircuit") -> None:
    """
    Bind event targets and export remedial groups after all physical devices exist.

    :param circuit: Source circuit containing event references.
    :param gslv_grid: Converted circuit containing the target devices.
    :return: None.
    """
    # Resolve references to the actual exported objects rather than detached copies.
    devices: dict[str, pg.EditableDevice] = dict()
    collections: tuple = (
        gslv_grid.buses, gslv_grid.loads, gslv_grid.static_generators,
        gslv_grid.generators, gslv_grid.batteries, gslv_grid.shunts,
        gslv_grid.controllable_shunts, gslv_grid.lines, gslv_grid.dc_lines,
        gslv_grid.transformers, gslv_grid.transformer_3ws, gslv_grid.windings,
        gslv_grid.vscs, gslv_grid.hvdc_lines, gslv_grid.substations,
        gslv_grid.voltage_levels, gslv_grid.areas, gslv_grid.zones,
        gslv_grid.countries, gslv_grid.facilities, gslv_grid.modelling_authorities,
        gslv_grid.branch_groups, gslv_grid.municipalities, gslv_grid.regions,
        gslv_grid.technologies, gslv_grid.fuels, gslv_grid.emission_gases,
    )
    for collection in collections:
        for device in collection:
            devices[device.get_idtag()] = device

    event_collections: tuple = (gslv_grid.contingencies, gslv_grid.investments)
    for events in event_collections:
        for event in events:
            target: pg.EditableDevice | None = devices.get(event.device_idtag, None)
            if target is None:
                pass
            else:
                event.device = target

    contingencies: dict[str, pg.ContingencyGroup] = {
        group.get_idtag(): group for group in gslv_grid.contingency_groups}
    groups: dict[str, pg.RemedialActionGroup] = dict()
    for source in circuit.remedial_action_groups:
        group: pg.RemedialActionGroup = pg.RemedialActionGroup(
            name=source.name, idtag=source.idtag, code=str(source.code), category=source.category)
        groups[source.idtag] = group
        gslv_grid.add_remedial_action_group(group)

    # A second pass supports predecessors that appear later in the source list.
    for source in circuit.remedial_action_groups:
        group = groups[source.idtag]
        group.conn_group = None if source.conn_group is None else contingencies[source.conn_group.idtag]
        group.prev_ra = None if source.prev_ra is None else groups[source.prev_ra.idtag]
        group.monitored_device = None if source.monitored_device is None else devices[source.monitored_device.idtag]
        group.property_type = (None if source.property_type is None else
                               remedial_action_property_dict[source.property_type])

    for source_action in circuit.remedial_actions:
        action: pg.RemedialAction = pg.RemedialAction(
            idtag=source_action.idtag, name=source_action.name, code=str(source_action.code),
            device_idtag=source_action.device_idtag,
            prop=contingency_ops_type_dict[source_action.prop],
            value=source_action.value,
            group=None if source_action.group is None else groups[source_action.group.idtag])
        target = devices.get(source_action.device_idtag, None)
        if target is None:
            pass
        else:
            action.device = target
        gslv_grid.add_remedial_action(action)
