# Dynamic simulation theory

Dynamic simulation computes how a power system evolves after a disturbance. Unlike a power flow, which solves one steady operating point, a dynamic study advances a set of state and algebraic variables through time while enforcing the electrical-network constraints.

This page contains the concepts shared by RMS and EMT. Formulation-specific settings, examples, and results are documented in [RMS simulations](rms_simulations.md) and [EMT simulations](emt_simulations.md).

## RMS and EMT domains

RMS and EMT represent the same physical system at different levels of detail.

| Aspect | RMS | EMT |
|---|---|---|
| Electrical representation | Fundamental-frequency phasors | Instantaneous phase-domain waveforms |
| Typical phenomena | Frequency, rotor angle, outer controls, transient stability | Switching, inner controls, waveform and phase interactions |
| Typical time step | Milliseconds | Microseconds or smaller, depending on the fastest phenomenon |
| Computational cost | Moderate | High |
| Network detail | Averaged electrical behaviour | Detailed electromagnetic behaviour |

Use the least detailed formulation that still resolves the phenomenon of interest. An RMS study is normally the first system-wide dynamic study. EMT is appropriate when waveform, switching, unbalance, or very fast control detail is essential.

## Differential-algebraic equations

VeraGrid assembles dynamic models as a differential-algebraic equation (DAE) system. A common semi-explicit representation is

```{math}
\dot{x} = f(x, z, p, t), \qquad 0 = g(x, z, p, t),
```

where:

- {math}`x` contains dynamic states;
- {math}`z` contains algebraic variables;
- {math}`p` contains constant and event-modifiable parameters;
- {math}`t` is simulation time;
- {math}`f` defines state evolution;
- {math}`g` enforces instantaneous device and network constraints.

The algebraic part includes quantities such as bus voltages, injected currents, and controller constraints. The differential part includes stored-energy and controller states. A valid model must provide enough independent equations to determine all unknowns without creating conflicting constraints.

### Current DAE authoring contract

New blocks declare their unknowns and equations through these collections:

| Collection | Purpose |
|---|---|
| `state_vars` | Variables that are integrated through time |
| `algebraic_vars` | Variables determined by algebraic constraints |
| `diff_vars` | Derivative symbols associated with states |
| `state_eqs` | Equations that relate states and derivatives |
| `algebraic_eqs` | Algebraic residual equations |
| `init_eqs` | Explicit initialization equations for variables |
| `diff_init_eqs` | Explicit initialization equations for derivatives |

`differential_eqs` is not the current authoring interface. It remains only as a compatibility field when loading older saved models. New models must use `state_vars`, `diff_vars`, and `state_eqs`.

For the detailed API and equation ownership rules, see [Writing DAE models in VeraGrid](dae_block_authoring.md).

## From blocks to one system

A device model is a graph of blocks. Each block owns variables, parameters, equations, ports, and optional runtime logic. Connections identify expressions that must be shared between blocks. The simulator then:

1. traverses the dynamic models assigned to grid devices;
2. resolves block connections and physical terminal bindings;
3. collects states, algebraic variables, derivatives, and parameters;
4. assembles local equations into one global DAE;
5. maps symbolic variable identifiers to numerical vector positions;
6. initializes the global problem;
7. integrates every event-group scenario;
8. stores trajectories together with the variable-to-column metadata.

The model graph is therefore not just a diagram. Its variable identities and connections define the global numerical problem.

## Initialization

Time integration requires a consistent initial state. In general, the initial values must satisfy the algebraic equations and must be compatible with the selected operating point.

The usual sequence is:

1. Solve the static network operating point.
2. Copy relevant bus and device quantities into the dynamic-model initialization expressions.
3. Evaluate explicit initialization equations where a variable can be computed directly.
4. Apply the selected consistency method to the remaining coupled variables.
5. Check the reported initialization status before interpreting trajectories.

### Explicit initialization

Explicit initialization evaluates the `init_eqs` and `diff_init_eqs` supplied by the blocks. It is fast and predictable when the model provides a complete dependency order. Missing or circular initialization dependencies cannot be repaired by time integration and should be corrected in the model.

### Consistent and pseudo-transient initialization

A coupled initialization method solves or relaxes the DAE residuals until the starting point is consistent. Pseudo-transient continuation introduces an artificial transient that can improve robustness for difficult initial points. EMT also provides an automatic selection that chooses the configured initialization path for the problem.

Initialization is not a substitute for a valid model. Large residuals can indicate an incorrect operating point, incompatible set-points, missing equations, incorrect units, or a disconnected physical terminal.

## Time integration

At each time step, the integration method approximates the relation between state values and derivatives. The algebraic equations must remain satisfied at the new time. Implicit DAE methods are commonly used because electrical and control models can be stiff.

The time step controls both accuracy and cost. It must be small enough to resolve the fastest phenomenon retained by the chosen model. A useful convergence check is to repeat the study with a smaller step and confirm that the quantities of interest do not change materially.

The integration method, initialization method, and available solver backend are selected in the RMS or EMT settings. See the formulation-specific pages for the choices exposed by the GUI.

## Events and scenarios

Dynamic events change model parameters while the simulation is running. VeraGrid organizes them in event groups:

- an **event group** is one complete scenario and produces one result group;
- a **step event** changes a parameter at one time;
- a **ramp event** changes a parameter continuously between two times.

A base case is represented by an event group with no events. At least one event group is required for the driver to produce a scenario trajectory.

Events act on parameters declared by the model. Saving the dynamic model before creating events ensures that the Events page sees the current parameter identities.

## Results and interpretation

Each result group contains a common time axis and trajectories for the variables assembled into the numerical problem. The result metadata preserves the association between a column, its symbolic variable, and its owning device or block.

Always verify the following before drawing conclusions:

- the expected event group produced results;
- initialization completed successfully;
- the simulation converged;
- the chosen time step resolves the observed transient;
- plotted variables belong to the intended device and model;
- discontinuities coincide with configured events rather than numerical failure.

The GUI workflow and API access patterns are described in the RMS and EMT result sections.

## Model validation checklist

Before a simulation:

- solve and inspect the static operating point;
- ensure every required device has the intended RMS or EMT model;
- connect every required grid terminal and block port;
- verify that variables and equations are neither missing nor duplicated;
- provide initialization equations for model-owned states and derivatives;
- use consistent SI or per-unit bases throughout each model;
- create at least one event group;
- save editor changes before using Events, Comparison, or Plots.

After a simulation:

- check initialization and convergence per event group;
- compare important signals against physical bounds;
- repeat sensitive cases with a smaller time step;
- compare RMS and EMT only at compatible signal definitions and time scales.

## Further reading

- [Building dynamic models](dynamic_modeling.md)
- [Dynamic workspace and editors](dynamic_editor.md)
- [Writing DAE models in VeraGrid](dae_block_authoring.md)
- [Dynamic physical network contracts](dynamic_physical_network_contracts.md)
- [RMS simulations](rms_simulations.md)
- [EMT simulations](emt_simulations.md)
- [RMS Small-Signal stability](small_signal_stability_rms.md)
- [EMT Small-Signal stability: Floquet analysis](small_signal_stability_emt.md)
