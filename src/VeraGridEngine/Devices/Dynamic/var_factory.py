# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import Union, List, Dict, Any, Tuple
import uuid

from VeraGridEngine.Devices.Parents.editable_device import EditableDevice
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowReferenceType
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, SharedVarReferenceType


def _new_uid() -> int:
    """
    Generate one fresh integer uid.

    :return: New unique integer identifier.
    """
    return uuid.uuid4().int


def find_var_by_persisted_identity(var_dict: Dict[int, Var],
                                   persisted_uid: int | None) -> Var | None:
    """
    Resolve a variable from either stable identity or legacy mutable UID.

    :param var_dict: Variable dictionary keyed by stable identity.
    :param persisted_uid: Identifier read from a persisted property.
    :return: Matching variable or ``None``.
    """
    direct_var: Var | None
    candidate_var: Var

    if persisted_uid is None:
        return None
    else:
        direct_var = var_dict.get(persisted_uid, None)

    if direct_var is not None:
        return direct_var
    else:
        pass

    # Files written before stable references were used store the mutable UID.
    # Keep that format readable while all new writes use non_mutable_uid.
    for candidate_var in var_dict.values():
        if candidate_var.uid == persisted_uid:
            return candidate_var
        else:
            pass

    return None


def build_persisted_identity_lookup(var_dict: Dict[int, Var]) -> Dict[int, Var]:
    """
    Build one constant-time lookup for stable and legacy mutable identities.

    Stable dictionary keys remain authoritative when a mutable UID collides
    with another variable's stable identity. This preserves the current
    connection semantics while avoiding a full dictionary scan for every
    symbolic leaf in legacy expression archives.

    :param var_dict: Variables keyed by their stable non-mutable identity.
    :return: Lookup containing stable identities and non-conflicting mutable UID aliases.
    """
    identity_lookup: Dict[int, Var] = dict(var_dict)
    candidate_var: Var

    for candidate_var in var_dict.values():
        if candidate_var.uid not in identity_lookup:
            identity_lookup[candidate_var.uid] = candidate_var
        else:
            pass

    return identity_lookup


def resolve_connection_vars(source_var: Var | None,
                            target_var: Var | None):
    """
    find variable roles in the connection
    :param source_var:
    :type source_var:
    :param target_var:
    :type target_var:
    :return:
    :rtype:
    """

    if source_var is not None and target_var is not None:
        if target_var.network_conn:
            return source_var, target_var
        else:
            return target_var, source_var
    else:
        return None, None


class Connection:
    """
    Lightweight saved description of one propagated variable connection.
    """
    __slots__ = (
        'non_mutable_uid',
        'name',
        'uid'
    )

    def __init__(self,
                 non_mutable_uid: int,
                 name: str,
                 uid: int) -> None:
        """
        Store the identity required to restore one detached variable.

        :param non_mutable_uid: Stable uid of the connected variable.
        :param name: Variable name to restore after disconnection.
        :param uid: Mutable uid to restore after disconnection.
        :return: None.
        """

        # Preserve the stable symbolic identity used to match the connection
        # entry during later remove operations.
        self.non_mutable_uid = non_mutable_uid
        # Preserve the pre-connection variable name so the symbolic variable
        # returns to its original label when the edge is removed.
        self.name = name
        # Preserve the pre-connection uid so the symbolic variable returns to
        # the exact original identity when the edge is removed.
        self.uid = uid


class VarFactory(EditableDevice):
    """
    VarFactory
    """

    __slots__ = (
        '_var_dict',
        '_const_dict',
        '_diff_var_dict',
        '_vars_info',
        '_references_dict',
        '_vars_references_dict',
        '_vars_connected_dict',

    )

    def __init__(self,
                 idtag: Union[str, None] = "",
                 name: str = "Var Factory",
                 code: str = "",
                 comment: str = "") -> None:
        """
        VarFactory
        :param idtag: String. Element unique identifier
        :param name: String. Contingency name
        :param code: String. Contingency code name
        :param comment: Comment
        """

        EditableDevice.__init__(self,
                                idtag=idtag,
                                code=code,
                                name=name,
                                device_type=DeviceType.VarFactory,
                                comment=comment)

        self._var_dict: Dict[int, Var] = dict()
        self._const_dict: Dict[int, Const] = dict()
        self._diff_var_dict: Dict[int, Var] = dict()
        self._vars_info: Dict[Any, List[Var]] = dict()
        self._references_dict: Dict[str, SharedVarReferenceType] = dict()
        self._vars_references_dict: Dict[int, List[Var]] = dict()
        self._vars_connected_dict = dict()

    @property
    def vars_info(self) -> Dict[Any, List[Var]]:
        return self._vars_info

    def get_vars_to_save(self,
                         dev: Any,
                         names: List[str]) -> List[Var]:
        """
        this function returns a list of variables which names are in names
        :param dev:
        :type dev:
        :param names:
        :type names:
        :return:
        :rtype:
        """
        return [v for v in self._vars_info[dev] if v.name in names]

    def add_var(self,
                name: str,
                reference: VarPowerFlowReferenceType | None = None,
                network_conn: bool = False,
                shared_reference: str | None | SharedVarReferenceType = None,
                non_mutable_uid: int | None = None,
                uid: int | None = None) -> Var:
        """
        Adds a ver to the class
        :param name:
        :param shared_reference:
        :param reference:
        :param network_conn:
        :param non_mutable_uid:
        :param uid:
        :return:
        """

        if isinstance(shared_reference, str):
            if shared_reference not in self._references_dict:
                self.create_reference(shared_reference)
                self._vars_references_dict[self._references_dict[shared_reference].uid] = list()

            v = Var(name=name, shared_reference=self._references_dict[shared_reference], reference=reference,
                    network_conn=network_conn, non_mutable_uid=non_mutable_uid, uid=uid,
                    diff_var=None, base_var=None)
            self.save_var_in_vars_references_dict(v, shared_reference)
            self._var_dict[v.non_mutable_uid] = v
            return v
        else:
            v = Var(name=name, reference=reference, network_conn=network_conn,
                    shared_reference=shared_reference, non_mutable_uid=non_mutable_uid, uid=uid,
                    diff_var=None, base_var=None)
            if shared_reference is not None:
                self.save_var_in_vars_references_dict(v, shared_reference.name)
            self._var_dict[v.non_mutable_uid] = v
            return v

    def add_shared_ref_to_var(self, v: Var, shared_reference: str | SharedVarReferenceType):

        if isinstance(shared_reference, str):
            if shared_reference not in self._references_dict:
                self.create_reference(shared_reference)
                self._vars_references_dict[self._references_dict[shared_reference].uid] = list()

            v.shared_ref = self._references_dict[shared_reference]
            self.save_var_in_vars_references_dict(v, shared_reference)

        else:
            v.shared_ref = shared_reference
            if shared_reference is not None:
                self.save_var_in_vars_references_dict(v, shared_reference.name)

    def save_var_in_vars_references_dict(self, var: Var, reference: str):
        self._vars_references_dict[self._references_dict[reference].uid].append(var)

    def create_reference(self,
                         reference_name: str,
                         uid: int | None = None) -> None:
        """
        Create one shared-variable reference with an optional existing identity.

        :param reference_name: Stable textual reference name.
        :param uid: Existing reference UID, or ``None`` to allocate one.
        :return: None.
        """
        self._references_dict[reference_name] = SharedVarReferenceType(
            name=reference_name,
            uid=uid,
        )
        self._vars_references_dict[self._references_dict[reference_name].uid] = list()

    def merge_editor_var_factory(self, working_var_factory: "VarFactory") -> None:
        """
        Merge the working var factory into this var factory.

        Stable variable and constant identities select the entries replaced by
        the editor objects. Registry lists are updated in place so their device
        and shared-reference ownership remains unchanged. Internal connection
        edges among editor-owned variables are replaced by the final working
        graph, while edges crossing into the rest of the circuit are preserved.

        :param working_var_factory: Private factory containing the accepted editor state.
        :return: None.
        """
        working_vars_by_non_mutable_uid: Dict[int, Var] = dict()
        working_non_mutable_uid: int
        working_var: Var

        for working_non_mutable_uid, working_var in working_var_factory.get_vars_dict().items():
            working_vars_by_non_mutable_uid[working_non_mutable_uid] = working_var

        for working_non_mutable_uid, working_var in working_var_factory.get_diff_var_dict().items():
            working_vars_by_non_mutable_uid[working_non_mutable_uid] = working_var

        # Shared references must belong to the persistent factory after the
        # editor factory is discarded. Existing names remain canonical.
        reference_name: str
        working_reference: SharedVarReferenceType
        persistent_reference: SharedVarReferenceType | None
        for reference_name, working_reference in working_var_factory.get_references_dict().items():
            persistent_reference = self._references_dict.get(reference_name, None)
            if persistent_reference is None:
                persistent_reference = working_reference
                self._references_dict[reference_name] = persistent_reference
                self._vars_references_dict[persistent_reference.uid] = list()
            else:
                pass

        for working_var in working_vars_by_non_mutable_uid.values():
            if working_var.shared_ref is not None:
                persistent_reference = self._references_dict.get(working_var.shared_ref.name, None)
                if persistent_reference is not None:
                    working_var.shared_ref = persistent_reference
                else:
                    raise KeyError(
                        f"Missing persistent shared reference '{working_var.shared_ref.name}'"
                    )
            else:
                pass

        # Replace existing variables and include symbols created in the editor.
        for working_non_mutable_uid, working_var in working_var_factory.get_vars_dict().items():
            self._var_dict[working_non_mutable_uid] = working_var

        for working_non_mutable_uid, working_var in working_var_factory.get_diff_var_dict().items():
            self._diff_var_dict[working_non_mutable_uid] = working_var

        working_const_uid: int
        working_const: Const
        for working_const_uid, working_const in working_var_factory.get_const_dict().items():
            self._const_dict[working_const_uid] = working_const

        # Replace variables held in device registration lists without changing
        # their owners or their established ordering.
        registered_vars: List[Var]
        registered_var_index: int
        registered_var: Var
        replacement_var: Var | None
        for registered_vars in self._vars_info.values():
            for registered_var_index, registered_var in enumerate(registered_vars):
                replacement_var = working_vars_by_non_mutable_uid.get(
                    registered_var.non_mutable_uid,
                    None,
                )
                if replacement_var is not None:
                    registered_vars[registered_var_index] = replacement_var
                else:
                    pass

        # Shared-reference lists require the same object replacement as device
        # lists, while keeping their canonical reference UID keys.
        referenced_vars: List[Var]
        for referenced_vars in self._vars_references_dict.values():
            for registered_var_index, registered_var in enumerate(referenced_vars):
                replacement_var = working_vars_by_non_mutable_uid.get(
                    registered_var.non_mutable_uid,
                    None,
                )
                if replacement_var is not None:
                    referenced_vars[registered_var_index] = replacement_var
                else:
                    pass

        # Include variables assigned to shared references created during the
        # editing session. Stable identities prevent duplicate list entries.
        working_reference_uid: int
        working_referenced_vars: List[Var]
        persistent_referenced_vars: List[Var]
        persistent_referenced_uids: set[int]
        for working_reference_uid, working_referenced_vars in \
                working_var_factory._vars_references_dict.items():
            persistent_referenced_vars = self._vars_references_dict.get(
                working_reference_uid,
                list(),
            )
            persistent_referenced_uids = set()
            for registered_var in persistent_referenced_vars:
                persistent_referenced_uids.add(registered_var.non_mutable_uid)

            for working_var in working_referenced_vars:
                if working_var.non_mutable_uid not in persistent_referenced_uids:
                    persistent_referenced_vars.append(working_var)
                    persistent_referenced_uids.add(working_var.non_mutable_uid)
                else:
                    pass

            self._vars_references_dict[working_reference_uid] = persistent_referenced_vars

        working_scope: set[int] = set(working_vars_by_non_mutable_uid.keys())
        persistent_source_uid: int
        persistent_connections: List[Connection]
        retained_connections: List[Connection]
        persistent_connection: Connection

        # Remove the previous internal subgraph. Cross-model and bus edges keep
        # their stable endpoints and therefore remain valid after replacement.
        for persistent_source_uid, persistent_connections in list(self._vars_connected_dict.items()):
            if persistent_source_uid in working_scope:
                retained_connections = list()
                for persistent_connection in persistent_connections:
                    if persistent_connection.non_mutable_uid in working_scope:
                        pass
                    else:
                        retained_connections.append(persistent_connection)

                if len(retained_connections) > 0:
                    self._vars_connected_dict[persistent_source_uid] = retained_connections
                else:
                    del self._vars_connected_dict[persistent_source_uid]
            else:
                pass

        # Copy the final internal graph, including restoration UID/name metadata.
        working_connections: List[Connection]
        working_connection: Connection
        merged_connections: List[Connection]
        for working_non_mutable_uid, working_connections in working_var_factory.get_connections_dict().items():
            if working_non_mutable_uid in working_scope:
                merged_connections = self._vars_connected_dict.get(
                    working_non_mutable_uid,
                    list(),
                )
                for working_connection in working_connections:
                    if working_connection.non_mutable_uid in working_scope:
                        merged_connections.append(Connection(
                            non_mutable_uid=working_connection.non_mutable_uid,
                            name=working_connection.name,
                            uid=working_connection.uid,
                        ))
                    else:
                        pass

                if len(merged_connections) > 0:
                    self._vars_connected_dict[working_non_mutable_uid] = merged_connections
                else:
                    pass
            else:
                pass

    def get_var(self, uid: int) -> Var | None:
        """
        Gets a Var from the class
        :param uid:
        :return:
        """
        found_var: Var | None = find_var_by_persisted_identity(
            var_dict=self._var_dict,
            persisted_uid=uid,
        )
        if found_var is not None:
            return found_var
        else:
            # Preserve the historical KeyError contract for truly missing
            # variable references after both lookup formats are exhausted.
            return self._var_dict[uid]


    def add_diff_var(self,
                     name: str,
                     reference: VarPowerFlowReferenceType | None = None,
                     network_conn: bool = False,
                     shared_reference: str | None | SharedVarReferenceType = None,
                     non_mutable_uid: int | None = None,
                     uid: int | None = None,
                     diff_var: Var | None = None,
                     base_var: Var | None = None) -> Var:
        """
        Adds a Diff ver to the class
        :param name:
        :param reference:
        :param shared_reference:
        :param non_mutable_uid:
        :param network_conn:
        :param uid:
        :param diff_var:
        :param base_var:
        :return:
        """
        if isinstance(shared_reference, str):
            if shared_reference not in self._references_dict:
                self.create_reference(shared_reference)
                self._vars_references_dict[self._references_dict[shared_reference].uid] = list()

            v = Var(name=name, shared_reference=self._references_dict[shared_reference], reference=reference,
                    network_conn=network_conn, non_mutable_uid=non_mutable_uid, uid=uid,
                    diff_var=diff_var, base_var=base_var)
            self.save_var_in_vars_references_dict(v, shared_reference)
            self._var_dict[v.non_mutable_uid] = v
            self._diff_var_dict[v.non_mutable_uid] = v
            return v
        else:
            v = Var(name=name, reference=reference, network_conn=network_conn,
                    shared_reference=shared_reference, non_mutable_uid=non_mutable_uid, uid=uid,
                    diff_var=diff_var, base_var=base_var)
            self._diff_var_dict[v.non_mutable_uid] = v
            return v

    def get_connection_source_non_mutable_uid(self,
                                              variable_non_mutable_uid: int) -> int:
        """
        Resolve the upstream owner of one connected variable identity.

        The saved connection graph is directional from an incoming source to
        substituted targets. A rename can originate from either endpoint in
        the editor, so it must first walk the reverse relation and then replay
        the existing forward propagation from the canonical source.

        :param variable_non_mutable_uid: Stable identity selected by the user.
        :return: Stable identity of the upstream connection owner.
        """
        current_non_mutable_uid: int = variable_non_mutable_uid
        visited_non_mutable_uids: set[int] = set()
        source_non_mutable_uid: int | None
        owner_non_mutable_uid: int
        connection_list: List[Connection]
        connection: Connection

        while current_non_mutable_uid not in visited_non_mutable_uids:
            visited_non_mutable_uids.add(current_non_mutable_uid)
            source_non_mutable_uid = None

            # Find the unique incoming owner without changing the established
            # source-to-target storage layout used by connect/disconnect.
            for owner_non_mutable_uid, connection_list in self._vars_connected_dict.items():
                for connection in connection_list:
                    if connection.non_mutable_uid == current_non_mutable_uid:
                        source_non_mutable_uid = owner_non_mutable_uid
                        break
                    else:
                        pass

                if source_non_mutable_uid is not None:
                    break
                else:
                    pass

            if source_non_mutable_uid is None:
                return current_non_mutable_uid
            else:
                current_non_mutable_uid = source_non_mutable_uid

        # A malformed cycle has no unique root. Returning the first repeated
        # identity keeps rename propagation finite and consistent with the
        # existing cycle guard in connect_variables_by_uid().
        return current_non_mutable_uid

    def get_diff_var(self, uid: int) -> Var:
        """
        Gets a Diff Var from the class
        :param uid:
        :return:
        """
        found_var: Var | None = find_var_by_persisted_identity(
            var_dict=self._diff_var_dict,
            persisted_uid=uid,
        )
        if found_var is not None:
            return found_var
        else:
            # Preserve the historical KeyError for a genuinely absent entry.
            return self._diff_var_dict[uid]

    def add_const(self,
                  value: float | None = None,
                  uid: int | None = None,
                  name: str = "") -> Const:
        """
        Adds a Cont to the class
        :param value:
        :param uid:
        :param name:
        :return:
        """
        v = Const(value=value, uid=uid, name=name)
        self._const_dict[v.uid] = v
        return v

    def connect_variables_by_uid(self,
                                 var_to_subs_non_mutable_uid: int,
                                 incoming_var_uid: int,
                                 incoming_var_name: str,
                                 visited_non_mutable_uids: set[int] | None = None) -> None:
        """
        Propagate one incoming variable identity through the saved connection graph.

        The connection registry can contain cycles when editor-side EMT models
        reconnect root mapping vars that already alias back into the same live
        symbolic chain. Track visited stable uids during one propagation walk so
        the alias update remains finite even when the graph contains loops.

        :param var_to_subs_non_mutable_uid: Stable uid of the variable to rewrite.
        :param incoming_var_uid: Mutable uid that should be propagated.
        :param incoming_var_name: Variable name that should be propagated.
        :param visited_non_mutable_uids: Stable uids already processed in this walk.
        :return: None.
        """
        next_visited_non_mutable_uids: set[int]
        connection: Connection

        if visited_non_mutable_uids is None:
            next_visited_non_mutable_uids = set()
        else:
            next_visited_non_mutable_uids = visited_non_mutable_uids

        if var_to_subs_non_mutable_uid in next_visited_non_mutable_uids:
            return
        else:
            next_visited_non_mutable_uids.add(var_to_subs_non_mutable_uid)

        if var_to_subs_non_mutable_uid in self._var_dict:
            self._var_dict[var_to_subs_non_mutable_uid].uid = incoming_var_uid
            self._var_dict[var_to_subs_non_mutable_uid].name = incoming_var_name
        elif var_to_subs_non_mutable_uid in self._diff_var_dict:
            # Differential variables are stored in the dedicated diff-variable
            # registry. Updating the wrong dictionary leaves the propagated
            # symbolic identity stale and breaks later validation against the
            # live bus variables.
            self._diff_var_dict[var_to_subs_non_mutable_uid].uid = incoming_var_uid
            self._diff_var_dict[var_to_subs_non_mutable_uid].name = incoming_var_name
        else:
            pass

        # recursivity for previous connected vars
        if var_to_subs_non_mutable_uid in self._vars_connected_dict:
            for connection in self._vars_connected_dict[var_to_subs_non_mutable_uid]:
                self.connect_variables_by_uid(connection.non_mutable_uid,
                                              incoming_var_uid,
                                              incoming_var_name,
                                              next_visited_non_mutable_uids)
        else:
            pass

    def _find_connection(
            self,
            incoming_non_mutable_uid: int,
            substituted_non_mutable_uid: int,
    ) -> Connection | None:
        """
        Return one saved factory edge and remove duplicate reopen records.

        :param incoming_non_mutable_uid: Stable identity owning the edge list.
        :param substituted_non_mutable_uid: Stable identity of the target variable.
        :return: Existing connection record, or ``None``.
        """
        connection_graph: Dict[int, List[Connection]] = self.get_connections_dict()
        connections: List[Connection] | None = connection_graph.get(incoming_non_mutable_uid, None)
        first_match: Connection | None = None
        deduplicated: List[Connection] = list()
        connection_record: Connection

        if connections is None:
            return None
        else:
            pass

        # Reopening is idempotent: retain the first matching edge and remove
        # duplicate records left by older restore cycles.
        for connection_record in connections:
            if connection_record.non_mutable_uid == substituted_non_mutable_uid:
                if first_match is None:
                    first_match = connection_record
                    deduplicated.append(connection_record)
                else:
                    pass
            else:
                deduplicated.append(connection_record)

        if len(deduplicated) != len(connections):
            connections[:] = deduplicated
        else:
            pass

        return first_match

    def register_symbolic_connection(self,
                                     source_var: Var | None,
                                     target_var: Var | None) -> None:
        """
        function to create a symbolic connection between two variables
        :param source_var:
        :type source_var:
        :param target_var:
        :type target_var:
        :return:
        :rtype:
        """

        var_to_substitute, incoming_var = resolve_connection_vars(
            source_var=source_var,
            target_var=target_var
        )

        if var_to_substitute is None or incoming_var is None:
            return
        else:
            pass

        # avoid connecting a variable with itself
        if var_to_substitute.non_mutable_uid == incoming_var.non_mutable_uid:
            return
        else:
            pass

        existing_connection: Connection | None = self._find_connection(
            incoming_non_mutable_uid=incoming_var.non_mutable_uid,
            substituted_non_mutable_uid=var_to_substitute.non_mutable_uid,
        )

        # Add the graph edge only once, but replay it for every working-copy rebuild.
        if existing_connection is None:
            if incoming_var.network_conn:
                self.connect_var_net_conn_upstream(var_to_substitute, incoming_var)
            else:
                self.add_connection(var_to_substitute, incoming_var)
        else:
            pass

    def unregister_symbolic_connection(
            self,
            source_var: Var | None,
            target_var: Var | None,
    ) -> None:
        """
        Remove the symbolic connection between variables that will no longer be connected by a graphical connection item.
        This function also propagates disconnection to upstream and downstream variables

        :param source_var: Target variable detached from the source.
        :param target_var: Source variable owning the connection record.
        :return: None.
        """
        var_to_disconnect: Var | None = None
        outgoing_var: Var | None = None

        if source_var is not None and target_var is not None:
            if target_var.network_conn:
                var_to_disconnect = source_var
                outgoing_var = target_var
            else:
                var_to_disconnect = target_var
                outgoing_var = source_var
        else:
            pass

        if var_to_disconnect is not None and outgoing_var is not None:

            # if the two variables are the same, no need to disconnect
            if var_to_disconnect.non_mutable_uid == outgoing_var.non_mutable_uid:
                return

            # VarFactory restores its canonical target before deleting the edge.
            if outgoing_var.network_conn:
                self.disconnect_var_net_conn_upstream(var_to_disconnect, outgoing_var=outgoing_var)
            else:
                self.remove_connection(var_to_disconnect, outgoing_var)

    def add_connection(self,
                       var_to_subs: Var,
                       incoming_var: Var) -> None:
        """
        Register and propagate one directed symbolic-variable connection.

        Reopening an editor and running dynamic preflight can request the same
        bus-to-device edge repeatedly. Keep one restoration record per stable
        target while still replaying the current incoming UID and name.

        :param var_to_subs: Target variable whose effective identity is replaced.
        :param incoming_var: Source variable providing the effective identity.
        :return: None.
        """
        connections: List[Connection]
        existing_connection: Connection

        if incoming_var.non_mutable_uid not in self._vars_connected_dict:
            self._vars_connected_dict[incoming_var.non_mutable_uid] = list()
        else:
            pass

        connections = self._vars_connected_dict[incoming_var.non_mutable_uid]
        for existing_connection in connections:
            # if connection already exists
            if existing_connection.non_mutable_uid == var_to_subs.non_mutable_uid:
                self.connect_variables_by_uid(var_to_subs.non_mutable_uid,
                                              incoming_var.uid,
                                              incoming_var.name)
                return
            else:
                pass

        connection = Connection(var_to_subs.non_mutable_uid, var_to_subs.name, var_to_subs.uid)
        connections.append(connection)
        self.connect_variables_by_uid(connection.non_mutable_uid, incoming_var.uid, incoming_var.name)

    def add_network_connection(self,
                               var_to_subs: Var,
                               incoming_var: Var,
                               connection_to_add: Connection | None = None) -> None:
        """
        Register and propagate one directed symbolic-variable connection.

        Reopening an editor and running dynamic preflight can request the same
        bus-to-device edge repeatedly. Keep one restoration record per stable
        target while still replaying the current incoming UID and name.

        :param var_to_subs: Target variable whose effective identity is replaced.
        :param incoming_var: Source variable providing the effective identity.
        :param connection_to_add:
        :return: None.
        """
        connections: List[Connection]
        existing_connection: Connection

        if incoming_var.non_mutable_uid not in self._vars_connected_dict:
            self._vars_connected_dict[incoming_var.non_mutable_uid] = list()
        else:
            pass

        connections = self._vars_connected_dict[incoming_var.non_mutable_uid]
        for existing_connection in connections:
            # if connection already exists
            if existing_connection.non_mutable_uid == var_to_subs.non_mutable_uid:
                self.connect_variables_by_uid(var_to_subs.non_mutable_uid,
                                              incoming_var.uid,
                                              incoming_var.name)
                return
            else:
                pass

        # propagate upstream
        if connection_to_add is not None:
            connections.append(connection_to_add)
            self.connect_variables_by_uid(connection_to_add.non_mutable_uid, incoming_var.uid, incoming_var.name)

        else:
            connection = Connection(var_to_subs.non_mutable_uid, var_to_subs.name, var_to_subs.uid)
            connections.append(connection)
            self.connect_variables_by_uid(connection.non_mutable_uid, incoming_var.uid, incoming_var.name)

        var_to_subs._network_conn = True

    def remove_connection(self,
                          var_to_disconnect: Var,
                          outgoing_var: Var) -> None:
        """
        Remove one saved variable connection if it still exists.

        :param var_to_disconnect: Variable that should be detached from the outgoing source.
        :param outgoing_var: Source variable that owns the propagated connection list.
        :return: None.
        """
        connections: List[Connection] | None = self._vars_connected_dict.get(outgoing_var.non_mutable_uid, None)

        # The editor can request a connection removal after the backing
        # connection registry was already pruned by a previous editor action.
        # In that case there is nothing left to remove and the state is already
        # consistent, so the function must exit quietly.
        if connections is None:
            return
        else:
            pass

        for connection_index, connection in enumerate(connections):
            # Restore the disconnected variable identity before removing the
            # propagated connection record so downstream references stop using
            # the outgoing variable metadata.
            if connection.non_mutable_uid == var_to_disconnect.non_mutable_uid:
                del connections[connection_index]

                if not var_to_disconnect.network_conn:
                    self.connect_variables_by_uid(connection.non_mutable_uid, connection.uid, connection.name)

                # Drop the now-empty registry entry to keep the connection map
                # aligned with the actual set of active propagated links.
                if len(connections) == 0:
                    del self._vars_connected_dict[outgoing_var.non_mutable_uid]
                else:
                    pass
                return
            else:
                pass

        # No matching propagated connection was present. The requested state is
        # therefore already reached and no extra action is necessary.
        return

    def add_connections(self,
                        vars_to_subs: List[Var],
                        incoming_vars: List[Var]):
        """
        create symbolic connections between two lists of variables
        :param vars_to_subs:
        :type vars_to_subs:
        :param incoming_vars:
        :type incoming_vars:
        :return:
        :rtype:
        """
        pairs: List[Tuple[Var, Var]] = list(zip(vars_to_subs, incoming_vars))
        var_to_subs: Var
        incoming_var: Var
        for var_to_subs, incoming_var in pairs:
            self.add_connection(var_to_subs, incoming_var)

    def find_var_conn_upstream(self, var: Var) -> tuple[Var, Connection] | tuple[None, None]:
        """
       function that returns an upstream connected variable for var
        :param var:
        :return:
        :rtype:
        """

        # find if a variable already ate the concerning variable
        var_to_connect_upstream: Var | None = None
        connection_found: Connection | None = None
        for key, value in self._vars_connected_dict.items():
            for connection in value:
                if connection.non_mutable_uid == var.non_mutable_uid:
                    connection_found = connection
                    if key in self._var_dict:
                        var_to_connect_upstream = self._var_dict[key]
                    elif key in self._diff_var_dict:
                        var_to_connect_upstream = self._diff_var_dict[key]
        if connection_found is not None and var_to_connect_upstream is not None:
            return var_to_connect_upstream, connection_found
        else:
            return None, None

    def _find_several_var_conn_upstream(self, var: Var) -> List[Var]:
        """
       function that returns an upstream connected variable for var
        :param var:
        :return:
        :rtype:
        """

        # find if a variable already ate the concerning variable
        vars_connected_upstream: List[Var] = list()
        for key, value in self._vars_connected_dict.items():
            for connection in value:
                if connection.non_mutable_uid == var.non_mutable_uid:
                    if key in self._var_dict:
                        var_to_connect_upstream = self._var_dict[key]
                    else:
                        var_to_connect_upstream = self._diff_var_dict[key]
                    vars_connected_upstream.append(var_to_connect_upstream)
        return vars_connected_upstream

    def connect_var_net_conn_upstream(self,
                                      var_to_subs,
                                      net_conn_in):
        """
        function to propagate a network connection upstream
        :param var_to_subs:
        :type var_to_subs:
        :param net_conn_in:
        :type net_conn_in:
        :return:
        :rtype:
        """
        # find vars connected upstream
        var_upstream, connection_upstream = self.find_var_conn_upstream(var_to_subs)
        self.add_network_connection(var_to_subs, net_conn_in, connection_upstream)

        if var_upstream is not None:
            self.connect_var_net_conn_upstream(var_upstream, net_conn_in)
        else:
            pass

    def disconnect_var_net_conn_upstream(self,
                                         var_to_disconnect,
                                         outgoing_var: Var | None = None,
                                         net_conn_orig: Var | None = None):
        """
        method to eliminate net connection and restore var
        :return:
        :rtype:
        """
        top_stream_conn: Connection | None = None
        save_connections: List[Connection] = list()

        # find downstream end var
        if net_conn_orig is None and outgoing_var is not None:
            net_conn_orig = self._find_last_var_downstream(var_to_disconnect)
            if net_conn_orig is None:
                net_conn_orig = outgoing_var
            for conn in self._vars_connected_dict[net_conn_orig.non_mutable_uid]:
                save_connections.append(conn)
            self.remove_connection(var_to_disconnect, outgoing_var)
        elif net_conn_orig is not None:
            for conn in self._vars_connected_dict[net_conn_orig.non_mutable_uid]:
                save_connections.append(conn)
            self.remove_connection(var_to_disconnect, net_conn_orig)

        # find vars connected upstream
        var_upstream, connection_upstream = self.find_var_conn_upstream(var_to_disconnect)
        if var_upstream is not None:
            self.disconnect_var_net_conn_upstream(var_upstream, net_conn_orig=net_conn_orig)
        else:
            # we have found the last var upstream, so we have to reconnect A --> B --> C

            # first find info from the top upstream found var (A)
            for connection in save_connections:
                if connection.non_mutable_uid == var_to_disconnect.non_mutable_uid:
                    top_stream_conn = connection
            if top_stream_conn is not None:
                self.connect_variables_by_uid(top_stream_conn.non_mutable_uid, top_stream_conn.uid,
                                              top_stream_conn.name)
                # restore net conn to False
                var_to_disconnect._network_conn = False
                self._recover_connections_downstream(var_to_disconnect)
            else:
                pass

    def _find_last_var_downstream(
            self,
            var: Var,
            upstream_var: Var | None = None,
            visited_non_mutable_uids: set[int] | None = None,
    ) -> Var | None:
        """
        Find the network variable connected at the downstream end.

        The search advances through downstream variables marked as network
        connections. Once the end is reached, it selects the upstream variable
        different from the variable used to enter the current node.

        :param var: Current variable being inspected.
        :param upstream_var: Previous variable in the downstream traversal.
        :param visited_non_mutable_uids: Stable variable identities already inspected.
        :return: Network variable found at the end, or ``None``.
        """
        current_visited_non_mutable_uids: set[int]

        # Share one stable-identity set throughout the recursive search so a
        # malformed cyclic connection graph cannot revisit the same variable.
        if visited_non_mutable_uids is None:
            current_visited_non_mutable_uids = set()
        else:
            current_visited_non_mutable_uids = visited_non_mutable_uids

        if var.non_mutable_uid in current_visited_non_mutable_uids:
            return None
        else:
            current_visited_non_mutable_uids.add(var.non_mutable_uid)

        downstream_non_mutable_uids: List[int] | None = self._find_downstream_vars(var)

        # If the initial variable is already the downstream end, the caller already
        # has the network variable in outgoing_var.
        if not downstream_non_mutable_uids:
            if upstream_var is None:
                return None
            else:
                upstream_vars: List[Var] = self._find_several_var_conn_upstream(var)
                var_found: Var

                # At the downstream end, discard the variable from which the
                # traversal arrived. The remaining owner is the network variable.
                for var_found in upstream_vars:
                    if var_found.non_mutable_uid != upstream_var.non_mutable_uid:
                        return var_found
                    else:
                        pass

                return None
        else:
            downstream_non_mutable_uid: int
            var_downstream: Var | None
            network_var: Var | None

            # Continue downstream until a terminal variable determines the result.
            for downstream_non_mutable_uid in downstream_non_mutable_uids:
                var_downstream = self._var_dict.get(downstream_non_mutable_uid, None)
                if var_downstream is None:
                    var_downstream = self._diff_var_dict.get(
                        downstream_non_mutable_uid,
                        None,
                    )
                else:
                    pass

                if var_downstream is not None:
                    if var_downstream.network_conn:
                        network_var = self._find_last_var_downstream(
                            var=var_downstream,
                            upstream_var=var,
                            visited_non_mutable_uids=current_visited_non_mutable_uids,
                        )
                        if network_var is not None:
                            return network_var
                        else:
                            pass
                    else:
                        pass
                else:
                    pass

            return None

    def _recover_connections_downstream(self,
                                        var: Var,
                                        only_net_conn: bool = False):
        """
        function that reconnects variables after removing network connections
        :param var:
        :type var:
        :return:
        :rtype:
        """
        # find downstream_vars
        downstream_vars_nun_mutable_uid = self._find_downstream_vars(var)
        if downstream_vars_nun_mutable_uid:
            for var_non_mut_uid in downstream_vars_nun_mutable_uid:
                if not only_net_conn:
                    self.connect_variables_by_uid(var_non_mut_uid, var.uid, var.name)
                # restore net conn to False
                if var_non_mut_uid in self._var_dict:
                    var_to_connect_upstream = self._var_dict[var_non_mut_uid]
                else:
                    var_to_connect_upstream = self._diff_var_dict[var_non_mut_uid]
                var_to_connect_upstream._network_conn = False
                self._recover_connections_downstream(var_to_connect_upstream, only_net_conn=True)
        else:
            pass

    def _find_downstream_vars(self, var: Var) -> List[int] | None:
        """
        function that finds first level downstream vars fo a var
        :param var:
        :type var:
        :return:
        :rtype:
        """

        downstream_vars_nun_mutable_uid: List[int] = list()
        connections: List[Connection] | None = self._vars_connected_dict.get(var.non_mutable_uid, None)
        if connections is not None:
            for connection in connections:
                downstream_vars_nun_mutable_uid.append(connection.non_mutable_uid)
            return downstream_vars_nun_mutable_uid
        else:
            return None

    def get_const(self, uid: int) -> Const:
        """
        Gets a Cont from the class
        :param uid:
        :return:
        """
        return self._const_dict[uid]

    def get_const_dict(self) -> Dict[int, Const]:
        """

        :return:
        """
        return self._const_dict

    def get_vars_dict(self) -> Dict[int, Var]:
        """

        :return:
        """
        return self._var_dict

    def get_diff_var_dict(self) -> Dict[int, Var]:
        """

        :return:
        """
        return self._diff_var_dict

    def get_references_dict(self) -> Dict[str, SharedVarReferenceType]:
        """

        :return:
        :rtype:
        """
        return self._references_dict

    def get_connections_dict(self) -> Dict[int, List[Connection]]:
        """

        :return:
        :rtype:
        """
        return self._vars_connected_dict

    def get_unique_template_name(self, name: str) -> str:
        """Return one template name that does not collide with existing symbols.

        Some EMT builders reserve their symbolic namespace at the template level
        before any variables are created. When the requested name is still free,
        this helper returns it unchanged. Otherwise, it appends an integer suffix.

        :param name: Requested template name.
        :return: Collision-free template name.
        """

        existing_names = set(v.name for v in self._var_dict.values())
        existing_names.update(v.name for v in self._diff_var_dict.values())

        if name not in existing_names:
            return name
        else:
            index: int = 1
            candidate: str = f"{name}_{index}"

            while candidate in existing_names:
                index += 1
                candidate = f"{name}_{index}"

            return candidate

    def parse_const_dict(self,
                         data_list: List[Dict[str, Any]]):
        """

        :param data_list:
        :return:
        """
        obj_dict: Dict[int, Const] = dict()
        for data in data_list:

            t = data["type"]
            if t == "Const":
                if data.get("kind") == "complex":
                    arr = data["value"]
                    obj = Const(value=complex(arr[0], arr[1]),
                                uid=data["uid"])
                else:
                    obj = Const(value=data["value"],
                                uid=data["uid"])

            else:
                raise ValueError(f"Unhandled symbolic primitive {t}")

            # at this point we can store the object
            obj_dict[obj.uid] = obj

        self._const_dict = obj_dict

    def parse_var_dict(self, data_list: List[Dict[str, Any]]):
        """

        :param data_list:
        :return:
        """
        obj_dict: Dict[int, Var] = dict()
        for data in data_list:
            data_tpe: Any = data.get("type", None)
            if data_tpe != "Var":
                continue
            else:
                pass

            # Older persisted symbolic models may not store the power-flow
            # reference field, so keep loading those files by defaulting to None.
            key_ref = None
            ref_data_dict: Any = data.get("shared_ref", None)
            if ref_data_dict is not None:
                ref_data_name = ref_data_dict.get("name", None)
                ref_data_uid = ref_data_dict.get("uid", None)
                key_ref: SharedVarReferenceType | None

                if ref_data_name is not None and ref_data_uid is not None:
                    if ref_data_name not in self._references_dict:
                        key_ref = SharedVarReferenceType(ref_data_name, ref_data_uid)
                        if key_ref is not None:
                            self._references_dict[ref_data_name] = key_ref
                    else:
                        key_ref = self._references_dict[ref_data_name]
                else:
                    key_ref = None

            ref_power_flow_data: Any = data.get("ref", None)
            key_power_flow_ref: VarPowerFlowReferenceType | None

            if ref_power_flow_data is not None:
                key_power_flow_ref = VarPowerFlowReferenceType(ref_power_flow_data)
            else:
                key_power_flow_ref = None

            # obj = Var(name=data["name"], uid=data["uid"], shared_reference=key_ref, reference=key_power_flow_ref, non_mutable_uid=data["non_mutable_uid"])
            obj_name: Any = data.get("name", "")
            obj_uid: Any = data.get("uid", None)
            obj_non_mutable_uid: Any = data.get("non_mutable_uid", None)

            # Legacy symbolic entries can miss one of the identity keys. Reuse
            # the surviving identifier so the rest of the dynamic block payload
            # can still be reconstructed.
            if obj_uid is None and obj_non_mutable_uid is None:
                continue
            else:
                pass

            if obj_uid is None:
                obj_uid = obj_non_mutable_uid
            else:
                pass

            if obj_non_mutable_uid is None:
                obj_non_mutable_uid = obj_uid
            else:
                pass

            obj = Var(name=obj_name, uid=obj_uid, shared_reference=key_ref, reference=key_power_flow_ref,
                      non_mutable_uid=obj_non_mutable_uid)
            if ref_data_dict is not None:
                ref_data_uid = ref_data_dict.get("uid", None)
                if ref_data_uid is not None:
                    if ref_data_uid in self._vars_references_dict:
                        self._vars_references_dict[ref_data_uid].append(obj)
                    else:
                        self._vars_references_dict[ref_data_uid] = list()
                        self._vars_references_dict[ref_data_uid].append(obj)

            # at this point we can store the object
            obj_dict[obj.non_mutable_uid] = obj

        self._var_dict = obj_dict

    def parse_diff_var_dict(self,
                            data_list: List[Dict[str, Any]]) -> None:
        """
        Parse persisted differential symbolic variables into the factory.

        The loader must rebuild each differential variable using the exact
        symbolic metadata stored in the ``.veragrid`` payload. In particular,
        the power-flow reference has to be converted back to the
        ``VarPowerFlowReferenceType`` enum so downstream EMT connection logic
        can distinguish branch terminal references such as ``vf_A`` and
        ``vt_A`` from bus references such as ``v_A``.

        :param data_list: Serialized differential variable records.
        :return: None.
        """
        obj_dict: Dict[int, Var] = dict()
        for data in data_list:
            data_tpe: Any = data.get("type", None)
            if data_tpe != "DiffVar":
                continue
            else:
                pass

            """
            lst.append({
                    "type": "DiffVar",
                    "name": expr.name,
                    "uid": expr.uid,
                    "base_var": _expr_to_dict(expr=expr.base_var, obj_dict=obj_dict),
                })
            """
            # Recover the base variable first because differential variables
            # are linked to the already reconstructed algebraic/differential
            # chain. This preserves the original derivative hierarchy.
            base_var_uid: Any = data.get("base_var", None)
            base_var: Var | None = find_var_by_persisted_identity(
                var_dict=self._var_dict,
                persisted_uid=base_var_uid,
            )
            if base_var is None:
                base_var = find_var_by_persisted_identity(
                    var_dict=self._diff_var_dict,
                    persisted_uid=base_var_uid,
                )
            else:
                pass
            if base_var is None:
                base_var = find_var_by_persisted_identity(
                    var_dict=obj_dict,
                    persisted_uid=base_var_uid,
                )
            else:
                pass

            if base_var is None:
                continue
            else:
                pass

            # Older persisted symbolic models may not store the power-flow
            # reference field on differential variables either.
            key_ref: SharedVarReferenceType | None = None
            ref_data_dict: Any = data.get("shared_ref", None)
            if ref_data_dict is not None:
                ref_data_name = ref_data_dict.get("name", None)
                ref_data_uid = ref_data_dict.get("uid", None)

                if ref_data_name is not None and ref_data_uid is not None:
                    if ref_data_name not in self._references_dict:
                        key_ref = SharedVarReferenceType(ref_data_name, ref_data_uid)
                        if key_ref is not None:
                            self._references_dict[ref_data_name] = key_ref
                        else:
                            pass
                    else:
                        key_ref = self._references_dict[ref_data_name]
                else:
                    key_ref = None
            else:
                pass

            # Convert the persisted textual reference back to the enum object.
            # Keeping the enum identity is required so EMT topology validation
            # can still recognize branch-side references after reopening files.
            reference_power_flow_data: Any = data.get("ref", None)
            reference_power_flow: VarPowerFlowReferenceType | None
            if reference_power_flow_data is not None:
                reference_power_flow = VarPowerFlowReferenceType(reference_power_flow_data)
            else:
                reference_power_flow = None

            obj_name: Any = data.get("name", "")
            obj_uid: Any = data.get("uid", None)
            if obj_uid is None:
                obj_uid = data.get("non_mutable_uid", None)
            else:
                pass

            if obj_uid is None:
                continue
            else:
                pass

            obj = Var(name=obj_name,
                      uid=obj_uid,
                      non_mutable_uid=data.get("non_mutable_uid", obj_uid),
                      base_var=base_var,
                      shared_reference=key_ref,
                      reference=reference_power_flow)

            if ref_data_dict is not None:
                ref_data_uid = ref_data_dict.get("uid", None)
                if ref_data_uid is not None:
                    if ref_data_uid in self._vars_references_dict:
                        self._vars_references_dict[ref_data_uid].append(obj)
                    else:
                        self._vars_references_dict[ref_data_uid] = list()
                        self._vars_references_dict[ref_data_uid].append(obj)
                else:
                    pass
            else:
                pass

            # at this point we can store the object
            obj_dict[obj.non_mutable_uid] = obj

        self._diff_var_dict = obj_dict

    def parse_references_dict(self, datalist: List[Dict[str, Any]]):
        """
        Parse references list into _references_dict and _vars_references_dict.

        :param datalist: List of dicts with "type", "name", "uid" for share_reference.
        :return:
        """
        for data in datalist:
            if data["type"] == "share_reference":
                ref = SharedVarReferenceType(name=data["name"], uid=data["uid"])
                self._references_dict[data["name"]] = ref
                self._vars_references_dict[ref.uid] = list()

    def parse_connections_dict(self, datalist: Dict[int, List[Any]]) -> None:
        """
        Parse serialized connections and replay their runtime alias state.

        The saved connection table stores the graph that links one incoming
        variable to one or more substituted variables through their stable
        non-mutable identities. Rebuilding only the graph is not sufficient for
        the runtime symbolic system, because fresh GUI-created models also apply
        UID/name aliasing immediately when the connection is created. The load
        path must therefore reconstruct the graph first and then replay the same
        alias propagation so reopened symbolic models behave like newly created
        ones.

        :param datalist: List of dicts with block_uid -> list of connection dicts.
        :return: None.
        """
        uid_key: int
        connections_list: List[Any]
        conn_data: Any
        for uid, connections_list in datalist.items():
            uid_key = int(uid)

            if uid_key not in self._vars_connected_dict:
                self._vars_connected_dict[uid_key] = list()
            else:
                pass

            for conn_data in connections_list:
                conn_tpe: Any = conn_data.get("type", None)
                if conn_tpe == "Connection":
                    conn_non_mutable_uid: Any = conn_data.get("non_mutable_uid", None)
                    conn_name: Any = conn_data.get("name", "")
                    conn_uid: Any = conn_data.get("uid", None)
                    if conn_non_mutable_uid is None or conn_uid is None:
                        continue
                    else:
                        pass

                    conn: Connection = Connection(
                        non_mutable_uid=conn_non_mutable_uid,
                        name=conn_name,
                        uid=conn_uid
                    )
                    self._vars_connected_dict[uid_key].append(conn)
                else:
                    pass

        # Replay the alias propagation only after the full graph has been
        # reconstructed. This mirrors the live connection workflow while also
        # ensuring recursive downstream links can be traversed during replay.
        incoming_non_mutable_uid: int
        connection_list: List[Connection]
        connection: Connection
        for incoming_non_mutable_uid, connection_list in self._vars_connected_dict.items():
            if incoming_non_mutable_uid in self._var_dict:
                incoming_var: Var | None = self._var_dict[incoming_non_mutable_uid]
            elif incoming_non_mutable_uid in self._diff_var_dict:
                incoming_var = self._diff_var_dict[incoming_non_mutable_uid]
            else:
                incoming_var = None

            if incoming_var is not None:
                for connection in connection_list:
                    self.connect_variables_by_uid(
                        connection.non_mutable_uid,
                        incoming_var.uid,
                        incoming_var.name,
                    )
            else:
                pass

    def register_var(self,
                     dev: Any,
                     var: Var):

        """
        Associate a variable with a device
        :param dev: Device
        :param var: Variable
        """

        var_list = self._vars_info.get(dev, None)

        if var_list is None:
            self._vars_info[dev] = [var]
        else:
            var_list.append(var)
