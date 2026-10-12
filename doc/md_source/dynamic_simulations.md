# 🧲 Dynamic simulations

VeraGrid provides two complementary time-domain simulation workflows:

- **RMS simulation** for phasor-domain electromechanical and controller dynamics.
- **EMT simulation** for instantaneous, phase-domain electromagnetic transients.
- **Small-signal stability** for RMS modal analysis and EMT Floquet analysis.

The dynamic documentation is organized by task. Start with the theory if you need to understand the mathematical model and initialization, continue with the RMS or EMT workflow for a simulation, and use the modelling section when creating or editing dynamic models.

## 1. Dynamic simulation theory

The general theory page explains differential-algebraic equations (DAEs), model assembly, initialization, time integration, events, and how to choose between RMS and EMT. The RMS and EMT pages then describe the formulation-specific workflow, settings, results, GUI procedure, and API example.

```{toctree}
:maxdepth: 2

dynamic_theory
rms_simulations
emt_simulations
```

### Small-signal stability

Small-signal studies use an initialized dynamic model to assess how small perturbations evolve. RMS analysis linearizes around an equilibrium or a selected trajectory point. EMT analysis evaluates a periodic steady-state trajectory using Floquet multipliers.

```{toctree}
:maxdepth: 1

small_signal_stability_rms
small_signal_stability_emt
```

## 2. Dynamic editor and model construction

Dynamic models can be assigned from a template or assembled from blocks. The modelling guide describes the common block structure and API workflow. The editor guide covers the model editor, Events, Comparison, and Plots pages. The DAE authoring guide is the detailed reference for writing equations and initialization expressions.

```{toctree}
:maxdepth: 2

dynamic_modeling
dynamic_editor
```

## 3. Dynamic model library

The library reference documents the models and reusable blocks currently shipped with VeraGrid. Its navigation follows the present library organization and is kept separate from the theory and authoring guides.

```{toctree}
:maxdepth: 2

dynamic_model_library_index
```

## Recommended reading paths

| Goal | Start here | Continue with |
|---|---|---|
| Choose a simulation domain | [Dynamic simulation theory](dynamic_theory.md) | [RMS](rms_simulations.md) or [EMT](emt_simulations.md) |
| Run an RMS study | [RMS simulations](rms_simulations.md) | [RMS practical session](RMS_practical_session.md) |
| Run an EMT study | [EMT simulations](emt_simulations.md) | [EMT practical session](EMT_practical_session.md) |
| Assess RMS small-signal stability | [RMS Small-Signal stability](small_signal_stability_rms.md) | Modal results and participation factors |
| Assess EMT periodic-orbit stability | [EMT Small-Signal stability](small_signal_stability_emt.md) | Floquet multipliers and modes |
| Build or edit a model | [Building dynamic models](dynamic_modeling.md) | [Dynamic workspace and editors](dynamic_editor.md) |
| Write DAE equations | [Writing DAE models in VeraGrid](dae_block_authoring.md) | [Physical network contracts](dynamic_physical_network_contracts.md) |
| Look up a supplied model | [Dynamic model library](dynamic_model_library_index.md) | The model's reference page |

## End-to-end workflow

1. Build or import the static network and solve the required operating point.
2. Assign an RMS or EMT model to every device that participates in the dynamic study.
3. Validate the model connections, variables, equations, parameters, and initialization data.
4. Create at least one RMS or EMT event group. A group can represent the undisturbed base case even when it contains no events.
5. Define optional step or ramp events and prepare reusable plots.
6. Configure the simulation horizon, time step, tolerance, initialization, and formulation-specific solver settings.
7. Run the simulation and inspect convergence, initialization status, trajectories, and plot groups.

The GUI and API operate on the same grid, model, event, and result objects. A model saved in the dynamic editor is therefore available to the simulation drivers and to API scripts.
