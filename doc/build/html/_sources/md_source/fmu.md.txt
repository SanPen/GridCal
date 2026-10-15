# 🔌 Functional Mock-up Units (FMUs)

VeraGrid can export symbolic dynamic models as [Functional Mock-up Units
(FMUs)](https://fmi-standard.org/), inspect existing FMUs, execute them through
FMPy, and attach them to RMS or EMT devices.

The package supports FMI 1.0, FMI 2.0, and FMI 3.0:

- **Co-Simulation**: the FMU owns its integration step and VeraGrid exchanges
  values at communication points.
- **Model Exchange**: VeraGrid owns the solver and evaluates states,
  derivatives, and events.

FMPy is an explicit dependency for FMI parsing, archive validation, native
library loading, and execution checks. FMU binaries are compiled through
VeraGrid's shared `Compiler` class.

## Export a Co-Simulation FMU

The high-level export operation is `export_model_as_fmu()`. It accepts a
symbolic `Block` hierarchy, generates FMI C code and XML, compiles the native
library, and packages the result as a `.fmu` archive.

```python
from pathlib import Path

from VeraGridEngine.IO.fmu.config import ExportConfig
from VeraGridEngine.IO.fmu.interface import export_model_as_fmu
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.enumerations import FmiVersion, InterfaceType


state: Var = Var("x")
derivative: Var = Var("dx", base_var=state)
model: Block = Block(
    state_vars=[state],
    state_eqs=[Const(1.0)],
    diff_vars=[derivative],
    init_values={state: Const(0.0)},
    out_vars=[state],
    name="FirstOrder",
)

config: ExportConfig = ExportConfig(
    model_name="FirstOrderCS",
    output_path=Path("build/FirstOrderCS.fmu"),
    interface_type=InterfaceType.CO_SIMULATION,
    fmi_version=FmiVersion.FMI_2_0,
    fixed_step=1.0e-3,
)

fmu_path: Path = export_model_as_fmu(model=model, cfg=config)
print(fmu_path)
```

`fixed_step` is the generated Co-Simulation communication step.

## Export a Model Exchange FMU

Model Exchange must be selected explicitly because `ExportConfig` defaults to
Co-Simulation.

```python
config: ExportConfig = ExportConfig(
    model_name="FirstOrderME",
    output_path=Path("build/FirstOrderME.fmu"),
    interface_type=InterfaceType.MODEL_EXCHANGE,
    fmi_version=FmiVersion.FMI_2_0,
)

fmu_path: Path = export_model_as_fmu(model=model, cfg=config)
```

For Model Exchange, VeraGrid performs numerical integration and event
coordination when the FMU is executed.

## Reuse the shared compiler

Most callers should omit the compiler argument. When caller-owned compiler
selection is required, pass `Compiler` directly. There is no FMU-specific
compiler session or lifecycle wrapper.

```python
from VeraGridEngine.Utils.Compiler.interface import Compiler


compiler: Compiler = Compiler()
fmu_path = export_model_as_fmu(model=model, cfg=config, compiler=compiler)
```

## Inspect an FMU

`read_fmu_model_description()` validates the archive and returns normalized
metadata without executing native code.

```python
from pathlib import Path

from VeraGridEngine.IO.fmu.model_description import (
    read_fmu_model_description,
    select_declared_fmu_interface,
)
from VeraGridEngine.enumerations import FmuInterfaceMode


fmu_path: Path = Path("build/FirstOrderCS.fmu")
metadata = read_fmu_model_description(fmu_path)
print(metadata.fmi_version)
print(metadata.model_name)
print(metadata.get_variable_names())

interface: FmuInterfaceMode = select_declared_fmu_interface(fmu_path)
print(interface)
```

Request a preferred interface explicitly when the archive may declare more than
one:

```python
interface = select_declared_fmu_interface(
    fmu_path,
    preferred_interface=FmuInterfaceMode.CO_SIMULATION,
)
```

## Validate and simulate with FMPy

Use FMPy for an independent standards-level check and standalone execution:

```python
from fmpy import simulate_fmu
from fmpy.validation import validate_fmu


validation_issues = validate_fmu("build/FirstOrderCS.fmu")
if validation_issues:
    raise RuntimeError(validation_issues)

result = simulate_fmu(
    filename="build/FirstOrderCS.fmu",
    start_time=0.0,
    stop_time=0.01,
    step_size=1.0e-3,
    output=("x",),
)
print(result["x"])
```

Use VeraGrid's execution and device APIs when the FMU participates in an RMS
or EMT simulation.

## Attach an FMU to a VeraGrid device

The script-facing device operation is `attach_fmu_to_device()`. Bindings use
the typed `FmuRefBinding` class rather than unstructured names.

```python
from pathlib import Path

from VeraGridEngine.IO.fmu.bindings import FmuRefBinding
from VeraGridEngine.IO.fmu.fmu_device_integration import (
    FmuDeviceAttachmentRequest,
    FmuReferenceValue,
    attach_fmu_to_device,
)
from VeraGridEngine.IO.fmu.model_description import FmuInterfaceMode
from VeraGridEngine.enumerations import FmuDeviceDomain, VarPowerFlowReferenceType


request: FmuDeviceAttachmentRequest = FmuDeviceAttachmentRequest(
    fmu_path=Path("build/FirstOrderCS.fmu"),
    domain=FmuDeviceDomain.RMS,
    mode=FmuInterfaceMode.CO_SIMULATION,
    input_bindings=(
        FmuRefBinding(
            reference=VarPowerFlowReferenceType.Vm,
            fmu_variable_name="u",
        ),
    ),
    output_bindings=(
        FmuRefBinding(
            reference=VarPowerFlowReferenceType.P,
            fmu_variable_name="x",
        ),
    ),
    output_defaults=(
        FmuReferenceValue(
            reference=VarPowerFlowReferenceType.P,
            value=0.0,
        ),
    ),
)

# `device` is an existing device and `grid` is its MultiCircuit.
attached_block = attach_fmu_to_device(device=device, grid=grid, request=request)
```

For Model Exchange, use a Model Exchange FMU and set:

```python
request.mode = FmuInterfaceMode.MODEL_EXCHANGE
```

FMI 3 worker-based configurations additionally require explicit worker limits
and typed configuration values.

## Configuration rules

- Select versions with `FmiVersion`, not ad-hoc strings.
- Select interfaces with `InterfaceType`.
- Verify FMU variable names with `read_fmu_model_description()` before binding.
- Use `FmuRefBinding` for device signals.
- Pass a `Compiler` only when caller-owned compiler selection is needed.
- Do not use the removed `runtime/`, `fmi1/`, `fmi2/`, or CLI paths.

## High-level operations

| Operation | Purpose |
| --- | --- |
| `export_model_as_fmu()` | Generate and package a VeraGrid model as an FMU. |
| `read_fmu_model_description()` | Inspect and validate FMU metadata. |
| `select_declared_fmu_interface()` | Select a declared FMI interface. |
| `attach_fmu_to_device()` | Attach an FMU to an RMS or EMT device. |
| `Compiler` | Compile generated native FMU code. |
| FMPy `validate_fmu()` / `simulate_fmu()` | Independently validate and execute FMUs. |
