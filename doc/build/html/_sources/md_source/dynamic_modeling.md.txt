# Building dynamic models

VeraGrid represents an RMS or EMT device model as a graph of reusable blocks. The same model objects can be created with the API or edited graphically in the dynamic workspace.

Use this page for the common modelling workflow. For the complete equation API, initialization rules, and validation details, continue with [Writing DAE models in VeraGrid](dae_block_authoring.md).

## General block structure

A block can contain:

| Element | Role |
|---|---|
| Input ports | Expressions received from another block or a grid terminal |
| Output ports | Expressions exposed to connected blocks |
| Parameters | Constant or event-modifiable model data |
| `state_vars` | Integrated dynamic states |
| `algebraic_vars` | Unknowns constrained instantaneously |
| `diff_vars` | Derivative symbols associated with states |
| `state_eqs` | State and derivative equations |
| `algebraic_eqs` | Algebraic residual equations |
| `init_eqs` | Explicit initial values for variables |
| `diff_init_eqs` | Explicit initial values for derivatives |
| Runtime logic | Discrete modes, limits, gates, and other procedural behaviour |
| Children | Nested blocks used to build a hierarchical model |

New blocks use `state_vars`, `diff_vars`, and `state_eqs` for differential behaviour. The old `differential_eqs` field is retained only to load legacy models and must not be used for new authoring.

## Model ownership and connections

Every equation has one owning block, and every model-owned unknown must be determined exactly once. Ports do not create an independent copy of a signal; a connection identifies how expressions are shared across the graph.

Grid connection blocks are created by the editor for the selected device. They expose the voltage, current, or other physical terminal contract expected by the RMS or EMT network formulation. Do not replace these terminals with unrelated free variables: the connection is what couples the device model to the global network equations.

## Construction workflow

The recommended sequence is the same in the GUI and the API:

1. Select the target device and simulation domain.
2. Start from the grid connection blocks supplied for that device.
3. Add the smallest set of functional blocks needed for the study.
4. Connect compatible ports and verify the signal direction.
5. Set parameters and operating-point bindings.
6. Declare states, algebraic variables, derivatives, equations, and initialization expressions.
7. Add runtime logic only when continuous equations cannot describe the behaviour.
8. Validate the complete model graph.
9. Save or assign the model to the device.

## Building and assigning models from the API

The API workflow uses the same `Block`, `Var`, `Expr`, and `VarFactory` objects used by the editor. The following function builds a reusable first-order lag block without assigning it to a specific grid device:

```python
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var


def build_first_order_lag(
        var_factory: VarFactory,
        time_constant_seconds: float,
        name: str
) -> Block:
    """
    Build a first-order lag whose output is also its dynamic state.

    :param var_factory: Grid-owned factory used to create symbolic identities.
    :param time_constant_seconds: Positive lag time constant in seconds.
    :param name: Human-readable block name.
    :return: Unconnected first-order lag block.
    """
    input_signal: Var = var_factory.add_var(name=name + "_input")
    output_state: Var = var_factory.add_var(name=name + "_output")
    time_constant: Var = var_factory.add_var(name=name + "_time_constant")
    time_constant_value: Const = var_factory.add_const(time_constant_seconds)

    block: Block = Block(
        name=name,
        state_vars=list([output_state]),
        state_eqs=list([
            (input_signal - output_state) / time_constant,
        ]),
        parameters=dict({
            time_constant: time_constant_value,
        }),
        init_eqs=dict({
            output_state: input_signal,
        }),
        in_vars=list([input_signal]),
        out_vars=list([output_state]),
    )
    return block
```

Add the returned block to a device-model root, connect its ports to the surrounding blocks, and expose only the network-facing variables on the root. The [DAE authoring guide](dae_block_authoring.md) contains a complete RMS device template with network and static-API mappings.

Once a complete root model has been built and validated, assign it to its grid device with the standard helper:

```python
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Parents.editable_device import EditableDevice
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model, set_rms_model


def assign_dynamic_model(
        device: EditableDevice,
        model: Block,
        var_factory: VarFactory,
        use_emt: bool
) -> None:
    """
    Assign an already constructed dynamic model to one grid device.

    :param device: Grid device that owns the dynamic model.
    :param model: Validated RMS or EMT block graph.
    :param var_factory: Variable factory owned by the target circuit.
    :param use_emt: ``True`` for an EMT model and ``False`` for an RMS model.
    :return: Nothing.
    """
    if use_emt:
        set_emt_model(device=device, model=model, var_factory=var_factory)
    else:
        set_rms_model(device=device, model=model, var_factory=var_factory)
```

In normal scripts, `model` is obtained from a supplied template builder or from a dedicated model-construction function. Keep model construction separate from simulation setup so the block graph can be validated and reused.

The detailed authoring guide includes complete examples for creating variables, derivatives, equations, ports, and initialization expressions.

## Parameters and events

A parameter that must change during a scenario must be declared as event-modifiable by the model. The Events page and event API refer to the model parameter identity, not only to its displayed name. Save the model before creating events so those identities remain stable.

Use constant parameters for immutable coefficients. Use runtime logic for discrete behaviour such as mode changes, saturation state, or switching gates. Avoid using runtime logic for relationships that can be expressed directly as DAE equations.

## Templates and copied models

A template is a reusable starting point. Once assigned to a device, the device model can be inspected or edited independently. The Comparison page groups compatible saved models and helps propagate selected parameter values across devices without replacing their full block graphs.

For the currently supplied models and blocks, see the [Dynamic model library](dynamic_model_library_index.md). The library reference is intentionally kept separate from authoring guidance.

## Validation

Validate the whole model, not only individual blocks. A useful review checks:

- all required ports are connected;
- grid connection blocks match the selected device and domain;
- every state has a corresponding derivative and state equation;
- algebraic equations are independent and have the correct ownership;
- initialization equations cover the intended starting state;
- parameter names and units match event and plot definitions;
- the model contains no references to objects outside its saved hierarchy.

The editor reports structural and equation diagnostics before changes are applied. Resolve these diagnostics before starting a simulation.

## Next steps

- [Dynamic workspace and editors](dynamic_editor.md): graphical editing, events, comparison, and plots.
- [Writing DAE models in VeraGrid](dae_block_authoring.md): complete symbolic authoring reference.
- [Dynamic physical network contracts](dynamic_physical_network_contracts.md): device-to-network terminal conventions.
