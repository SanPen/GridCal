# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import Any

from VeraGridEngine.IO.fmu.expression import ExprToCVisitor
from VeraGridEngine.IO.fmu.CosimulationInterface.export_ir import ExportLogicEntry, ExportModel
from VeraGridEngine.IO.fmu.CosimulationInterface.variable_map import CVariableResolver
from VeraGridEngine.Utils.Symbolic.symbolic import CmpOp, Comparison, Expr, Var, _dict_to_expr



def _expr_like_from_dict(data: dict[str, Any]) -> Any:
    """Execute the `_expr_like_from_dict` operation.

    :param data: Function input.
    :return: Function result.
    """
    kind = str(data.get("kind", "Expr"))
    if kind == "Expr":
        return _dict_to_expr(data["expr"])
    if kind == "Comparison":
        rhs_raw = data["rhs"]
        rhs: Any
        if bool(data.get("rhs_is_expr", False)):
            rhs = _dict_to_expr(rhs_raw)
        else:
            rhs = rhs_raw
        return Comparison(lhs=_dict_to_expr(data["lhs"]), op=CmpOp(str(data["op"])), rhs=rhs)
    raise ValueError(f"Unsupported procedural expression kind: {kind!r}")


def _render_numeric(visitor: ExprToCVisitor, value: Any) -> str:
    """Execute the `_render_numeric` operation.

    :param visitor: Function input.
    :param value: Function input.
    :return: Function result.
    """
    if isinstance(value, dict) and "kind" in value:
        return visitor.render(_expr_like_from_dict(value))
    if isinstance(value, (int, float, bool)):
        return visitor.render(float(value))
    if isinstance(value, str):
        try:
            return visitor.render(Var(value))
        except Exception as exc:  # pragma: no cover - defensive fallback
            raise ValueError(f"Could not resolve procedural reference {value!r}") from exc
    if isinstance(value, Expr):
        return visitor.render(value)
    raise ValueError(f"Unsupported procedural numeric value: {value!r}")


def _render_bool(visitor: ExprToCVisitor, value: Any) -> str:
    """Execute the `_render_bool` operation.

    :param visitor: Function input.
    :param value: Function input.
    :return: Function result.
    """
    code = _render_numeric(visitor, value)
    return f"(({code}) != 0.0)"


def _target_expr(resolver: CVariableResolver, name: str) -> str:
    """Execute the `_target_expr` operation.

    :param resolver: Function input.
    :param name: Function input.
    :return: Function result.
    """
    variable = resolver.by_name.get(name)
    if variable is None:
        raise KeyError(f"Unknown procedural target variable {name!r}")
    return resolver.resolve_target(variable.uid)


def render_procedural_c(export_model: ExportModel, resolver: CVariableResolver) -> str:
    """Execute the `render_procedural_c` operation.

    :param export_model: Function input.
    :param resolver: Function input.
    :return: Function result.
    """
    visitor = ExprToCVisitor(resolver)
    lines: list[str] = [
        '#include "generated_model.h"',
        '#include "generated_metadata.h"',
        '#include "runtime_support.h"',
        "",
        "static double vg_logic_nan(void) {",
        "    volatile double zero = 0.0;",
        "    return zero / zero;",
        "}",
        "",
        "double generated_procedural_next_event(ModelInstance* instance, double t_prev, double t_target) {",
        "    double next_time = vg_logic_nan();",
        "    (void)t_prev;",
    ]

    for entry in export_model.logic_entries:
        base_r = entry.index * 5
        logic_type = entry.logic_type
        if logic_type == "pickup_dropoff":
            lines.extend(
                [
                    f"    {{ /* {entry.name or logic_type} */",
                    f"        double pending_pickup = instance->logic_reals[{base_r + 3}];",
                    f"        double pending_drop = instance->logic_reals[{base_r + 4}];",
                    "        if (!isnan(pending_pickup) && pending_pickup > t_prev && pending_pickup <= t_target && (isnan(next_time) || pending_pickup < next_time)) next_time = pending_pickup;",
                    "        if (!isnan(pending_drop) && pending_drop > t_prev && pending_drop <= t_target && (isnan(next_time) || pending_drop < next_time)) next_time = pending_drop;",
                    "    }",
                ]
            )
        elif logic_type == "delayed_threshold_latch":
            lines.extend(
                [
                    f"    {{ /* {entry.name or logic_type} */",
                    f"        double pending_trip = instance->logic_reals[{base_r + 1}];",
                    f"        double pending_reset = instance->logic_reals[{base_r + 2}];",
                    "        if (!isnan(pending_trip) && pending_trip > t_prev && pending_trip <= t_target && (isnan(next_time) || pending_trip < next_time)) next_time = pending_trip;",
                    "        if (!isnan(pending_reset) && pending_reset > t_prev && pending_reset <= t_target && (isnan(next_time) || pending_reset < next_time)) next_time = pending_reset;",
                    "    }",
                ]
            )
    lines.extend(["    return next_time;", "}", "", "void generated_procedural_update(ModelInstance* instance, double t) {"])

    for entry in export_model.logic_entries:
        base_r = entry.index * 5
        base_i = entry.index * 3
        data = entry.data
        logic_type = entry.logic_type

        if logic_type == "fixed_sample":
            target = _target_expr(resolver, str(data["output_var_name"]))
            condition = _render_bool(visitor, data["condition_expr"])
            lines.extend(
                [
                    f"    /* {entry.name or logic_type} */",
                    f"    if (!instance->logic_ints[{base_i}]) {{",
                    f"        {target} = {condition} ? 1.0 : 0.0;",
                    f"        instance->logic_ints[{base_i}] = 1;",
                    "    }",
                ]
            )
        elif logic_type == "sampled_value":
            target = _target_expr(resolver, str(data["output_var_name"]))
            source = _render_numeric(visitor, data["source_expr"])
            lines.extend([
                f"    /* {entry.name or logic_type} */",
                f"    {target} = {source};",
            ])
        elif logic_type == "flipflop":
            target = _target_expr(resolver, str(data["output_var_name"]))
            set_expr = _render_bool(visitor, data["set_expr"])
            reset_expr = _render_bool(visitor, data["reset_expr"])
            lines.extend(
                [
                    f"    /* {entry.name or logic_type} */",
                    f"    if (!instance->logic_ints[{base_i}]) {{",
                    f"        instance->logic_reals[{base_r}] = {set_expr} ? 1.0 : 0.0;",
                    f"        instance->logic_ints[{base_i}] = 1;",
                    "    } else {",
                    f"        if ({set_expr} && !{reset_expr}) instance->logic_reals[{base_r}] = 1.0;",
                    f"        else if (!{set_expr} && {reset_expr}) instance->logic_reals[{base_r}] = 0.0;",
                    "    }",
                    f"    {target} = instance->logic_reals[{base_r}];",
                ]
            )
        elif logic_type == "pickup_dropoff":
            target = _target_expr(resolver, str(data["output_var_name"]))
            bool_expr = _render_bool(visitor, data["bool_expr"])
            pickup_delay = f"fmax(0.0, {_render_numeric(visitor, data['pickup_delay_expr'])})"
            drop_delay = f"fmax(0.0, {_render_numeric(visitor, data['drop_delay_expr'])})"
            lines.extend(
                [
                    f"    /* {entry.name or logic_type} */",
                    f"    {{ int initialized = instance->logic_ints[{base_i}];",
                    f"      double state = instance->logic_reals[{base_r}];",
                    f"      double pending_pickup = instance->logic_reals[{base_r + 3}];",
                    f"      double pending_drop = instance->logic_reals[{base_r + 4}];",
                    f"      int bool_on = {bool_expr};",
                    f"      double pickup_delay = {pickup_delay};",
                    f"      double drop_delay = {drop_delay};",
                    "      if (!initialized) {",
                    "          instance->logic_ints[%d] = 1;" % base_i,
                    "          if (bool_on && pickup_delay <= 1e-15) { state = 1.0; }",
                    "          else if (bool_on) { pending_pickup = t + pickup_delay; }",
                    "      }",
                    "      if (state < 0.5) {",
                    "          pending_drop = NAN;",
                    "          if (bool_on) { if (isnan(pending_pickup)) pending_pickup = t + pickup_delay; } else { pending_pickup = NAN; }",
                    "          if (!isnan(pending_pickup) && t >= pending_pickup - 1e-15) { state = 1.0; pending_pickup = NAN; }",
                    "      } else {",
                    "          pending_pickup = NAN;",
                    "          if (!bool_on) { if (isnan(pending_drop)) pending_drop = t + drop_delay; } else { pending_drop = NAN; }",
                    "          if (!isnan(pending_drop) && t >= pending_drop - 1e-15) { state = 0.0; pending_drop = NAN; }",
                    "      }",
                    f"      instance->logic_reals[{base_r}] = state;",
                    f"      instance->logic_reals[{base_r + 3}] = pending_pickup;",
                    f"      instance->logic_reals[{base_r + 4}] = pending_drop;",
                    f"      {target} = state;",
                    "    }",
                ]
            )
        elif logic_type == "reset_on_rising_edge":
            target = _target_expr(resolver, str(data["target_var_name"]))
            reset_expr = _render_bool(visitor, data["reset_expr"])
            value_expr = _render_numeric(visitor, data["value_expr"])
            lines.extend(
                [
                    f"    /* {entry.name or logic_type} */",
                    f"    {{ int high = {reset_expr};",
                    f"      if (high && !instance->logic_ints[{base_i + 1}]) {target} = {value_expr};",
                    f"      instance->logic_ints[{base_i}] = 1;",
                    f"      instance->logic_ints[{base_i + 1}] = high;",
                    "    }",
                ]
            )
        elif logic_type == "delayed_threshold_latch":
            target = _target_expr(resolver, str(data["mode_var_name"]))
            monitored = _render_numeric(visitor, {"kind": "Expr", "expr": {"type": "Var", "name": str(data['monitored_var_name']), "uid": -1, "base_var": "None"}})
            threshold = float(data["threshold"])
            delay = float(data["delay"])
            reset_delay = data.get("reset_delay", None)
            reset_code = "NAN" if reset_delay is None else format(float(reset_delay), ".17g")
            lines.extend(
                [
                    f"    /* {entry.name or logic_type} */",
                    f"    {{ double measured = {monitored};",
                    f"      int comparator_on = measured >= {threshold:.17g};",
                    f"      int tripped = instance->logic_ints[{base_i}];",
                    f"      double pending_trip = instance->logic_reals[{base_r + 1}];",
                    f"      double pending_reset = instance->logic_reals[{base_r + 2}];",
                    "      if (tripped) {",
                    f"          {target} = 0.0;",
                    "          if (!isnan(pending_reset) && t >= pending_reset - 1e-15) {",
                    "              tripped = 0;",
                    "              pending_reset = NAN;",
                    f"              {target} = 1.0;",
                    "          }",
                    "      } else {",
                    "          if (comparator_on) { if (isnan(pending_trip)) pending_trip = t + %.17g; } else { pending_trip = NAN; }" % delay,
                    "          if (!isnan(pending_trip) && t >= pending_trip - 1e-15) {",
                    "              tripped = 1;",
                    f"              {target} = 0.0;",
                    f"              pending_reset = isnan({reset_code}) ? NAN : (t + {reset_code});",
                    "              pending_trip = NAN;",
                    "          } else {",
                    f"              {target} = 1.0;",
                    "          }",
                    "      }",
                    f"      instance->logic_ints[{base_i}] = tripped;",
                    f"      instance->logic_reals[{base_r + 1}] = pending_trip;",
                    f"      instance->logic_reals[{base_r + 2}] = pending_reset;",
                    "    }",
                ]
            )

    lines.extend(["}", ""])
    return "\n".join(lines)
