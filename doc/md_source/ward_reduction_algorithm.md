# Ward-Based Network Reduction with Integral Generator Relocation
*Detailed algorithm, data flow, and mapping to the MATLAB implementation (MATPOWER format)*

Author: eRoots Analytics — Technical Note  
Date: 2025-08-18

---

## 0) Purpose and Big Picture

We want a reduced network that preserves how the **internal/boundary** area "sees" the external grid, while keeping generators **intact** (no fractional splitting). The process uses **two Ward reductions on the original full system** with different retained sets, plus a **generator relocation** step driven by **electrical proximity**.

Key idea:
- Run Ward reduction once to build the **structural reduced grid** over the **boundary buses** only.
- Run Ward reduction again with **generators retained** as well to build a **reduced generator model** used only to decide where each generator should be moved.
- Move each external generator **integrally** to the **closest boundary bus** by electrical distance.
- Assemble the final equivalent by placing generators on top of the structural reduced grid.

This approach avoids fractional generator allocation (classical Ward) and yields a compact, interpretable equivalent.

---

## 1) Notation and Data Structures (MATPOWER)

- **Full system** (G0) with:
  - `mpc.bus`: [nbus × …] bus table
  - `mpc.branch`: [nbranch × …] branch table with series r, x and status
  - `mpc.gen`: [ngen × …] generator table
  - Optional: `mpc.dcline`
- **Retained sets**:
  - B: chosen **boundary buses** (study-area interface)
  - G: **generator buses** in the full model
- **BCIRC**: branch "circuit numbers" to identify originals, parallels, and **equivalent** lines after reduction.
- **Shunts**: converted to **PQ loads** before elimination (Ward assumptions).

Sparse matrix storage used by the implementation:
- `ERP`: End-of-row pointers of sparse Y
- `CIndx`: Column indices of sparse Y values
- `ERPU`, `CIndxU`: symbolic U-structure pointers (right-of-diagonal entries)
- `ERPEQ`, `CIndxEQ`: pointers indexing **equivalent lines** between boundary buses produced by elimination

---

## 2) Mathematical Basis (Ward / Schur Complement)

Partition the bus admittance matrix by **retained** (i) and **eliminated** (e) nodes:
$$
Y = \begin{bmatrix} Y_{ii} & Y_{ie} \\ Y_{ei} & Y_{ee} \end{bmatrix},\quad
\begin{bmatrix} I_i \\ I_e \end{bmatrix} = 
\begin{bmatrix} Y_{ii} & Y_{ie} \\ Y_{ei} & Y_{ee} \end{bmatrix}
\begin{bmatrix} V_i \\ V_e \end{bmatrix}.
$$

Eliminating e (assuming $I_e=0$ for WA, or retaining injections for WI) yields:
$$
Y^{\text{eq}}_{ii} = Y_{ii} - Y_{ie} Y_{ee}^{-1} Y_{ei},
$$
with additional **equivalent shunts** and **equivalent branches** coupling retained buses. In practice, we implement this by **partial LU factorisation** of $Y$ with careful ordering to control fill-ins.

---

## 3) Data Flow and Grid Versions

We will keep track of **which grid is being transformed** at each stage.

- G0: **Original full network** (input)
- G1: **Boundary Reduced Model** (Ward on B only) — used as the **structural base** of the final equivalent
- G2: **Reduced Generator Model** (Ward on B ∪ G) — used **only** to decide generator relocation
- G★: **Final Equivalent** = G1 + generators placed according to relocation map computed from G2

Important: **Both Ward reductions are run on G0** with different retained sets. They are not sequential modifications of the same intermediate grid.

---

## 4) End-to-End Algorithm (with inputs/outputs per step)

### Step 0 — Preprocess the full model (acts on G0)

**Input:** G0, external-bus list E to be eliminated  
**Actions:**
1. Remove isolated buses and their incident elements.
2. Remove out-of-service branches and any branches incident to isolated buses.
3. Remove generators at isolated buses. Remove HVDC lines tied to isolated buses.
4. Update the external-bus list E to exclude previously isolated buses.  
**Output:** Cleaned full model G0' and updated E.

---

### Step 1 — Build sparse Y and pivoting info (acts on G0')

**Input:** G0', E, boundary set B  
**Actions:**
1. Assemble compact-storage Y: arrays `ERP`, `CIndx`, `DataB`.
2. Compute permutation so that rows/cols for **external buses** go first, followed by **boundary**, then **others**.  
   - Apply **Tinney 1 ordering** within the external block to reduce fill-ins in LU.
3. Pivot the data into this order to prepare for partial factorisation.  
**Output:** Pivoted sparse Y structure and pointers; permutation maps.

---

### Step 2 — Partial **symbolic** LU (acts on G0' structure)

**Input:** `ERP`, `CIndx`, stop index = |E|, boundary list B  
**Actions:**
1. Traverse rows 1..|E| (the external block) symbolically to determine the **U-pattern** on the right of the diagonal for each eliminated row: `ERPU`, `CIndxU`.
2. Identify the **fill-ins** that will appear in the rows/cols of boundary buses due to eliminating externals. These fill-ins correspond to **equivalent lines** connecting boundary buses. Store their indices via `ERPEQ`, `CIndxEQ`.  
**Output:** `ERPU`, `CIndxU`, `ERPEQ`, `CIndxEQ` = symbolic scaffolding for numerical elimination and equivalent line extraction.

---

### Step 3 — Partial **numerical** LU (acts on G0' numerics)

**Input:** Pivoted `DataB`, `ERP`, `CIndx`; symbolic `ERPU`, `CIndxU`, `ERPEQ`, `CIndxEQ`; stop index = |E|; boundary list.  
**Actions:**
1. Sweep rows 1..|E|. For each eliminated external row do the usual LU updates of its active pattern, using the already-built symbolic structure.
2. **Accumulate** values on the boundary rows generated by the elimination. Two arrays are produced:
   - `DataEQ`: numerical values for the **equivalent branch reactances/susceptances** between boundary buses (at indices `CIndxEQ` across `ERPEQ` blocks).
   - `DataShunt`: the **equivalent shunts** added to each boundary bus due to elimination of externals.
3. The diagonal inverses for eliminated rows are also formed as part of the LU process.  
**Output:** Numeric equivalents: `DataEQ` (equiv. lines) and `DataShunt` (equiv. shunts) for boundary buses.

---

### Step 4 — First Ward reduction to build G1 (acts on G0' with retained B)

**Input:** Clean full model G0', retained set B  
**Actions:**
1. Convert all explicit shunts to **PQ loads** (so that shunt effects are captured as injections).
2. Eliminate all **external** buses (those not in B) using the partial LU results:
   - Insert **equivalent lines** between boundary buses using `DataEQ`.
   - Add **equivalent shunts** at boundary buses using `DataShunt`.
3. Optionally prune **unrealistic equivalent lines** with very large impedance. Thresholds are heuristic, e.g. |x| > 5 p.u., or |x| ≥ 10 × max(|x| of originals).  
**Output:** G1 = **Boundary Reduced Model**.  
- Buses: only B  
- Lines: originals among B plus equivalent lines  
- Loads: original loads on B plus equivalent PQ from eliminated externals  
- Generators: not preserved here (will be placed later)

**Role:** G1 will be the **structural base** of the final equivalent.

---

### Step 5 — Second Ward reduction to build G2 (acts on G0' with retained B ∪ G)

**Input:** Clean full model G0'; retained set B ∪ G  
**Actions:**
1. Convert shunts to PQ loads.
2. Eliminate all buses **not** in B ∪ G.
3. Keep all **generator buses** and boundary buses. The network now contains **paths** (original or equivalent) from each generator bus to at least one boundary bus.  
**Output:** G2 = **Reduced Generator Model**.  
- Buses: B ∪ G  
- Lines: originals + equivalents connecting generators to boundaries  
- Loads: equivalent PQ seen by these buses  
- Generators: still at their (retained) original buses

**Role:** G2 is used **only to compute generator relocation** targets.

---

### Step 6 — Generator relocation map from G2

**Input:** G2; set B; option `acflag`  
**Actions (per generator bus g):**
1. Build a **topology with consolidated parallels**: merge parallel lines into one using parallel impedance combination $z_{eq} = (z_1^{-1} + z_2^{-1} + \cdots)^{-1}$.
2. Define edge weights as **|impedance|** of each line. If `acflag=0`, set r=0 and use only x. If `acflag=1`, use $|z| = \sqrt{r^2 + x^2}$.
3. Compute **shortest electrical distance** from g to any $b \in B$ over the graph. The implementation uses a level-by-level relaxation that is equivalent to a Dijkstra-like update on |z| path sums.
4. Assign the generator **integrally** to the **closest boundary bus** $b^*(g)$ that minimises total path |z|.

**Output:** **Relocation map** Link(g) = $b^*(g)$ for all generators. Also record any **islanded** cases where no path to a boundary exists.

**Note on "reverse power flow" intuition:** This distance measure can be viewed as tracing "how easily" injected power at g would reach the boundary. It is a diagnostic; no actual power flow is solved here.

---

### Step 7 — Assemble the final equivalent G★

**Input:** G1 (structural base) and **relocation map** from Step 6  
**Actions:**
1. Copy G1 as the base of G★.
2. For each generator, **move** it from its original external bus to the assigned boundary bus $b^*(g)$. No splitting.
3. Optionally perform **load redistribution / inverse power-flow** fitting so that net injections on the reduced grid reproduce the operating point more faithfully (DC option available).  
4. Apply **post-processing**:
   - Remove very high-impedance equivalent lines if still present.
   - Renumber buses/branches/generators for compactness.
   - Update `BCIRC` to tag parallels and equivalents.

**Output:** G★ — the **Final Ward-based Equivalent** ready for PF/OPF on the retained region.

---

## 5) Detailed Mapping to MATLAB Functions (toolbox logic)

- **PreProcessData:** removes isolated/out-of-service elements; updates external list; clears gens on isolated buses; cleans DC lines attached to isolated buses.
- **Initiation / BuildYMat:** assemble Y in compact storage (`ERP`, `CIndx`, `DataB`), track branch circuits `BCIRC`, bus maps `newbusnum`/`oldbusnum`, self shunts.
- **PivotData / TinneyOne:** place external block first, then boundary, then others; apply Tinney 1 to reduce fill.
- **PartialSymLU:** symbolic pass to build `ERPU`, `CIndxU` and to identify **equivalent-line positions** between boundary buses via `ERPEQ`, `CIndxEQ`.
- **PartialNumLU:** numerical pass producing `DataEQ` and `DataShunt` that quantitatively define the equivalent lines and shunts.
- **DoReduction:** wraps the above to generate a reduced MATPOWER case for a given retained set.
  - Called twice to create G1 and G2 from the same full model but different retained sets.
- **MoveExGen:** builds the **relocation map** using impedance-based shortest paths on G2. Merges parallels, allows ignoring/including r via `acflag`, detects islanding, and outputs `Link` and the new generator bus vector.
- **LoadRedistribution:** optional inverse PF step to better match the original injections after movement.
- **Final pruning:** delete extreme-|x| equivalents (heuristic threshold), print summary, and return the reduced case, generator mapping, and `BCIRC` tags.

---

## 6) Pseudocode

```python
def ward_equiv_with_integral_gen_move(mpc_full, boundary_buses, pf_flag=0, acflag=0):
    # Step 0
    mpc0, E = preprocess(mpc_full, E_guess_from_user_or_boundary)
    
    # Step 1–3 scaffolding to support DoReduction
    scaffolding = build_sparse_and_symbolic(mpc0, E, boundary_buses)
    
    # Step 4: First Ward (boundary only) -> G1
    G1 = do_reduction(mpc0, retain=boundary_buses, scaffolding=scaffolding)
    prune_large_equivalents(G1)
    
    # Step 5: Second Ward (boundary + all generator buses) -> G2
    gen_buses = set(mpc0.gen[:, 0])
    retain2 = boundary_buses.union(gen_buses)
    G2 = do_reduction(mpc0, retain=retain2, scaffolding=scaffolding)
    
    # Step 6: Generator relocation on G2
    link_map = relocate_generators(G2, boundary_buses, acflag)
    
    # Step 7: Assemble final equivalent G*
    Gstar = place_gens_on_boundary(G1, link_map)
    if pf_flag:
        Gstar = inverse_power_flow_redistribution(mpc0, Gstar)
    final_prune_and_renumber(Gstar)
    return Gstar, link_map
```

---

## 7) Practical Notes and Edge Cases

- **Thresholds for pruning equivalents** are heuristics. Two common rules:
  - Remove lines with |x| > 5 p.u.
  - Remove lines with |x| exceeding 10 × the maximum original |x|.
- **HVDC terminals** must not be eliminated (error out if a DC terminal is in the external set).
- **Parallel lines** must be merged before distance calculations for relocation:
  $$
  z_{\text{eq}} = \left(\sum_k 1/z_k\right)^{-1}.
  $$
- **Islanded generators** in G2 get flagged. They cannot be mapped to any boundary bus.
- **DC vs AC distance** for relocation:
  - `acflag=0`: use reactance x only (DC-style)
  - `acflag=1`: use |z| with r included
- **Accuracy knobs**:
  - Choosing a slightly **wider boundary** reduces equivalent sensitivity and improves PF matching.
  - Optional inverse PF improves nodal injections after generator movement.

---

## 8) Validation Checklist

1. PF on G★ converges with reasonable mismatch.
2. Voltages at boundary buses close to those of the full network.
3. Branch flows at and near the boundary within acceptable error bands.
4. N−1 tests on the retained region do not show pathological divergence that was absent in the full model.
5. Generator relocation map contains no islanded surprises; totals match.

---

## 9) References and Further Reading

- Ward equivalencing by Schur complement; WA/WI/WX variants; reduced admittance:
  - $Y_{ii}^{\text{eq}} = Y_{ii} - Y_{ie} Y_{ee}^{-1} Y_{ei}$.
- Implementation concepts used here:
  - Partial symbolic and numerical LU to harvest equivalent branches and shunts;
  - Tinney 1 ordering for fill-control;
  - Equivalent-line pruning heuristics;
  - Integral generator relocation via impedance-based shortest paths.

These notes synthesise the documented method and the MATLAB routines that implement it in a MATPOWER-compatible workflow.
