# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from pathlib import Path
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, fromstring, tostring

from VeraGridEngine.enumerations import FmiVersion
from VeraGridEngine.IO.fmu.ExportInterface.export_ir import ExportModel, ExportVariable, VariableCategory


def emit_model_description(
    export_model: ExportModel,
    fmi_version: FmiVersion = FmiVersion.FMI_2_0,
) -> str:
    """Serialize a validated model-exchange model using the selected FMI schema.

    :param export_model: Neutral export representation to serialize.
    :param fmi_version: FMI schema generation written to the document.
    :return: UTF-8 XML text containing the complete model description.
    """
    model_variables: list[ExportVariable] = list(export_model.xml_variables())
    if fmi_version == FmiVersion.FMI_1_0:
        xml_index_by_uid: dict[int, int] = dict()
        for index, variable in enumerate(model_variables, start=1):
            xml_index_by_uid[variable.uid] = index
        root = Element(
            "fmiModelDescription",
            dict(
                fmiVersion="1.0",
                modelName=export_model.model_name,
                modelIdentifier=export_model.model_identifier,
                guid=export_model.guid,
                generationTool="veragrid_fmu_me_export",
                variableNamingConvention="flat",
                numberOfContinuousStates=str(
                    export_model.counts.get("states", 0)
                ),
                numberOfEventIndicators=str(
                    export_model.counts.get("event_indicators", 0)
                ),
            ),
        )
        SubElement(
            root,
            "DefaultExperiment",
            dict(
                startTime="0.0",
                tolerance=format(export_model.relative_tolerance, ".17g"),
            ),
        )
        model_variables_element = SubElement(root, "ModelVariables")
        for variable in model_variables:
            if variable.causality in ("input", "output"):
                fmi_one_causality: str = variable.causality
            else:
                fmi_one_causality = "internal"
            if variable.causality == "parameter" or variable.variability in (
                "fixed",
                "tunable",
            ):
                fmi_one_variability: str = "parameter"
            else:
                fmi_one_variability = variable.variability
            attrs: dict[str, str] = dict(
                name=variable.name,
                valueReference=str(variable.value_reference),
                causality=fmi_one_causality,
                variability=fmi_one_variability,
            )
            scalar = SubElement(model_variables_element, "ScalarVariable", attrs)
            real_attrs: dict[str, str] = dict()
            if variable.start is not None:
                real_attrs["start"] = format(variable.start, ".17g")
            else:
                pass
            if variable.nominal is not None:
                real_attrs["nominal"] = format(variable.nominal, ".17g")
            else:
                pass
            SubElement(scalar, "Real", real_attrs)
    elif fmi_version == FmiVersion.FMI_3_0:
        root = Element(
            "fmiModelDescription",
            dict(
                fmiVersion="3.0",
                modelName=export_model.model_name,
                instantiationToken=export_model.guid,
                generationTool="veragrid_fmu_me_export",
                variableNamingConvention="flat",
            ),
        )
        SubElement(
            root,
            "ModelExchange",
            dict(
                modelIdentifier=export_model.model_identifier,
                needsExecutionTool="false",
                canGetAndSetFMUState="false",
                canSerializeFMUState="false",
                providesDirectionalDerivatives="false",
                providesAdjointDerivatives="false",
                needsCompletedIntegratorStep="true" if export_model.needs_completed_integrator_step() else "false",
                providesEvaluateDiscreteStates="false",
            ),
        )
        SubElement(
            root,
            "DefaultExperiment",
            dict(
                startTime="0.0",
                stepSize=format(export_model.default_step_size, ".17g"),
                tolerance=format(export_model.relative_tolerance, ".17g"),
            ),
        )
        model_variables_element = SubElement(root, "ModelVariables")
        maximum_value_reference: int = -1
        for variable in model_variables:
            attrs: dict[str, str] = dict(
                name=variable.name,
                valueReference=str(variable.value_reference),
                causality=variable.causality,
                variability=variable.variability,
            )
            if variable.initial is not None:
                attrs["initial"] = variable.initial
            else:
                pass
            if variable.start is not None:
                attrs["start"] = format(variable.start, ".17g")
            else:
                pass
            if variable.nominal is not None:
                attrs["nominal"] = format(variable.nominal, ".17g")
            else:
                pass
            if variable.category == VariableCategory.DERIVATIVE and variable.derivative_of_uid is not None:
                attrs["derivative"] = str(export_model.variable_by_uid(variable.derivative_of_uid).value_reference)
            else:
                pass
            SubElement(model_variables_element, "Float64", attrs)
            if variable.value_reference > maximum_value_reference:
                maximum_value_reference = variable.value_reference
            else:
                pass
        event_value_reference_start: int = maximum_value_reference + 1
        for event_indicator in export_model.event_indicators:
            event_value_reference: int = event_value_reference_start + event_indicator.index
            SubElement(
                model_variables_element,
                "Float64",
                dict(
                    name=f"__veragrid_event_indicator_{event_indicator.index}",
                    valueReference=str(event_value_reference),
                    causality="local",
                    variability="continuous",
                ),
            )
        time_value_reference: int = event_value_reference_start + len(export_model.event_indicators)
        SubElement(
            model_variables_element,
            "Float64",
            dict(
                name="time",
                valueReference=str(time_value_reference),
                causality="independent",
                variability="continuous",
            ),
        )
        structure = SubElement(root, "ModelStructure")
        for variable in export_model.output_variables():
            SubElement(structure, "Output", dict(valueReference=str(variable.value_reference)))
        for variable in export_model.derivative_variables():
            SubElement(structure, "ContinuousStateDerivative", dict(valueReference=str(variable.value_reference)))
        for variable in export_model.initial_unknown_variables():
            SubElement(structure, "InitialUnknown", dict(valueReference=str(variable.value_reference)))
        for event_indicator in export_model.event_indicators:
            event_value_reference = event_value_reference_start + event_indicator.index
            SubElement(structure, "EventIndicator", dict(valueReference=str(event_value_reference)))
    else:
        if fmi_version != FmiVersion.FMI_2_0:
            raise NotImplementedError(f"FMI {fmi_version.value} Model Exchange XML is not implemented")
        else:
            pass
        xml_index_by_uid: dict[int, int] = dict()
        for index, variable in enumerate(model_variables, start=1):
            xml_index_by_uid[variable.uid] = index
        root = Element(
            "fmiModelDescription",
            dict(
                fmiVersion="2.0",
                modelName=export_model.model_name,
                guid=export_model.guid,
                generationTool="veragrid_fmu_me_export",
                variableNamingConvention="flat",
                numberOfEventIndicators=str(export_model.counts.get("event_indicators", 0)),
            ),
        )
        SubElement(
            root,
            "ModelExchange",
            dict(
                modelIdentifier=export_model.model_identifier,
                completedIntegratorStepNotNeeded="false" if export_model.needs_completed_integrator_step() else "true",
                canGetAndSetFMUstate="false",
                canSerializeFMUstate="false",
                providesDirectionalDerivative="false",
            ),
        )
        SubElement(
            root,
            "DefaultExperiment",
            dict(
                startTime="0.0",
                stepSize=format(export_model.default_step_size, ".17g"),
                tolerance=format(export_model.relative_tolerance, ".17g"),
            ),
        )
        model_variables_element = SubElement(root, "ModelVariables")
        for variable in model_variables:
            attrs = dict(
                name=variable.name,
                valueReference=str(variable.value_reference),
                causality=variable.causality,
                variability=variable.variability,
            )
            if variable.initial is not None:
                attrs["initial"] = variable.initial
            else:
                pass
            scalar = SubElement(model_variables_element, "ScalarVariable", attrs)
            real_attrs: dict[str, str] = dict()
            if variable.start is not None:
                real_attrs["start"] = format(variable.start, ".17g")
            else:
                pass
            if variable.nominal is not None:
                real_attrs["nominal"] = format(variable.nominal, ".17g")
            else:
                pass
            if variable.category == VariableCategory.DERIVATIVE and variable.derivative_of_uid is not None:
                real_attrs["derivative"] = str(xml_index_by_uid[variable.derivative_of_uid])
            else:
                pass
            SubElement(scalar, "Real", real_attrs)
        structure = SubElement(root, "ModelStructure")
        outputs = export_model.output_variables()
        if len(outputs) > 0:
            outputs_element = SubElement(structure, "Outputs")
            for variable in outputs:
                SubElement(outputs_element, "Unknown", dict(index=str(xml_index_by_uid[variable.uid])))
        else:
            pass
        derivatives = export_model.derivative_variables()
        if len(derivatives) > 0:
            derivatives_element = SubElement(structure, "Derivatives")
            for variable in derivatives:
                SubElement(derivatives_element, "Unknown", dict(index=str(xml_index_by_uid[variable.uid])))
        else:
            pass
        initial_unknowns = export_model.initial_unknown_variables()
        if len(initial_unknowns) > 0:
            initial_unknowns_element = SubElement(structure, "InitialUnknowns")
            for variable in initial_unknowns:
                SubElement(initial_unknowns_element, "Unknown", dict(index=str(xml_index_by_uid[variable.uid])))
        else:
            pass
    xml_bytes: bytes = tostring(root, encoding="utf-8")
    pretty: str = minidom.parseString(xml_bytes).toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")
    fromstring(pretty)
    return pretty

def write_model_description(
    export_model: ExportModel,
    path: str | Path,
    fmi_version: FmiVersion = FmiVersion.FMI_2_0,
) -> Path:
    """Write one model-exchange model description to disk.

    :param export_model: Neutral export representation to serialize.
    :param path: Destination XML path.
    :param fmi_version: FMI schema generation written to the document.
    :return: Written destination path.
    """
    output_path: Path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(emit_model_description(export_model, fmi_version), encoding="utf-8")
    return output_path
