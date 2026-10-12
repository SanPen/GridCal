# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Resolve mapped RMS device powers into topology-owned bus balances.

Signal wiring is intentionally absent from this module. Each declaration says
which symbolic P/Q variable belongs to a physical terminal, and the assigned
VeraGrid device supplies the bus that owns the resulting nodal injection.
"""

from VeraGridEngine.basic_structures import BoolVec, ObjVec
from VeraGridEngine.enumerations import VarPowerFlowReferenceType
from VeraGridEngine.Utils.Symbolic.block import (
    Block,
)
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var


class RmsMappedPowerEntry:
    """One normalized mapped-power terminal owned by static topology."""

    __slots__ = (
        "bus_index", "sign", "active_reference", "reactive_reference",
        "active_power", "reactive_power",
    )

    def __init__(
            self,
            bus_index: int,
            sign: float,
            active_reference: VarPowerFlowReferenceType | None,
            reactive_reference: VarPowerFlowReferenceType | None,
            active_power: Var | None,
            reactive_power: Var | None,
    ) -> None:
        """Store the mapped quantities and their static terminal ownership.

        :param bus_index: Physical bus owning this terminal.
        :param sign: Sign used when adding the terminal power to its bus.
        :param active_reference: Canonical active power reference, if present.
        :param reactive_reference: Canonical reactive power reference, if present.
        :param active_power: Symbolic active power variable, if present.
        :param reactive_power: Symbolic reactive power variable, if present.
        :return: None.
        """
        self.bus_index: int = bus_index
        self.sign: float = sign
        self.active_reference: VarPowerFlowReferenceType | None = active_reference
        self.reactive_reference: VarPowerFlowReferenceType | None = reactive_reference
        self.active_power: Var | None = active_power
        self.reactive_power: Var | None = reactive_power


def _resolve_mapped_power(
        model: Block,
        reference: VarPowerFlowReferenceType,
) -> Var | None:
    """Resolve one mapped terminal power only when it is a symbolic variable.

    :param model: Dynamic block declaring the terminal reference.
    :param reference: Canonical terminal power reference to resolve.
    :return: Mapped variable, or None when no variable is declared.
    """
    if reference in model.external_mapping:
        value: Expr = model.E(reference)
        if isinstance(value, Var):
            return value
        else:
            return None
    else:
        return None


def resolve_rms_mapped_power_references(
        model: Block,
        bus_from_index: int | None = None,
        bus_to_index: int | None = None,
        bus_from_is_dc: bool | None = None,
        bus_to_is_dc: bool | None = None,
        bus_index: int | None = None,
        bus_is_dc: bool | None = None,
        ignore_dc_from_reactive: bool = False,
) -> list[RmsMappedPowerEntry]:
    """Normalize canonical P/Q mappings against static-device topology."""
    p: Var | None = _resolve_mapped_power(model, VarPowerFlowReferenceType.P)
    q: Var | None = _resolve_mapped_power(model, VarPowerFlowReferenceType.Q)
    pf: Var | None = _resolve_mapped_power(model, VarPowerFlowReferenceType.Pf)
    qf: Var | None = _resolve_mapped_power(model, VarPowerFlowReferenceType.Qf)
    pt: Var | None = _resolve_mapped_power(model, VarPowerFlowReferenceType.Pt)
    qt: Var | None = _resolve_mapped_power(model, VarPowerFlowReferenceType.Qt)
    has_bus_mapping = p is not None or q is not None
    has_branch_mapping = any(value is not None for value in (pf, qf, pt, qt))
    if has_bus_mapping and has_branch_mapping:
        raise ValueError("RMS model mixes one-terminal and two-terminal power references")
    else:
        pass

    if has_bus_mapping:
        if bus_index is None or bus_is_dc is None:
            raise ValueError("RMS bus terminal requires one-terminal device topology")
        else:
            pass
        if q is not None and bus_is_dc:
            raise ValueError("RMS terminal declares reactive power on a DC bus")
        else:
            pass
        return [RmsMappedPowerEntry(
            bus_index=bus_index,
            sign=1.0,
            active_reference=VarPowerFlowReferenceType.P if p is not None else None,
            reactive_reference=VarPowerFlowReferenceType.Q if q is not None else None,
            active_power=p,
            reactive_power=q,
        )]
    else:
        pass

    result: list[RmsMappedPowerEntry] = list()
    if pf is not None or qf is not None:
        if bus_from_index is None or bus_from_is_dc is None:
            raise ValueError("RMS from terminal requires two-terminal device topology")
        else:
            pass
        if qf is not None and bus_from_is_dc:
            if ignore_dc_from_reactive:
                qf = None
            else:
                raise ValueError("RMS terminal declares reactive power on a DC bus")
        else:
            pass
        result.append(RmsMappedPowerEntry(
            bus_index=bus_from_index,
            sign=-1.0,
            active_reference=VarPowerFlowReferenceType.Pf if pf is not None else None,
            reactive_reference=VarPowerFlowReferenceType.Qf if qf is not None else None,
            active_power=pf,
            reactive_power=qf,
        ))
    else:
        pass
    if pt is not None or qt is not None:
        if bus_to_index is None or bus_to_is_dc is None:
            raise ValueError("RMS to terminal requires two-terminal device topology")
        else:
            pass
        if qt is not None and bus_to_is_dc:
            raise ValueError("RMS terminal declares reactive power on a DC bus")
        else:
            pass
        result.append(RmsMappedPowerEntry(
            bus_index=bus_to_index,
            sign=-1.0,
            active_reference=VarPowerFlowReferenceType.Pt if pt is not None else None,
            reactive_reference=VarPowerFlowReferenceType.Qt if qt is not None else None,
            active_power=pt,
            reactive_power=qt,
        ))
    else:
        pass
    return result


def _add_terminal_balance_value(
        balance: ObjVec,
        balance_used: BoolVec,
        bus_index: int,
        value: Expr,
) -> bool:
    """Add one symbolic contribution to a preallocated nodal balance.

    :param balance: Preallocated symbolic balance array.
    :param balance_used: Flags identifying initialized balance entries.
    :param bus_index: Network bus index selected from device topology.
    :param value: Symbolic contribution to add.
    :return: Whether at least one mapped power was assembled.
    """
    if balance_used[bus_index]:
        balance[bus_index] += value
    else:
        balance[bus_index] = value
        balance_used[bus_index] = True


def assemble_rms_mapped_power_references(
        model: Block,
        active_power_balance: ObjVec,
        active_power_balance_used: BoolVec,
        reactive_power_balance: ObjVec,
        reactive_power_balance_used: BoolVec,
        bus_from_index: int | None = None,
        bus_to_index: int | None = None,
        bus_from_is_dc: bool | None = None,
        bus_to_is_dc: bool | None = None,
        bus_index: int | None = None,
        bus_is_dc: bool | None = None,
        ignore_dc_from_reactive: bool = False,
) -> bool:
    """Assemble mapped RMS powers using topology supplied by the static device.

    ``P``/``Q`` belong to a one-terminal device bus, ``Pf``/``Qf`` to the
    physical from side, and ``Pt``/``Qt`` to the physical to side.  The
    reference type therefore supplies the dynamic quantity semantics while
    the owning static device remains the sole source of terminal topology.

    :return: Whether at least one mapped power was assembled.
    """
    assembled = False
    entries = resolve_rms_mapped_power_references(
        model=model,
        bus_from_index=bus_from_index,
        bus_to_index=bus_to_index,
        bus_from_is_dc=bus_from_is_dc,
        bus_to_is_dc=bus_to_is_dc,
        bus_index=bus_index,
        bus_is_dc=bus_is_dc,
        ignore_dc_from_reactive=ignore_dc_from_reactive,
    )
    for entry in entries:
        if entry.active_power is not None:
            _add_terminal_balance_value(
                balance=active_power_balance,
                balance_used=active_power_balance_used,
                bus_index=entry.bus_index,
                value=entry.sign * entry.active_power,
            )
            assembled = True
        else:
            pass
        if entry.reactive_power is not None:
            _add_terminal_balance_value(
                balance=reactive_power_balance,
                balance_used=reactive_power_balance_used,
                bus_index=entry.bus_index,
                value=entry.sign * entry.reactive_power,
            )
            assembled = True
        else:
            pass
    return assembled


def convert_rms_ac_power_balance_to_current_balance(
        bus_index: int,
        voltage_real: Var,
        voltage_imaginary: Var,
        active_power_balance: ObjVec,
        active_power_balance_used: BoolVec,
        reactive_power_balance: ObjVec,
        reactive_power_balance_used: BoolVec,
        real_current_balance: ObjVec,
        real_current_balance_used: BoolVec,
        imaginary_current_balance: ObjVec,
        imaginary_current_balance_used: BoolVec,
) -> None:
    """Convert one AC nodal power contribution into phasor current balance.

    The phasor solver owns Kirchhoff current equations, while the shared RMS
    device contract declares terminal active and reactive powers. For
    ``S = V * conjugate(I)``, the equivalent balance current is obtained from
    ``I = conjugate(S) / conjugate(V)``. Existing branch and injection current
    terms remain in the same preallocated nodal arrays.

    :param bus_index: AC network bus index to convert.
    :param voltage_real: Real component of the AC bus voltage.
    :param voltage_imaginary: Imaginary component of the AC bus voltage.
    :param active_power_balance: Preallocated nodal active-power expressions.
    :param active_power_balance_used: Active-power initialization flags.
    :param reactive_power_balance: Preallocated nodal reactive-power expressions.
    :param reactive_power_balance_used: Reactive-power initialization flags.
    :param real_current_balance: Preallocated nodal real-current expressions.
    :param real_current_balance_used: Real-current initialization flags.
    :param imaginary_current_balance: Preallocated nodal imaginary-current expressions.
    :param imaginary_current_balance_used: Imaginary-current initialization flags.
    :return: None.
    """
    if active_power_balance_used[bus_index] or reactive_power_balance_used[bus_index]:
        active_power: Expr | Var | Const
        reactive_power: Expr | Var | Const
        if active_power_balance_used[bus_index]:
            active_power = active_power_balance[bus_index]
        else:
            active_power = Const(0.0)
        if reactive_power_balance_used[bus_index]:
            reactive_power = reactive_power_balance[bus_index]
        else:
            reactive_power = Const(0.0)

        # Convert the declared complex-power balance at the physical AC bus
        # into the current coordinates used by the phasor KCL formulation.
        voltage_magnitude_squared: Expr = (
            voltage_real * voltage_real
            + voltage_imaginary * voltage_imaginary
        )
        real_current: Expr = (
            active_power * voltage_real
            + reactive_power * voltage_imaginary
        ) / voltage_magnitude_squared
        imaginary_current: Expr = (
            active_power * voltage_imaginary
            - reactive_power * voltage_real
        ) / voltage_magnitude_squared
        _add_terminal_balance_value(
            balance=real_current_balance,
            balance_used=real_current_balance_used,
            bus_index=bus_index,
            value=real_current,
        )
        _add_terminal_balance_value(
            balance=imaginary_current_balance,
            balance_used=imaginary_current_balance_used,
            bus_index=bus_index,
            value=imaginary_current,
        )
    else:
        pass
