# ⚡ Short-Circuit

The calculation of short-circuit currents is crucial for the proper functioning and safety of a power system.
It ensures that equipment such as circuit breakers or transformers can withstand fault currents without failure.
This analysis is also essential for calculating the potential rise at substations and nearby metallic structures,
thus ensuring safety and preventing damage to sensitive infrastructure.

Short-circuit calculations are carried out during the system design phase to determine the ratings of new equipment and
are periodically updated to verify that existing assets remain adequate as the system evolves. These calculations are
critical for setting protection relays, which must act swiftly to avoid system-wide failures. They also assist in the
design of grounding systems and the assessment of power quality issues when new loads are introduced into the network.

Short-circuit faults can occur between phases or between phases and earth. These include one-phase to earth,
phase-to-phase, two-phase to earth, three-phase clear of earth, and three-phase to earth faults. The three-phase fault,
which symmetrically affects all three phases, is the only balanced fault, while all others are unbalanced.
A one-phase to earth fault can cause a voltage rise on the health phases, potentially leading to a flashover and
creating a short-circuit fault, known as a cross-country fault. Some faults may evolve during the fault period, such as
a one-phase to earth fault developing into a two-phase to earth fault, which typically occurs in overhead lines or 
substations.

The majority of short-circuit faults, especially in overhead line systems, are weather-related, with lightning strikes,
wind, ice, and salt pollution being the most common causes. Lightning strikes can generate extremely high voltages,
potentially causing flashovers and short-circuit faults, particularly on overhead lines. Equipment failures due to
ageing, mechanical issues, or poor installation are also significant contributors. Human error, such as leaving
isolated equipment connected during maintenance, can also result in faults when the equipment is re-energised.
Around 90\% of short-circuit faults occur on overhead lines, with approximately 70\% of these being
phase-to-ground faults.

## Short-Circuit in the Phase Reference Frame

The formulation for simulating short-circuit faults in the phase reference frame in GridCal will be detailed step by
step. A key advantage of having modelled the entire network in the phases and implementing the power flow using the 
three phases instead of sequences is that we can now easily simulate any type of short-circuit by simply adding a fault
impedance to the bus of interest, whether between the three phases, between one phase and earth, between two phases, etc.
Furthermore, both the system voltage and short-circuit current results will be in their actual values, rather than
sequence values, which also simplifies fault analysis.

### Linearisation

The first step in performing the short-circuit calculation is to determine the state of the network prior to the fault.
To achieve this, GridCal will perform the three-phase power flow calculation, which has been developed to determine
the voltage at each bus before the fault $\vec{U}_{pf}$. This initial step will also provide the other electrical
magnitudes of the system, such as the admittance matrix of the branches $\vec{Y}_b$, the power $\vec{S}_0$,
current $\vec{I}_0$, and admittance $\vec{Y}_0$ matrices of the loads or shunt elements, and the complex power vector
for each bus $\vec{S}_{pf}$.

Once the power flow calculation has been performed and the necessary results obtained, the second step is to linearise
the entire system, that is, to convert all power and current injections to their equivalent admittance values.
This way, the system can be solved simply by applying Ohm's law, without the need for any iterative algorithms like
Newton-Raphson.

The admittance of the branches, $\vec{Y}_b$, is already known, as well as that of the loads defined as constant
admittance, $\vec{Y}_0$. However, the loads defined as constant power must be converted by dividing by the square of
the voltage vector's magnitude:

$$
\vec{Y}_{0_S} = \dfrac{\vec{S}_0^*}{U_{pf}^2}
$$

The loads defined as constant current must also be converted to their equivalent admittance by dividing by the voltage
vector:

$$
\vec{Y}_{0_I} = \dfrac{\vec{I}_0}{\vec{U}_{pf}}
$$

Therefore, the sum of these three admittances will make up the admittance matrix of the loads:

$$
\vec{Y}_{\text{loads}} = \vec{Y}_0 + \vec{Y}_{0_S} + \vec{Y}_{0_I}
$$

In the unbalanced three-phase power flow simulation, the generators had been modelled as simple power injections into
the system, which was completely valid. However, this is not sufficient when performing the short-circuit analysis, as
the impedance of the generator must also be taken into account. GridCal has been programmed to accept a $3 \times 3$
impedance matrix, which includes both the self and mutual impedances between the $abc$ phases. Furthermore, it is
common to encounter generator impedances in the sequence domain. Therefore, Fortescue’s theorem must be applied to
obtain the equivalent values for the three phases:

$$
\vec{Z}_{gen_{abc}} =
\begin{bmatrix}
\vec{Z}_0 + \vec{Z}_1 + \vec{Z}_2 & \vec{Z}_0 + \vec{a}\vec{Z}_1 + \vec{a}^2\vec{Z}_2 & \vec{Z}_0 + \vec{a}^2\vec{Z}_1 + \vec{a}\vec{Z}_2 \\
\vec{Z}_0 + \vec{a}^2\vec{Z}_1 + \vec{a}\vec{Z}_2 & \vec{Z}_0 + \vec{Z}_1 + \vec{Z}_2 & \vec{Z}_0 + \vec{a}\vec{Z}_1 + \vec{a}^2\vec{Z}_2 \\
\vec{Z}_0 + \vec{a}\vec{Z}_1 + \vec{a}^2\vec{Z}_2 & \vec{Z}_0 + \vec{a}^2\vec{Z}_1 + \vec{a}\vec{Z}_2 & \vec{Z}_0 + \vec{Z}_1 + \vec{Z}_2
\end{bmatrix}
$$

Where the transformation eigenvector $\vec{a} = e^{j2\pi/3}$ is used. Then, the impedance matrix is linearly inverted 
to finally find the admittance of the generators:

$$
\vec{Y}_{\text{gen}} = \dfrac{1}{\vec{Z}_{\text{gen}}}
$$

Finally, the only remaining admittance to be obtained is that of the fault itself. For instance, in the case of a
phase-to-earth fault, this impedance must be connected between the affected phase and earth. This fault impedance
$\vec{Z}_{f}$ shall be specified by the GridCal user on the bus on which the short-circuit is to be simulated, as well
as the short-circuit type and the affected phases. Again, this impedance will be inverted to obtain the fault admittance:

$$
\vec{Y}_{f} = \dfrac{1}{\vec{Z}_{f}}
$$

Thus, the total linearised admittance will be equal to the sum of the admittance of the branches, the loads, the
generators, and the fault admittance:

$$
\vec{Y}_{\text{linear}} = \vec{Y}_b + \vec{Y}_{\text{loads}} + \vec{Y}_{\text{gen}} + \vec{Y}_{f}
$$

### Induced Electromotive Force

Another key parameter that must be transferred from the power flow to the short-circuit analysis is the induced
electromotive force (EMF) in the generators, $\vec{E}$, as this is the only voltage that will not change during the
fault. The electromotive force depends on the flux induced in the machine's rotor, and therefore on the excitation
current. It can be assumed that the internal voltage $\vec{E}$ of the generator remains constant during the duration
of the fault. The generator could be modelled during the short-circuit using the classic Thévenin equivalent, that is,
as an ideal voltage source in series with the generator’s impedance, as shown in the electrical circuit of figure bellow:

![Generator's Thevenin](figures/3ph_thevenin.png "Generator's Thevenin")

This circuit allows us to obtain the value of the induced electromotive force, given the voltage $\vec{U}_{pf}$ and
power $\vec{S}_{pf}$ before the fault at the generator’s output bus:

$$
\vec{E} = \vec{U}_{pf} + \vec{Z}_{\text{gen}} \cdot \vec{I}_{pf} = \vec{U}_{pf} + \dfrac{\vec{S}_{pf}^*}{\vec{Y}_{\text{gen}} \cdot \vec{U}_{pf}^*}
$$

### Norton Current and Short-Circuit Voltage

However, this would require to add a fictitious bus into the original system between the generator’s impedance and the
ideal voltage source. This presents a significant challenge because both the values of the power flow voltage vector
$\vec{U}_{pf}$ and the already linearised admittance matrix $\vec{Y}_{\text{linear}}$ are referenced by bus, and all
these connections would be more difficult to handle. Therefore, the generator is modelled using its Norton equivalent,
that is, an ideal current source in parallel with the generator’s impedance, as shown in the following schematic:

![Generator's Norton](figures/3ph_norton.png "Generator's Norton")

The Norton current source will take the value of the internal voltage multiplied by its admittance:

$$
\vec{I}_{N} = \vec{Y}_{\text{gen}} \cdot \ \vec{E}
$$

This Norton current vector will be of size $n$ buses, but only the nodes with a connected generator will have these
founded values, while the rest will simply have a value of zero. Finally, this current vector $\vec{I}_{N}$ will be
multiplied by the inverse of the linearised admittance matrix $\vec{Y}_{\text{linear}}$ of size $n \times n$,
resulting in the short-circuit voltage vector for the different buses:

$$
\vec{U}_{sc} = \vec{Y}_{\text{linear}}^{-1} \cdot \vec{I}_{N}
$$

### Single Line-to-Ground Fault (SLG)

### Line-to-Line Fault (LL)

### Double Line-to-Ground Fault (DLG)

### Three-Phase Fault (LLL)

### Three-Phase-to-Ground Fault (LLLG)

### Benchmark - SLG Fault in the IEEE 13 Node Test Feeder

```python

```

## Short-Circuit in the Sequence Components

GridCal has unbalanced (sequence and rectangular) short circuit calculations.

### API

 Now let's run a line-ground short circuit in the third bus of
the South island of New Zealand grid example from reference book
Computer Analysis of Power Systems by J. Arrillaga and C.P. Arnold.

```python
import os
import GridCalEngine as gce

folder = os.path.join('..', 'Grids_and_profiles', 'grids')
fname = os.path.join(folder, 'South Island of New Zealand.gridcal')

grid = gce.open_file(filename=fname)

# Define fault index explicitly
fault_index = 2

# Run a Line-Ground short circuit on the bus at index 2
# Since we do not provide any power flow results, it will run one for us
results = gce.short_circuit(grid, fault_index, fault_type=gce.FaultType.LG)

print("Short circuit power: ", results.SCpower[fault_index])
```

A more elaborated way to run the simulation, controlling all the steps:

```python
import os
import GridCalEngine as gce

folder = os.path.join('..', 'Grids_and_profiles', 'grids')
fname = os.path.join(folder, 'South Island of New Zealand.gridcal')

grid = gce.open_file(filename=fname)

pf_options = gce.PowerFlowOptions()
pf = gce.PowerFlowDriver(grid, pf_options)
pf.run()

fault_index = 2
sc_options = gce.ShortCircuitOptions(bus_index=fault_index,
                                     fault_type=gce.FaultType.LG)

sc = gce.ShortCircuitDriver(grid, options=sc_options,
                            pf_options=pf_options,
                            pf_results=pf.results)
sc.run()

print("Short circuit power: ", sc.results.SCpower[fault_index])
```

Output:

```text
Short circuit power:  -217.00 MW - 680.35j MVAr
```

Sequence voltage, currents and powers are also available.

### Theory


### 3-Phase Short Circuit

First, declare an array of zeros of size equal to the number of nodes in the
circuit.

$$
    \textbf{I} = \{0, 0, 0, 0, ..., 0\}
$$

Then for single bus failure, compute the short circuit current at the selected bus $i$ and assign
that value in the $i^{th}$ position of the array $\textbf{I}$.

$$
    \textbf{I}_i = - \frac{\textbf{V}_{pre-failure, i}}{\textbf{Z}_{i, i} + z_f}
$$

Then, compute the voltage increment for all the circuit nodes as:

$$
    \Delta \textbf{V} = \textbf{Z} \times \textbf{I}
$$

Finally, define the voltage at all the nodes as:

$$
    \textbf{V}_{post-failure} = \textbf{V}_{pre-failure} + \Delta \textbf{V}
$$


- $\textbf{I}$: Array of fault currents at the system nodes.
- $\textbf{I}_B$: Subarray of $\textbf{I}$ such that all entries for non-selected buses are removed.
- $\textbf{V}_{pre-failure}$: Array of system voltages prior to the failure. This is obtained from the power flow study.
- $\textbf{V}_{pre-failure, B}$: Subarray of $\textbf{V}_{pre-failure}$ such that all entries for non-selected buses are removed.
- $z_f$: Impedance of the failure itself. This is a given value, although you can set it to zero if you don't know.
- $\textbf{z}_{f, B}$: Impedance of the failures of selected buses $B$.
- $\textbf{Z}$: system impedance matrix. Obtained as the inverse of the complete system admittance matrix.
- $\textbf{Z}_B$: submatrix of $\textbf{Z}$ such that all rows and columns for non-selected buses are removed.
