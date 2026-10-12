# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from pathlib import Path
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, fromstring, tostring

from VeraGridEngine.enumerations import FmiVersion
from VeraGridEngine.IO.fmu.CosimulationInterface.export_ir import ExportModel, ExportVariable


def emit_model_description(
    export_model: ExportModel,
    fmi_version: FmiVersion = FmiVersion.FMI_2_0,
) -> str:
    """Serialize a validated co-simulation model using the selected FMI schema.

    :param export_model: Neutral export representation to serialize.
    :param fmi_version: FMI schema generation written to the document.
    :return: UTF-8 XML text containing the complete model description.
    """
    exposed: list[ExportVariable] = list(export_model.exposed_variables())
    if fmi_version == FmiVersion.FMI_1_0:
        root = Element(
            "fmiModelDescription",
            dict(
                fmiVersion="1.0",
                modelName=export_model.model_name,
                modelIdentifier=export_model.model_identifier,
                guid=export_model.guid,
                generationTool="veragrid_fmu_export",
                variableNamingConvention="flat",
                numberOfContinuousStates="0",
                numberOfEventIndicators="0",
            ),
        )
        SubElement(
            root,
            "DefaultExperiment",
            dict(startTime="0.0"),
        )
        model_variables = SubElement(root, "ModelVariables")
        for variable in exposed:
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
            scalar = SubElement(model_variables, "ScalarVariable", attrs)
            real_attrs: dict[str, str] = dict()
            if variable.start is not None:
                real_attrs["start"] = format(variable.start, ".17g")
            else:
                pass
            SubElement(scalar, "Real", real_attrs)
        implementation = SubElement(root, "Implementation")
        standalone = SubElement(implementation, "CoSimulation_StandAlone")
        SubElement(
            standalone,
            "Capabilities",
            dict(
                canHandleVariableCommunicationStepSize="true",
                canHandleEvents="false",
                canRejectSteps="false",
                canInterpolateInputs="false",
                maxOutputDerivativeOrder="0",
                canRunAsynchronuously="false",
                canSignalEvents="false",
                canBeInstantiatedOnlyOncePerProcess="false",
                canNotUseMemoryManagementFunctions="false",
            ),
        )
    else:
        if fmi_version == FmiVersion.FMI_3_0:
            root = Element(
            "fmiModelDescription",
            dict(
                fmiVersion="3.0",
                modelName=export_model.model_name,
                instantiationToken=export_model.guid,
                generationTool="veragrid_fmu_export",
                variableNamingConvention="flat",
            ),
        )
            SubElement(
            root,
            "CoSimulation",
            dict(
                modelIdentifier=export_model.model_identifier,
                needsExecutionTool="false",
                canGetAndSetFMUState="false",
                canSerializeFMUState="false",
                providesDirectionalDerivatives="false",
                providesAdjointDerivatives="false",
                canHandleVariableCommunicationStepSize="true",
                fixedInternalStepSize=format(export_model.fixed_step, ".17g"),
                maxOutputDerivativeOrder="0",
                providesIntermediateUpdate="false",
                mightReturnEarlyFromDoStep="false",
                canReturnEarlyAfterIntermediateUpdate="false",
                hasEventMode="false",
            ),
        )
            SubElement(
            root,
            "DefaultExperiment",
            dict(startTime="0.0", stepSize=format(export_model.fixed_step, ".17g")),
        )
            model_variables = SubElement(root, "ModelVariables")
            for variable in exposed:
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
                SubElement(model_variables, "Float64", attrs)
            maximum_value_reference: int = -1
            for variable in exposed:
                if variable.value_reference is not None and variable.value_reference > maximum_value_reference:
                    maximum_value_reference = variable.value_reference
                else:
                    pass
            time_value_reference: int = maximum_value_reference + 1
            SubElement(
            model_variables,
            "Float64",
            dict(
                name="time",
                valueReference=str(time_value_reference),
                causality="independent",
                variability="continuous",
            ),
        )
            structure = SubElement(root, "ModelStructure")
            for variable in exposed:
                if variable.causality == "output":
                    SubElement(structure, "Output", dict(valueReference=str(variable.value_reference)))
                else:
                    pass
            for variable in exposed:
                if variable.causality == "output" and variable.initial in {"calculated", "approx"}:
                    SubElement(structure, "InitialUnknown", dict(valueReference=str(variable.value_reference)))
                else:
                    pass
        else:
            if fmi_version != FmiVersion.FMI_2_0:
                raise NotImplementedError(f"FMI {fmi_version.value} Co-Simulation XML is not implemented")
            else:
                pass
            root = Element(
            "fmiModelDescription",
            dict(
                fmiVersion="2.0",
                modelName=export_model.model_name,
                guid=export_model.guid,
                generationTool="veragrid_fmu_export",
                variableNamingConvention="flat",
                numberOfEventIndicators="0",
            ),
        )
            SubElement(
            root,
            "CoSimulation",
            dict(
                modelIdentifier=export_model.model_identifier,
                canHandleVariableCommunicationStepSize="true",
                canInterpolateInputs="false",
                maxOutputDerivativeOrder="0",
                canGetAndSetFMUstate="false",
                canSerializeFMUstate="false",
                providesDirectionalDerivative="false",
            ),
        )
            SubElement(
            root,
            "DefaultExperiment",
            dict(startTime="0.0", stepSize=format(export_model.fixed_step, ".17g")),
        )
            model_variables = SubElement(root, "ModelVariables")
            for variable in exposed:
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
                scalar = SubElement(model_variables, "ScalarVariable", attrs)
                real_attrs: dict[str, str] = dict()
                if variable.start is not None:
                    real_attrs["start"] = format(variable.start, ".17g")
                else:
                    pass
                SubElement(scalar, "Real", real_attrs)
            structure = SubElement(root, "ModelStructure")
            outputs_element = SubElement(structure, "Outputs")
            initial_unknown_indices: list[int] = list()
            for index, variable in enumerate(exposed, start=1):
                if variable.causality == "output":
                    SubElement(outputs_element, "Unknown", dict(index=str(index)))
                else:
                    pass
                if variable.causality == "output" and variable.initial in {"calculated", "approx"}:
                    initial_unknown_indices.append(index)
                else:
                    pass
            if len(initial_unknown_indices) > 0:
                initial_unknowns = SubElement(structure, "InitialUnknowns")
                for index in initial_unknown_indices:
                    SubElement(initial_unknowns, "Unknown", dict(index=str(index)))
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
    """Write one co-simulation model description to disk.

    :param export_model: Neutral export representation to serialize.
    :param path: Destination XML path.
    :param fmi_version: FMI schema generation written to the document.
    :return: Written destination path.
    """
    output_path: Path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(emit_model_description(export_model, fmi_version), encoding="utf-8")
    return output_path
