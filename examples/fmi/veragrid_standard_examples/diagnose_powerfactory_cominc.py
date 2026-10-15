"""Isolate event-presence dependence of the licensed GENSAL ComInc crash.

The probe changes only the event population of one authenticated standard cell.
Its receipts remain outside the repository and do not certify numerical behavior.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import multiprocessing
from multiprocessing.process import BaseProcess
import os
from pathlib import Path
import secrets
import subprocess
import sys
from typing import cast
from xml.etree import ElementTree

from examples.fmi.powerfactory_first_order.run_powerfactory_first_order import (
    PowerFactoryApplication,
    PowerFactoryObject,
    assert_owned,
    bootstrap_probe_project,
    cleanup_probe_project,
    create_owned_object,
    inspect_process_inventory,
    load_powerfactory,
    set_owned_attribute,
    verify_active_cell,
)
from examples.fmi.veragrid_standard_examples.run_powerfactory_matrix import (
    PowerFactoryCell,
    add_result_variables,
    configure_standard_cell,
    load_catalog_cells,
)
from examples.fmi.veragrid_standard_examples.supervise_powerfactory_matrix import hash_file


def read_bootstrap_identity(journal_path: Path, nonce: str) -> tuple[str, str]:
    """Read one exact disposable identity from the worker's first journal row.

    :param journal_path: Append-only journal produced by the diagnostic worker.
    :param nonce: Parent-created hexadecimal token used in the project name.
    :return: Exact project name and current-user child full name.
    """
    if len(nonce) == 64 and all(character in "0123456789abcdef" for character in nonce):
        pass
    else:
        raise ValueError("Diagnostic nonce is not 64 lowercase hexadecimal characters")
    with journal_path.resolve(strict=True).open("r", encoding="utf-8") as stream:
        first_line: str = stream.readline()
    first_record: object = json.loads(first_line)
    expected_name: str = "VG_StandardMatrix_" + nonce[:12]
    if isinstance(first_record, dict):
        record: dict[str, object] = first_record
    else:
        raise ValueError("Bootstrap journal entry is malformed")
    parent_name: str = str(record.get("parent_full_name", ""))
    valid: bool = bool(
        record.get("operation", None) == "BOOTSTRAP_CREATE_PROJECT"
        and record.get("name", None) == expected_name
        and record.get("grid_name", None) == "StandardMatrixGrid"
        and record.get("parent_class", None) == "IntUser"
        and record.get("verified_absent", None) is True
        and parent_name.startswith("\\")
        and parent_name.endswith(".IntUser")
        and parent_name.count("\\") == 1
    )
    if valid:
        return expected_name, parent_name + "\\" + expected_name + ".IntPrj"
    else:
        raise ValueError("Bootstrap identity is not the parent nonce's direct project")


def classify_native_exit(worker_pid: int, started_at_utc: datetime, binding: Path, worker_exit_code: int) -> dict[str, object]:
    """Match a native worker exit to one structured Windows Application Error.

    :param worker_pid: Exact spawned Python process identifier.
    :param started_at_utc: Parent observation immediately before spawn.
    :param binding: Explicit PowerFactory binding inside the installation root.
    :param worker_exit_code: Operating-system exit code of the worker.
    :return: Matched WER fields or an explicitly inconclusive attribution.
    """
    if worker_exit_code == 0:
        return {"status": "NOT_APPLICABLE", "worker_exit_code": worker_exit_code}
    else:
        pass
    powershell: Path = Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe").resolve(strict=True)
    start_text: str = started_at_utc.isoformat()
    script: str = (
        "$ErrorActionPreference='Stop';"
        "$start=[datetime]::Parse('" + start_text + "');"
        "$events=Get-WinEvent -FilterHashtable @{LogName='Application';Id=1000;StartTime=$start} -ErrorAction Stop;"
        "$events | ForEach-Object { $_.ToXml() } | ConvertTo-Json -Compress"
    )
    process: subprocess.CompletedProcess[str] = subprocess.run(
        [str(powershell), "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, encoding="utf-8", errors="strict", timeout=30.0, check=False,
    )
    if process.returncode == 0 and process.stderr == "" and process.stdout.strip() != "":
        raw_events: object = json.loads(process.stdout)
    else:
        return {"status": "INCONCLUSIVE", "reason": "Structured Windows Application Error XML unavailable"}
    if isinstance(raw_events, str):
        event_xmls: tuple[str, ...] = (raw_events,)
    elif isinstance(raw_events, list) and all(isinstance(item, str) for item in raw_events):
        event_xmls = tuple(raw_events)
    else:
        return {"status": "INCONCLUSIVE", "reason": "Windows event payload is malformed"}
    namespace: str = "{http://schemas.microsoft.com/win/2004/08/events/event}"
    expected_module: Path = binding.parent.parent.parent / "digadm.dll"
    expected_application: Path = Path(sys._base_executable).resolve(strict=True)
    event_xml: str
    for event_xml in event_xmls:
        root: ElementTree.Element = ElementTree.fromstring(event_xml)
        system: ElementTree.Element | None = root.find(namespace + "System")
        event_data: ElementTree.Element | None = root.find(namespace + "EventData")
        if system is not None and event_data is not None:
            event_id: ElementTree.Element | None = system.find(namespace + "EventID")
            fields: dict[str, str] = dict()
            data_node: ElementTree.Element
            for data_node in event_data.findall(namespace + "Data"):
                field_name: str | None = data_node.get("Name")
                if field_name is not None:
                    fields[field_name] = data_node.text or ""
                else:
                    pass
            try:
                reported_pid: int = int(fields.get("ProcessId", ""), 16)
            except ValueError:
                reported_pid = -1
            match: bool = bool(
                event_id is not None and event_id.text == "1000"
                and reported_pid == worker_pid
                and fields.get("AppName", "").lower() == "python.exe"
                and Path(fields.get("AppPath", "")).resolve(strict=False) == expected_application
                and fields.get("ModuleName", "").lower() == "digadm.dll"
                and Path(fields.get("ModulePath", "")).resolve(strict=False) == expected_module.resolve(strict=True)
                and fields.get("ModuleVersion", "") == "25.0.6.0"
                and fields.get("ExceptionCode", "").lower() == "c0000005"
            )
            if match:
                return {"status": "MATCHED_NATIVE_CRASH", "worker_pid": worker_pid, "worker_exit_code": worker_exit_code, "event_fields": fields, "event_xml": event_xml}
            else:
                pass
        else:
            pass
    return {"status": "INCONCLUSIVE", "reason": "No exact PID, executable, module, version and code match"}


def recover_journal_project(arguments: argparse.Namespace, nonce: str, worker_pid: int) -> None:
    """Recover only the exact inactive project named by the worker journal.

    :param arguments: Explicit vendor paths and external evidence directory.
    :param nonce: Parent-created worker token.
    :param worker_pid: Joined worker PID whose native process must be absent.
    :return: None; a receipt is written on every successful recovery.
    """
    output_dir: Path = arguments.output_dir.resolve(strict=True)
    project_name: str
    full_name: str
    project_name, full_name = read_bootstrap_identity(output_dir / "mutation-journal.jsonl", nonce)
    before: dict[str, object] = inspect_process_inventory(worker_pid)
    rows_value: object = before.get("rows", None)
    if isinstance(rows_value, list):
        rows: list[object] = rows_value
    else:
        rows = list((rows_value,))
    if rows == list():
        pass
    else:
        raise RuntimeError("Worker or PowerFactory native process remains; recovery refused")
    with ExitStack() as resources:
        module = load_powerfactory(arguments.binding, arguments.powerfactory_root, resources)
        application: PowerFactoryApplication = module.GetApplicationExt()
        current_user: PowerFactoryObject | None = application.GetCurrentUser()
        expected_parent: str = full_name.rsplit("\\", 1)[0]
        if current_user is not None and str(current_user.GetFullName()) == expected_parent:
            pass
        else:
            raise RuntimeError("Current PowerFactory user differs from bootstrap journal")
        projects: list[PowerFactoryObject] = current_user.GetContents("*.IntPrj", 0)
        matches: list[PowerFactoryObject] = [project for project in projects if str(project.GetAttribute("loc_name")) == project_name]
        if len(matches) == 1 and str(matches[0].GetFullName()) == full_name:
            target: PowerFactoryObject = matches[0]
            active: PowerFactoryObject | None = application.GetActiveProject()
            if active is None or str(active.GetFullName()) != full_name:
                journal_path: Path = output_dir / "recovery-journal.jsonl"
                with journal_path.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(json.dumps({"operation": "DELETE_EXACT_INACTIVE_OWNED_ROOT", "target": full_name, "worker_pid": worker_pid}, sort_keys=True) + "\n")
                deletion_result: int | None = target.Delete()
                deletion_code: int = 0 if deletion_result is None else int(deletion_result)
                remaining: list[PowerFactoryObject] = current_user.GetContents("*.IntPrj", 0)
                absent: bool = all(str(project.GetFullName()) != full_name for project in remaining)
                receipt: dict[str, object] = {"status": "PASS" if deletion_code == 0 and absent else "FAIL", "project_full_name": full_name, "delete_code": deletion_code, "project_absent_after": absent, "process_before": before}
            else:
                raise RuntimeError("Recovery target remains active; deletion refused")
        elif len(matches) == 0:
            receipt = {"status": "PASS", "project_full_name": full_name, "project_absent_before": True, "process_before": before}
        else:
            raise RuntimeError("Recovery target is ambiguous or has wrong ancestry")
        (output_dir / "recovery-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        application = cast(PowerFactoryApplication, None)


def run_no_event_worker(arguments: argparse.Namespace, nonce: str) -> None:
    """Execute exactly one imported standard cell through ComInc without events.

    :param arguments: Explicit catalog, repository, vendor and output paths.
    :param nonce: Parent-created project identity token.
    :return: None; the worker writes a bounded command and cleanup receipt.
    """
    if sys.dont_write_bytecode and len(nonce) == 64:
        pass
    else:
        raise ValueError("Diagnostic requires python -B and a 64-hex parent nonce")
    repository_root: Path = arguments.repository_root.resolve(strict=True)
    catalog_root: Path = arguments.catalog_root.resolve(strict=True)
    if catalog_root.is_relative_to(repository_root):
        pass
    else:
        raise ValueError("Catalog escapes the explicit repository")
    cells: tuple[PowerFactoryCell, ...] = load_catalog_cells(catalog_root)
    selected: tuple[PowerFactoryCell, ...] = tuple(cell for cell in cells if cell.family == "GENSAL" and cell.version == "2.0" and cell.interface == "cs")
    expected_fmu_sha256: str = "58d4f4377be92d96d13a06425700d7b082307bc0694993520e1bfd789a886916"
    if len(selected) == 1 and selected[0].fmu_sha256 == expected_fmu_sha256:
        cell: PowerFactoryCell = selected[0]
    else:
        raise ValueError("Exact GENSAL FMI 2 CS cell is absent or changed")
    output_dir: Path = arguments.output_dir.resolve(strict=False)
    output_dir.mkdir(parents=True, exist_ok=False)
    journal_path: Path = output_dir / "mutation-journal.jsonl"
    journal_path.write_text("", encoding="utf-8")
    phase_path: Path = output_dir / "native-phase-log.jsonl"
    worker_pid: int = os.getpid()
    before: dict[str, object] = inspect_process_inventory(worker_pid)
    rows_value: object = before.get("rows", None)
    rows: list[object] = rows_value if isinstance(rows_value, list) else list((rows_value,))
    if any(isinstance(row, dict) and "PowerFactory" in str(row.get("Name", "")) for row in rows):
        raise RuntimeError("Pre-existing PowerFactory process")
    else:
        pass
    (output_dir / "process-before.json").write_text(json.dumps(before, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    project_name: str = "VG_StandardMatrix_" + nonce[:12]
    sealed_revision_sha256: str = "3d37e0350632083b0946e1b3f930837e5889569b4cb4b6464a187a92b4a44c6c"
    outcome: dict[str, object] = {"sealed_dossier_sha256": sealed_revision_sha256, "run_nonce": nonce, "worker_pid": worker_pid, "model_name": cell.model_name, "fmu_sha256": cell.fmu_sha256, "integration_step_s": 0.001, "event_count": 0, "status": "FAIL"}
    with ExitStack() as resources:
        module = load_powerfactory(arguments.binding, arguments.powerfactory_root, resources)
        application: PowerFactoryApplication = module.GetApplicationExt()
        current_user: PowerFactoryObject | None = None
        owned_project: PowerFactoryObject | None = None
        prior_project: PowerFactoryObject | None = None
        prior_study: PowerFactoryObject | None = None
        cleanup: dict[str, object] = {"status": "NOT_STARTED"}
        try:
            current_user, owned_project, prior_project, prior_study = bootstrap_probe_project(application, project_name, "StandardMatrixGrid", journal_path)
            network_folder: PowerFactoryObject | None = application.GetProjectFolder("netdat", 1)
            if network_folder is not None:
                assert_owned(network_folder, owned_project)
            else:
                raise RuntimeError("Owned network folder unavailable")
            grids: list[PowerFactoryObject] = network_folder.GetContents("*.ElmNet", 1)
            grid_matches: list[PowerFactoryObject] = [candidate for candidate in grids if str(candidate.GetAttribute("loc_name")) == "StandardMatrixGrid"]
            if len(grid_matches) == 1:
                grid: PowerFactoryObject = grid_matches[0]
                assert_owned(grid, owned_project)
            else:
                raise RuntimeError("Owned grid is ambiguous")
            bus: PowerFactoryObject = create_owned_object(grid, "ElmTerm", "Standard_110kV_Bus", owned_project, journal_path)
            set_owned_attribute(bus, "uknom", 110.0, owned_project, journal_path)
            cubicle: PowerFactoryObject = create_owned_object(bus, "StaCubic", "ExternalGrid", owned_project, journal_path)
            source: PowerFactoryObject = create_owned_object(grid, "ElmXnet", "Standard_External_Grid", owned_project, journal_path)
            set_owned_attribute(source, "bus1", cubicle, owned_project, journal_path)
            set_owned_attribute(source, "usetp", 1.0, owned_project, journal_path)
            instance, model, frame, slot, composite, observed_inputs, observed_outputs = configure_standard_cell(application, owned_project, grid, cell, journal_path)
            outcome["observed_inputs"] = observed_inputs
            outcome["observed_outputs"] = observed_outputs
            active: dict[str, object] = verify_active_cell(application, owned_project, instance)
            if active.get("status", None) == "PASS":
                pass
            else:
                raise RuntimeError("PowerFactory active FMU set is not exact")
            command_names: tuple[str, ...] = ("ComLdf", "ComInc", "ComSim", "ElmRes")
            commands: list[PowerFactoryObject] = list()
            command_name: str
            for command_name in command_names:
                command_value: PowerFactoryObject | None = application.GetFromStudyCase(command_name)
                if command_value is not None:
                    assert_owned(command_value, owned_project)
                    commands.append(command_value)
                else:
                    raise RuntimeError("Owned study command " + command_name + " is missing")
            load_flow: PowerFactoryObject = commands[0]
            initial_conditions: PowerFactoryObject = commands[1]
            simulation: PowerFactoryObject = commands[2]
            result: PowerFactoryObject = commands[3]
            settings: tuple[tuple[str, object], ...] = (("iopt_sim", "rms"), ("errseq", 0.000001), ("iopt_adapt", 0), ("dtgrd", 0.001), ("dtout", 0.001), ("iopt_sync", 1), ("syncperiod", 0.001), ("ciopt_sample", 2), ("tstart", 0.0))
            setting: tuple[str, object]
            for setting in settings:
                set_owned_attribute(initial_conditions, setting[0], setting[1], owned_project, journal_path)
            set_owned_attribute(simulation, "tstop", cell.stop_time, owned_project, journal_path)
            with phase_path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps({"phase": "BEFORE_ADD_VARS", "model_name": cell.model_name, "integration_step_s": 0.001}, sort_keys=True) + "\n")
            codes: dict[str, int] = add_result_variables(result, instance, cell)
            if all(code == 0 for code in codes.values()):
                pass
            else:
                raise RuntimeError("PowerFactory rejected named result variables")
            with phase_path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps({"phase": "AFTER_ADD_VARS", "model_name": cell.model_name, "integration_step_s": 0.001}, sort_keys=True) + "\n")
                stream.write(json.dumps({"phase": "BEFORE_COMLDF", "model_name": cell.model_name, "integration_step_s": 0.001}, sort_keys=True) + "\n")
            load_code: int = int(load_flow.Execute())
            outcome["ComLdf"] = load_code
            with phase_path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps({"phase": "AFTER_COMLDF", "command_code": load_code}, sort_keys=True) + "\n")
            if load_code == 0:
                with phase_path.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(json.dumps({"phase": "BEFORE_COMINC"}, sort_keys=True) + "\n")
                init_code: int = int(initial_conditions.Execute())
                outcome["ComInc"] = init_code
                with phase_path.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(json.dumps({"phase": "AFTER_COMINC", "command_code": init_code}, sort_keys=True) + "\n")
                outcome["status"] = "PASS" if init_code == 0 else "FAIL"
            else:
                pass
        except Exception as exception:
            outcome["error"] = f"{exception.__class__.__name__}: {exception}"
        finally:
            if current_user is not None and owned_project is not None:
                cleanup = cleanup_probe_project(application, current_user, owned_project, project_name, prior_project, prior_study, journal_path)
            else:
                cleanup = {"status": "NO_VERIFIED_PROJECT"}
            outcome["cleanup"] = cleanup
            (output_dir / "worker-observation.json").write_text(json.dumps(outcome, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        application = cast(PowerFactoryApplication, None)


def parse_arguments() -> argparse.Namespace:
    """Parse only explicit local paths required by the licensed diagnostic.

    :return: Namespace containing repository, catalog, vendor and output paths.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--catalog-root", type=Path, required=True)
    parser.add_argument("--powerfactory-root", type=Path, required=True)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    """Supervise one no-event worker and retain a bounded diagnostic verdict.

    :return: Zero only for authenticated event-presence dependence evidence.
    """
    arguments: argparse.Namespace = parse_arguments()
    output_dir: Path = arguments.output_dir.resolve(strict=False)
    if not output_dir.exists() and sys.dont_write_bytecode:
        pass
    else:
        raise RuntimeError("Output must be fresh and Python must run with -B")
    supervisor_pid: int = os.getpid()
    before: dict[str, object] = inspect_process_inventory(supervisor_pid)
    rows_value: object = before.get("rows", None)
    rows: list[object] = rows_value if isinstance(rows_value, list) else list((rows_value,))
    if any(isinstance(row, dict) and "PowerFactory" in str(row.get("Name", "")) for row in rows):
        raise RuntimeError("A PowerFactory native process exists before diagnosis")
    else:
        pass
    nonce: str = secrets.token_hex(32)
    started_at_utc: datetime = datetime.now(timezone.utc)
    context: multiprocessing.context.BaseContext = multiprocessing.get_context("spawn")
    worker: BaseProcess = context.Process(target=run_no_event_worker, args=(arguments, nonce))
    worker.start()
    worker_pid_value: int | None = worker.pid
    if worker_pid_value is not None:
        worker_pid: int = worker_pid_value
    else:
        raise RuntimeError("Spawned diagnostic worker has no PID")
    worker.join()
    worker_exit_value: int | None = worker.exitcode
    if worker_exit_value is not None:
        worker_exit_code: int = worker_exit_value
    else:
        raise RuntimeError("Diagnostic worker did not exit")
    after: dict[str, object] = inspect_process_inventory(worker_pid)
    after_rows_value: object = after.get("rows", None)
    after_rows: list[object] = after_rows_value if isinstance(after_rows_value, list) else list((after_rows_value,))
    if after_rows == list():
        pass
    else:
        raise RuntimeError("Worker or native PowerFactory process remains; recovery refused")
    (output_dir / "process-after-release.json").write_text(json.dumps(after, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    attribution: dict[str, object] = classify_native_exit(worker_pid, started_at_utc, arguments.binding, worker_exit_code)
    (output_dir / "native-attribution.json").write_text(json.dumps(attribution, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    observation_path: Path = output_dir / "worker-observation.json"
    if observation_path.is_file():
        observation: dict[str, object] = json.loads(observation_path.read_text(encoding="utf-8"))
    else:
        observation = dict()
    cleanup_value: object = observation.get("cleanup", None)
    cleanup: dict[str, object] = cleanup_value if isinstance(cleanup_value, dict) else dict()
    if cleanup.get("status", None) == "PASS":
        recovery_status: str = "NOT_NEEDED"
    elif (output_dir / "mutation-journal.jsonl").is_file():
        recovery: BaseProcess = context.Process(target=recover_journal_project, args=(arguments, nonce, worker_pid))
        recovery.start()
        recovery.join()
        recovery_receipt: Path = output_dir / "recovery-receipt.json"
        recovery_status = "PASS" if recovery.exitcode == 0 and recovery_receipt.is_file() and json.loads(recovery_receipt.read_text(encoding="utf-8")).get("status", None) == "PASS" else "FAIL"
    else:
        recovery_status = "NO_PROJECT_JOURNAL"
    if worker_exit_code == 0 and observation.get("ComLdf", None) == 0 and observation.get("ComInc", None) == 0 and cleanup.get("status", None) == "PASS":
        verdict: str = "EVENT_PRESENCE_DEPENDENCE"
    elif attribution.get("status", None) == "MATCHED_NATIVE_CRASH" and recovery_status == "PASS":
        verdict = "EVENT_PRESENCE_NOT_NECESSARY"
    else:
        verdict = "INCONCLUSIVE"
    sealed_revision_sha256: str = "3d37e0350632083b0946e1b3f930837e5889569b4cb4b6464a187a92b4a44c6c"
    receipt: dict[str, object] = {"schema_version": "1.0", "sealed_dossier_sha256": sealed_revision_sha256, "run_nonce": nonce, "worker_pid": worker_pid, "worker_exit_code": worker_exit_code, "worker_observation_sha256": hash_file(observation_path) if observation_path.is_file() else None, "native_attribution_sha256": hash_file(output_dir / "native-attribution.json"), "recovery_status": recovery_status, "verdict": verdict, "root_cause": "NOT_ESTABLISHED", "permanent_correction": "NOT_AUTHORIZED"}
    (output_dir / "diagnostic-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 0 if verdict == "EVENT_PRESENCE_DEPENDENCE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
