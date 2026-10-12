import math
import traceback
import numpy as np
from typing import Any, Literal

# import pandapower
# import pandapower as pdp
import pandas as pd
# import pypowsybl
# import pypowsybl as pp
# from pypowsybl import PyPowsyblError
# from pypowsybl.network import Network
from VeraGridEngine.basic_structures import Logger

from VeraGridEngine.IO.others.helper_pow2pp import create_switches, catch_exceptions, set_index_as_column, \
    find_voltage_levels, drop_irrelevant_columns
from VeraGridEngine.Utils.Symbolic import log

IDENTIFIER_COLUMN_NAME = "uuid"

CREATE_EXT_FOR_SLACK = False
logger = Logger()
frequency = 50


def find_bus_ids(
        element_table: pd.DataFrame,
        pandapower_net: "pandapower.pandapowerNet",
        target_column_name: str = "bus",
        column_name_element_table: str = "bus_id",
) -> pd.DataFrame:
    """Simplified version that doesn't rely on the identifier column"""

    # Create a mapping from bus name to index (assuming bus names are the powsybl IDs)
    bus_name_to_index = {}
    for idx, bus_row in pandapower_net.bus.iterrows():
        bus_name = bus_row.get("name")
        if bus_name is not None and not pd.isna(bus_name):
            bus_name_to_index[bus_name] = idx

    # Map the bus IDs to pandapower bus indices
    element_table[target_column_name] = element_table[column_name_element_table].map(
        bus_name_to_index
    )

    # Handle missing buses
    in_service_columns = {"connected", "in_service"}.intersection(element_table.columns)
    if len(in_service_columns) > 0:
        element_table.loc[
            element_table[target_column_name].isna(), list(in_service_columns)
        ] = False

    return element_table


def get_bus_index(pandapower_net: "pdp.pandapowerNet", bus_id: str) -> Any | None:
    """Get pandapower bus index from powsybl bus ID"""
    if (
            pandapower_net.bus.empty
            or IDENTIFIER_COLUMN_NAME not in pandapower_net.bus.columns
    ):
        return None

    # Find the bus with matching powsybl_id
    matches = pandapower_net.bus[pandapower_net.bus[IDENTIFIER_COLUMN_NAME] == bus_id]

    if not matches.empty:
        # Return the index of the first matching bus
        return matches.index[0]

    return None


def convert_to_pandapower(network: "pp.network.Network") -> "pdp.pandapowerNet":
    """Convert pypowsybl network to pandapower network"""
    try:
        import pandapower as pdp
    except ImportError:
        return

    pandapower_net = pdp.create_empty_network(
        name=network.name if network.name else "converted_network"
    )

    # Create buses first (they are needed for other elements)
    create_buses(pandapower_net, network)

    # Create other elements
    create_loads(pandapower_net, network)
    create_generators(pandapower_net, network)
    create_lines(pandapower_net, network)
    create_2w_transformers(pandapower_net, network)
    create_3w_transformers(pandapower_net, network)
    create_shunts(pandapower_net, network)
    create_switches(pandapower_net, network)

    return pandapower_net


def create_buses(
        pandapower_net: "pdp.pandapowerNet", powsybl_net: "pp.network.Network"
) -> None:
    """Create buses from pypowsybl network, handling UUID suffixes"""
    buses = powsybl_net.get_buses()

    if buses.empty:
        return

    # Create pandapower buses
    bus_data = []
    for bus_id, bus in buses.iterrows():
        # Get voltage level information
        vl_info = powsybl_net.get_voltage_levels().loc[bus["voltage_level_id"]]

        bus_data.append(
            {
                "name": bus_id,
                "vn_kv": vl_info["nominal_v"],
                "type": "b",
                "zone": None,
                "in_service": True,
                IDENTIFIER_COLUMN_NAME: bus_id,
            }
        )

    pandapower_net.bus = pd.DataFrame(bus_data)


def create_loads(
        pandapower_net: "pdp.pandapowerNet", powsybl_net: "pp.network.Network"
) -> None:
    """Create loads from pypowsybl network"""
    loads = powsybl_net.get_loads()

    if loads.empty:
        return

    load_data = []
    # bus_mapping = pandapower_net.bus.set_index(IDENTIFIER_COLUMN_NAME).index

    for load_id, load in loads.iterrows():
        # Find corresponding bus
        bus_idx = get_bus_index(pandapower_net, load.bus_id)
        if bus_idx is None:
            continue

        load_data.append(
            {
                "name": load_id,
                "bus": bus_idx,
                "p_mw": load["p0"],
                "q_mvar": load["q0"],
                "const_z_percent": 0,
                "const_i_percent": 0,
                "sn_mva": None,
                "scaling": 1.0,
                "in_service": load.get("connected", True),
                IDENTIFIER_COLUMN_NAME: load_id,
            }
        )

    if load_data:
        pandapower_net.load = pd.DataFrame(load_data)


def create_generators(
        pandapower_net: "pdp.pandapowerNet", powsybl_net: "pp.network.Network"
) -> None:
    """Create generators from pypowsybl network, excluding slack generators"""
    generators = powsybl_net.get_generators()

    if generators.empty:
        return

    # Identify slack generators first
    slack_generators = identify_slack_generators(
        powsybl_net, generators, pandapower_net.bus
    )
    slack_gen_ids = (
        slack_generators.index.tolist() if not slack_generators.empty else []
    )
    gen_data = []
    if slack_gen_ids and len(slack_gen_ids) > 0:
        # Filter out slack generators
        regular_generators = generators[~generators.index.isin(slack_gen_ids)]
        if CREATE_EXT_FOR_SLACK:
            ext_grid_data = []
            for gen_id in slack_gen_ids:
                gen = slack_generators.loc[gen_id]
                # Find corresponding bus
                bus_idx = get_bus_index(pandapower_net, gen["bus_id"])
                if bus_idx is None:
                    continue

                # Calculate voltage in per unit
                bus_vn_kv = pandapower_net.bus.loc[bus_idx, "vn_kv"]
                vm_pu = (
                        gen.get("target_v", bus_vn_kv) / bus_vn_kv
                )  # Default to nominal voltage if target_v not available

                ext_grid_data.append(
                    {
                        "name": f"ext_grid_{gen_id}",
                        "bus": bus_idx,
                        "vm_pu": vm_pu,
                        "va_degree": 0.0,  # Reference angle
                        "in_service": gen.get("connected", True),
                        IDENTIFIER_COLUMN_NAME: gen_id,
                    }
                )

            if ext_grid_data:
                pandapower_net.ext_grid = pd.DataFrame(ext_grid_data)
                logger.add_info(
                    f"Created {len(ext_grid_data)} external grid(s) from slack generators"
                )
        else:
            for gen_id in slack_gen_ids:
                gen = slack_generators.loc[gen_id]
                bus_idx = get_bus_index(pandapower_net, gen["bus_id"])
                gen_data.append(
                    {
                        "name": gen_id,
                        "bus": get_bus_index(pandapower_net, gen["bus_id"]),
                        "p_mw": gen["target_p"],
                        "vm_pu": gen["target_v"]
                                 / pandapower_net.bus.loc[bus_idx, "vn_kv"],
                        "sn_mva": gen["rated_s"],
                        "min_p_mw": gen["min_p"],
                        "max_p_mw": gen["max_p"],
                        "min_q_mvar": gen["min_q"],
                        "max_q_mvar": gen["max_q"],
                        "in_service": gen.get("connected", True),
                        "slack": True,
                        "slack_weight": 1,
                        IDENTIFIER_COLUMN_NAME: gen_id,
                    }
                )
    else:
        regular_generators = generators

    if regular_generators.empty:
        return

    sgen_data = []
    for gen_id, gen in regular_generators.iterrows():
        # Find corresponding bus
        bus_idx = get_bus_index(pandapower_net, gen.bus_id)
        if bus_idx is None:
            continue
        if not gen.get("voltage_regulator_on", False):
            sgen_data.append(
                {
                    "name": gen_id,
                    "bus": bus_idx,
                    "p_mw": gen["target_p"],
                    "q_mvar": math.sqrt(gen["rated_s"] ** 2 - gen["target_p"] ** 2),
                    "sn_mva": gen["rated_s"],
                    "in_service": gen.get("connected", True),
                    "scaling": 1.0,
                    IDENTIFIER_COLUMN_NAME: gen_id,
                }
            )
            if sgen_data:
                pandapower_net.sgen = pd.DataFrame(sgen_data)
        else:
            # Get bus voltage for per-unit conversion
            bus_vn_kv = pandapower_net.bus.loc[bus_idx, "vn_kv"]

            target_v = gen.get(
                "target_v", bus_vn_kv
            )  # Default to bus voltage if not specified

            # Calculate voltage setpoint in per-unit
            vm_pu = target_v / bus_vn_kv if bus_vn_kv > 0 else 1.0

            # Handle reactive power limits
            min_q = gen.get("min_q", -9999)  # Very negative if not limited
            max_q = gen.get("max_q", 9999)  # Very positive if not limited

            # If no explicit limits, set reasonable defaults based on generator size
            rated_s = gen.get("rated_s", 100.0)
            if min_q == -9999:
                min_q = -rated_s * 0.8  # Typical limit: 80% of rated apparent power
            if max_q == 9999:
                max_q = rated_s * 0.8  # Typical limit: 80% of rated apparent power
            gen_data.append(
                {
                    "name": gen_id,
                    "bus": bus_idx,
                    "p_mw": gen["target_p"],
                    "vm_pu": vm_pu,
                    "sn_mva": gen["rated_s"],
                    "min_p_mw": gen["min_p"],
                    "max_p_mw": gen["max_p"],
                    "min_q_mvar": min_q,
                    "max_q_mvar": max_q,
                    "in_service": gen.get("connected", True),
                    "slack": False,
                    "slack_weight": 1,
                    "scaling": 1,
                    IDENTIFIER_COLUMN_NAME: gen_id,
                }
            )

            if gen_data:
                pandapower_net.gen = pd.DataFrame(gen_data)
                logger.add_info(
                    "Created {len(gen_data)} regular generators, excluded {len(slack_gen_ids)} slack generators"
                )


def create_lines(
        pandapower_net: "pdp.pandapowerNet", powsybl_net: "pp.network.Network"
) -> None:
    """Create lines from pypowsybl network"""
    lines = powsybl_net.get_lines()

    if lines.empty:
        return

    line_data = []

    for line_id, line in lines.iterrows():
        # Find corresponding buses
        from_bus_idx = get_bus_index(pandapower_net, line["bus1_id"])
        to_bus_idx = get_bus_index(pandapower_net, line["bus2_id"])

        if from_bus_idx is None or to_bus_idx is None:
            continue
        # Convert b1 + b2 to c_nf_per_km
        b1 = line.get('b1', 0)
        b2 = line.get('b2', 0)
        total_susceptance = b1 + b2

        # Convert susceptance to capacitance
        capacitance_farads = total_susceptance / (2 * np.pi * frequency)
        line_data.append(
            {
                "name": line_id,
                "from_bus": from_bus_idx,
                "to_bus": to_bus_idx,
                "length_km": 1.0,  # Default length
                "r_ohm_per_km": line["r"],
                "x_ohm_per_km": line["x"],
                "c_nf_per_km": capacitance_farads * 1e9,  # Simplified
                "max_i_ka": 1000.0,  # Default
                "in_service": line["connected1"] and line["connected2"],
                "parallel": 1,
                "g_us_per_km": 0,
                "df": 1,
                IDENTIFIER_COLUMN_NAME: line_id,
            }
        )

    if line_data:
        pandapower_net.line = pd.DataFrame(line_data)


def identify_slack_generators(
        powsybl_net: "Network", generators: pd.DataFrame, bus: pd.DataFrame
) -> pd.DataFrame:
    """Identify slack generators based on extensions or other criteria"""
    try:
        slack_ext = powsybl_net.get_extensions("slackTerminal")
        if not slack_ext.empty:
            return generators[
                generators[IDENTIFIER_COLUMN_NAME].isin(slack_ext["element_id"])
            ]
    except Exception as exc:
        logger.add_info(f"slack extension not found {exc}")
        # Fallback: pick generator(s) with the largest max_p_mw
    if not generators.empty and "max_p_mw" in generators:
        max_p = generators["max_p_mw"].max()
        candidates = generators[generators["max_p_mw"] == max_p]

        if len(candidates) > 1:
            # Tiebreaker: pick the one connected to the highest voltage bus
            slack_gen_idx = (
                candidates["bus_id"].apply(lambda x: bus.loc[x, "vn_kv"]).idxmax()
            )
        else:
            slack_gen_idx = candidates.index[0]

        return generators.loc[[slack_gen_idx]]
    # Fallback: first generator or based on some criteria
    if not generators.empty:
        return generators.head(1)
    return pd.DataFrame()


@catch_exceptions
def create_2w_transformers(
        pandapower_net: "pandapower.pandapowerNet", powsybl_net: "Network"
) -> None:
    trafo2w = powsybl_net.get_2_windings_transformers()

    if trafo2w.empty:
        return

    set_index_as_column(trafo2w)

    # Get voltage levels for proper voltage setting
    voltage_levels = powsybl_net.get_voltage_levels()[["nominal_v"]]

    # Add voltage level information
    trafo2w = pd.merge(
        trafo2w,
        voltage_levels.rename(columns={"nominal_v": "vn_hv_kv"}),
        left_on="voltage_level1_id",
        right_index=True,
        how="left",
    )
    trafo2w = pd.merge(
        trafo2w,
        voltage_levels.rename(columns={"nominal_v": "vn_lv_kv"}),
        left_on="voltage_level2_id",
        right_index=True,
        how="left",
    )

    trafo2w["in_service"] = trafo2w[["connected1", "connected2"]].all(axis=1)
    trafo2w = find_bus_ids(trafo2w, pandapower_net, "hv_bus", "bus1_id")
    trafo2w = find_bus_ids(trafo2w, pandapower_net, "lv_bus", "bus2_id")

    # Add tap changer parameters
    trafo2w = add_tap_parameters_for_ratio_tap_changer(powsybl_net, trafo2w)
    trafo2w = add_tap_parameters_for_phase_tap_changer(powsybl_net, trafo2w)

    # Set transformer parameters

    # Handle missing values at DataFrame level BEFORE iterating
    if "rated_s" in trafo2w.columns:
        trafo2w["rated_s"] = trafo2w["rated_s"].fillna(100.0)
    else:
        trafo2w["rated_s"] = 100.0
    trafo2w["sn_mva"] = trafo2w["rated_s"]
    # Calculate short circuit parameters
    calculate_short_circuit_voltage(trafo2w)
    calculate_iron_losses_and_open_loop_losses(trafo2w)

    # ACTUALLY CREATE THE TRANSFORMERS IN PANDAPOWER NETWORK
    trafo_data = []
    for idx, trafo in trafo2w.iterrows():
        # Skip if buses are not found
        if pd.isna(trafo["hv_bus"]) or pd.isna(trafo["lv_bus"]):
            continue

        trafo_data.append(
            {
                "name": trafo.get("name", f"trafo_{idx}"),
                "hv_bus": int(trafo["hv_bus"]),
                "lv_bus": int(trafo["lv_bus"]),
                "sn_mva": trafo["sn_mva"],
                "vn_hv_kv": trafo["vn_hv_kv"],
                "vn_lv_kv": trafo["vn_lv_kv"],
                "vk_percent": trafo.get("vk_percent", 10.0),
                "vkr_percent": trafo.get("vkr_percent", 0.5),
                "pfe_kw": trafo.get("pfe_kw", 0),
                "i0_percent": trafo.get("i0_percent", 0),
                "shift_degree": 0,
                "tap_side": trafo.get("tap_side", "hv"),
                "tap2_side": trafo.get("tap2_side", "hv"),
                "tap_pos": trafo.get("tap_pos", 0),
                "tap2_pos": trafo.get("tap2_pos", 0),
                "tap_neutral": trafo.get("tap_neutral", 0),
                "tap2_neutral": trafo.get("tap2_neutral", 0),
                "tap_min": trafo.get("tap_min", 0),
                "tap2_min": trafo.get("tap2_min", 0),
                "tap_max": trafo.get("tap_max", 0),
                "tap2_max": trafo.get("tap2_max", 0),
                "tap_step_percent": trafo.get("tap_step_percent", 0),
                "tap2_step_percent": trafo.get("tap2_step_percent", 0),
                "tap_step_degree": trafo.get("tap_step_degree", 0),
                "tap2_step_degree": trafo.get("tap2_step_degree", 0),
                "in_service": trafo["in_service"],
                "parallel": 1,
                "oltc": trafo.get("oltc", False),
                "power_station_unit": False,
                # tap_changer_type # only consider if in power flow if calc_v_angle=True
                # tap2_changer_type
                # "leakage_resistance_ratio_hv": 1,
                # "lleakage_reactance_ratio_hv": 10,
                "df": 1,
                IDENTIFIER_COLUMN_NAME: idx,
            }
        )

    if trafo_data:
        pandapower_net.trafo = pd.DataFrame(trafo_data)

    # Create result table
    # if not trafo2w.empty:
    # res_trafo = trafo2w[["p1", "p2", "q1", "q2"]].copy()
    # res_trafo.columns = ["p_hv_mw", "p_lv_mw", "q_hv_mvar", "q_lv_mvar"]
    # pandapower_net.res_trafo = res_trafo


def calculate_short_circuit_voltage(trafo_table: pd.DataFrame) -> None:
    """Calculate short circuit voltage parameters for transformers with proper defaults"""
    for idx, trafo in trafo_table.iterrows():
        try:
            # Calculate short circuit impedance - use safe defaults if missing values
            r_val = trafo.get("r", 0.01)  # Default small resistance
            x_val = trafo.get("x", 0.1)  # Default reactance

            # Get nominal voltages with defaults
            vn_lv_kv = trafo["vn_lv_kv"]
            rated_s = max(trafo.get("rated_s", 100.0), 1)  # Avoid division by zero

            # if r/x missing, pick safe per-unit defaults instead of raw ohms
            if (pd.isna(r_val) or r_val == 0) and (pd.isna(x_val) or x_val == 0):
                trafo_table.loc[idx, "vk_percent"] = 10.0
                trafo_table.loc[idx, "vkr_percent"] = 0.5
                continue

            z_base = vn_lv_kv ** 2 / rated_s
            z_actual = complex(r_val, x_val)

            trafo_table.loc[idx, "vk_percent"] = abs(z_actual) / z_base * 100
            trafo_table.loc[idx, "vkr_percent"] = (
                r_val / z_base * 100 if r_val != 0.0 else 0.001
            )

        except (TypeError, ValueError, ZeroDivisionError) as e:
            # Set reasonable defaults if calculation fails
            trafo_table.loc[idx, "vk_percent"] = 10.0  # Typical value
            trafo_table.loc[idx, "vkr_percent"] = 0.5  # Typical value
            (f"Warning: Using default values for transformer {idx}: {e}")


def calculate_iron_losses_and_open_loop_losses(trafo_table: pd.DataFrame) -> None:
    """Calculate iron losses with proper defaults"""
    for idx, trafo in trafo_table.iterrows():
        try:
            # Use defaults if values are missing
            g_val = trafo.get("g", 0.0001)  # Default small conductance
            b_val = trafo.get("b", 0.001)  # Default susceptance
            vn_lv_kv = trafo.get("vn_lv_kv", 1.0)
            rated_s = trafo.get("rated_s", 100.0)

            trafo_table.loc[idx, "pfe_kw"] = g_val * vn_lv_kv ** 2 * 1000

            # Calculate no-load current percentage
            y_mag = math.sqrt(g_val ** 2 + b_val ** 2)
            if rated_s > 0:
                trafo_table.loc[idx, "i0_percent"] = (
                        math.sqrt(3) * y_mag * vn_lv_kv ** 2 / rated_s * 100
                )
            else:
                trafo_table.loc[idx, "i0_percent"] = 0.5  # Default

        except (TypeError, ValueError) as e:
            # Set reasonable defaults
            trafo_table.loc[idx, "pfe_kw"] = 10.0  # Typical iron losses in kW
            trafo_table.loc[idx, "i0_percent"] = 0.5  # Typical no-load current
            logger.add_warning(
                f"Warning: Using default values for transformer losses {idx}: {e}"
            )


@catch_exceptions
def create_shunts(
        pandapower_net: "pandapower.pandapowerNet", powsybl_net: "Network"
) -> None:
    shunts = powsybl_net.get_shunt_compensators()
    set_index_as_column(shunts)

    shunts = find_voltage_levels(shunts, powsybl_net)
    shunts = find_bus_ids(shunts, pandapower_net)

    # Convert conductance and susceptance to pandapower format
    # p = V² * g, q = V² * b (in MW/MVar)
    shunts["p_mw"] = shunts["g"] * shunts["vn_kv"] ** 2
    shunts["q_mvar"] = shunts["b"] * shunts["vn_kv"] ** 2
    shunts["in_service"] = shunts.get("connected", True)
    shunts["step"] = shunts.get("section_count", 1)
    shunts["max_step"] = shunts.get("max_section_count", 1)

    pandapower_net.shunt = drop_irrelevant_columns(shunts, "shunt")


#
# @catch_exceptions
# def create_switches(
#     pandapower_net: pandapower.pandapowerNet, powsybl_net: Network
# ) -> None:
#     """
#     Handle switch conversion from powsybl to pandapower.
#     Pandapower supports two types of switches: bus-bus and bus-element.
#     """
#     switches = powsybl_net.get_switches(all_attributes=True)
#
#     if switches.empty:
#         return
#
#     set_index_as_column(switches)
#
#     # Map powsybl switch types to pandapower types
#     switch_type_mapping = {
#         "BREAKER": "CB",
#         "DISCONNECTOR": "DS",
#         "LOAD_BREAK_SWITCH": "LBS",
#     }
#     switches["type"] = switches["kind"].map(switch_type_mapping).fillna("DS")
#
#     # Set switch status
#     switches["closed"] = ~switches["open"]
#
#     # Process switches based on topology type
#     voltage_levels = powsybl_net.get_voltage_levels()
#
#     switch_data = []
#     for vl_id, voltage_level in voltage_levels.iterrows():
#         try:
#             # Try node-breaker topology first
#             vl_switches = process_node_breaker_switches(
#                 powsybl_net, vl_id, switches, pandapower_net
#             )
#             switch_data.append(vl_switches)
#         except PyPowsyblError:
#             # Fall back to bus-breaker topology
#             vl_switches = process_bus_breaker_switches(
#                 powsybl_net, vl_id, switches, pandapower_net
#             )
#             switch_data.append(vl_switches)
#
#     if switch_data:
#         all_switches = pd.concat(switch_data, ignore_index=True)
#         pandapower_net.switch = drop_irrelevant_columns(all_switches, "switch")
#
#
# def process_node_breaker_switches(
#     powsybl_net: Network, vl_id: str, all_switches: pd.DataFrame, pandapower_net
# ) -> pd.DataFrame:
#     """Process switches in node-breaker topology"""
#     nb_topology = powsybl_net.get_node_breaker_topology(vl_id)
#     vl_switches = all_switches[all_switches["voltage_level_id"] == vl_id].copy()
#
#     if vl_switches.empty:
#         return pd.DataFrame()
#
#     switch_list = []
#
#     for _, switch in vl_switches.iterrows():
#         node1 = switch["node1"]
#         node2 = switch["node2"]
#
#         # Get connectable information for both nodes
#         conn1 = get_connectable_for_node(
#             nb_topology, node1, pandapower_net, powsybl_net
#         )
#         conn2 = get_connectable_for_node(
#             nb_topology, node2, pandapower_net, powsybl_net
#         )
#
#         switch_info = {
#             IDENTIFIER_COLUMN_NAME: switch[IDENTIFIER_COLUMN_NAME],
#             "name": switch["name"],
#             "type": switch["type"],
#             "closed": switch["closed"],
#             "z_ohm": 0.001,
#         }
#
#         # Determine switch type (bus-bus or bus-element)
#         if conn1["type"] == "bus" and conn2["type"] == "bus":
#             # Bus-bus switch
#             switch_info.update(
#                 {"bus": conn1["bus_id"], "element": conn2["bus_id"], "et": "b"}
#             )
#         elif conn1["type"] == "bus" and conn2["type"] == "element":
#             # Bus-element switch
#             switch_info.update(
#                 {
#                     "bus": conn1["bus_id"],
#                     "element": conn2["element_id"],
#                     "et": conn2["element_type"],
#                 }
#             )
#         elif conn1["type"] == "element" and conn2["type"] == "bus":
#             # Element-bus switch
#             switch_info.update(
#                 {
#                     "bus": conn2["bus_id"],
#                     "element": conn1["element_id"],
#                     "et": conn1["element_type"],
#                 }
#             )
#         else:
#             # Element-element switch - create an intermediate bus
#             intermediate_bus = create_intermediate_bus(
#                 pandapower_net, vl_id, powsybl_net
#             )
#             switch_info.update(
#                 {
#                     "bus": intermediate_bus,
#                     "element": conn1["element_id"],
#                     "et": conn1["element_type"],
#                 }
#             )
#             # Create second switch for the other element
#             switch_info2 = switch_info.copy()
#             switch_info2.update(
#                 {
#                     "bus": intermediate_bus,
#                     "element": conn2["element_id"],
#                     "et": conn2["element_type"],
#                 }
#             )
#             switch_list.append(switch_info2)
#
#         switch_list.append(switch_info)
#
#     return pd.DataFrame(switch_list)
#
#
# def process_bus_breaker_switches(
#     powsybl_net: Network, vl_id: str, all_switches: pd.DataFrame, pandapower_net
# ) -> pd.DataFrame:
#     """Process switches in bus-breaker topology"""
#     # bb_topology = powsybl_net.get_bus_breaker_topology(vl_id)
#     vl_switches = all_switches[all_switches["voltage_level_id"] == vl_id].copy()
#
#     if vl_switches.empty:
#         return pd.DataFrame()
#
#     switch_list = []
#
#     for _, switch in vl_switches.iterrows():
#         bus1_id = switch["bus1_id"]
#         bus2_id = switch["bus2_id"]
#
#         # Get pandapower bus indices
#         bus1_idx = get_pandapower_bus_index(pandapower_net, bus1_id)
#         bus2_idx = get_pandapower_bus_index(pandapower_net, bus2_id)
#
#         if pd.notna(bus1_idx) and pd.notna(bus2_idx):
#             # Bus-bus switch
#             switch_info = {
#                 IDENTIFIER_COLUMN_NAME: switch[IDENTIFIER_COLUMN_NAME],
#                 "name": switch["name"],
#                 "type": switch["type"],
#                 "closed": switch["closed"],
#                 "bus": bus1_idx,
#                 "element": bus2_idx,
#                 "et": "b",
#                 "z_ohm": 0.001,
#             }
#             switch_list.append(switch_info)
#
#     return pd.DataFrame(switch_list)
#
#
# def get_connectable_for_node(
#     nb_topology, node_id: int, pandapower_net, powsybl_net
# ) -> dict:
#     """Get connectable information for a node in node-breaker topology"""
#     node_info = nb_topology.nodes.loc[node_id]
#
#     if node_info["connectable"] and pd.notna(node_info["connectable_id"]):
#         # This node is connected to a specific element
#         element_id = node_info["connectable_id"]
#         element_type = map_element_type(node_info["connectable_type"])
#         return {
#             "type": "element",
#             "element_id": element_id,
#             "element_type": element_type,
#         }
#     else:
#         # This node represents a bus
#         return {
#             "type": "bus",
#             "bus_id": create_or_get_bus_for_node(
#                 pandapower_net, node_id, nb_topology, powsybl_net
#             ),
#         }
#


def map_element_type(powsybl_type: str) -> str:
    """Map powsybl element types to pandapower element types"""
    element_type_mapping = {
        "LINE": "l",
        "TWO_WINDINGS_TRANSFORMER": "t",
        "THREE_WINDINGS_TRANSFORMER": "t3",
        "LOAD": "l",  # Loads are handled differently in pandapower
        "GENERATOR": "g",
        "SHUNT_COMPENSATOR": "s",
    }
    return element_type_mapping.get(powsybl_type, "b")  # Default to bus


def create_or_get_bus_for_node(
        pandapower_net: "pandapower.pandapowerNet", node_id: int, nb_topology, powsybl_net
) -> int:
    """Create or get a pandapower bus for a node"""
    # Check if we already created a bus for this node
    if (
            hasattr(pandapower_net, "_node_bus_mapping")
            and node_id in pandapower_net._node_bus_mapping
    ):
        return pandapower_net._node_bus_mapping[node_id]

    # Create new bus
    voltage_level_id = nb_topology.voltage_level_id
    vl_info = powsybl_net.get_voltage_levels().loc[voltage_level_id]

    new_bus_idx = len(pandapower_net.bus)
    new_bus = pd.DataFrame(
        {
            "name": f"node_{node_id}",
            "vn_kv": vl_info["nominal_v"],
            "type": "b",
            "zone": None,
            "in_service": True,
            IDENTIFIER_COLUMN_NAME: f"node_{node_id}",
        },
        index=[new_bus_idx],
    )

    pandapower_net.bus = pd.concat([pandapower_net.bus, new_bus])

    # Store mapping
    if not hasattr(pandapower_net, "_node_bus_mapping"):
        pandapower_net._node_bus_mapping = {}
    pandapower_net._node_bus_mapping[node_id] = new_bus_idx

    return new_bus_idx


def create_intermediate_bus(
        pandapower_net: "pandapower.pandapowerNet", vl_id: str, powsybl_net
) -> int:
    """Create an intermediate bus for element-element switches"""
    vl_info = powsybl_net.get_voltage_levels().loc[vl_id]

    new_bus_idx = len(pandapower_net.bus)
    new_bus = pd.DataFrame(
        {
            "name": f"intermediate_bus_{new_bus_idx}",
            "vn_kv": vl_info["nominal_v"],
            "type": "b",
            "zone": None,
            "in_service": True,
            IDENTIFIER_COLUMN_NAME: f"intermediate_{new_bus_idx}",
        },
        index=[new_bus_idx],
    )

    pandapower_net.bus = pd.concat([pandapower_net.bus, new_bus])
    return new_bus_idx


def get_pandapower_bus_index(
        pandapower_net: "pandapower.pandapowerNet", bus_id: str
) -> Any | None:
    """Get pandapower bus index from powsybl bus ID"""
    if IDENTIFIER_COLUMN_NAME in pandapower_net.bus.columns:
        match = pandapower_net.bus[pandapower_net.bus[IDENTIFIER_COLUMN_NAME] == bus_id]
        if not match.empty:
            return match.index[0]
    return None


@catch_exceptions
def create_3w_transformers(
        pandapower_net: "pandapower.pandapowerNet", powsybl_net: "Network"
) -> None:
    """
    Create 3-winding transformers with proper parameter conversion and tap changer handling.
    """
    trafo3w = powsybl_net.get_3_windings_transformers(all_attributes=True)

    if trafo3w.empty:
        return

    set_index_as_column(trafo3w)

    # Get voltage levels for proper voltage setting
    voltage_levels = powsybl_net.get_voltage_levels()[["nominal_v"]]

    # Add voltage level information for all three windings
    trafo3w = pd.merge(
        trafo3w,
        voltage_levels.rename(columns={"nominal_v": "vn_hv_kv"}),
        left_on="voltage_level1_id",
        right_index=True,
        how="left",
    )
    trafo3w = pd.merge(
        trafo3w,
        voltage_levels.rename(columns={"nominal_v": "vn_mv_kv"}),
        left_on="voltage_level2_id",
        right_index=True,
        how="left",
    )
    trafo3w = pd.merge(
        trafo3w,
        voltage_levels.rename(columns={"nominal_v": "vn_lv_kv"}),
        left_on="voltage_level3_id",
        right_index=True,
        how="left",
    )

    # Set service status
    trafo3w["in_service"] = trafo3w[["connected1", "connected2", "connected3"]].all(
        axis=1
    )

    # Find bus connections
    trafo3w = find_bus_ids(trafo3w, pandapower_net, "hv_bus", "bus1_id")
    trafo3w = find_bus_ids(trafo3w, pandapower_net, "mv_bus", "bus2_id")
    trafo3w = find_bus_ids(trafo3w, pandapower_net, "lv_bus", "bus3_id")

    # Add tap changer parameters
    trafo3w = add_tap_parameters_for_3w_ratio_tap_changer(powsybl_net, trafo3w)
    trafo3w = add_tap_parameters_for_3w_phase_tap_changer(powsybl_net, trafo3w)

    # Convert impedance parameters
    calculate_3w_impedance_parameters(trafo3w)

    # Calculate short circuit parameters
    # calculate_3w_short_circuit_parameters(trafo3w)

    # Calculate iron losses
    calculate_3w_iron_losses(trafo3w)

    # Set pandapower specific parameters
    trafo3w["sn_hv_mva"] = trafo3w["rated_s1"]
    trafo3w["sn_mv_mva"] = trafo3w["rated_s2"]
    trafo3w["sn_lv_mva"] = trafo3w["rated_s3"]
    trafo3w["tap_at_star_point"] = False
    # Set vector group (default to Dyn5 if not specified)
    trafo3w["vector_group"] = "Dyn5"
    trafo3w["df"] = 0.0
    trafo3w.loc[:, "tap_side"] = "hv"
    trafo3w.loc[:, "scaling"] = 1.0

    pandapower_net.trafo3w = drop_irrelevant_columns(trafo3w, "trafo3w")

    # # Create result table
    # if not trafo3w.empty:
    #     res_trafo3w = trafo3w[["p1", "p2", "p3", "q1", "q2", "q3"]].copy()
    #     res_trafo3w.columns = [
    #         "p_hv_mw",
    #         "p_mv_mw",
    #         "p_lv_mw",
    #         "q_hv_mvar",
    #         "q_mv_mvar",
    #         "q_lv_mvar",
    #     ]
    #
    #     # Add current values (convert from A to kA)
    #     res_trafo3w["i_hv_ka"] = trafo3w["i1"] * 1e-3
    #     res_trafo3w["i_mv_ka"] = trafo3w["i2"] * 1e-3
    #     res_trafo3w["i_lv_ka"] = trafo3w["i3"] * 1e-3
    #
    #     pandapower_net.res_trafo3w = res_trafo3w


def add_tap_parameters_for_3w_ratio_tap_changer(
        powsybl_net: "pypowsybl.network.Network", trafo_table: pd.DataFrame
) -> pd.DataFrame:
    """Add ratio tap changer parameters for 3-winding transformers"""
    ratio_tap_changers = powsybl_net.get_ratio_tap_changers()

    if ratio_tap_changers.empty:
        return trafo_table

    # Filter for 3w transformer tap changers
    trafo_ids = trafo_table[IDENTIFIER_COLUMN_NAME].unique()
    ratio_tap_changers = ratio_tap_changers[ratio_tap_changers.index.isin(trafo_ids)]

    if ratio_tap_changers.empty:
        return trafo_table

    # Process each transformer
    for trafo_id in trafo_ids:
        if trafo_id in ratio_tap_changers.index:
            tap_changer = ratio_tap_changers.loc[trafo_id]
            steps = powsybl_net.get_ratio_tap_changer_steps().loc[trafo_id]

            # Determine which winding has the tap changer
            regulated_side = tap_changer.get("regulated_side", "ONE")
            winding_map = {"ONE": "hv", "TWO": "mv", "THREE": "lv"}

            # Set tap parameters
            idx = trafo_table[trafo_table[IDENTIFIER_COLUMN_NAME] == trafo_id].index
            if not idx.empty:
                trafo_table.loc[idx, "tap_side"] = winding_map.get(regulated_side, "hv")
                trafo_table.loc[idx, "tap_step_degree"] = (
                    0  # considering pure ratio, phase is handled for tap_2
                )
                trafo_table.loc[idx, "tap_pos"] = tap_changer["tap"]
                trafo_table.loc[idx, "tap_min"] = tap_changer["low_tap"]
                trafo_table.loc[idx, "tap_max"] = tap_changer["high_tap"]
                trafo_table.loc[idx, "tap_neutral"] = (
                                                              tap_changer["high_tap"] - tap_changer["low_tap"]
                                                      ) / 2 + tap_changer["low_tap"]

                # Calculate tap step percentage
                if len(steps) > 1:
                    neutral_pos = trafo_table.loc[idx, "tap_neutral"].values[0]
                    if neutral_pos in steps.index and (neutral_pos + 1) in steps.index:
                        rho_neutral = steps.loc[neutral_pos, "rho"]
                        rho_next = steps.loc[neutral_pos + 1, "rho"]
                        step_percent = (rho_next - rho_neutral) * 100
                        trafo_table.loc[idx, "tap_step_percent"] = step_percent

    return trafo_table


def add_tap_parameters_for_3w_phase_tap_changer(
        powsybl_net: "pypowsybl.network.Network", trafo_table: pd.DataFrame
) -> pd.DataFrame:
    """Add phase tap changer parameters for 3-winding transformers"""
    phase_tap_changers = powsybl_net.get_phase_tap_changers()

    if phase_tap_changers.empty:
        return trafo_table

    # Filter for 3w transformer tap changers
    trafo_ids = trafo_table[IDENTIFIER_COLUMN_NAME].unique()
    phase_tap_changers = phase_tap_changers[phase_tap_changers.index.isin(trafo_ids)]

    if phase_tap_changers.empty:
        return trafo_table

    # Process each transformer
    for trafo_id in trafo_ids:
        if trafo_id in phase_tap_changers.index:
            tap_changer = phase_tap_changers.loc[trafo_id]
            steps = powsybl_net.get_phase_tap_changer_steps().loc[trafo_id]

            # Determine which winding has the tap changer
            regulated_side = tap_changer.get("regulated_side", "ONE")
            winding_map = {"ONE": "hv", "TWO": "mv", "THREE": "lv"}
            tap_side = winding_map.get(regulated_side, "hv")

            # Set tap parameters with '2' suffix for phase tap changers
            idx = trafo_table[trafo_table[IDENTIFIER_COLUMN_NAME] == trafo_id].index
            if not idx.empty:
                trafo_table.loc[idx, "tap2_pos"] = tap_changer["tap"]
                trafo_table.loc[idx, "tap2_min"] = tap_changer["low_tap"]
                trafo_table.loc[idx, "tap2_max"] = tap_changer["high_tap"]
                trafo_table.loc[idx, "tap2_neutral"] = (
                                                               tap_changer["high_tap"] - tap_changer["low_tap"]
                                                       ) / 2 + tap_changer["low_tap"]

                # Calculate tap step degree
                if len(steps) > 1:
                    neutral_pos = trafo_table.loc[idx, "tap2_neutral"].values[0]
                    if neutral_pos in steps.index and (neutral_pos + 1) in steps.index:
                        alpha_neutral = steps.loc[neutral_pos, "alpha"]
                        alpha_next = steps.loc[neutral_pos + 1, "alpha"]
                        step_degree = alpha_next - alpha_neutral
                        trafo_table.loc[idx, "tap2_step_degree"] = step_degree

    return trafo_table


def calculate_3w_impedance_parameters(
        trafo_table: pd.DataFrame,
        conv: Literal["pairwise_min", "global_max", "common_ref"] = "pairwise_min",
        ref_winding: str = "hv",
        Sbase_common: float | None = None,
) -> None:
    """
    Convert star-leg impedances (r1,x1,r2,x2,r3,x3 in ohm) to vk_/vkr_ percent fields.

    Parameters
    ----------
    trafo_table : pd.DataFrame
        Must contain columns: r1,x1,r2,x2,r3,x3, vn_hv_kv, vn_mv_kv, vn_lv_kv,
        rated_s1/rated_s2/rated_s3 (MVA)
    conv : {"pairwise_min","global_max","common_ref"}
        Which S-base convention to use:
          - "pairwise_min": use S_base for each pair = min(sn_w1, sn_w2)  (powsybl-style)
          - "global_max": use S_base = max(sn_hv, sn_mv, sn_lv) for all pairs
          - "common_ref": use a single Sbase_common and a single ref_winding for Vref
    ref_winding : {"hv","mv","lv"}
        Used only when conv == "common_ref".
    Sbase_common : float | None
        If provided used as Sbase in "common_ref"; otherwise uses max rated winding.
    """
    for idx, trafo in trafo_table.iterrows():
        # read star-leg impedances (Ohm)
        Z1 = complex(trafo.get("r1", 0.0), trafo.get("x1", 0.0))
        Z2 = complex(trafo.get("r2", 0.0), trafo.get("x2", 0.0))
        Z3 = complex(trafo.get("r3", 0.0), trafo.get("x3", 0.0))

        # pairwise impedances (Ohm)
        Z_hm = Z1 + Z2  # HV–MV
        Z_ml = Z2 + Z3  # MV–LV
        Z_hl = Z1 + Z3  # HV–LV

        # rated apparent powers (MVA)
        sn_hv = trafo.get("rated_s1", 0.0) or 0.0
        sn_mv = trafo.get("rated_s2", 0.0) or 0.0
        sn_lv = trafo.get("rated_s3", 0.0) or 0.0

        # canonical winding voltages (kV)
        vh = trafo["vn_hv_kv"]
        vm = trafo["vn_mv_kv"]
        vl = trafo["vn_lv_kv"]

        # helper to compute percent for a given Z (ohm), Vref_kv and Sbase_mva
        def to_percent(Z_ohm, Vref_kv, Sbase_mva):
            if Sbase_mva <= 0:
                raise ValueError("Sbase must be > 0")
            Zbase = (Vref_kv ** 2) / Sbase_mva
            Zpu = Z_ohm / Zbase
            vk = abs(Zpu) * 100.0
            vkr = Zpu.real * 100.0
            return vk, vkr

        if conv == "pairwise_min":
            # powsybl style: each vk_ij uses min rated S of the two windings,
            # and Vref chosen according to the winding of the higher side of the pair
            S_hm = min(
                sn_hv if sn_hv > 0 else float("inf"),
                sn_mv if sn_mv > 0 else float("inf"),
            )
            S_ml = min(
                sn_mv if sn_mv > 0 else float("inf"),
                sn_lv if sn_lv > 0 else float("inf"),
            )
            S_hl = min(
                sn_hv if sn_hv > 0 else float("inf"),
                sn_lv if sn_lv > 0 else float("inf"),
            )

            # if any min yields inf (no rated S provided) fall back to max available
            fallback_S = max(sn_hv, sn_mv, sn_lv) or 100.0
            if not math.isfinite(S_hm):
                S_hm = fallback_S
            if not math.isfinite(S_ml):
                S_ml = fallback_S
            if not math.isfinite(S_hl):
                S_hl = fallback_S

            vk_hm, vkr_hm = to_percent(
                Z_hm, vh, S_hm
            )  # HV–MV: Vref = HV (use higher-voltage winding)
            vk_ml, vkr_ml = to_percent(Z_ml, vm, S_ml)  # MV–LV: Vref = MV
            vk_hl, vkr_hl = to_percent(Z_hl, vh, S_hl)  # HV–LV: Vref = HV

        elif conv == "global_max":
            S_all = max(sn_hv, sn_mv, sn_lv) or 100.0
            # choose a consistent Vref per pair (use the higher-voltage winding for hv pairs)
            vk_hm, vkr_hm = to_percent(Z_hm, vh, S_all)
            vk_ml, vkr_ml = to_percent(Z_ml, vm, S_all)
            vk_hl, vkr_hl = to_percent(Z_hl, vh, S_all)

        elif conv == "common_ref":
            Sref = Sbase_common or (max(sn_hv, sn_mv, sn_lv) or 100.0)
            if ref_winding.lower() == "hv":
                Vref = vh
            elif ref_winding.lower() == "mv":
                Vref = vm
            elif ref_winding.lower() == "lv":
                Vref = vl
            else:
                raise ValueError("ref_winding must be 'hv','mv' or 'lv'")
            vk_hm, vkr_hm = to_percent(Z_hm, Vref, Sref)
            vk_ml, vkr_ml = to_percent(Z_ml, Vref, Sref)
            vk_hl, vkr_hl = to_percent(Z_hl, Vref, Sref)
        else:
            raise ValueError("Unknown conv mode")

        # write to table (note naming: pandapower expects vk_hv_percent=HV–MV etc)
        trafo_table.loc[idx, "vk_hv_percent"] = vk_hm
        trafo_table.loc[idx, "vkr_hv_percent"] = vkr_hm

        trafo_table.loc[idx, "vk_mv_percent"] = vk_ml
        trafo_table.loc[idx, "vkr_mv_percent"] = vkr_ml

        trafo_table.loc[idx, "vk_lv_percent"] = vk_hl
        trafo_table.loc[idx, "vkr_lv_percent"] = vkr_hl

        # optional default shifts
        trafo_table.loc[idx, "shift_mv_degree"] = trafo.get("shift_mv_degree", 0.0)
        trafo_table.loc[idx, "shift_lv_degree"] = trafo.get("shift_lv_degree", 0.0)


def calculate_3w_iron_losses(trafo_table: pd.DataFrame) -> None:
    """Calculate iron losses for 3-winding transformers"""
    for idx, trafo in trafo_table.iterrows():
        # Calculate iron losses from conductance (g) values
        # Use the LV side voltage as reference
        v_lv = trafo["vn_lv_kv"]

        if "g1" in trafo:
            # Iron losses are typically dominated by the core, so we use g1 (HV side)
            pfe_kw = trafo["g1"] * (v_lv * 1000) ** 2 / 1000  # Convert to kW
            trafo_table.loc[idx, "pfe_kw"] = pfe_kw

        if "b1" in trafo:
            # Calculate no-load current percentage
            y_mag = math.sqrt(trafo.get("g1", 0) ** 2 + trafo.get("b1", 0) ** 2)
            i0_percent = y_mag * v_lv ** 2 / trafo.get("rated_s1", 100) * 100
            trafo_table.loc[idx, "i0_percent"] = i0_percent


## Enhanced 2-Winding Transformer Tap Changer Functions


def add_tap_parameters_for_ratio_tap_changer(
        powsybl_net: "pypowsybl.network.Network", trafo_table: pd.DataFrame
) -> pd.DataFrame:
    """Comprehensive ratio tap changer parameter calculation"""
    ratio_tap_changers = powsybl_net.get_ratio_tap_changers(all_attributes=True)

    if ratio_tap_changers.empty:
        return trafo_table

    # Merge tap changer info
    trafo_table = pd.merge(
        trafo_table,
        ratio_tap_changers[
            [
                "tap",
                "low_tap",
                "high_tap",
                "regulated_side",
                "target_v",
                "target_deadband",
            ]
        ],
        left_on=IDENTIFIER_COLUMN_NAME,
        right_index=True,
        how="left",
    )

    # Get tap steps for detailed calculation
    ratio_tap_changer_steps = powsybl_net.get_ratio_tap_changer_steps(
        all_attributes=True
    )

    for idx, trafo in trafo_table.iterrows():
        trafo_id = trafo[IDENTIFIER_COLUMN_NAME]

        if trafo_id in ratio_tap_changers.index:
            # Basic tap parameters
            trafo_table.loc[idx, "tap_pos"] = ratio_tap_changers.loc[trafo_id, "tap"]
            trafo_table.loc[idx, "tap_min"] = ratio_tap_changers.loc[
                trafo_id, "low_tap"
            ]
            trafo_table.loc[idx, "tap_max"] = ratio_tap_changers.loc[
                trafo_id, "high_tap"
            ]
            trafo_table.loc[idx, "tap_neutral"] = (
                                                          ratio_tap_changers.loc[trafo_id, "high_tap"]
                                                          - ratio_tap_changers.loc[trafo_id, "low_tap"]
                                                  ) / 2 + ratio_tap_changers.loc[trafo_id, "low_tap"]

            # Tap side mapping
            regulated_side = ratio_tap_changers.loc[trafo_id, "regulated_side"]
            trafo_table.loc[idx, "tap_side"] = "lv" if regulated_side == "ONE" else "hv"

            # Calculate detailed tap step parameters
            if trafo_id in ratio_tap_changer_steps.index.get_level_values(0):
                steps = ratio_tap_changer_steps.loc[trafo_id]
                # here check if ratio has also alpha , if so proviide for tap_type both
                calculate_detailed_tap_parameters(trafo_table, idx, steps, "ratio")

            if trafo_table.loc[idx, "tap_side"] == "hv":
                trafo_v = trafo["vn_hv_kv"]
            else:
                trafo_v = trafo["vn_lv_kv"]
            # Voltage regulation parameters
            trafo_table.loc[idx, "tap_voltage_regulation"] = True
            trafo_table.loc[idx, "tap_vm_setpoint_pu"] = (
                    ratio_tap_changers.loc[trafo_id, "target_v"] / trafo_v
            )
            trafo_table.loc[idx, "tap_voltage_deadband_pu"] = (
                    ratio_tap_changers.loc[trafo_id, "target_deadband"] / trafo_v
            )
            trafo_table.loc[idx, "oltc"] = ratio_tap_changers.loc[trafo_id, "on_load"]
        else:
            trafo_table.loc[idx, "oltc"] = False
            trafo_table.loc[idx, "tap_min"] = 0
            trafo_table.loc[idx, "tap_max"] = 0
            trafo_table.loc[idx, "tap_neutral"] = 0
            trafo_table.loc[idx, "tap_pos"] = 0
            trafo_table.loc[idx, "tap_step_percent"] = 0
            trafo_table.loc[idx, "tap_step_degree"] = 0
    return trafo_table


def add_tap_parameters_for_phase_tap_changer(
        powsybl_net: "pypowsybl.network.Network", trafo_table: pd.DataFrame
) -> pd.DataFrame:
    """Comprehensive phase tap changer parameter calculation"""
    phase_tap_changers = powsybl_net.get_phase_tap_changers(all_attributes=True)

    if phase_tap_changers.empty:
        return trafo_table

    # Merge phase tap changer info with suffix
    phase_cols = [
        "tap",
        "low_tap",
        "high_tap",
        "regulated_side",
        "regulation_mode",
        "regulation_value",
    ]
    phase_tap_changers_suffix = phase_tap_changers[phase_cols].add_suffix("2")

    trafo_table = pd.merge(
        trafo_table,
        phase_tap_changers_suffix,
        left_on=IDENTIFIER_COLUMN_NAME,
        right_index=True,
        how="left",
    )

    # Get phase tap steps for detailed calculation
    phase_tap_changer_steps = powsybl_net.get_phase_tap_changer_steps(
        all_attributes=True
    )

    for idx, trafo in trafo_table.iterrows():
        trafo_id = trafo[IDENTIFIER_COLUMN_NAME]

        if trafo_id in phase_tap_changers.index:

            # Basic tap parameters
            trafo_table.loc[idx, "tap2_pos"] = phase_tap_changers.loc[trafo_id, "tap"]
            trafo_table.loc[idx, "tap2_min"] = phase_tap_changers.loc[
                trafo_id, "low_tap"
            ]
            trafo_table.loc[idx, "tap2_max"] = phase_tap_changers.loc[
                trafo_id, "high_tap"
            ]
            trafo_table.loc[idx, "tap2_neutral"] = (
                                                           phase_tap_changers.loc[trafo_id, "high_tap"]
                                                           - phase_tap_changers.loc[trafo_id, "low_tap"]
                                                   ) / 2 + phase_tap_changers.loc[trafo_id, "low_tap"]

            # Tap side mapping
            regulated_side = phase_tap_changers.loc[trafo_id, "regulated_side"]
            trafo_table.loc[idx, "tap2_side"] = (
                "hv" if regulated_side == "ONE" else "lv"
            )

            # Calculate detailed tap step parameters
            if trafo_id in phase_tap_changer_steps.index.get_level_values(0):
                steps = phase_tap_changer_steps.loc[trafo_id]
                calculate_detailed_tap_parameters(trafo_table, idx, steps, "phase")

            # Regulation mode parameters
            regulation_mode = phase_tap_changers.loc[trafo_id, "regulation_mode"]
            trafo_table.loc[idx, "tap2_regulation_mode"] = regulation_mode.lower()
            trafo_table.loc[idx, "tap2_regulation_value"] = phase_tap_changers.loc[
                trafo_id, "regulation_value"
            ]
        else:
            trafo_table.loc[idx, "tap2_min"] = 0
            trafo_table.loc[idx, "tap2_max"] = 0
            trafo_table.loc[idx, "tap2_neutral"] = 0
            trafo_table.loc[idx, "tap2_pos"] = 0
            trafo_table.loc[idx, "tap2_step_percent"] = 0
            trafo_table.loc[idx, "tap2_step_degree"] = 0
    return trafo_table


def calculate_detailed_tap_parameters(
        trafo_table: pd.DataFrame, idx: int, steps: pd.DataFrame, tap_type: str
) -> None:
    """
    Map powsybl tap data to pandapower so that the *current tap position* is accurate.
    This is only good for the snapshot anaylsis. (tap_pos cannot be changed in
     pandapower, the position should be changed in powsybl)

    """
    prefix = "tap2_" if tap_type == "phase" else "tap_"
    current_pos = trafo_table.loc[idx, f"{prefix}pos"]

    if current_pos not in steps.index:
        raise ValueError(f"Tap position {current_pos} not found")
    tap_neutral = trafo_table.loc[idx, f"{prefix}neutral"]
    trafo_table.loc[idx, f"{prefix}tap_pos"] = current_pos
    if tap_type == "ratio":
        alpha = 0.
        rho = steps.loc[current_pos, "rho"]
        if "alpha" in steps.columns:
            alpha = steps.loc[current_pos, "alpha"]  # if alpha value is there
        if current_pos == tap_neutral:
            step_percent = 0.0
            step_degree = 0.0
        else:
            step_percent = (rho - 1.0) * 100.0 / (current_pos - tap_neutral)
            step_degree = alpha / (current_pos - tap_neutral)
        trafo_table.loc[idx, f"{prefix}step_percent"] = step_percent
        trafo_table.loc[idx, f"{prefix}step_degree"] = step_degree

    elif tap_type == "phase":  # phase shifter
        rho = 0.
        alpha = steps.loc[current_pos, "alpha"]
        if "rho" in steps.columns:
            rho = steps.loc[current_pos, "rho"]  # if rho is present
        if current_pos == tap_neutral:
            step_percent = 0.0
            step_degree = 0.0
        else:
            step_percent = (rho - 1.0) * 100.0 / (current_pos - tap_neutral)
            step_degree = alpha / (current_pos - tap_neutral)

        trafo_table.loc[idx, f"{prefix}step_degree"] = step_degree
        trafo_table.loc[idx, f"{prefix}step_percent"] = step_percent
    else:
        logger.add_warning(f"{tap_type} not processed")
