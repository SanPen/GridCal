from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, List


ROOT = Path(__file__).resolve().parent
MD_SOURCE = ROOT / "md_source"
DEVICES_DIR = MD_SOURCE / "devices"
DATA_MODELS_FILE = MD_SOURCE / "data_models.md"
MODELLING_SOURCE_FILE = DEVICES_DIR / "_modelling_source.md"
MODELLING_FILE = MD_SOURCE / "modelling.md"


@dataclass(frozen=True)
class DeviceDoc:
    category: str
    class_name: str
    filename: str


DEVICE_DOCS: List[DeviceDoc] = [
    DeviceDoc("Substation", "Bus", "bus.md"),
    DeviceDoc("Substation", "BusBar", "bus_bar.md"),
    DeviceDoc("Substation", "VoltageLevel", "voltage_level.md"),
    DeviceDoc("Substation", "Substation", "substation.md"),
    DeviceDoc("Regions", "Country", "country.md"),
    DeviceDoc("Regions", "Community", "community.md"),
    DeviceDoc("Regions", "Region", "region.md"),
    DeviceDoc("Regions", "Municipality", "municipality.md"),
    DeviceDoc("Regions", "Area", "area.md"),
    DeviceDoc("Regions", "Zone", "zone.md"),
    DeviceDoc("Injections", "Generator", "generator.md"),
    DeviceDoc("Injections", "Battery", "battery.md"),
    DeviceDoc("Injections", "Load", "load.md"),
    DeviceDoc("Injections", "Shunt", "shunt.md"),
    DeviceDoc("Injections", "ControllableShunt", "controllable_shunt.md"),
    DeviceDoc("Injections", "CurrentInjection", "current_injection.md"),
    DeviceDoc("Injections", "StaticGenerator", "static_generator.md"),
    DeviceDoc("Injections", "ExternalGrid", "external_grid.md"),
    DeviceDoc("Branches", "Line", "line.md"),
    DeviceDoc("Branches", "DcLine", "dc_line.md"),
    DeviceDoc("Branches", "Winding", "winding.md"),
    DeviceDoc("Branches", "Transformer2W", "transformer_2w.md"),
    DeviceDoc("Branches", "Transformer3W", "transformer_3w.md"),
    DeviceDoc("Branches", "TransformerNW", "transformer_nw.md"),
    DeviceDoc("Branches", "SeriesReactance", "series_reactance.md"),
    DeviceDoc("Branches", "HvdcLine", "hvdc_line.md"),
    DeviceDoc("Branches", "VSC", "vsc.md"),
    DeviceDoc("Branches", "UPFC", "upfc.md"),
    DeviceDoc("Branches", "Switch", "switch.md"),
    DeviceDoc("Catalogue", "Wire", "wire.md"),
    DeviceDoc("Catalogue", "OverheadLineType", "overhead_line_type.md"),
    DeviceDoc("Catalogue", "UndergroundCableType", "underground_cable_type.md"),
    DeviceDoc("Catalogue", "UndergroundLineType", "underground_line_type.md"),
    DeviceDoc("Catalogue", "SequenceLineType", "sequence_line_type.md"),
    DeviceDoc("Catalogue", "TransformerType", "transformer_type.md"),
    DeviceDoc("Groups", "BranchGroup", "branch_group.md"),
    DeviceDoc("Groups", "Facility", "facility.md"),
    DeviceDoc("Groups", "ModellingAuthority", "modelling_authority.md"),
    DeviceDoc("Associations", "Technology", "technology.md"),
    DeviceDoc("Associations", "Fuel", "fuel.md"),
    DeviceDoc("Associations", "EmissionGas", "emission_gas.md"),
    DeviceDoc("Associations", "Owner", "owner.md"),
    DeviceDoc("Contingencies", "ContingencyGroup", "contingency_group.md"),
    DeviceDoc("Contingencies", "Contingency", "contingency.md"),
    DeviceDoc("Contingencies", "RemedialActionGroup", "remedial_action_group.md"),
    DeviceDoc("Contingencies", "RemedialAction", "remedial_action.md"),
    DeviceDoc("Contingencies", "ShortCircuitEvent", "short_circuit_event.md"),
    DeviceDoc("Investments", "InvestmentsGroup", "investments_group.md"),
    DeviceDoc("Investments", "Investment", "investment.md"),
    DeviceDoc("Fluid", "FluidNode", "fluid_node.md"),
    DeviceDoc("Fluid", "FluidPath", "fluid_path.md"),
    DeviceDoc("Fluid", "FluidTurbine", "fluid_turbine.md"),
    DeviceDoc("Fluid", "FluidPump", "fluid_pump.md"),
    DeviceDoc("Fluid", "FluidP2x", "fluid_p2x.md"),
    DeviceDoc("Dynamic", "RmsEventsGroup", "rms_events_group.md"),
    DeviceDoc("Dynamic", "RmsEvent", "rms_event.md"),
    DeviceDoc("Dynamic", "EmtEventsGroup", "emt_events_group.md"),
    DeviceDoc("Dynamic", "EmtEvent", "emt_event.md"),
    DeviceDoc("Templates", "RmsModelTemplate", "rms_model_template.md"),
    DeviceDoc("Templates", "EmtModelTemplate", "emt_model_template.md"),
    DeviceDoc("Templates", "FmuTemplate", "fmu_template.md"),
    DeviceDoc("Measurements", "PiMeasurement", "pi_measurement.md"),
    DeviceDoc("Measurements", "QiMeasurement", "qi_measurement.md"),
    DeviceDoc("Measurements", "PfMeasurement", "pf_measurement.md"),
    DeviceDoc("Measurements", "QfMeasurement", "qf_measurement.md"),
    DeviceDoc("Measurements", "IfMeasurement", "if_measurement.md"),
    DeviceDoc("Measurements", "PtMeasurement", "pt_measurement.md"),
    DeviceDoc("Measurements", "QtMeasurement", "qt_measurement.md"),
    DeviceDoc("Measurements", "ItMeasurement", "it_measurement.md"),
    DeviceDoc("Measurements", "VmMeasurement", "vm_measurement.md"),
    DeviceDoc("Measurements", "VaMeasurement", "va_measurement.md"),
    DeviceDoc("Measurements", "PgMeasurement", "pg_measurement.md"),
    DeviceDoc("Measurements", "QgMeasurement", "qg_measurement.md"),
]


CATEGORY_NOTES = {
    "Substation": "This device belongs to the electrical topology and location hierarchy managed directly by `MultiCircuit`.",
    "Regions": "This device provides geographical or administrative context for topology and reporting.",
    "Associations": "This device is used as reusable metadata that other assets can reference through associations.",
    "Injections": "This device connects to a bus and contributes power, current, or admittance to the solved network model.",
    "Branches": "This device links terminals or represents a network element between buses.",
    "Catalogue": "This device stores reusable equipment data that can be applied to physical network elements.",
    "Groups": "This device organizes assets for modelling, ownership, filtering, or reporting.",
    "Contingencies": "This device defines study events, outages, switching actions, or remedial actions.",
    "Investments": "This device is used by expansion-planning and candidate-investment workflows.",
    "Fluid": "This device belongs to the fluid and hydro layer that can be modelled alongside the electrical network.",
    "Dynamic": "This device supports RMS or EMT event scheduling and dynamic simulations.",
    "Templates": "This device stores reusable native or FMU-backed dynamic model templates.",
    "Measurements": "This device stores measurement data used by observability and state-estimation workflows.",
}


DEVICE_NOTES = {
    "Bus": "A `Bus` is the main electrical node in `MultiCircuit`. It holds voltage state variables and anchors injections, branch terminals, and operational limits.",
    "BusBar": "A `BusBar` represents an explicit busbar object inside a voltage level. It is useful when diagram structure or substation-level topology needs to be preserved.",
    "VoltageLevel": "A `VoltageLevel` groups buses and busbars that belong to the same nominal voltage inside a substation.",
    "Substation": "A `Substation` is the top-level station object used to group voltage levels, buses, and related physical assets.",
    "Country": "A `Country` groups assets at country scope for reporting, filtering, transfer-capacity studies, and geographic organization.",
    "Community": "A `Community` is an intermediate regional grouping that can be attached to buses and inherited by connected assets.",
    "Region": "A `Region` groups substations and buses below the community level and above municipalities.",
    "Municipality": "A `Municipality` stores local administrative context for buses and substations.",
    "Area": "An `Area` groups buses for operational aggregation and transfer-capacity workflows.",
    "Zone": "A `Zone` is a market or study grouping used to aggregate buses and branches.",
    "Generator": "A `Generator` models a controllable bus-connected source. In steady state it behaves as a power injection, and for short-circuit studies it also exposes sequence impedance data.",
    "Battery": "A `Battery` extends generator-style injection modelling with energy-capacity and state-of-charge parameters for storage studies.",
    "Load": "A `Load` implements the ZIP formulation and supports single-phase, two-phase, three-phase, star, and delta modelling patterns.",
    "StaticGenerator": "A `StaticGenerator` represents a fixed P/Q injection or an optional VSC-equivalent Q-V droop control.",
    "ExternalGrid": "An `ExternalGrid` represents an equivalent network connection used to model an upstream or boundary system.",
    "Shunt": "A `Shunt` represents a bus-connected admittance used for reactive support, compensation, and unbalanced admittance modelling.",
    "ControllableShunt": "A `ControllableShunt` extends shunt modelling with discrete or controllable reactive support behaviour.",
    "CurrentInjection": "A `CurrentInjection` injects current directly at a bus and is useful when the source model is expressed naturally in current form.",
    "Line": "A `Line` is the standard AC branch model. It supports positive-sequence and phase-domain formulations, templates, and geometric line-data workflows.",
    "DcLine": "A `DcLine` models a physical line inside a detailed DC grid. It applies the common [Cable System](underground_line_type.md#applying-cable-system-to-a-dc-line) catalogue, selecting one conductor with `dc_conductor`. The system supplies DC resistance and dynamic L/C; length and rating belong to the branch. A branch without a template remains a resistive line.",
    "Winding": "A `Winding` is one terminal element of a multi-winding transformer representation and is primarily used inside transformer assemblies.",
    "Transformer2W": "A `Transformer2W` is the standard two-winding transformer model used in steady-state, short-circuit, and catalogue-driven workflows.",
    "Transformer3W": "A `Transformer3W` stores a three-winding transformer and its associated winding objects.",
    "TransformerNW": "A `TransformerNW` generalizes transformer representation to an arbitrary number of windings.",
    "SeriesReactance": "A `SeriesReactance` is a branch whose main purpose is to model concentrated series reactance between buses.",
    "HvdcLine": "An `HvdcLine` is the aggregated two-converter AC-DC transfer model used for simple HVDC corridors.",
    "VSC": "A `VSC` is the detailed voltage-source-converter branch used for explicit AC-DC grid modelling and converter control formulations.",
    "UPFC": "A `UPFC` models a unified power flow controller embedded in the AC network.",
    "Switch": "A `Switch` models a topological switching element that can open or close network connectivity.",
    "Wire": "A `Wire` stores conductor parameters used by overhead-line templates and geometry-based line calculations.",
    "OverheadLineType": "An `OverheadLineType` stores reusable conductor geometry and the derived impedance and admittance matrices for overhead lines.",
    "UndergroundLineType": "An `UndergroundLineType` stores reusable cable data for underground line modelling.",
    "SequenceLineType": "A `SequenceLineType` stores reusable positive-, negative-, and zero-sequence branch data.",
    "TransformerType": "A `TransformerType` stores reusable nameplate and test-sheet data that can be applied to transformer objects.",
    "BranchGroup": "A `BranchGroup` organizes network branches into study or ownership groupings.",
    "Facility": "A `Facility` groups assets that belong to the same site or installation.",
    "ModellingAuthority": "A `ModellingAuthority` identifies the authority responsible for the data model of an asset.",
    "Technology": "A `Technology` is a reusable association used to tag injections and assets by technology type.",
    "Fuel": "A `Fuel` is a reusable association used to tag generating assets by fuel type.",
    "EmissionGas": "An `EmissionGas` is a reusable association used to tag emitting assets for planning and reporting.",
    "Owner": "An `Owner` is a reusable association attached to assets through ownership lists.",
    "ContingencyGroup": "A `ContingencyGroup` groups related contingency actions into a reusable study set.",
    "Contingency": "A `Contingency` describes one outage or operational change applied during contingency analysis.",
    "RemedialActionGroup": "A `RemedialActionGroup` groups corrective actions that may be applied after a contingency.",
    "RemedialAction": "A `RemedialAction` defines one corrective control or switching action.",
    "ShortCircuitEvent": "A `ShortCircuitEvent` defines a fault event for short-circuit calculations.",
    "InvestmentsGroup": "An `InvestmentsGroup` groups expansion candidates into reusable planning sets.",
    "Investment": "An `Investment` defines one candidate asset action for expansion planning.",
    "FluidNode": "A `FluidNode` is the nodal storage or hydraulic state point used in fluid-network modelling.",
    "FluidPath": "A `FluidPath` links fluid nodes and represents the transport path of the fluid network.",
    "FluidTurbine": "A `FluidTurbine` converts hydraulic or fluid energy into electrical generation within the fluid layer.",
    "FluidPump": "A `FluidPump` consumes electrical power to move fluid between nodes.",
    "FluidP2x": "A `FluidP2x` represents power-to-x conversion between electrical and fluid-energy domains.",
    "RmsEventsGroup": "An `RmsEventsGroup` groups RMS dynamic events into a reusable schedule.",
    "RmsEvent": "An `RmsEvent` defines one event applied during RMS dynamic simulations.",
    "EmtEventsGroup": "An `EmtEventsGroup` groups EMT events into a reusable schedule.",
    "EmtEvent": "An `EmtEvent` defines one event applied during EMT simulations.",
    "RmsModelTemplate": "A `RmsModelTemplate` stores a reusable RMS dynamic model definition.",
    "EmtModelTemplate": "An `EmtModelTemplate` stores a reusable EMT dynamic model definition.",
    "FmuTemplate": "A `FmuTemplate` stores reusable FMU metadata for RMS or EMT integration.",
    "PiMeasurement": "A `PiMeasurement` stores active-power injection measurements at buses.",
    "QiMeasurement": "A `QiMeasurement` stores reactive-power injection measurements at buses.",
    "PfMeasurement": "A `PfMeasurement` stores active-power flow measurements on branch from-ends.",
    "QfMeasurement": "A `QfMeasurement` stores reactive-power flow measurements on branch from-ends.",
    "IfMeasurement": "An `IfMeasurement` stores current measurements on branch from-ends.",
    "PtMeasurement": "A `PtMeasurement` stores active-power flow measurements on branch to-ends.",
    "QtMeasurement": "A `QtMeasurement` stores reactive-power flow measurements on branch to-ends.",
    "ItMeasurement": "An `ItMeasurement` stores current measurements on branch to-ends.",
    "VmMeasurement": "A `VmMeasurement` stores bus voltage-magnitude measurements.",
    "VaMeasurement": "A `VaMeasurement` stores bus voltage-angle measurements.",
    "PgMeasurement": "A `PgMeasurement` stores active-power generation measurements.",
    "QgMeasurement": "A `QgMeasurement` stores reactive-power generation measurements.",
}


AUTO_GENERATED_COMMENT = "<!-- Auto-generated by doc/generate_device_docs.py. Do not edit this file directly. -->\n\n"


def extract_between(text: str, start: str, end: str | None = None) -> str:
    start_idx = text.index(start)
    if end is None:
        end_idx = len(text)
    else:
        end_idx = text.index(end, start_idx)
    return text[start_idx:end_idx].strip() + "\n"


def replace_first_heading(text: str, new_heading: str) -> str:
    return re.sub(r"^#{2,3} .*$", new_heading, text, count=1, flags=re.MULTILINE)


def fix_device_relative_assets(text: str) -> str:
    """Rebase chapter-relative links for the generated device pages.

    :param text: Device section using chapter-relative asset and modelling links.
    :return: Section with paths relative to the devices directory.
    """
    text = text.replace("](figures/", "](../figures/")
    text = text.replace('src="figures/', 'src="../figures/')
    text = text.replace("](modelling.md#", "](../modelling.md#")
    text = text.replace("](file_operations.md#", "](../file_operations.md#")
    return text


def parse_markdown_table(table_lines: List[str]) -> List[Dict[str, str]]:
    headers = [cell.strip() for cell in table_lines[0].strip("|").split("|")]
    rows: List[Dict[str, str]] = []
    for line in table_lines[2:]:
        values = [cell.strip() for cell in line.strip("|").split("|")]
        row = {headers[idx]: values[idx] if idx < len(values) else "" for idx in range(len(headers))}
        rows.append(row)
    return rows


def parse_veragrid_tables(text: str) -> Dict[str, Dict[str, object]]:
    start_idx = text.index("## VeraGrid")
    end_idx = text.index("\n## CGMES", start_idx)
    section = text[start_idx:end_idx]
    lines = section.splitlines()
    tables: Dict[str, Dict[str, object]] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("### "):
            name = line[4:].strip()
            i += 1
            while i < len(lines) and not lines[i].startswith("|"):
                i += 1
            table_lines: List[str] = []
            while i < len(lines) and lines[i].startswith("|"):
                table_lines.append(lines[i])
                i += 1
            if table_lines:
                tables[name] = {
                    "table": "\n".join(table_lines).strip() + "\n",
                    "rows": parse_markdown_table(table_lines),
                }
            continue
        i += 1
    return tables


def get_profile_enabled_properties(rows: List[Dict[str, str]]) -> List[str]:
    result: List[str] = []
    for row in rows:
        if row.get("has_profile", "").strip() == "True":
            result.append(row.get("name", "").strip())
    return result


def render_property_block(class_name: str, table_info: Dict[str, object]) -> str:
    """Render registered properties and their profile availability.

    :param class_name: Name of the device class being documented.
    :param table_info: Parsed property rows and their Markdown table.
    :return: Registered-property section for the device.
    """
    rows = table_info["rows"]  # type: ignore[index]
    table: str = str(table_info["table"])
    # Construction descriptions use native property names; omit import-field annotations.
    if class_name == "UndergroundCableType":
        table = re.sub(r" \([^)]*\)", "", table)
    else:
        pass
    profiles = get_profile_enabled_properties(rows)  # type: ignore[arg-type]
    parts = ["### Registered properties\n"]
    if profiles:
        profile_text = ", ".join(f"`{name}`" for name in profiles)
        parts.append(f"Profile-enabled properties: {profile_text}.\n")
    else:
        parts.append("Profile-enabled properties: none.\n")
    parts.append("\n")
    parts.append(table)
    parts.append("\n")
    return "".join(parts)


def render_generic_device_doc(device: DeviceDoc, table_info: Dict[str, object]) -> str:
    title = device.class_name
    note = DEVICE_NOTES.get(device.class_name, f"`{device.class_name}` is a `{device.category}` device exposed by `MultiCircuit`.")
    category_note = CATEGORY_NOTES[device.category]
    return (
        f"## {title}\n\n"
        f"{note}\n\n"
        f"{category_note}\n\n"
        f"{render_property_block(device.class_name, table_info)}"
    )


def build_legacy_sections(source_text: str) -> Dict[str, str]:
    overview = source_text.split("# 📐 Grid Modelling", 1)[1]
    overview = extract_between(overview, "\n", "\n## Lines").strip() + "\n"

    lines_block = extract_between(source_text, "## Lines", "## Transformers")
    transformers_block = extract_between(source_text, "## Transformers", "## Loads and Shunts")
    loads_block = extract_between(source_text, "## Loads and Shunts", "## Generators")
    generators_block = extract_between(source_text, "## Generators", "## AC-DC modelling")
    acdc_block = extract_between(
        source_text,
        "## AC-DC modelling",
        "## Distribution Grid Example in the Sequence Reference Frame",
    )
    distribution_block = extract_between(
        source_text,
        "## Distribution Grid Example in the Sequence Reference Frame",
        "## Power Flow on the 5-Node Example Grid",
    )
    power_flow_block = extract_between(
        source_text,
        "## Power Flow on the 5-Node Example Grid",
        "## Substations modelling",
    )

    impedance_start = "### Constant impedance (Z) modelling of three-phase star-connected loads and shunts"
    current_start = "### Constant current (I) modelling of three-phase star-connected loads"
    load_intro = extract_between(loads_block, "## Loads and Shunts", impedance_start)
    impedance_block = extract_between(loads_block, impedance_start, current_start)
    current_and_power_block = extract_between(loads_block, current_start, None)

    hvdc_start = "### HvdcLine: Modelling AC-DC links the easy way"
    vsc_start = "### Vsc: Modelling AC-DC links the better way"
    acdc_intro = extract_between(acdc_block, "## AC-DC modelling", hvdc_start)
    hvdc_block = extract_between(acdc_block, hvdc_start, vsc_start)
    vsc_block = extract_between(acdc_block, vsc_start, None)

    return {
        "overview": overview,
        "line": replace_first_heading(lines_block, "## Line"),
        "transformer_2w": replace_first_heading(transformers_block, "## Transformer2W"),
        "load": (
            "## Load\n\n"
            + load_intro.split("\n", 1)[1].strip()
            + "\n\n"
            + "The impedance component of the ZIP formulation shares the same admittance modelling described in the `Shunt` section.\n\n"
            + current_and_power_block
        ),
        "shunt": (
            "## Shunt\n\n"
            + "Shunt elements were documented together with loads in the original modelling chapter. "
            + "For shunts, the relevant part is the constant-impedance formulation reproduced below.\n\n"
            + impedance_block
        ),
        "generator": replace_first_heading(generators_block, "## Generator"),
        "hvdc_line": (
            "## HvdcLine\n\n"
            + acdc_intro.split("\n", 1)[1].strip()
            + "\n\n"
            + hvdc_block
        ),
        "vsc": replace_first_heading(vsc_block, "## VSC"),
        "distribution": distribution_block,
        "power_flow_example": power_flow_block,
    }


def write_text(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def generate_device_docs() -> None:
    """Generate device pages and the combined modelling chapter from authored sources.

    :return: None.
    """
    DEVICES_DIR.mkdir(parents=True, exist_ok=True)

    data_models_text = DATA_MODELS_FILE.read_text(encoding="utf-8")
    source_text = MODELLING_SOURCE_FILE.read_text(encoding="utf-8")
    cable_source: str = (DEVICES_DIR / "_underground_catalogue_source.md").read_text(encoding="utf-8")
    transformer3w_source: str = (DEVICES_DIR / "_transformer_3w_source.md").read_text(encoding="utf-8")

    tables = parse_veragrid_tables(data_models_text)
    legacy = build_legacy_sections(source_text)

    root_sections: Dict[str, str] = {
        "Line": legacy["line"],
        "Transformer2W": legacy["transformer_2w"],
        "Transformer3W": transformer3w_source,
        "Load": legacy["load"],
        "Shunt": legacy["shunt"],
        "Generator": legacy["generator"],
        "StaticGenerator": (DEVICES_DIR / "_static_generator_source.md").read_text(encoding="utf-8"),
        "ControllableShunt": (DEVICES_DIR / "_controllable_shunt_source.md").read_text(encoding="utf-8"),
        "HvdcLine": legacy["hvdc_line"],
        "VSC": legacy["vsc"],
        "UndergroundCableType": extract_between(cable_source, "## UndergroundCableType", "## UndergroundLineType"),
        "UndergroundLineType": extract_between(cable_source, "## UndergroundLineType"),
    }

    for device in DEVICE_DOCS:
        table_info = tables.get(device.class_name)
        if table_info is None:
            raise KeyError(f"Could not find data-model table for {device.class_name}")

        root_doc = root_sections.get(device.class_name)
        if root_doc is None:
            root_doc = render_generic_device_doc(device, table_info)
        else:
            root_doc = root_doc.rstrip() + "\n\n" + render_property_block(device.class_name, table_info)

        device_text = AUTO_GENERATED_COMMENT + fix_device_relative_assets(root_doc)
        write_text(DEVICES_DIR / device.filename, device_text)
        root_sections[device.class_name] = root_doc

    chapter_parts = [AUTO_GENERATED_COMMENT, "# 📐 Grid Modelling\n\n", legacy["overview"].strip(), "\n\n"]

    for device in DEVICE_DOCS:
        chapter_parts.append(root_sections[device.class_name].strip())
        chapter_parts.append("\n\n")

    chapter_parts.append(legacy["distribution"].strip())
    chapter_parts.append("\n\n")
    chapter_parts.append(legacy["power_flow_example"].strip())
    chapter_parts.append("\n")

    write_text(MODELLING_FILE, "".join(chapter_parts))


if __name__ == "__main__":
    generate_device_docs()
