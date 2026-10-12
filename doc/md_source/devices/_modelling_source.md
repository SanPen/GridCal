# 📐 Grid Modelling

Three-phase AC systems dominate power transmission and distribution for their efficiency, capacity, and compatibility.
While ideal systems are balanced and suitable for positive-sequence analysis, real networks often experience asymmetries
from untransposed lines, uneven loads, single-phase connections, and converter-based resources. The classical
symmetrical components method simplifies unbalanced fault analysis but struggles with strong sequence coupling,
non-linearities, and complex topologies.

Direct phase-domain (abc) modelling overcomes these limitations by representing actual phase quantities, naturally
handling asymmetry, non-linearities, and all fault types. It is particularly suited for transient simulations, EMTP
tools, and control design across all voltage levels.

Power systems comprise generators, transformers, lines, loads, and compensation equipment, interconnected from
generation through transmission and distribution to end users. Transmission operates at high voltages to reduce losses,
with transformers stepping voltages up or down as required. Transmission circuits often include series and shunt
compensation, while transformer winding configurations must be carefully modelled under unbalanced conditions. At the
distribution level, load points can be highly unbalanced due to single-phase connections.

<div style="text-align: center;">
    <img src="https://github.com/SanPen/VeraGrid/blob/master/doc/md_source/figures/3ph_PowerSystem.png?raw=true"
    alt="Electrical power system network"
    title="Electrical power system network"
    width="90%"/>
</div>

## Lines

VeraGrid uses the same `Line` branch for overhead and underground AC lines. Both connect two buses and use a
series impedance and a shunt admittance; their physical construction determines how these parameters are calculated.
The reusable catalogue objects are distinct from the branch installed in the network:

| Purpose | Overhead lines | Underground lines |
|---|---|---|
| Conductor or cable construction | `Wire` | `UndergroundCableType` |
| Geometry and per-unit-length electrical parameters | `OverheadLineType` (Tower) | `UndergroundLineType` |
| Connection between buses, length and applied template | `Line` | `Line` |

The [underground cable construction](modelling.md#undergroundcabletype) and
[underground line template](modelling.md#undergroundlinetype) catalogue entries describe all their input parameters.
The following sections explain the common electrical model and the calculation specific to each technology.

### Common electrical model

#### π model

Transmission lines are mathematically modelled to describe their electrical behaviour. The inductive and resistive
effects of multiconductor lines are represented by a series impedance matrix, while capacitive effects are modelled as
a shunt admittance matrix. Together, these form the basis of the $\pi$-equivalent model commonly used in power system
studies.

<div style="text-align: center;">
    <img src="https://github.com/SanPen/VeraGrid/blob/master/doc/md_source/figures/3ph_pi_model.png?raw=true"
    alt="Line π equivalent circuit"
    title="Line π equivalent circuit"
    width="60%"/>
</div>

It consists of:

- Series impedance: $Z_{\text{series}} = R + jX$

- Shunt admittance: $Y_{\text{shunt}} = G + jB$

In the $\pi$-model, $R$ represents conductor resistance, $X$ the self and mutual inductive reactances, $G$ the shunt
conductance through insulation, and $B$ the shunt susceptance from line capacitance. Half of the total shunt admittance
is placed at each end, with series impedance in the middle.

#### Phase matrices, length and per-unit conversion

Matrix dimensions depend on the conductors represented, not on a universal five-wire assumption. A primitive matrix
retains individual conductors, including any ground wires or metallic sheaths. After the appropriate grounding
conditions and reductions, a complete three-phase circuit has a $3\times3$ phase matrix:

$$
\vec{Z} =
\begin{bmatrix}
\vec{Z}_{aa} & \vec{Z}_{ab} & \vec{Z}_{ac} \\
\vec{Z}_{ba} & \vec{Z}_{bb} & \vec{Z}_{bc} \\
\vec{Z}_{ca} & \vec{Z}_{cb} & \vec{Z}_{cc}
\end{bmatrix}
$$

Single- and two-phase circuits retain only their represented phases. A metallic sheath is not a fourth phase or an
explicit network neutral. Phase matrices preserve geometrical asymmetry and mutual coupling, which cannot generally
be replaced by a single positive-sequence impedance.

Use primes for quantities per unit length: $Z'$ in $\Omega$/km and $Y'$ in S/km. For a branch of length $\ell$ in km,
with voltage base $V_b$ in kV and three-phase power base $S_b$ in MVA:

$$
Z_b=\frac{V_b^2}{S_b},\qquad Z_{\mathrm{pu}}=\frac{\ell Z'}{Z_b},\qquad
Y_{\mathrm{sh,pu}}=\ell Y' Z_b,\qquad Y_{\mathrm{s,pu}}=Z_{\mathrm{pu}}^{-1}.
$$

The two diagonal blocks of the branch nodal admittance are $Y_{\mathrm{s,pu}}+Y_{\mathrm{sh,pu}}/2$;
the off-diagonal blocks are $-Y_{\mathrm{s,pu}}$. The connected-bus voltage supplies the base when applying a template.
The cable builder displays admittance in $\mu$S/km, whereas the template's numerical admittance matrices use S/km.
The branch stores `ys` in p.u. and `ysh` in micro-p.u.; the compiler converts the latter before splitting it between ends.

### Overhead lines

Overhead lines consist of conductors above ground, possibly with bundled phase conductors, an explicit neutral or
ground wires. Conductor heights and spacings, internal impedance and the earth-return path determine the parameters.

<div style="text-align: center;">
    <img src="https://github.com/SanPen/VeraGrid/blob/master/doc/md_source/figures/3ph_power_line.png?raw=true"
    alt="Overhead conductor arrangement"
    width="30%"/>
</div>

#### Series impedance

Carson’s equations calculate the series self and mutual impedances of overhead transmission lines, accounting for the
ground return path. They assume long, horizontally arranged conductors with average height for sag effects, homogeneous
and lossless free space, uniform earth properties, and conductor spacing much greater than conductor radius to neglect
proximity effects. The impedance matrix elements are derived from the tower geometry and conductor characteristics.

<div style="text-align: center;">
    <img src="https://github.com/SanPen/VeraGrid/blob/master/doc/md_source/figures/3ph_carson.png?raw=true"
    alt="Carson’s geometry data of the tower"
    title="Carson’s geometry data of the tower"
    width="30%"/>
</div>

Then, the following equations are implemented to obtain the self and mutual values:

$$
    \vec{Z}_{ii} = (R_i+R^c_{ii}) + j \left(\omega \frac{\mu_0}{2\pi} \ln{\frac{2h_i}{r_i}} + X_i + X^c_{ii} \right)
    \label{eq:Carson_Zii}
$$

$$
    \vec{Z}_{ij} = \vec{Z}_{ji} =
    R^c_{ij} + j \left( \omega \frac{\mu_0}{2\pi} \ln{\frac{D_{ij}}{d_{ij}}} + X^c_{ij} \right)
    \label{eq:Carson_Zij}
$$

Where:
- $R_i$ and $X_i$ are the internal resistance and reactance of conductor $i$ in $\Omega$/km.
- $R^c$ and $X^c$ are the Carson's correction terms for earth return effects in $\Omega$/km.
- $\mu_0 = 4\pi\cdot 10^{-4}$ is the permeability of free space in H/km.
- $\omega = 2\pi f$ is the angular frequency in rad/s.
- $h_i$ is the average height above ground of conductor $i$ in m.
- $r_i$ is the radius of conductor $i$ in m.
- $d_{ij}$ is the distance between conductors $i$ and $j$ in m.
- $D_{ij}$ is the distance between conductor $i$ and the image of conductor $j$ in m.

The correction terms $R^c$ and $X^c$ are derived from an infinite integral representing the impedance contribution due
to the earth return path.

#### Shunt admittance

Just as series impedance accounts for resistance and inductance, shunt admittance includes capacitance between
conductors and ground, and between conductors themselves. Under the assumptions of lossless air, uniformly grounded
earth, and conductor radii much smaller than inter-conductor spacing, these capacitances can be modelled mathematically
to compute the corresponding shunt admittances.

$$
    P_{ii} = \frac{1}{2 \pi \varepsilon_0} \ln{\frac{2 h_i}{r_i}}
$$

$$
    P_{ij} = \frac{1}{2 \pi \varepsilon_0} \ln{\frac{D_{ij}}{d_{ij}}}
$$

These expressions form Maxwell's potential-coefficient matrix $P$, not the admittance matrix itself. With
$\varepsilon_0=8.854187817\cdot10^{-9}$ F/km, $P$ is in km/F. After conductor bundling and any grounded-conductor
elimination in the potential formulation, the shunt admittance is:

$$
    C'=P^{-1},\qquad Y'=j\omega P^{-1}\quad[\mathrm{S/km}].
$$

The inversion is a matrix inversion, not an element-by-element reciprocal.

#### Ground-wire reduction

Kron's reduction, or node elimination, is a technique from network theory used to simplify a multi-node electrical
network by eliminating certain nodes, often called internal or passive nodes, while preserving the electrical
behaviour at the remaining nodes.

Assuming a set of nodes divided into two groups between ground conductors $g$ (to eliminate) and phase conductors $p$
(to keep), the impedance matrix is partitioned accordingly:

$$
    \vec{Z} =
    \begin{bmatrix}
        \vec{Z}_{gg} & \vec{Z}_{gp} \\
        \vec{Z}_{pg} & \vec{Z}_{pp} 
    \end{bmatrix}
$$

Where:
- $\vec{Z}_{gg}$ is the impedance between eliminated nodes.
- $\vec{Z}_{gp}$ is the mutual impedance between eliminated and preserved nodes.
- $\vec{Z}_{pg}$ is the mutual impedance between preserved and eliminated nodes.
- $\vec{Z}_{pp}$ is the impedance between preserved nodes.

Then, the network equations are:

$$
    \begin{bmatrix}
        \vec{U}_{g} \\
        \vec{U}_{p}
    \end{bmatrix}
    =
    \begin{bmatrix}
        \vec{Z}_{gg} & \vec{Z}_{gp} \\
        \vec{Z}_{pg} & \vec{Z}_{pp} 
    \end{bmatrix}
    \begin{bmatrix}
        \vec{I}_{g} \\
        \vec{I}_{p}
    \end{bmatrix}
$$

Assuming that the eliminated nodes are held at zero voltage because they are grounded, $\vec{U}_{g} = 0$. From the
first row of the system:

$$
    \vec{I}_e = -\vec{Z}_{gg}^{-1} \cdot \vec{Z}_{gp} \cdot \vec{I}_{p}
$$

Then, substituting $\vec{I}_e$ in the second row:

$$
    \vec{U}_p = (\vec{Z}_{pp} - \vec{Z}_{pg} \cdot \vec{Z}_{gg}^{-1} \cdot \vec{Z}_{gp}) \vec{I}_{p}
$$

Finally, the Kron-reduced impedance matrix is defined as:

$$
    \vec{Z}_\text{Kron} = \vec{Z}_{pp} - \vec{Z}_{pg} \cdot \vec{Z}_{gg}^{-1} \cdot \vec{Z}_{gp}
$$

This new matrix allows to describe the electrical behaviour of the remaining phase nodes $p$, while implicitly
incorporating the effect of the eliminated ground nodes $g$, which were assumed to be held at 0 V.

#### Line definition example

```python
import VeraGridEngine.api as gce
import numpy as np

logger = gce.Logger()
grid = gce.MultiCircuit()
grid.fBase = 60

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus_632 = gce.Bus(name='632', Vnom=4.16, xpos=0, ypos=0)
bus_632.is_slack = True
grid.add_bus(obj=bus_632)

bus_671 = gce.Bus(name='671', Vnom=4.16, xpos=0, ypos=100 * 5)
grid.add_bus(obj=bus_671)

# ----------------------------------------------------------------------------------------------------------------------
# Impedance [Ohm/km] and Admittance [S/km]
# ----------------------------------------------------------------------------------------------------------------------
z_601 = np.array([
    [0.3465 + 1j * 1.0179, 0.1560 + 1j * 0.5017, 0.1580 + 1j * 0.4236],
    [0.1560 + 1j * 0.5017, 0.3375 + 1j * 1.0478, 0.1535 + 1j * 0.3849],
    [0.1580 + 1j * 0.4236, 0.1535 + 1j * 0.3849, 0.3414 + 1j * 1.0348]
], dtype=complex) / 1.60934

y_601 = np.array([
    [1j * 6.2998, 1j * -1.9958, 1j * -1.2595],
    [1j * -1.9958, 1j * 5.9597, 1j * -0.7417],
    [1j * -1.2595, 1j * -0.7417, 1j * 5.6386]
], dtype=complex) / 10 ** 6 / 1.60934

# ----------------------------------------------------------------------------------------------------------------------
# Line Configuration
# ----------------------------------------------------------------------------------------------------------------------
config_601 = gce.create_known_abc_overhead_template(name='Config. 601',
                                                    z_nabc=z_601,
                                                    ysh_nabc=y_601,
                                                    phases=np.array([1, 2, 3]),
                                                    Vnom=4.16,
                                                    frequency=60)
grid.add_overhead_line(config_601)

# ----------------------------------------------------------------------------------------------------------------------
# Lines Definition
# ----------------------------------------------------------------------------------------------------------------------
line_632_671 = gce.Line(bus_from=bus_632,
                        bus_to=bus_671,
                        length=2000 * 0.0003048)
line_632_671.apply_template(config_601, grid.Sbase, grid.fBase, logger)
grid.add_line(obj=line_632_671)
```

#### Definition of a line from the wire configuration

**Definition of the exercise**

In this tutorial we are going to define a 3-phase line with 4 wires of two different types.

The cable types are the following:

| name         | r        | x   | gmr      | max_current |
|--------------|----------|-----|----------|-------------|
| ACSR 6/1     | 1.050117 | 0.0 | 0.001274 | 180.0       |
| Class A / AA | 0.379658 | 0.0 | 0.004267 | 263.0       |

These are taken from the data_sheets__ section

The layout is the following:

| Wire         | x(m) | y(m) | Phase |
|--------------|------|------|-------|
| ACSR 6/1     | 0    | 7    | 1 (A) |
| ACSR 6/1     | 0.4  | 7    | 2 (B) |
| ACSR 6/1     | 0.8  | 7    | 3 (C) |
| Class A / AA | 0.3  | 6.5  | 0 (N) |

**Practice**


We may start with a prepared example from the ones provided in the `grids and profiles` folder.
The example file is `Some distribution grid.xlsx`. First define the wires that you are going 
to use in the tower. For that, we proceed to the tab `Database -> Catalogue -> Wire`.

![](figures/tutorials/tower/wires.png)

Then, we proceed to the tab `Database -> Catalogue -> Tower`. Then we select
one of the existing towers or we create one with the (+) button.

![](figures/tutorials/tower/tower.png)

By clicking on the edit button (pencil) we open a new window with the `Tower builder` editor. 
Here we enter the tower definition, and once we are done, we click on the compute button (calculator). 
Then the tower cross-section will
be displayed and the results will appear in the following tabs.

![](figures/tutorials/tower/editor1.png)

This tab shows the series impedance matrix ($\Omega / km$) in several forms:

- Per phase without reduction.
- Per phase with the neutral embedded.
- Sequence reduction.

![](figures/tutorials/tower/editorZ.png)

This tab shows the series shunt admittance matrix ($\mu S / km$) in several forms:

- Per phase without reduction.
- Per phase with the neutral embedded.
- Sequence reduction.

![](figures/tutorials/tower/editorY.png)

When closed, the values are applied to the overhead line catalogue type that we were editing.

### Underground lines

An underground system is built from positioned instances of `UndergroundCableType`. Each instance represents a
single-core cable with a solid conducting core and one concentric tubular metallic sheath. Main insulation separates
the two conductors; outer insulation separates the sheath from the surrounding earth. Thus there are two conducting
layers and two dielectric regions. The model below assumes direct burial in homogeneous, nonmagnetic soil and
ideal grounding of the sheaths when forming the phase-only equivalent.

#### Cable construction and system geometry

![Cable layers and positive burial-depth convention; schematic, not to scale](figures/underground_cable_geometry.svg)

Let $r_c$ denote the core radius, $r_{si}$ and $r_{so}$ the inner and outer sheath radii, and $r_o$ the overall
cable radius. From the construction inputs, expressed in mm:

$$
r_c=\frac{d_c}{2},\qquad r_{si}=r_c+t_i,\qquad r_{so}=r_{si}+t_s,\qquad
r_o=\frac{d_{\mathrm{cable}}}{2},\qquad t_o=r_o-r_{so}.
$$

Here $d_c$ is `core_diameter`, $t_i$ is `main_insulation_thickness`, $t_s$ is `sheath_thickness` and
$d_{\mathrm{cable}}$ is `cable_diameter`. The outer insulation thickness $t_o$ is derived, not an independent input.
The electromagnetic equations below use radii in metres, so these dimensions are multiplied by $10^{-3}$ first.
Physically valid concentric layers require $0<r_c<r_{si}<r_{so}<r_o$.

Each cable centre has horizontal coordinate $x_i$ and **positive burial depth** $h_i$, both in metres.
For two distinct cables:

$$
d_{ij}=\sqrt{(x_i-x_j)^2+(h_i-h_j)^2},\qquad
D_{ij}=\sqrt{(x_i-x_j)^2+(h_i+h_j)^2},\qquad
\theta_{ij}=\arccos\frac{h_i+h_j}{D_{ij}}.
$$

$D_{ij}$ is the distance to the other cable's image across the earth surface. For a self term, the earth-return
calculation uses $d_{ii}=r_{o,i}$, $D_{ii}=2h_i$ and $\theta_{ii}=0$.

#### Series impedance

**Material properties and core.** The effective resistivity of each conducting layer is

$$
\rho=\frac{10^{-8}\rho_{\mu\Omega\mathrm{cm}}}{C_f/100}\quad[\Omega\,\mathrm{m}],\qquad
\mu=\mu_0\mu_r,\qquad \mu_0=4\pi\,10^{-7}\ \mathrm{H/m},\qquad \omega=2\pi f.
$$

$C_f$ is the conducting filling factor in percent, **not capacitance**. It accounts for the conducting fraction
of the geometric cross-section. This expression applies to both conducting layers when the shared
`resistance_input` selector is `Resistivity and filling factor`. Their DC resistances are derived as
$R_{\mathrm{dc},c}=1000\rho_c/(\pi r_c^2)$ and
$R_{\mathrm{dc},s}=1000\rho_s/[\pi(r_{so}^2-r_{si}^2)]$ in Ω/km.

Alternatively, select `DC resistance` and supply **both** `core_dc_resistance` and `sheath_dc_resistance`
at 20 °C in Ω/km. The effective resistivities used in the same equations below are then

$$
\rho_c=\frac{R_{\mathrm{dc},c}\pi r_c^2}{1000},\qquad
\rho_s=\frac{R_{\mathrm{dc},s}\pi(r_{so}^2-r_{si}^2)}{1000}\quad[\Omega\,\mathrm m].
$$

The four material resistivity/filling-factor inputs are inactive in this mode; the numerical routine receives
each effective resistivity with a 100% effective filling factor. One selector governs both layers, preventing
two independent resistance definitions from competing. See the
[cable catalogue](modelling.md#undergroundcabletype) for editing, validation and file-compatibility details.

Using modified Bessel functions $I_\nu$ and $K_\nu$, the solid-core surface impedance is

$$
m_c=\sqrt{\frac{j\omega\mu_c}{\rho_c}}\sqrt{k_s},\qquad
z_c=1000\frac{\rho_c m_c}{2\pi r_c}\frac{I_0(m_c r_c)}{I_1(m_c r_c)}\quad[\Omega/\mathrm{km}].
$$

The factor $k_s$ is `skin_effect_factor`; the factor 1000 converts impedance per metre to impedance per kilometre.
No proximity-effect correction is applied by this calculation.

**Metallic sheath.** For the sheath propagation constant $m_s=\sqrt{j\omega\mu_s/\rho_s}$, define
$u=m_s r_{si}$, $v=m_s r_{so}$ and $\Delta=I_1(v)K_1(u)-I_1(u)K_1(v)$. Its inner, outer and mutual
surface impedances, respectively, are

$$
z_{si}=1000\frac{\rho_s m_s}{2\pi r_{si}}
\frac{I_0(u)K_1(v)+K_0(u)I_1(v)}{\Delta},
$$

$$
z_{so}=1000\frac{\rho_s m_s}{2\pi r_{so}}
\frac{I_0(v)K_1(u)+K_0(v)I_1(u)}{\Delta},\qquad
z_{sm}=1000\frac{\rho_s}{2\pi r_{si}r_{so}\Delta}.
$$

**Insulating regions and internal matrix.** The longitudinal magnetic-field contribution of an insulating annulus is

$$
z_{\mathrm{ins}}(r_1,r_2)=1000\frac{j\omega\mu_0}{2\pi}\ln\frac{r_2}{r_1}.
$$

This is an inductive contribution to the series model, not a current flowing through the dielectric.
Set $L_{11}=z_c+z_{\mathrm{ins}}(r_c,r_{si})+z_{si}$,
$L_{22}=z_{so}+z_{\mathrm{ins}}(r_{so},r_o)$ and $L_{12}=-z_{sm}$.
Transforming the two coaxial loop equations to core/sheath conductor quantities gives

$$
Z'_{\mathrm{int}}=
\begin{bmatrix}
L_{11}+2L_{12}+L_{22}&L_{12}+L_{22}\\
L_{12}+L_{22}&L_{22}
\end{bmatrix}.
$$

**Earth return.** With soil resistivity $\rho_e$ in $\Omega$ m, conductivity $\sigma_e=1/\rho_e$ in S/m and
$m_e=\sqrt{j\omega\mu_0\sigma_e}$, the earth-return contribution is

$$
z'_{e,ij}=1000\left[
\frac{j\omega\mu_0}{2\pi}\left(K_0(m_e d_{ij})-K_0(m_e D_{ij})\right)
+\frac{\omega\mu_0}{\pi}\left(P(\alpha_{ij},\theta_{ij})+jQ(\alpha_{ij},\theta_{ij})\right)
\right],\qquad \alpha_{ij}=D_{ij}\sqrt{\omega\mu_0\sigma_e}.
$$

$P$ and $Q$ are the Carson correction coefficients. The implementation evaluates their small-argument expansion
through eighth order in `calculate_carson_coefficients()`; its stated range is $\alpha<5$. It does not implement a
separate large-argument branch. See the numerical scope note below for the additional fixed self-term adjustment.

**Primitive assembly.** For $n$ cables, order the conductors as
$[c_1,\ldots,c_n,s_1,\ldots,s_n]$: all cores first, then all sheaths. With the earth-return matrix $E$ and each
cable's internal matrix entries, the $2n\times2n$ series matrix is

$$
Z'_{\mathrm{primitive}}=
\begin{bmatrix}
E+\operatorname{diag}(Z'_{\mathrm{int},11})&E+\operatorname{diag}(Z'_{\mathrm{int},12})\\
E+\operatorname{diag}(Z'_{\mathrm{int},12})&E+\operatorname{diag}(Z'_{\mathrm{int},22})
\end{bmatrix}.
$$

Thus three single-core cables produce a $6\times6$ primitive matrix, not a six-phase circuit.

#### Shunt admittance

The main and outer coaxial capacitances per metre are

$$
C'_m=\frac{2\pi\varepsilon_0\varepsilon_{r,m}}{\ln(r_{si}/r_c)},\qquad
C'_o=\frac{2\pi\varepsilon_0\varepsilon_{r,o}}{\ln(r_o/r_{so})},\qquad
\varepsilon_0=8.854187817\cdot10^{-12}\ \mathrm{F/m}.
$$

For each insulating region, relative permittivity controls capacitance and loss tangent controls dielectric losses:

$$
y'=1000\,\omega C'(\tan\delta+j)\quad[\mathrm{S/km}].
$$

Here $\tan\delta$ is dimensionless, not a percentage. With diagonal matrices $Y_m$ and $Y_o$ containing these
main and outer admittances, the primitive matrix in the same core-then-sheath order is

$$
Y'_{\mathrm{primitive}}=
\begin{bmatrix}Y_m&-Y_m\\-Y_m&Y_m+Y_o\end{bmatrix}.
$$

This screened coaxial model has no direct electrostatic coupling between the cores of different cables.
Both insulating regions are nevertheless present in the primitive matrix.

#### Grounded-sheath reduction

The phase-only model eliminates the sheaths under an ideal-grounding assumption. Partition the primitive series
matrix into core and sheath blocks, indexed $c$ and $s$. Setting the longitudinal sheath voltage drop to zero gives

$$
Z'_{\mathrm{phase}}=Z'_{cc}-Z'_{cs}(Z'_{ss})^{-1}Z'_{sc}.
$$

For the shunt equations $I_c=Y'_{cc}U_c+Y'_{cs}U_s$, ideal grounding means $U_s=0$. Therefore

$$
Y'_{\mathrm{phase}}=Y'_{cc}=Y_m.
$$

The shunt reduction is **not** the Schur complement used for series impedance. In particular, outer-insulation
permittivity and loss tangent affect the primitive shunt matrix but not the reduced core shunt matrix under this
grounding assumption. Finite sheath-earthing impedance, single-point bonding and cross-bonding are not represented.

#### Phase and sequence matrices

The reduced matrices keep the phase ordering defined by the cable composition. For each complete ABC circuit,
symmetrical components are obtained without transposing or averaging the physical geometry:

$$
A=\begin{bmatrix}1&1&1\\1&a^2&a\\1&a&a^2\end{bmatrix},\qquad a=e^{j2\pi/3},\qquad
Z'_{012}=A^{-1}Z'_{abc}A,\qquad Y'_{012}=A^{-1}Y'_{abc}A.
$$

The sequence order is zero, positive, negative. Multiple complete circuits use a block-diagonal transformation.
Sequence matrices need not be diagonal for an asymmetric system. A single- or two-phase system retains its valid
phase matrices but has no complete sequence representation. The scalar `R`, `X`, `B`, `R0`, `X0`, `B0` fields
summarize diagonal sequence entries when available; they do not replace the full phase matrices in unbalanced studies.

#### Definition from the GUI

The following example uses three identical 10 kV cables with the construction defaults listed in
[UndergroundCableType](modelling.md#undergroundcabletype).

1. In `Model / Database -> Catalogue -> Cable`, add an entry named `Demo cable`.
   Set `nominal voltage` to 10 kV. Keep the default 10 mm core diameter, 5 mm main insulation thickness,
   1 mm sheath thickness and 30 mm overall cable diameter, with the remaining material defaults.
   Leave the common `resistance input` selector at `Resistivity and filling factor`: both layers' material
   inputs are editable and their derived DC resistances are read-only. Alternatively choose `DC resistance`,
   enter positive core and sheath values in Ω/km at 20 °C, and use the same geometry; all four material-input
   cells become inactive.
2. In `Catalogue -> Cable System`, create `Buried circuit` and open its editor using the edit button.
   Set voltage to 10 kV, frequency to 50 Hz, earth resistivity to 100 $\Omega$ m and rated current to 0.4 kA.
3. Select `Demo cable` in the cable catalogue and press `+` three times. Set the composition rows to:

   | Cable | X (m) | Depth (m) | Phase | Derived circuit | Derived phase name |
   |---|---:|---:|---:|---:|---|
   | Demo cable | -0.15 | 0.8 | 1 | 1 | A |
   | Demo cable | 0.00 | 0.8 | 2 | 1 | B |
   | Demo cable | 0.15 | 0.8 | 3 | 1 | C |

4. Press the calculator button. Check the geometry and choose primitive, phase or sequence impedance/admittance
   in the matrix selector. Impedance is displayed in $\Omega$/km and admittance in $\mu$S/km.
5. Accept the cable-system editor. Double-click the network line in the schematic and open its `Line editor` tab.
   Choose `Buried circuit` under `Available templates`, then press `Load template values`. Set length to 1 km
   and press the tab's `Accept` button to apply the template. Selecting a combo-box entry alone does not load it.

The line editor lists templates matching the connected-bus nominal voltage, so use 10 kV buses for this example.
The current GUI applies circuit 1 for an underground template; it does not offer arbitrary underground circuit selection.

The construction is shared catalogue data: editing it can affect several templates. Recalculate affected systems
and reapply their templates to the branches after changing construction, geometry or frequency. Reapply the template
after changing the branch length as well. An existing branch's applied matrices must not be assumed to refresh merely
because its template reference or a construction field changed.

#### Definition from Python

This example builds the same geometry without opening the GUI. The frequency of the system and the network agree;
`Imax` is supplied as a rating, not computed from a thermal model.

```python
import VeraGridEngine.api as vg


def underground_line_example() -> None:
    """Create a cable construction, calculate its system and apply it to a branch.

    :return: None.
    """
    grid: vg.MultiCircuit = vg.MultiCircuit()
    grid.fBase = 50.0
    logger: vg.Logger = vg.Logger()

    # The reusable construction describes layers, not their installation positions.
    cable: vg.UndergroundCableType = vg.UndergroundCableType(
        name="Demo cable", nominal_voltage=10.0,
        core_diameter=10.0, main_insulation_thickness=5.0,
        sheath_thickness=1.0, cable_diameter=30.0,
    )
    grid.add_underground_cable(cable)
    system: vg.UndergroundLineType = vg.UndergroundLineType(
        name="Buried circuit", Vnom=10.0, Imax=0.4,
        freq=50.0, earth_resistivity=100.0,
    )

    # One positioned instance per phase; depth is positive below the earth surface.
    phase: int
    xpos: float
    for phase, xpos in enumerate((-0.15, 0.0, 0.15), start=1):
        system.add_cable_relationship(cable=cable, xpos=xpos, ypos=0.8, phase=phase)
    calculated: bool = system.compute(logger=logger)
    if calculated:
        grid.add_underground_line(system)
        print("Z phase [ohm/km]:", system.z_nabc)
        print("Y phase [S/km]:", system.y_nabc)

        # Applying the template includes the branch length and the network base.
        source: vg.Bus = grid.add_bus(vg.Bus(name="Source", Vnom=10.0))
        destination: vg.Bus = grid.add_bus(vg.Bus(name="Destination", Vnom=10.0))
        line: vg.Line = grid.add_line(
            vg.Line(bus_from=source, bus_to=destination, length=1.0)
        )
        line.apply_template(obj=system, Sbase=grid.Sbase, freq=grid.fBase, logger=logger)
    else:
        print(logger)


underground_line_example()
```

For this example, the primitive matrices are $6\times6$ and the phase matrices are $3\times3$.
The reduced self-impedance of phase A is approximately $0.36590254+j0.15735713$ $\Omega$/km;
its shunt susceptance is approximately 57.99 $\mu$S/km. These are per-kilometre quantities, not per-unit branch values.

## Transformers

Power transformers link network sections operating at different voltages, such as generators and transmission systems.
For two-winding, three-phase transformers, the winding impedance $\vec{Z}_s$ is derived from short-circuit tests, and
the iron-core shunt admittance $\vec{Y}_{sh}$ from open-circuit tests. Modelling begins with the schematic of the basic
two-winding transformer:

<div style="text-align: center;">
    <img src="https://github.com/SanPen/VeraGrid/blob/master/doc/md_source/figures/3ph_single_phase_transformer.png?raw=true"
    alt="Two-winding transformer"
    title="Two-winding transformer"
    width="50%"/>
</div>

A transformer’s primary and secondary windings, with $N_p$ and $N_s$ turns respectively, have their voltages and
currents related through short-circuit and open-circuit admittance parameters. These relationships are represented in
the transformer’s electrical equivalent circuit:

<div style="text-align: center;">
    <img src="https://github.com/SanPen/VeraGrid/blob/master/doc/md_source/figures/3ph_transformer_electrical_circuit.png?raw=true"
    alt="Transformer electrical equivalent circuit"
    title="Transformer electrical equivalent circuit"
    width="90%"/>
</div>

In the per-unit system, the transformer voltage ratio $N_p:N_s$ becomes $1:1$. Many transformers include tap
changers to regulate voltage by adjusting the ratio to $\vec{m}:1$. In the $\pi$-model, virtual tap transformers
$m_f$ and $m_t$ reconcile device and bus nominal voltages. From the single-phase transformer model, the corresponding
primitive admittance matrix is then derived to relate primary and secondary voltages and currents.

$$
    \begin{bmatrix}
        \vec{I_p} \\
        \vec{I_s}
    \end{bmatrix}
    =
    \begin{bmatrix}
        \dfrac{ \vec{Y}_s+\dfrac{\vec{Y}_{sh}}{2}} {m^2 \, m_f^2} & \dfrac{-\vec{Y}_s}{\vec{m}^* \, m_f \, m_t} \\
        \dfrac{-\vec{Y}_s}{\vec{m} \, m_t \, m_f} & \dfrac{\vec{Y}_s+\dfrac{\vec{Y}_{sh}}{2}}{m_t^2}
    \end{bmatrix}
    \begin{bmatrix}
        \vec{U_p} \\
        \vec{U_s}
    \end{bmatrix}
$$

Using nodal analysis, single-phase transformer models can be extended to multi-winding, multi-phase configurations by
mapping winding voltages and currents (e.g., “$1,2,3,4,5,6$”) into the “$A,B,C,a,b,c$” phase frame. The primitive
parameters of three identical single-phase units are then combined to represent the full three-phase transformer.

$$
    \begin{bmatrix}
        \vec{I}_1 \\
        \vec{I}_2 \\
        \vec{I}_3 \\
        \vec{I}_4 \\
        \vec{I}_5 \\
        \vec{I}_6
    \end{bmatrix}
    =
    \begin{bmatrix}
        \dfrac{ \vec{Y}_s+\dfrac{\vec{Y}_{sh}}{2}} {m^2m_f^2} & \dfrac{-\vec{Y}_s}{\vec{m}^*m_fm_t} & 0 & 0 & 0 & 0 \\
        \dfrac{-\vec{Y}_s}{\vec{m}m_tm_f} & \dfrac{\vec{Y}_s+\dfrac{\vec{Y}_{sh}}{2}}{m_t^2} & 0 & 0 & 0 & 0 \\
        0 & 0 & \dfrac{ \vec{Y}_s+\dfrac{\vec{Y}_{sh}}{2}} {m^2m_f^2} & \dfrac{-\vec{Y}_s}{\vec{m}^*m_fm_t} & 0 & 0 \\
        0 & 0 & \dfrac{-\vec{Y}_s}{\vec{m}m_tm_f} & \dfrac{\vec{Y}_s+\dfrac{\vec{Y}_{sh}}{2}}{m_t^2} & 0 & 0 \\
        0 & 0 & 0 & 0 & \dfrac{ \vec{Y}_s+\dfrac{\vec{Y}_{sh}}{2}} {m^2m_f^2} & \dfrac{-\vec{Y}_s}{\vec{m}^*m_fm_t} \\
        0 & 0 & 0 & 0 & \dfrac{-\vec{Y}_s}{\vec{m}m_tm_f} & \dfrac{\vec{Y}_s+\dfrac{\vec{Y}_{sh}}{2}}{m_t^2}
    \end{bmatrix}
    \begin{bmatrix}
        \vec{U}_1 \\
        \vec{U}_2 \\
        \vec{U}_3 \\
        \vec{U}_4 \\
        \vec{U}_5 \\
        \vec{U}_6
    \end{bmatrix}
$$

Expressed in compact form, the resulting expression is:

$$
    \vec{I}_\text{coils} = \vec{Y}_\text{primitive} \cdot \vec{U}_\text{coils}
$$

Which can be operated in order to relate phase magnitudes:

$$
    \vec{I}_\text{phases} = C_I^{-1} \cdot \vec{Y}_\text{primitive} \cdot C_U \cdot \vec{U}_\text{phases}
    \label{eq:Y_transformer1}
$$

It follows that the next step is to find the connectivity matrices $C_U$ and $C_I$, which relate the voltages and
currents at each winding to the phase magnitudes, to obtain the transformer admittance matrix $\vec{Y}$.
This matrix links the primary and secondary phase voltages and currents:

$$
    \vec{Y} = C_I^{-1} \cdot \vec{Y}_\text{primitive} \cdot C_U
\label{eq:Y_transformer}
$$

The three-phase windings of power transformers may be connected in several ways. In high voltage transmission the most
popular connections are star and delta, although the zig-zag connection is also used in distribution systems, depicted
in figure bellow. Consequently, connectivity matrices must be computed for each configuration.

<div style="text-align: center;">
    <img src="https://github.com/SanPen/VeraGrid/blob/master/doc/md_source/figures/3ph_zigzag.png?raw=true"
    alt="Zig-zag transformer"
    title="Zig-zag transformer"
    width="40%"/>
</div>

For instance, the following figure shows the three-phase delta-star (Dy) connection:

<div style="text-align: center;">
    <img src="https://github.com/SanPen/VeraGrid/blob/master/doc/md_source/figures/3ph_Dy_connection.png?raw=true"
    alt="Dy connection"
    title="Dy connection"
    width="70%"/>
</div>

The transformation matrix $C_U$, which relates the voltages of each winding to the corresponding phase voltages,
is given explicitly in the following expression:

$$
    \begin{bmatrix}
        \vec{U}_1 \\
        \vec{U}_2 \\
        \vec{U}_3 \\
        \vec{U}_4 \\
        \vec{U}_5 \\
        \vec{U}_6
    \end{bmatrix}
    =
    \begin{bmatrix}
        \dfrac{1}{\sqrt{3}} & -\dfrac{1}{\sqrt{3}} & 0 & 0 & 0 & 0 \\
        0 & 0 & 0 & 1 & 0 & 0 \\
        0 & \dfrac{1}{\sqrt{3}} & -\dfrac{1}{\sqrt{3}} & 0 & 0 & 0 \\
        0 & 0 & 0 & 0 & 1 & 0 \\
        -\dfrac{1}{\sqrt{3}} & 0 & \dfrac{1}{\sqrt{3}} & 0 & 0 & 0 \\
        0 & 0 & 0 & 0 & 0 & 1 \\
    \end{bmatrix}
    \begin{bmatrix}
        \vec{U}_A \\
        \vec{U}_B \\
        \vec{U}_C \\
        \vec{U}_a \\
        \vec{U}_b \\
        \vec{U}_c
    \end{bmatrix}
$$

And in compact form:

$$
    \vec{U}_\text{coils} = C_U \cdot \vec{U}_\text{phases}
$$

Similarly, the inverse current connectivity matrix $C_I^{-1}$ is obtained:

$$
    \begin{bmatrix}
        \vec{I}_A \\
        \vec{I}_B \\
        \vec{I}_C \\
        \vec{I}_a \\
        \vec{I}_b \\
        \vec{I}_c
    \end{bmatrix}
    =
    \begin{bmatrix}
        \dfrac{1}{\sqrt{3}} & 0 & 0 & 0 & -\dfrac{1}{\sqrt{3}} & 0 \\
        -\dfrac{1}{\sqrt{3}} & 0 & \dfrac{1}{\sqrt{3}} & 0 & 0 & 0 \\
        0 & 0 & -\dfrac{1}{\sqrt{3}} & 0 & \dfrac{1}{\sqrt{3}} & 0 \\
        0 & 1 & 0 & 0 & 0 & 0 \\
        0 & 0 & 0 & 1 & 0 & 0 \\
        0 & 0 & 0 & 0 & 0 & 1 \\
    \end{bmatrix}
    \begin{bmatrix}
        \vec{I}_1 \\
        \vec{I}_2 \\
        \vec{I}_3 \\
        \vec{I}_4 \\
        \vec{I}_5 \\
        \vec{I}_6
    \end{bmatrix}
$$

And also in compact form:

$$
    \vec{I}_\text{phases} = C_I^{-1} \cdot \vec{I}_\text{coils}
$$

The full transformer admittance matrix for the Dy connection is obtained by substituting the connectivity matrices $C_U$
and $C_I$:

$$
    \vec{Y} = C_I^{-1} \cdot \vec{Y}_\text{primitive} \cdot C_U
$$

Finally, the transformer admittance matrix for the Dy connection is computed:

$$
\vec{Y}
    =
    \begin{bmatrix}
        \dfrac{2\vec{Y}_s+\vec{Y}_{sh}}{3m^2m_f^2} & \dfrac{-\vec{Y}_s-\dfrac{\vec{Y}_{sh}}{2}}{3m^2m_f^2} & \dfrac{-\vec{Y}_s-\dfrac{\vec{Y}_{sh}}{2}}{3m^2m_f^2} & \dfrac{-\vec{Y_s}}{\sqrt{3}\vec{m}^*m_fm_t} & 0 & \dfrac{\vec{Y_s}}{\sqrt{3}\vec{m}^*m_fm_t} \\
        \dfrac{-\vec{Y}_s-\dfrac{\vec{Y}_{sh}}{2}}{3m^2m_f^2} & \dfrac{2\vec{Y}_s+\vec{Y}_{sh}}{3m^2m_f^2} & \dfrac{-\vec{Y}_s-\dfrac{\vec{Y}_{sh}}{2}}{3m^2m_f^2} & \dfrac{\vec{Y_s}}{\sqrt{3}\vec{m}^*m_fm_t} & \dfrac{-\vec{Y_s}}{\sqrt{3}\vec{m}^*m_fm_t} & 0 \\
        \dfrac{-\vec{Y}_s-\dfrac{\vec{Y}_{sh}}{2}}{3m^2m_f^2} & \dfrac{-\vec{Y}_s-\dfrac{\vec{Y}_{sh}}{2}}{3m^2m_f^2} & \dfrac{2\vec{Y}_s+\vec{Y}_{sh}}{3m^2m_f^2} & 0 & \dfrac{\vec{Y_s}}{\sqrt{3}\vec{m}^*m_fm_t} & \dfrac{-\vec{Y_s}}{\sqrt{3}\vec{m}^*m_fm_t} \\
        \dfrac{-\vec{Y_s}}{\sqrt{3}\vec{m}m_tm_f} & \dfrac{\vec{Y_s}}{\sqrt{3}\vec{m}m_tm_f} & 0 & \dfrac{\vec{Y}_s+\dfrac{\vec{Y}_{sh}}{2}}{m_t^2} & 0 & 0 \\
        0 & \dfrac{-\vec{Y_s}}{\sqrt{3}\vec{m}m_tm_f} & \dfrac{\vec{Y_s}}{\sqrt{3}\vec{m}m_tm_f} & 0 & \dfrac{\vec{Y}_s+\dfrac{\vec{Y}_{sh}}{2}}{m_t^2} & 0 \\
        \dfrac{\vec{Y_s}}{\sqrt{3}\vec{m}m_tm_f} & 0 & \dfrac{-\vec{Y_s}}{\sqrt{3}\vec{m}m_tm_f} & 0 & 0 & \dfrac{\vec{Y}_s+\dfrac{\vec{Y}_{sh}}{2}}{m_t^2} \\
    \end{bmatrix}
$$

The admittance matrices for the other eight possible configurations have been obtained using exactly the same procedure.

### Vector group and clock notation

The vector group and clock notation define the connection type of the high-voltage (HV) and low-voltage (LV) windings
of a three-phase transformer, as well as the phase displacement between their voltages.
The HV side connection is indicated first using uppercase letters, followed by the LV side in lowercase.
The phase displacement is then specified using clock notation:

<div style="text-align: center;">
    <img src="https://github.com/SanPen/VeraGrid/blob/master/doc/md_source/figures/3ph_clock_notation.png?raw=true"
    alt="Clock notation"
    title="Clock notation"
    width="30%"/>
</div>

The full circumference of a clock is $360^\circ$, which, divided by its $12$ hours, assigns $30^\circ$ to each hour.
If the high-voltage (HV) side is taken as the reference, the low-voltage (LV) side indicates the phase displacement
between the two voltages. For instance, a \textbf{Dy5} transformer connection means that the HV side is delta-connected,
the LV side is star-connected, and the phase displacement between them is $150^\circ$ ($5 \cdot 30^\circ$), as
illustrated in the figure above.

### Transformer definition example

```python
import VeraGridEngine.api as gce
from VeraGridEngine import WindingType

logger = gce.Logger()
grid = gce.MultiCircuit()
grid.fBase = 60

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus_1 = gce.Bus(name='633', Vnom=4.16, xpos=100 * 5, ypos=0)
grid.add_bus(obj=bus_1)

bus_2 = gce.Bus(name='634', Vnom=0.48, xpos=200 * 5, ypos=0)
grid.add_bus(obj=bus_2)

# ----------------------------------------------------------------------------------------------------------------------
# Transformer Definition
# ----------------------------------------------------------------------------------------------------------------------
trafo_1 = gce.Transformer2W(name='Transformer',
                            bus_from=bus_1,
                            bus_to=bus_2,
                            HV=4.16,
                            LV=0.48,
                            nominal_power=0.5,
                            rate=0.5,
                            r=1,
                            x=2)
trafo_1.conn_f = WindingType.GroundedStar
trafo_1.conn_t = WindingType.GroundedStar
grid.add_transformer2w(trafo_1)
```

### Transformer definition from SC test values

The transformers are modeled as π branches too. In order to get the series impedance and shunt admittance of
the transformer to match the branch model, it is advised to transform the specification sheet values of the device
into the desired values. The values to take from the specs sheet are:

- $S_n$: Nominal power in MVA.
- $HV$: Voltage at the high-voltage side in kV.
- $LV$: Voltage at the low-voltage side in kV.
- $V_{hv\_bus}$: Nominal voltage of the high-voltage side bus kV.
- $V_{lv\_bus}$: Nominal voltage of the low-voltage side bus kV.
- $V_{sc}$: Short circuit voltage in %.
- $P_{cu}$: Copper losses in kW.
- $I_0$: No load current in %.
- $Share_{hv1}$: Contribution to the HV side. Value from 0 to 1.


Short circuit impedance (p.u. of the machine)

$$
    z_{sc} = \frac{V_{sc}}{100}
$$

Short circuit resistance (p.u. of the machine)

$$
    r_{sc} = \frac{P_{cu} / 1000}{ S_n }
$$

Short circuit reactance (p.u. of the machine)
Can only be computed if $r_{sc} < z_{sc}$

$$
    x_{sc} = \sqrt{z_{sc}^2 - r_{sc}^2}
$$

Series impedance (p.u. of the machine)

$$
    z_s = r_{sc} + j \cdot x_{sc}
$$

The issue with this is that we now must convert $zs$ from machine base to the system base.

First we compute the High voltage side:

$$
    z_{base}^{HV} = \frac{HV^2}{S_n}
$$

$$
    z_{base}^{hv\_bus} = \frac{V_{hv\_bus}^2}{S_{base}}
$$

$$
    z_{s\_HV}^{system}  = z_s\cdot  \frac{z_{base}^{HV}}{z_{base}^{hv\_bus}} \cdot Share_{hv1}  = z_s \cdot  \frac{HV^2 \cdot S_{base}}{V_{hv\_bus}^2 \cdot S_n}  \cdot Share_{hv1}
$$

Now, we compute the Low voltage side:

$$
    z_{base}^{LV} = \frac{LV^2}{S_n}
$$

$$
    z_{base}^{lv\_bus} = \frac{V_{lv\_bus}^2}{S_{base}}
$$

$$
    z_{s\_LV}^{system} = z_s \cdot \frac{z_{base}^{LV}}{z_{base}^{lv\_bus}}  \cdot (1 - Share_{hv1})  = z_s \cdot  \frac{LV^2 \cdot S_{base}}{V_{lv\_bus}^2 \cdot S_n}  \cdot (1 - Share_{hv1})
$$


Finally, the system series impedance in p.u. is:

$$
    z_s = z_{s\_HV}^{system} + z_{s\_LV}^{system}
$$

Now, the leakage impedance (shunt of the model)

$$
    r_m = \frac{S_{base}}{P_{fe} / 1000}
$$

$$
    z_m = \frac{100 \cdot S_{base}}{I0 \cdot S_n}
$$

$$
    x_m = \sqrt{\frac{ - r_m^2 \cdot z_m^2}{z_m^2 - r_m^2}}
$$

Finally, the shunt admittance is (p.u. of the system):

$$
    y_{shunt} = \frac{1}{r_m} + j \cdot \frac{1}{x_m}
$$

### Inverse definition of SC values from π model

In VeraGrid I found the need to find the short circuit values 
($P_{cu}, V_{sc}, r_{fe}, I0$) from the branch values (*R*, *X*, *G*, *B*). Hence the following formulas:

$$
    z_{sc} = \sqrt{R^2 + X^2}
$$

$$
    V_{sc} = 100 \cdot z_{sc}
$$

$$
    P_{cu} = R \cdot S_n \cdot 1000
$$


$$
    zl = 1 / (G + j B)
$$

$$
    r_{fe} = zl.real
$$

$$
    xm = zl.imag
$$

$$
    I0 = 100 \cdot \sqrt{1 / r_{fe}^2 + 1 / xm^2}
$$

## Loads and Shunts

Given the diversity of loads in power networks, they are grouped into bulk consumption points and represented using the
ZIP model, which combines impedance, current, and power components.

<div style="text-align: center;">
    <img src="https://github.com/SanPen/VeraGrid/blob/master/doc/md_source/figures/3ph_zip_model.png?raw=true"
    alt="ZIP model"
    title="ZIP model"
    width="50%"/>
</div>

In steady-state studies, loads are represented as three-phase power sinks, connected in star or delta. Since the
formulation uses phase-to-neutral voltages and line currents, all loads are modelled as
star-connected, requiring delta loads to be converted to star equivalents for impedance, current, and power injections.

<div style="text-align: center;">
    <img src="https://github.com/SanPen/VeraGrid/blob/master/doc/md_source/figures/3ph_loads_star_delta.png?raw=true"
    title="Star and delta connected loads"
    width="70%"/>
</div>

### Constant impedance (Z) modelling of three-phase star-connected loads and shunts

Constant impedance loads and shunts are defined in terms of conductance G [MW] and susceptance B [MVAr].
If these elements have the three-phases active, and they are connected in star, the diagonal of the 3x3 admittance
matrix $\vec{Y}_0$ is simply filled with the values defined for each phase:

$$
\vec{Y}_0 =
\begin{bmatrix}
    \vec{Y}_a & 0 & 0 \\
    0 & \vec{Y}_b & 0 \\
    0 & 0 & \vec{Y}_c \\
\end{bmatrix}
$$

<div style="text-align: center;">
    <img src="https://github.com/SanPen/VeraGrid/blob/master/doc/md_source/figures/3ph_star_impedance.png?raw=true"
    title="Three-phase star impedance loads"
    width="50%"/>
</div>

#### Example

```python
import VeraGridEngine.api as gce
from VeraGridEngine import ShuntConnectionType

logger = gce.Logger()
grid = gce.MultiCircuit()

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus = gce.Bus(name='Bus', Vnom=0.48)
grid.add_bus(obj=bus)

# ----------------------------------------------------------------------------------------------------------------------
# Three-phase star impedance load
# ----------------------------------------------------------------------------------------------------------------------
load = gce.Load(G1=0.160,
                B1=0.110,
                G2=0.120,
                B2=0.090,
                G3=0.120,
                B3=0.090)
load.conn = ShuntConnectionType.GroundedStar
grid.add_load(bus=bus, api_obj=load)
```

### Constant impedance (Z) modelling of three-phase delta-connected loads and shunts

However, if the load is defined in delta connection, the 3x3 matrix shown bellow will be used to mathematically
model the load or the shunt element:

$$
\vec{Y}_0 = \dfrac{1}{3}
\begin{bmatrix}
    \vec{Y}_{ab} + \vec{Y}_{ca} & -\vec{Y}_{ab} & -\vec{Y}_{ca} \\
    -\vec{Y}_{ab} & \vec{Y}_{ab} + \vec{Y}_{bc} & -\vec{Y}_{bc} \\
    -\vec{Y}_{ca} & -\vec{Y}_{bc} & \vec{Y}_{bc} + \vec{Y}_{ca} \\
\end{bmatrix}
$$

<div style="text-align: center;">
    <img src="https://github.com/SanPen/VeraGrid/blob/master/doc/md_source/figures/3ph_delta_impedance.png?raw=true"
    title="Three-phase delta impedance loads"
    width="60%"/>
</div>

#### Example

```python
import VeraGridEngine.api as gce
from VeraGridEngine import ShuntConnectionType

logger = gce.Logger()
grid = gce.MultiCircuit()

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus = gce.Bus(name='Bus', Vnom=0.48)
grid.add_bus(obj=bus)

# ----------------------------------------------------------------------------------------------------------------------
# Three-phase delta impedance load
# ----------------------------------------------------------------------------------------------------------------------
load = gce.Load(G1=0.160,
                B1=0.110,
                G2=0.120,
                B2=0.090,
                G3=0.120,
                B3=0.090)
load.conn = ShuntConnectionType.Delta
grid.add_load(bus=bus, api_obj=load)
```

### Constant impedance (Z) modelling of two-phase loads and shunts

Two-phase loads and shunts defined as admittances are converted to their corresponding equivalent power values in star
configuration. This conversion is carried out using the voltage, and the resulting power values must be updated at each
iteration of the algorithm. Therefore, in this case, the values are not stored in the admittance matrix $\vec{Y}_0$ but
rather in the power vector $\vec{S}_0$. The current flowing through this type of load is equal to the voltage difference
between the phases to which it is connected, multiplied by its admittance, as shown the equation bellow. By multiplying
the resulting current in each phase by its corresponding voltage, the power value can be obtained.

$$
\vec{I}_{a} = (\vec{U}_{a} - \vec{U}_{b}) \cdot \dfrac{\vec{Y}_{ab}}{3}
$$

In the case where the load is connected between phases $a$ and $c$, the conversion is as follows:

$$
\vec{S}_0 = 
\begin{bmatrix}
    \vec{U}_{a} \cdot \left[ (\vec{U}_{a} - \vec{U}_{c}) \cdot \dfrac{\vec{Y}_{ca}}{3} \right]^* \\
    0 \\
    \vec{U}_{c} \cdot \left[ (\vec{U}_{c} - \vec{U}_{a}) \cdot \dfrac{\vec{Y}_{ca}}{3} \right]^* \\
\end{bmatrix}
$$

<div style="text-align: center;">
    <img src="https://github.com/SanPen/VeraGrid/blob/master/doc/md_source/figures/3ph_two_phase_impedance.png?raw=true"
    title="Two-phase impedance loads"
    width="40%"/>
</div>

#### Example

```python
import VeraGridEngine.api as gce
from VeraGridEngine import ShuntConnectionType

logger = gce.Logger()
grid = gce.MultiCircuit()

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus = gce.Bus(name='Bus', Vnom=0.48)
grid.add_bus(obj=bus)

# ----------------------------------------------------------------------------------------------------------------------
# Two-phase impedance load
# ----------------------------------------------------------------------------------------------------------------------
load = gce.Load(G1=0.0,
                B1=0.0,
                G2=0.0,
                B2=0.0,
                G3=0.230,
                B3=0.132)
load.conn = ShuntConnectionType.Delta
grid.add_load(bus=bus, api_obj=load)
```

### Constant impedance (Z) modelling of single-phase loads and shunts

Finally, single-phase loads and shunt elements are modelled as in the previous three-phase star case, but only saving
the admittance value for the active phase, for instance phase $b$:

$$
\vec{Y}_0 =
\begin{bmatrix}
    0 & 0 & 0 \\
    0 & \vec{Y}_b & 0 \\
    0 & 0 & 0 \\
\end{bmatrix}
$$

<div style="text-align: center;">
    <img src="https://github.com/SanPen/VeraGrid/blob/master/doc/md_source/figures/3ph_single_phase_impedance.png?raw=true"
    title="Single-phase impedance loads"
    width="20%"/>
</div>

#### Example

```python
import VeraGridEngine.api as gce
from VeraGridEngine import ShuntConnectionType

logger = gce.Logger()
grid = gce.MultiCircuit()

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus = gce.Bus(name='Bus', Vnom=0.48)
grid.add_bus(obj=bus)

# ----------------------------------------------------------------------------------------------------------------------
# Single-phase impedance load
# ----------------------------------------------------------------------------------------------------------------------
load = gce.Load(G1=0.0,
                B1=0.0,
                G2=0.128,
                B2=0.086,
                G3=0.0,
                B3=0.0)
load.conn = ShuntConnectionType.GroundedStar
grid.add_load(bus=bus, api_obj=load)
```

### Constant current (I) modelling of three-phase star-connected loads

Traditionally, in positive sequence power flow analysis, constant current loads are directly stored in the $\vec{I}_0$
vector. However, since we are performing a three-phase power flow, the voltage angles of phases b and c are not zero,
so they must be taken into account. For both three-phase current star-connected loads, the defined phase currents are
stored in the vector $\vec{I}_0$ as follows:

$$
\vec{I}_0 =
\begin{bmatrix}
    \vec{I}_a^* \, e^{j \, \delta_a} \\
    \vec{I}_b^* \, e^{j \, \delta_b} \\
    \vec{I}_c^* \, e^{j \, \delta_c} \\
\end{bmatrix}
$$

<div style="text-align: center;">
    <img src="https://github.com/SanPen/VeraGrid/blob/master/doc/md_source/figures/3ph_star_current.png?raw=true"
    title="Three-phase star current loads"
    width="50%"/>
</div>

#### Example

```python
import VeraGridEngine.api as gce
from VeraGridEngine import ShuntConnectionType

logger = gce.Logger()
grid = gce.MultiCircuit()

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus = gce.Bus(name='Bus', Vnom=0.48)
grid.add_bus(obj=bus)

# ----------------------------------------------------------------------------------------------------------------------
# Three-phase star current load
# ----------------------------------------------------------------------------------------------------------------------
load = gce.Load(Ir1=0.160,
                Ii1=0.110,
                Ir2=0.120,
                Ii2=0.090,
                Ir3=0.120,
                Ii3=0.090)
load.conn = ShuntConnectionType.GroundedStar
grid.add_load(bus=bus, api_obj=load)
```

### Constant current (I) modelling of three-phase delta-connected loads

However, if the current load is defined in delta connection, the vector shown bellow will be used to mathematically
model the element:

$$
\vec{I}_0 =
\begin{bmatrix}
\dfrac{\vec{I}_{ab}^* \, e^{j \, (\delta_a - \delta_b)} - \vec{I}_{ca}^* \, e^{j \, (\delta_c - \delta_a)}}{\sqrt{3}} \\
\dfrac{\vec{I}_{bc}^* \, e^{j \, (\delta_b - \delta_c)} - \vec{I}_{ab}^* \, e^{j \, (\delta_a - \delta_b)}}{\sqrt{3}} \\
\dfrac{\vec{I}_{ca}^* \, e^{j \, (\delta_c - \delta_a)} - \vec{I}_{bc}^* \, e^{j \, (\delta_b - \delta_c)}}{\sqrt{3}} \\
\end{bmatrix}
$$

Note that for loads connected between phases, the voltage angle to be applied is not that of the
phase to which the current load will be mapped, but rather the angle of the voltage difference
between the two phases to which the current-defined load is connected. Then, the angles
will be updated in each iteration, adding significant complexity compared to the traditional power flow.

<div style="text-align: center;">
    <img src="https://github.com/SanPen/VeraGrid/blob/master/doc/md_source/figures/3ph_delta_current.png?raw=true"
    title="Three-phase delta current loads"
    width="60%"/>
</div>

#### Example

```python
import VeraGridEngine.api as gce
from VeraGridEngine import ShuntConnectionType

logger = gce.Logger()
grid = gce.MultiCircuit()

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus = gce.Bus(name='Bus', Vnom=0.48)
grid.add_bus(obj=bus)

# ----------------------------------------------------------------------------------------------------------------------
# Three-phase delta current load
# ----------------------------------------------------------------------------------------------------------------------
load = gce.Load(Ir1=0.160,
                Ii1=0.110,
                Ir2=0.120,
                Ii2=0.090,
                Ir3=0.120,
                Ii3=0.090)
load.conn = ShuntConnectionType.Delta
grid.add_load(bus=bus, api_obj=load)
```

### Constant current (I) modelling of two-phase loads

Two-phase current loads, connected for instance between phases $a$ and $c$, are modelled in the same way as three-phase
delta-connected loads. The only difference is that, in this case, the current is defined solely as $vec{I}_{ca}$, while the
other phase-to-phase currents remain zero:

$$
\vec{I}_0 =
\begin{bmatrix}
\dfrac{- \vec{I}_{ca}^* \, e^{j \, (\delta_c - \delta_a)}}{\sqrt{3}} \\
0 \\
\dfrac{ \vec{I}_{ca}^* \, e^{j \, (\delta_c - \delta_a)}}{\sqrt{3}} \\
\end{bmatrix}
$$

<div style="text-align: center;">
    <img src="https://github.com/SanPen/VeraGrid/blob/master/doc/md_source/figures/3ph_two_phase_current.png?raw=true"
    title="Two-phase current loads"
    width="40%"/>
</div>

#### Example

```python
import VeraGridEngine.api as gce
from VeraGridEngine import ShuntConnectionType

logger = gce.Logger()
grid = gce.MultiCircuit()

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus = gce.Bus(name='Bus', Vnom=0.48)
grid.add_bus(obj=bus)

# ----------------------------------------------------------------------------------------------------------------------
# Two-phase current load
# ----------------------------------------------------------------------------------------------------------------------
load = gce.Load(Ir1=0.0,
                Ii1=0.0,
                Ir2=0.0,
                Ii2=0.0,
                Ir3=0.170,
                Ii3=0.151)
load.conn = ShuntConnectionType.Delta
grid.add_load(bus=bus, api_obj=load)
```

### Constant current (I) modelling of single-phase loads

Finally, single-phase current loads, connected for instance to phase $b$, are modelled in the same way as three-phase
star-connected loads. The difference lies in the fact that the absent phases are stored with a value of zero.

$$
\vec{I}_0 =
\begin{bmatrix}
    0 \\
    \vec{I}_b^* \, e^{j \, \delta_b} \\
    0 \\
\end{bmatrix}
$$

<div style="text-align: center;">
    <img src="https://github.com/SanPen/VeraGrid/blob/master/doc/md_source/figures/3ph_single_phase_current.png?raw=true"
    title="Single-phase current loads"
    width="20%"/>
</div>

#### Example

```python
import VeraGridEngine.api as gce
from VeraGridEngine import ShuntConnectionType

logger = gce.Logger()
grid = gce.MultiCircuit()

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus = gce.Bus(name='Bus', Vnom=0.48)
grid.add_bus(obj=bus)

# ----------------------------------------------------------------------------------------------------------------------
# Single-phase current load
# ----------------------------------------------------------------------------------------------------------------------
load = gce.Load(Ir1=0.0,
                Ii1=0.0,
                Ir2=0.170,
                Ii2=0.080,
                Ir3=0.0,
                Ii3=0.0)
load.conn = ShuntConnectionType.GroundedStar
grid.add_load(bus=bus, api_obj=load)
```

### Constant power (P) modelling of three-phase star-connected loads

Finally, we will address the modelling of constant power loads. In the case of a three-phase power load connected in
star, the values defined by the user are stored in the $vec{S}_0$ vector for each phase:

$$
\vec{S}_0 =
\begin{bmatrix}
\vec{S}_a \\
\vec{S}_b \\
\vec{S}_c \\
\end{bmatrix}
$$

<div style="text-align: center;">
    <img src="https://github.com/SanPen/VeraGrid/blob/master/doc/md_source/figures/3ph_star_power.png?raw=true"
    title="Three-phase star power loads"
    width="50%"/>
</div>

#### Example

```python
import VeraGridEngine.api as gce
from VeraGridEngine import ShuntConnectionType

logger = gce.Logger()
grid = gce.MultiCircuit()

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus = gce.Bus(name='Bus', Vnom=0.48)
grid.add_bus(obj=bus)

# ----------------------------------------------------------------------------------------------------------------------
# Three-phase star power load
# ----------------------------------------------------------------------------------------------------------------------
load = gce.Load(P1=0.485,
                Q1=0.190,
                P2=0.068,
                Q2=0.060,
                P3=0.290,
                Q3=0.212)
load.conn = ShuntConnectionType.GroundedStar
grid.add_load(bus=bus, api_obj=load)
```

### Constant power (P) modelling of three-phase delta-connected loads

In contrast, if the three-phase power load is connected in delta, the developed transformation to its star equivalent
involves the phase-to-ground voltages. Then, the power transformation vector to star will be
updated in each iteration, adding significant complexity compared to the traditional power flow.

$$
\vec{S}_0 = 
\begin{bmatrix}
\dfrac{\vec{U}_a \cdot \vec{S}_{ab}}{\vec{U}_a - \vec{U}_b} - \dfrac{\vec{U}_a \cdot \vec{S}_{ca}}{\vec{U}_c - \vec{U}_a} \\
\dfrac{\vec{U}_b \cdot \vec{S}_{bc}}{\vec{U}_b - \vec{U}_c} - \dfrac{\vec{U}_b \cdot \vec{S}_{ab}}{\vec{U}_a - \vec{U}_b} \\
\dfrac{\vec{U}_c \cdot \vec{S}_{ca}}{\vec{U}_c - \vec{U}_a} - \dfrac{\vec{U}_c \cdot \vec{S}_{bc}}{\vec{U}_b - \vec{U}_c} \\
\end{bmatrix}
$$

<div style="text-align: center;">
    <img src="https://github.com/SanPen/VeraGrid/blob/master/doc/md_source/figures/3ph_delta_power.png?raw=true"
    title="Three-phase delta power loads"
    width="60%"/>
</div>

#### Example

```python
import VeraGridEngine.api as gce
from VeraGridEngine import ShuntConnectionType

logger = gce.Logger()
grid = gce.MultiCircuit()

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus = gce.Bus(name='Bus', Vnom=0.48)
grid.add_bus(obj=bus)

# ----------------------------------------------------------------------------------------------------------------------
# Three-phase delta power load
# ----------------------------------------------------------------------------------------------------------------------
load = gce.Load(P1=0.385,
                Q1=0.220,
                P2=0.385,
                Q2=0.220,
                P3=0.385,
                Q3=0.220)
load.conn = ShuntConnectionType.Delta
grid.add_load(bus=bus, api_obj=load)
```

### Constant power (P) modelling of two-phase loads

Two-phase power loads, connected for instance between phases $a$ and $c$, are modelled in the same way as three-phase
delta-connected loads. The only difference is that, in this case, the power is defined solely as $vec{S}_{ca}$, while the
other phase-to-phase powers remain zero:

$$
\vec{S}_0 = 
\begin{bmatrix}
-\dfrac{\vec{U}_a \cdot \vec{S}_{ca}}{\vec{U}_c - \vec{U}_a} \\
0 \\
\dfrac{\vec{U}_c \cdot \vec{S}_{ca}}{\vec{U}_c - \vec{U}_a} \\
\end{bmatrix}
$$

<div style="text-align: center;">
    <img src="https://github.com/SanPen/VeraGrid/blob/master/doc/md_source/figures/3ph_two_phase_power.png?raw=true"
    title="Two-phase power loads"
    width="40%"/>
</div>

#### Example

```python
import VeraGridEngine.api as gce
from VeraGridEngine import ShuntConnectionType

logger = gce.Logger()
grid = gce.MultiCircuit()

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus = gce.Bus(name='Bus', Vnom=0.48)
grid.add_bus(obj=bus)

# ----------------------------------------------------------------------------------------------------------------------
# Two-phase power load
# ----------------------------------------------------------------------------------------------------------------------
load = gce.Load(P1=0.0,
                Q1=0.0,
                P2=0.0,
                Q2=0.0,
                P3=0.160,
                Q3=0.110)
load.conn = ShuntConnectionType.Delta
grid.add_load(bus=bus, api_obj=load)
```

### Constant power (P) modelling of single-phase loads

Finally, single-phase power loads, connected for instance to phase $b$, are modelled in the same way as three-phase
star-connected loads. The difference lies in the fact that the absent phases are stored with a value of zero:

$$
\vec{S}_0 =
\begin{bmatrix}
0 \\
\vec{S}_b \\
0 \\
\end{bmatrix}
$$

<div style="text-align: center;">
    <img src="https://github.com/SanPen/VeraGrid/blob/master/doc/md_source/figures/3ph_single_phase_power.png?raw=true"
    title="Single-phase power loads"
    width="20%"/>
</div>

#### Example

```python
import VeraGridEngine.api as gce
from VeraGridEngine import ShuntConnectionType

logger = gce.Logger()
grid = gce.MultiCircuit()

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus = gce.Bus(name='Bus', Vnom=0.48)
grid.add_bus(obj=bus)

# ----------------------------------------------------------------------------------------------------------------------
# Single-phase power load
# ----------------------------------------------------------------------------------------------------------------------
load = gce.Load(P1=0.0,
                Q1=0.0,
                P2=0.170,
                Q2=0.125,
                P3=0.0,
                Q3=0.0)
load.conn = ShuntConnectionType.GroundedStar
grid.add_load(bus=bus, api_obj=load)
```

## Generators

For the power flow simulations, generators had been modelled as simple power injections into the system, which was
completely valid. However, this is not sufficient when performing the short-circuit analysis, as the impedance of the
generator must also be taken into account. VeraGrid has been programmed to accept a $3 \times 3$ impedance matrix, which
includes both the self and mutual impedances between the $abc$ phases.

It is also common to encounter generator impedances in the sequence domain. Therefore, Fortescue’s theorem is
applied to obtain the equivalent values for the three phases:

$$
\vec{Z}_{gen_{abc}} =
\begin{bmatrix}
\vec{Z}_0 + \vec{Z}_1 + \vec{Z}_2 & \vec{Z}_0 + \vec{a}\vec{Z}_1 + \vec{a}^2\vec{Z}_2 & \vec{Z}_0 + \vec{a}^2\vec{Z}_1 + \vec{a}\vec{Z}_2 \\
\vec{Z}_0 + \vec{a}^2\vec{Z}_1 + \vec{a}\vec{Z}_2 & \vec{Z}_0 + \vec{Z}_1 + \vec{Z}_2 & \vec{Z}_0 + \vec{a}\vec{Z}_1 + \vec{a}^2\vec{Z}_2 \\
\vec{Z}_0 + \vec{a}\vec{Z}_1 + \vec{a}^2\vec{Z}_2 & \vec{Z}_0 + \vec{a}^2\vec{Z}_1 + \vec{a}\vec{Z}_2 & \vec{Z}_0 + \vec{Z}_1 + \vec{Z}_2
\end{bmatrix}
$$

Where the transformation eigenvector $\vec{a} = e^{j2\pi/3}$ is used.

The generator could be modelled during the short-circuit using the classic Thévenin equivalent, that is, as an ideal
voltage source in series with the generator’s impedance, as shown in the electrical circuit of the following figure:

<div style="text-align: center;">
    <img src="https://github.com/SanPen/VeraGrid/blob/master/doc/md_source/figures/3ph_thevenin.png?raw=true"
    title="Thévenin equivalent circuit"
    width="50%"/>
</div>

However, this would require to add an additional bus to the original system between the generator’s impedance and the
ideal voltage source. Therefore, the generator can be also modelled using its Norton equivalent, that is, an ideal current source
in parallel with the generator’s impedance, as shown in the schematic bellow:

<div style="text-align: center;">
    <img src="https://github.com/SanPen/VeraGrid/blob/master/doc/md_source/figures/3ph_norton.png?raw=true"
    title="Norton equivalent circuit"
    width="35%"/>
</div>

The Norton current source will take the value of the internal voltage multiplied by its admittance:

$$
\vec{I}_{N} = \vec{Y}_{gen} \cdot \ \vec{E}
$$

#### Example

```python
import VeraGridEngine.api as gce

logger = gce.Logger()
grid = gce.MultiCircuit()

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus = gce.Bus(name='Bus', Vnom=4.16)
grid.add_bus(obj=bus)

# ----------------------------------------------------------------------------------------------------------------------
# Generator
# ----------------------------------------------------------------------------------------------------------------------
gen = gce.Generator(vset=1.0, r1=0.004, x1=0.5, r2=0.02, x2=0.5, r0=0.01, x0=0.08)
grid.add_generator(bus=bus, api_obj=gen)
```


## AC-DC modelling

Here we are going to explore the modelling of AC-DC power systems.

### HvdcLine: Modelling AC-DC links the easy way

The easy way of modelling HVDC links is by using the 2-generator model.
In VeraGrid this is represented by the `HvdcLine`device.

![hvcd_line_schematic.png](figures/hvcd_line_schematic.png)

This is a well known model in the literature, however you cannot represent a
proper DC grid with it, nor you can simulate contingencies on the DC elements 
or have more than one cable at a time.

![hvdcline.png](figures/hvdcline.png)

#### Controls available

The `HvdcLine` device has only 2 controls: Active power control (`Pset`) and AC line emulation (`free`)

| Control type | Effect                                                      |
|--------------|-------------------------------------------------------------|
| Pset         | Set active power                                            |
| free         | AC emulation:<br/>$P = P_0 + k \cdot (\theta_f - \theta_t)$ |

Let's see a python example using 4 buses:

```python
import VeraGridEngine as vg

# Grid instantiation
grid = vg.MultiCircuit()

# Define buses
bus1 = grid.add_bus(vg.Bus(name='B1', Vnom=135, is_slack=True))
bus2 = grid.add_bus(vg.Bus(name='B2', Vnom=135))
bus5 = grid.add_bus(vg.Bus(name='B5', Vnom=135))
bus6 = grid.add_bus(vg.Bus(name='B6', Vnom=135))

# Define AC lines
line12 = grid.add_line(vg.Line(name='L12', bus_from=bus1, bus_to=bus2, r=0.001, x=0.01))
line25 = grid.add_line(vg.Line(name='L25', bus_from=bus2, bus_to=bus5, r=0.05, x=0.05))
line56 = grid.add_line(vg.Line(name='L56', bus_from=bus5, bus_to=bus6, r=0.001, x=0.01))
line256 = grid.add_line(vg.Line(name='L562', bus_from=bus5, bus_to=bus6, r=0.001, x=0.01))

# Define Hvdc Line
line34 = grid.add_hvdc(vg.HvdcLine(name='L34', bus_from=bus2, bus_to=bus5, Pset=0.2))

# Define generators
grid.add_generator(bus=bus1, api_obj=vg.Generator(name='Gen1', P=1.0, vset=1.01))
grid.add_generator(bus=bus6, api_obj=vg.Generator(name='Gen2', P=1.0, vset=1.02))

# Define loads
grid.add_load(bus=bus2, api_obj=vg.Load(name='Load1', P=3.0, Q=0.3))
grid.add_load(bus=bus5, api_obj=vg.Load(name='Load2', P=2.0, Q=0.5))

# Run power flow
pf_options = vg.PowerFlowOptions(solver_type=vg.SolverType.PowellDogLeg,
                                 retry_with_other_methods=False)
pf_driver = vg.PowerFlowDriver(grid=grid, options=pf_options)
pf_driver.run()

print('Bus values')
print(pf_driver.results.get_bus_df())

print('Branch values')
print(pf_driver.results.get_branch_df())

print("error:", pf_driver.results.error)

vg.save_file(grid, "6bus_a.veragrid")
```

### Vsc: Modelling AC-DC links the better way

A better way of simulating AC-DC grids is what led us to research the literature
for formulations that were complete, correct and explicit. Founding none, we
started to create a formulation, by means of introducing how a converter device should behave. 

![vsc_converter.png](figures/vsc_converter.png)

It turns out that a converter cannot be a regular $\pi$-branch. 
It has to be a _decoupled_ branch represented by two injections.
More or less like the 2-generators model: 2 injections plus a coupling equation.

![acdc_grid.png](figures/acdc_grid.png)

By introducing this type of branch, we get the freedom to represent the 
AC and DC grids in any level of detail.


### Solvability rules

The power flow simulation is an optimization problem 
formed by equality constraints. Because of this: 

- For every AC island we must specify one voltage module $Vm$ and one voltage angle $\theta$. 
Usually, at the so called *slack bus*.

- For every DC island there must be a $Vm$ set point. 
This can be thought of as a DC slack.

- An AC branch has 4 unknowns ($Vm_f, Vm_t, \theta_f, \theta_t$) 
and 4 equations ($P_f, P_t, Q_f, Q_t$).

- A DC branch has 2 unknowns ($Vm_f, Vm_t$) and 2 equations 
($P_f, P_t$).

- A converter branch has 3 unknowns ($Vm_f, Vm_t, \theta_t$) 
and only 1 _natural_ equation, the losses equation.
That is why every converter must control two magnitudes to 
add the 2 extra equations needed. 


Since we must ensure equal number of unknowns and equations globally, 
there is a control compatibility theory.

### Controls available

Steaming from the solvability rules, we can introduce the converter controls.
For every converter we need to choose 2 controls to ensure solvability.

| Control type  | Effect                                             |
|---------------|----------------------------------------------------|
| $Vm_{dc}$     | Voltage module control at the DC side (from side)  |
| $Vm_{ac}$     | Voltage module control at the AC side (to side)    |
| $\theta_{ac}$ | Voltage angle control at the AC side (to side)     |
| $P_{ac}$      | Active power control at the AC side (to side)      |
| $Q_{ac}$      | Reactive power control at the AC side (to side)    |
| $P_{dc}$      | Active power control at the DC side (from side)    |


### Putting it all together

We wanted a no-compromise AC-DC power flow with good convergence properties.

![](figures/acdc_pf_formulation.png)

This method was introduced in [here](https://upcommons.upc.edu/server/api/core/bitstreams/c522ad67-438a-48c3-aa1b-a03859cd6659/content)
and further developed in VeraGrid from 2024 to 2025.

### 6-bus example

```python
import VeraGridEngine as vg

# Grid instantiation
grid = vg.MultiCircuit()

# Define buses
bus1 = grid.add_bus(vg.Bus(name='B1', Vnom=135, is_slack=True))
bus2 = grid.add_bus(vg.Bus(name='B2', Vnom=135))
bus3 = grid.add_bus(vg.Bus(name='B3', Vnom=100, is_dc=True))
bus4 = grid.add_bus(vg.Bus(name='B4', Vnom=100, is_dc=True))
bus5 = grid.add_bus(vg.Bus(name='B5', Vnom=135))
bus6 = grid.add_bus(vg.Bus(name='B6', Vnom=135))

# Define AC lines
line12 = grid.add_line(vg.Line(name='L12', bus_from=bus1, bus_to=bus2, r=0.001, x=0.1))
line25 = grid.add_line(vg.Line(name='L25', bus_from=bus2, bus_to=bus5, r=1.05, x=0.5))
line56 = grid.add_line(vg.Line(name='L56', bus_from=bus5, bus_to=bus6, r=0.001, x=0.1))
line256 = grid.add_line(vg.Line(name='L562', bus_from=bus5, bus_to=bus6, r=0.001, x=0.1))

# Define DC lines
line34 = grid.add_dc_line(vg.DcLine(name='L34', bus_from=bus3, bus_to=bus4, r=2.05))

# Define VSCs
vsc1 = grid.add_vsc(vg.VSC(name='VSC1', bus_from=bus3, bus_to=bus2, 
                           rate=100, alpha1=0.001, alpha2=0.015, alpha3=0.01,
                           control1=vg.ConverterControlType.Vm_ac, 
                           control2=vg.ConverterControlType.Pdc,
                           control1_val=1.0333, 
                           control2_val=0.2))

vsc2 = grid.add_vsc(vg.VSC(name='VSC2', bus_from=bus4, bus_to=bus5, 
                           rate=100, alpha1=0.001, alpha2=0.015, alpha3=0.01,
                           control1=vg.ConverterControlType.Vm_dc, 
                           control2=vg.ConverterControlType.Qac,
                           control1_val=1.05, 
                           control2_val=-7.21))

# Define generators
grid.add_generator(bus=bus1, api_obj=vg.Generator(name='Gen1', P=1.0, vset=1.01))
grid.add_generator(bus=bus6, api_obj=vg.Generator(name='Gen2', P=1.0, vset=1.02))

# Define loads
grid.add_load(bus=bus2, api_obj=vg.Load(name='Load1', P=3.0, Q=0.3))
grid.add_load(bus=bus5, api_obj=vg.Load(name='Load2', P=2.0, Q=0.5))

# Run power flow
pf_options = vg.PowerFlowOptions(solver_type=vg.SolverType.PowellDogLeg,
                                 retry_with_other_methods=False)
pf_driver = vg.PowerFlowDriver(grid=grid, options=pf_options)
pf_driver.run()

print('Bus values')
print(pf_driver.results.get_bus_df())
print(pf_driver.results.get_bus_df().to_markdown(tablefmt="grid"))

print('Branch values')
print(pf_driver.results.get_branch_df())
print(pf_driver.results.get_branch_df().to_markdown(tablefmt="grid"))

print("error:", pf_driver.results.error)

vg.save_file(grid, "6bus.veragrid")
```


|    |      Vm |        Va |         P |              Q |
|----|---------|-----------|-----------|----------------|
| B1 | 1.01    |  0        | 15.5919   | -236.815       |
| B2 | 1.0333  | -0.215613 | -3        |   -0.299984    |
| B3 | 1.04608 |  0        | -0.197999 |   -9.75607e-22 |
| B4 | 1.05    |  0        |  0.198741 |    9.79262e-22 |
| B5 | 1.02144 |  0.362496 | -2        |   -0.499983    |
| B6 | 1.02    |  0.373325 |  1        |  -29.3828      |


|      |        Pf |             Qf |         Pt |            Qt |   loading |       Ploss |       Qloss |
|------|-----------|----------------|------------|---------------|-----------|-------------|-------------|
| L12  | 15.5919   | -236.815       | -15.0397   | 242.337       | 1559.19   | 0.552148    | 5.52148     |
| L25  |  1.66417  |   22.9626      |  -1.41595  | -22.7143      |  166.417  | 0.248218    | 0.248218    |
| L56  | -0.497924 |   14.7122      |   0.500001 | -14.6914      |  -49.7924 | 0.00207697  | 0.0207697   |
| L562 | -0.497924 |   14.7122      |   0.500001 | -14.6914      |  -49.7924 | 0.00207697  | 0.0207697   |
| L34  | -0.199999 |   -9.75607e-22 |   0.200749 |   9.79262e-22 |  -19.9999 | 0.000749344 | 3.65533e-24 |


## Distribution Grid Example in the Sequence Reference Frame

This tutorial shows a step by step guide on how to build distribution grid 
system that contains: 13 Buses, 4 Transformers, 4 Loads. 
The tutorial shows how to create a grid using time profiles and device templates. 
The tutorial also contains:

- Easy drag and drop creation of components.
- Transformer type creation.
- Overhead lines creation.
- Templates for transformers and overhead lines.
- Import of profiles into the loads.
- Set s power flow snapshot from the profiles.
- Execution of power flow.
- Execution of power flow time series.
- Automatic precision adjustment.
- Results visualization.
- Live results visualization (grid colouring).

A video tutorial can be found [here](https://www.youtube.com/watch?v=Yx3zRYRbe04&t=404s)

Note: this tutorial was made with VeraGrid v 4.0.0

However, we will do this using the VeraGrid GUI.

### Step 0: System Overview

The system grid is supposed to look like the figure below.

![](figures/tutorials/dg/overview.png)

The system features:

- 9 Buses.
- 5 Transformers.
- 4 Loads.
- 7 Lines.

Solution file of the grid system can be found in 
[GitHub](https://github.com/SanPen/VeraGrid/blob/devel/Grids_and_profiles/grids/Some%20distribution%20grid%20(Video).veragrid)



### Step 1: Create a Transformer

Open VeraGrid:

1. 'Drag and drop' 2 'Bus' element to the diagram canvas:

![](figures/tutorials/dg/busaddition.png)

2. Select (double 'click') Bus 0 and change the parameters (on the left side pane):


| name     | HV Bus |
|----------|--------|
| Vnom[kV] |   20   |


3. Select (double 'click') Bus 1 and change the parameters (on the left side pane):

|   name   | Bus 2  |
|----------|--------|
| Vnom[kV] | 10     |

4. Hover over either bus element, 'click and drag' (when there is a cross) to the other bus to create a branch.

![](figures/tutorials/dg/transformer.png)

> Note: A transformer will be created between HV Bus and Bus 2 when nominal voltage values are different.

> Note: The name of an element may not change until you 'double click' the element on the diagram canvas after the change.

### Step 2: Create Lines of Different Lengths

1. Create 3 more Buses (Bus 3, Bus 4 and Bus 5) and create a branch between them.

![](figures/tutorials/dg/threebusaddition.png)


2. Select the branch between Bus 2 and Bus 3 and change its parameters to:


|   name     | Line 1 |
|------------|--------|
| length[km] | 5      |

3. Select the branch between Bus 3 and Bus 4 and change its parameters to:


|   name     | Line 2 |
|------------|--------|
| length[km] | 3      |


4. Select the branch between Bus 4 and Bus 5 and change its parameters to:

|   name     | Line 3 |
|------------|--------|
| length[km] | 7      |


> Note: Element placing can be changed by 'clicking' the square on the right hand side of a bus.

### Step 3: Add More Lines and Buses

1. Add Bus 6 to the right of Bus 2.
2. Add Bus 7 to the right of Bus 3.
3. Add Bus 8 and Bus 10 to the left of Bus 4.
4. Add Bus 9 and Bus 11 to the left of Bus 5.

![](figures/tutorials/dg/morebuses.png)

5. Select the branch between Bus 2 and Bus 6 and change its parameters to:

|   name     | Line 4 |
|------------|--------|
| length[km] | 2      |

5. Select the branch between Bus 3 and Bus 7 and change its parameters to:


|   name     | Line 5 |
|------------|--------|
| length[km] | 1.6    |

6. Select the branch between Bus 4 and Bus 8 and change its parameters to:


|   name     | Line 7 |
|------------|--------|
| length[km] | 1.5    |


7. Select the branch between Bus 5 and Bus 9 and change its parameters to:


|   name     | Line 8 |
|------------|--------|
| length[km] | 2      |

![](figures/tutorials/dg/morebuseslines.png)


### Step 4: Create Loads

1. Select Bus 10 and change parameters to:


|   name   | House 3  |
|----------|----------|
| Vnom[kV] | 0.4      |

2. Create a line between Bus 8 and House 3 (a transformer will be created). Rename it to 'TR House 3'.

3. Select Bus 11 and change parameters to:

|   name   | House 4  |
|----------|----------|
| Vnom[kV] | 0.4      |

4. Create a line between Bus 9 and House 4 (a transformer will be created). Rename it to 'TR House 4'.

5. Right 'click' on House 3 and select 'Add Load'.

6. Right 'click' on House 4 and select 'Add Load'.

![](figures/tutorials/dg/loads.png)


### Step 5: Create House 1 and House 2

1. Create load House 1: Create a new bus and name it 'House 1' to the right of Bus 6, and a transformer in the line between Bus 6 and House 1. The parameters are the following:

| name     | House 1  |
|----------|----------|
| Vnom[kV] |   0.4    |

2. Create load House 2: Create a new bus and name it 'House 2' to the right of Bus 7, and a transformer in the line between Bus 7 and House 2. The parameters are the following:

| name     | House 2  |
|----------|----------|
| Vnom[kV] |   0.4    |

The full system topology looks like:

![](figures/tutorials/dg/fourhouses.png)


> Note: do not forget to add the load after you rename the House buses.

### Step 6: Defining the Main Transformer

In order to define the type of transformer a catalogue is available within the VeraGrid repository.

This transformer is the transformer between HV Bus and Bus 2. The transformer is: 25 MV 20/10 kV.

1. Access the catalogue (Excel file). It can be found in the repository at `VeraGrid/Grids_and_profiles/grids/equipment` and select 'equipment.ods'.

2. Select the 'Transformers' sheet.

3. Remove all filters on the 'Rate (MVA)' column by pressing on the downward arrow.

![](figures/tutorials/dg/downtriangle.png)


4. Select the '20 kV' filter on the 'HV (kV)' column using the downward arrow.

4. Select the '10 kV' filter on the 'LV (kV)' column using the downward arrow.


6. The parameters of the transformer are:

| name               | 25 MVA 20/10 kV |
|--------------------|-----------------|
| Rate[MVA]          | 25              |
| Frequency[Hz]      | 50              |
| HV[kV]             | 20              |
| LV[kV]             | 10              |
| Copper Losses[kW]  | 102.76          |
| No Load Losses[kW] | 10.96           |
| No Load Current[%] | 0.1             |
| V Short Circuit[%] | 10.3            |
| HV Vector Group    | YN              |
| LV Vector Group    | D               |
| Phase Shift        | 5               |

7. Double click on the transformer between HV Bus and Bus 2 and enter the 
following parameters (based on the model selected):

|   Sn   | 25     |
|--------|--------|
|  Pcu   | 102.76 |
|   Pfe  | 10.96  |
|   lo   | 0.1    |
|    Vsc | 10.3   |

8. Once the parameters are placed, right click and select 'Add to catalogue'. 
This way the branch p.u. values are calculated from the template values.

> Note: In the new VeraGrid version, a transformer can be defined by just 
  right clicking on the desired transformer and selecting the type from the drop down menu.

> Note: All of the element types can be found under the 'Types catalogue' 
> tab after clicking on the desired element, then clock 'Load Values' to change the parameters.

### Step 7: Defining Load Transformers

The transformers used for the 4 loads (houses) a 10 to 0.4 kV transformer will be used. 
The name is a '0.016 MVA 10/0.4 kV ET 16/23 SGB'.

1. Using the same catalogue find the transformer and do this for the transformer between Bus 6 and House 1.

2. The parameters of the transformer are:

|        name        | 0.016 MVA 10/0.4 kV ET 16/23 SGB  |
|--------------------|-----------------------------------|
|     Rate[MVA]      | 0.016                             |
|   Frequency[Hz]    | 50                                |
|       HV[kV]       | 10                                |
|       LV[kV]       | 0.4                               |
|  Copper Losses[kW] | 0.45                              |
| No Load Losses[kW] | 0.11                              |
| No Load Current[%] | 0.68751                           |
| V Short Circuit[%] | 3.75                              |
| HV Vector Group    | Y                                 |
|   LV Vector Group  | ZN                                |
|   Phase Shift      | 5                                 |

3. Fill these values out for the pop up menu:

|   Sn   | 0.016    |
|--------|----------|
|  Pcu   | 0.45     |
|   Pfe  | 0.11     |
|   lo   | 0.687510 |
|    Vsc | 3.75     |

4. Right click on the transformer and select 'Add to catalogue' this will create a template for quick add.

5. Rename the transformer to 'TR house 1'.

6. On the lower tabs select 'Types catalogue'.

![](figures/tutorials/dg/typescatalogue.png)


7. Select the transformer that has the characteristics of the 10 to 0.4 kV transformer and 
rename it to 'House trafo'. Now you have defined a transformer type that can be added to many transformers.

> Note: In the new VeraGrid version, a transformer can be defined by just right clicking on 
  the desired transformer and selecting the type from the drop down menu.

### Step 8: Defining Other Transformers

Now that 'House trafo' has been created, other transformers can be set to the same type.

1. In the 'Schematic' tab change the name of the other load transformers to their respective load (i.e. House 3 transformer rename to 'TR house 3').

2. Double click on the transformer

3. Click 'Load Values' to set the parameters.

4. Repeat for all desired transformers: TR house 3, TR house 4, TR house 2.

> Note: this can be done with all elements either to preloaded models or models you create.


### Step 9: Defining Wires and Overhead Lines

1. Just like in Step 7 access the 'Types catalouge' and select 'Wires'.

2. All of the wire types will show up and select the 17th option 'AWG SLD'. The parameters are:


|  R [Oh/Km]        | 1.485077  |
|-------------------|-----------|
|   X [Ohm/Km]      | 0         |
|    GMR [m]        | 0.001603  |
|  Max Current [kA] | 0.11      |

> Note: A new wire or custom wire can be added using the '+' button on the top right.

3. Now that you have located the wire you will use, in the same tab of 'Data structures' select 'Overhead Lines'.

4. Click on the '+' sign at the top right to create a new element. A new element '0:Tower' should come up.

5. Select the element '0: Tower' and click on the pencil on the top right corner to edit. A new window should pop up.

6. Rename the overhead line to: 'Distribution Line'.

7. Select the wire 'AWG SLD', highlight it and click on the '+' sign on the 'Wire composition' section below:

![](figures/tutorials/dg/awgsld.png)



8. Add the 'AWG SLD' wire three times to enter the wire arrangement. The formulas come from ATP-EMTP.

9. Give each cable a different phase: 1, 2 and 3. Enter the following parameters for Phase 2 and Phase 3.

| Wire      | X[m] | Y [m] | Phase |
|-----------|------|-------|-------|
|  AWG SLD  |  0   |  7.0  | 1     |
|  AWG SLD  |0.4   |  7.3  | 2     |
|  AWG SLD  |0.8   |  7.0  | 3     |

![](figures/tutorials/dg/threeawgsld.png)


10. Click on the 'Compute matrices' button the little calculator on the bottom right and you will be able to see:

-Tower Wire Position (right).
- Z Series [Ohm/Km] for ABCN (under the 'Z series' tab at the top).
- Z Series [Ohm/Km] for ABC (under the 'Z series' tab at the top).
- Z Series [Ohm/Km] for the sequence components (under the 'Z series' tab at the top).
- Y shunt [uS/Km] for ABCN (under the 'Y shunt' tab at the top).
- Y shunt [uS/Km] for ABC (under the 'Y shunt' tab at the top).
- Y shunt [uS/Km] for the sequence components (under the 'Y shunt' tab at the top).

12. Close the window, and your 'Elements Data' tab should look lie:

13. To apply this model to the lines in the model: In the 'Schematic' tab change the name of the other load transformers to their respective load (i.e. House 3 transformer rename to 'TR house 3').

14. Double click on the desired line. Click 'Load Values' to set the parameters.

15. Repeat for all desired lines. In this case Line 1 to Line 8. The 'Objecs -> Line' Data tab should look like:

![](figures/tutorials/dg/threeawgsld.png)

> Note: this can be done with all elements either to preloaded models or models you create.

### Step 10: Importing Load Profiles

1. Head to the 'Time Events' tab on the bottom part of the GUI. Then click on the left and select 'Import Profiles'. This should bring up the 'Profile Import Dialogue' box.

![](figures/tutorials/dg/importprofiles.png)

> Note: Make sure that the desired object is set to 'Load' and power types are both set to 'P'.

2. Click on 'Import file' box on the left. This will bring up a file explorer tab.

3. In the installation location head to '../VeraGrid/Grids_and_Profiles/profiles/..' then select the Excel file called: 'Total_profiles_1W_1H.xlsx'.

![](figures/tutorials/dg/filelocation.png)


4. On the next dialogue box select 'Sheet 1' and 'OK'. Wait for all the profiles to load.

5. Any load profile can be selected. For example, click on 'USA_AL_Dothan.Muni.AP.7222268_TMY3_BASE(kW)'. Then select the 'Plot' tab to see the load profile in kW for January 2018.

![](figures/tutorials/dg/loadprofilechart.png)

> Note: in the 'Assignation' tab, the units can be changed to: T, G, k , m Watts.

Set the units to 'k'.

6. On the right, you can see the different 'Objectives', fill the out by double-clicking on a profile and then double-clicking in the 'active' box of the desired 'Objective'. The profiles are assigned as follows:
    - Load@House 1: 'USA_AL_Muscle.Shoals.Rgni.AP.723235_TMY3_BASE(k@)'.
    - Load@House 2: 'USA_AZ_Douglas-Bisbee.Douglas.intl.AP.722735_TMY3_BASE(k@)'.
    - Load@House 3: 'USA_AL_Tuscaloosa.Muni.AP.722286_TMY3_BASE(k@)'.
    - Load@House 4: 'USA_AL_Birmingham.Muni.AP.722286_TMY3_BASE(k@)'.

The selection should look like this:

![](figures/tutorials/dg/profileselection.png)

Click 'Accept' to load the profiles.

7. On the 'Time events' tab, confirm that the time series has bene added:

![](figures/tutorials/dg/timeevents.png)

8. To set the reactive power as a copy of the active power and scale it, click on the dropdown menu and select 'Q'. Then click next to it on the 'Copy the selected profile into the profiles selected next to this button' button. When the pop up box comes on confirming the action select 'Yes'.

![](figures/tutorials/dg/scaling.png)

![](figures/tutorials/dg/pprofile.png)


9. On the bottom left side scale it by 0.8 and click on the multiply button. The profile should look like this:

![](figures/tutorials/dg/qprofile.png)


9. The profiles can be visualized by 1) selecting the times, and load, and clicking on the 'Plot the selected project's profile' button.

![](figures/tutorials/dg/profilegraph.png)


10. Power flow snapshots can be seen also by going to the 'Time events' tabs, and then

![](figures/tutorials/dg/snapshotpf.png)


### Step 10: Set Power Flow From A Profile

Once we have checked that the profiles are okay, we can set the power flow snapshot from the profiles and run a power flow.

1. Head to the 'Time Series' Tab and select '2018+01-03T12:00:00.00000000000000'.

![](figures/tutorials/dg/timeselection.png)


2. Select the 'Assign selected values to the selected time slot to the grid'.

3. Select 'Yes'.


### Step 11: Running a Power Flow

In order to run the power flow, we must select the slack bus. If you try run without one, you will get this error message:

![](figures/tutorials/dg/noslackbus.png)


> Note: to run a Power Flow, select the 'Power Flow' button in the red square in the figure above.

1. Return to the 'Schematic' tab.

2. Select the 'HV Bus'.

3. On the left pane, select 'True' in the 'is_slack' option.

![](figures/tutorials/dg/isslack.png)


4. Click on the 'Power Flow' button and the grid will be colored according to the voltage or loading.

![](figures/tutorials/dg/runpf.png)


5. Click on the 'Power Flow Time Series' button and the grid will be colored according to th

![](figures/tutorials/dg/runpftimeseries.png)


6. In addition by hovering above a transformer you can see the loading percentage and the power.

![](figures/tutorials/dg/transformerpower.png)


### Step 12: Results & Features

Here are some of the few results and features that are available with VeraGrid. All results can be found in the 'Results' tab. Here you can see a list of all studies perfomed and their respective results:

![](figures/tutorials/dg/results.png)


In the results you can also choose from:

- Study
- Result Type
- Devices

From here you can choose and customize the plot and results that are displayed to you.

![](figures/tutorials/dg/resultsorting.png)


Select the Study, Result Type and Devices, then the Data will pop up in table format, 
to graph it use the 'Graph' button on the top right. The graph will come up on a new figure:

![](figures/tutorials/dg/resultselection.png)

In the 'Schematic' Tab, you can visualize the result's profiles, by selection the load, right click and selecting 'Plot Profiles':

![](figures/tutorials/dg/plotprofiles.png)

From the result plots you can do various things with the plot:

![](figures/tutorials/dg/plotoptions.png)

## Power Flow on the 5-Node Example Grid

This example creates the five-node grid from the fantastic book
"Power System Load Flow Analysis" and runs a power flow. After the power flow is executed,
the results are printed on the console.

```python
import VeraGridEngine.api as gce

# declare a circuit object
grid = gce.MultiCircuit()

# Add the buses and the generators and loads attached
bus1 = gce.Bus('Bus 1', Vnom=20)
# bus1.is_slack = True  # we may mark the bus a slack
grid.add_bus(bus1)

# add a generator to the bus 1
gen1 = gce.Generator('Slack Generator', vset=1.0)
grid.add_generator(bus1, gen1)

# add bus 2 with a load attached
bus2 = gce.Bus('Bus 2', Vnom=20)
grid.add_bus(bus2)
grid.add_load(bus2, gce.Load('load 2', P=40, Q=20))

# add bus 3 with a load attached
bus3 = gce.Bus('Bus 3', Vnom=20)
grid.add_bus(bus3)
grid.add_load(bus3, gce.Load('load 3', P=25, Q=15))

# add bus 4 with a load attached
bus4 = gce.Bus('Bus 4', Vnom=20)
grid.add_bus(bus4)
grid.add_load(bus4, gce.Load('load 4', P=40, Q=20))

# add bus 5 with a load attached
bus5 = gce.Bus('Bus 5', Vnom=20)
grid.add_bus(bus5)
grid.add_load(bus5, gce.Load('load 5', P=50, Q=20))

# add Lines connecting the buses
grid.add_line(gce.Line(bus1, bus2, name='line 1-2', r=0.05, x=0.11, b=0.02))
grid.add_line(gce.Line(bus1, bus3, name='line 1-3', r=0.05, x=0.11, b=0.02))
grid.add_line(gce.Line(bus1, bus5, name='line 1-5', r=0.03, x=0.08, b=0.02))
grid.add_line(gce.Line(bus2, bus3, name='line 2-3', r=0.04, x=0.09, b=0.02))
grid.add_line(gce.Line(bus2, bus5, name='line 2-5', r=0.04, x=0.09, b=0.02))
grid.add_line(gce.Line(bus3, bus4, name='line 3-4', r=0.06, x=0.13, b=0.03))
grid.add_line(gce.Line(bus4, bus5, name='line 4-5', r=0.04, x=0.09, b=0.02))

results = gce.power_flow(grid)

print(grid.name)
print('Converged:', results.converged, 'error:', results.error)
print(results.get_bus_df())
print(results.get_branch_df())
```


## Substations modelling

To be done.
