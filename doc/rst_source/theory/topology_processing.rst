======================
Topology Processing
======================

Introduction
------------

In this section, we are going to explain how to do topology processing properly
for once and for all. This topic is of capital importance in power systems but is
rarely dealt with in a structured and comprehensive manner.

A power system model is essentially a graph. A graph is an abstract construct
where relationships are represented. In power systems, we aim to store the
relationships between calculation points (referred to as buses from now on)
through edges (referred to as branches from now on). Both buses and branches
in power systems have properties that define the relationships and even how
these relationships vary over time.

**What is a Graph in Power Systems?**

To understand topology processing, it's essential to grasp the basics of graph
theory. In a power system graph:

- **Nodes (Buses):** Represent points of calculation, such as substations, generation points, or load centers.
- **Edges (Branches):** Represent the connections, such as transmission lines, transformers, or circuit breakers.

This abstraction simplifies the network while retaining its essential
connectivity and operational properties.

**Why is Topology Processing Important?**

Topology processing ensures that the network's operational model accurately
reflects its physical state. Without proper processing, analyses may yield
inaccurate results, leading to operational inefficiencies or even failures.

Key reasons include:

- Ensuring the model is computationally feasible.
- Identifying and correcting data inconsistencies.
- Optimizing the simulation by reducing unnecessary complexities.

In less abstract terms, topology processing is about determining the simulatable
sub-circuits within a circuit. Here, a circuit refers to a collection of equipment,
its relationships, and states in the most general sense. We perform the topology
processing as a precaution before simulating, because what we want is to be able to
use the electrotechnical formulas to get the physical magnitudes, and for that we must
abide to some rules. Thus, from circuit theory, we derive the following fundamental
relationship:

.. math::

    Y \times V = I^*

Where:

- :math:`Y` is the nodal admittance matrix.
- :math:`V` is the vector of bus voltages.
- :math:`I` is the vector of current injections at the buses.

To solve for :math:`V`, we need to invert :math:`Y`:

.. math::

    V = Y^{-1} \times I^*

However, :math:`Y` may not always be invertible for any arbitrary collection
of equipment. This necessitates finding sub-circuits. Additionally, certain
branches in the circuit might have zero impedance, making :math:`Y` singular. We
must eliminate these problematic branches as part of the processing.

Steps in Topology Processing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Broadly, topology processing involves the following steps:

1. **Reduce problematic branches:** Address switches and jumpers that cause singularities.
2. **Find the simulatable islands:** Identify isolated groups of interconnected elements.
3. **Segment the circuit into sub-circuits:** Divide the system into smaller, manageable parts.
4. **Simulate each circuit independently:** Perform separate analyses for each sub-circuit.*
5. **Reassemble the results:** Combine outcomes to match the original circuit structure.

.. note::

   Steps 2 to 5 are necessary only for simulations reliant on equality constraints,
    such as power flow. Simulations involving overdetermined linear systems, such as
    optimizations, do not require separate handling of islands.


Performing topology processing requires one critical function: the island search.
This function identifies interconnected segments of the network, ensuring accurate
representation of the system's operational state.



1 Reducing problematic branches
------------------------------------------------

In the context of power systems, certain branches can cause computational issues due
to their characteristics, such as zero impedance or inactive status. These branches,
referred to as *problematic branches*, must be effectively reduced to ensure accurate
simulations and analyses. To better understand this, let’s examine the following
example circuit:

+----------+--------+-----------+-----------+--------+
| Bus from | Bus to | Reducible | impedance | active |
+----------+--------+-----------+-----------+--------+
| 0        | 1      | yes       | 0         | yes    |
+----------+--------+-----------+-----------+--------+
| 0        | 2      | no        | 0.05j     | yes    |
+----------+--------+-----------+-----------+--------+
| 1        | 3      | no        | 0.01j     | yes    |
+----------+--------+-----------+-----------+--------+
| 2        |  3     | yes       | 0         | no     |
+----------+--------+-----------+-----------+--------+

.. note::

    It is important to understand the meaning of zero when talking about physical magnitudes
    such as the impedance. Zero is the *absence of*, therefore zero impedance means that
    the branch is not there. Hence, we must remove it and join the buses it connects.

This circuit consists of 4 buses and 4 branches. Two of these branches are marked
as "reducible," meaning their removal is needed to not impact the network's functional
properties for simulation purposes. These zero-impedance branches do not contribute to
the network’s overall impedance matrix, but would make it singular if added.
To identify reducible branches, we construct an adjacency matrix representing
connections between buses. The adjacency matrix is computed using the following algorithm:

.. code-block::

    n = number of buses
    m = number of branches
    A = lil_matrix(n, n)
    for k=0 to m:
        f = bus from of the branch k
        t = bus to of the branch k
        if branch k is active and reducible:
            A(f, f) += 1
            A(f, t) += 1
            A(t, f) += 1
            A(t, t) += 1
        end-if
    end-for

A method that is found to be approximately 2.5 times faster in practice is the following:

.. code-block::

    n = number of buses
    m = number of branches
    C = lil_matrix(m, n)
    for k=0 to m:
        f = bus from of the branch k
        t = bus to of the branch k
        if branch k is active and reducible:
            C(k, f) = 1
            C(k, t) = 1
        end-if
    end-for
    A = C.transpose x C

.. note::

    Both methods require matrices `C` and `A` to be sparse. Dense matrices would
    demand excessive memory and computational resources, making them impractical
    for power system applications.


The nifty trick of composing A with the reducible elements, allows us to use a
standard island-finding algorithm to identify groups of buses connected by
reducible elements that can be treated as a single bus because they are
*topologically* the same place.
In the given example, buses 0 and 1 are grouped, meaning bus 1 is effectively
merged into bus 0. Buses 2 and 3 remain as independent nodes.

After processing the reducible branches, the simplified circuit is:

+----------+--------+-----------+
| Bus from | Bus to | impedance |
+----------+--------+-----------+
| 0        | 2      | 0.05j     |
+----------+--------+-----------+
| 0        | 3      | 0.01j     |
+----------+--------+-----------+


2 Finding the simulatable islands
------------------------------------

Now that we have a system without problematic branches, we need to proceed with
the island slicing. For that, we need to compute the Adjacency matrix using the
non-reducible, active branches. This is, the branches that have impedances and
can transmit electricity:

.. code-block::

    n = number of buses
    m = number of branches
    C = lil_matrix(m, n)
    for k=0 to m:
        f = bus from of the branch k
        t = bus to of the branch k
        if (branch k is active) and (bus f is active) and (bus t is active):
            C(k, f) = 1
            C(k, t) = 1
        end-if
    end-for

    A = C.transpose x C

1. **Initialization:** A sparse auxiliary matrix `C` is initialized to capture branch
   connections.
2. **Branch Iteration:** Each branch is checked for activity and the corresponding buses
   are verified to be active.
3. **Matrix Assembly:** Connections between the "from" and "to" buses are recorded in `C`.
4. **Adjacency Matrix Construction:** The final adjacency matrix `A` is obtained through
   a matrix multiplication operation on `C`.

With the adjacency matrix `A` constructed, standard island-detection algorithms can be
applied to identify groups of interconnected buses. These groups, referred to as
"simulatable islands," represent sub-networks that can independently support simulation.

.. code-block::

    islands = find_islands(A)

The `islands` variable contains a list of vectors, where each vector represents the
indices of buses within a single island. For example, in a simple network, two
interconnected buses might form one island, while isolated buses form separate islands.

For each identified island, it is crucial to verify the presence of at least one voltage
source or slack node. Without a slack node, the island cannot be powered, resulting in a
blackout for that portion of the network. Slack nodes provide the necessary reference
voltage and power balance for the island’s operation.


3 Segment the circuit into islands
------------------------------------

After removing problematic branches, the next crucial step is to segment the circuit
into islands. An island is defined as a group of interconnected buses that form an
independent sub-network. This segmentation is essential for accurately analyzing and
simulating the system. To achieve this, we slice the grid's data structures based on
the island information.

An island is represented as a vector of bus indices. For instance, if an island
contains buses 4, 5, 6, and 7, this vector would be `[4, 5, 6, 7]`. Using this
information, slicing a data structure containing only bus data is straightforward.
However, slicing structures such as branch or load data requires additional steps.

To efficiently handle slicing, we create a bus mapping array that maps the original
bus indices to the indices of the island. For example, consider a circuit with 8
buses, where the island comprises buses 4, 5, 6, and 7. The mapping process is as
follows:

1. Initialize an array of size 8 filled with `-1` to represent unmapped buses.
2. Assign new island indices to the corresponding positions in the array.

.. code-block::

    island = (4, 5, 6, 7)
    bus_map = -1 x ones(8)
    ii = 0
    for i in island:
        bus_map[i] = ii
        ii += 1
    end-for

    The bus map is:
    bus_map = (-1, -1, -1, -1, 0, 1, 2, 3)


Now, consider the following branch data for the grid:

+----------+----------+--------+
| Name     | bus_from | bus_to |
+----------+----------+--------+
| 0:Branch | 2        | 0      |
+----------+----------+--------+
| 1:Branch | 3        | 2      |
+----------+----------+--------+
| 2:Branch | 1        | 0      |
+----------+----------+--------+
| 3:Branch | 1        | 2      |
+----------+----------+--------+
| 4:Branch | 6        | 4      |
+----------+----------+--------+
| 5:Branch | 7        | 6      |
+----------+----------+--------+
| 6:Branch | 5        | 4      |
+----------+----------+--------+
| 7:Branch | 5        | 6      |
+----------+----------+--------+

With a simple algorithm we can determine which branch indices belong to the island:

.. code-block::

    m = number of branches
    elements_indices = list()
    for k=0 to m:
        f = branch k from bus
        t = branch k to bus
        if bus_map[f] > -1 and bus_map[t] > -1:
            elements_indices.add(k)

    in this case
    elements_indices = (4, 5, 6, 7)

Hence, the sliced island branch data is:

+----------+----------+--------+
| Name     | bus_from | bus_to |
+----------+----------+--------+
| 4:Branch | 6        | 4      |
+----------+----------+--------+
| 5:Branch | 7        | 6      |
+----------+----------+--------+
| 6:Branch | 5        | 4      |
+----------+----------+--------+
| 7:Branch | 5        | 6      |
+----------+----------+--------+

Using the bus_map, we need to re-map the "from" and "to" buses of the sliced structure:

+----------+----------+--------+
| Name     | bus_from | bus_to |
+----------+----------+--------+
| 4:Branch | 2        | 0      |
+----------+----------+--------+
| 5:Branch | 3        | 2      |
+----------+----------+--------+
| 6:Branch | 1        | 0      |
+----------+----------+--------+
| 7:Branch | 1        | 2      |
+----------+----------+--------+

For data structures like loads, the slicing process is similar. However, these
structures typically involve a single bus index rather than "from" and "to" indices.
By consistently applying the bus mapping array, we can accurately extract relevant
data for any island.

Segmenting the circuit into islands eliminates inactive buses, branches, and devices
that might otherwise introduce errors into simulations. This step significantly
improves computational efficiency and ensures cleaner, more reliable data for
numerical calculations such as power flow analysis. The resulting islands form
distinct, manageable sub-networks ready for independent simulation and analysis.

Summary of the steps
------------------------------------

- First we must detect which buses are electrically (and topologically) the same as others.
- Then we find the electrical islands.

For both steps we use the islands search over an adjacency matrix (A).
In the first connectivity matrix (A), we reflect the connections of the branches that we want to reduce.
In the second connectivity matrix (A), we reflect the connection of the branches that we want to keep.

.. figure:: ./../figures/TopologyProcessing1.png
    :alt: Topology processing steps


Islands search function
------------------------------------

The island search function is a depth-first search that exploits the CSC structure of
the adjacency matrix. The particular version of the DFS algorithm presented here avoids
recursivity in favor of cues for faster execution.

.. code-block::

    indptr: index pointers in the CSC scheme
    indices: column indices in the CSCS scheme
    active: array of bus active states
    n = bus number

    visited = zeros(n)

    islands = list()

    node_count = 0
    current_island = zeros(n)

    island_idx = 0

    for node=0 to node_number:

        if not visited[node] and active[node]:

            stack = list()
            stack.add(node)

            while stack.size > 0:

                v = stack.first
                remove first element from the stack

                if not visited[v]:

                    visited[v] = 1

                    current_island[node_count] = v
                    node_count += 1

                    for i=indptr[v] to indptr[v + 1]:
                        k = indices[i]
                        if not visited[k] and active[k]:
                            stack.add(k)
                        end-if
                    end-for
                end-if
            end-while

            # slice the current island to its actual size
            island = current_island[:node_count].copy()
            island.sort()  # sort in-place

            # assign the current island
            islands.append(island)

            # increase the islands index, because
            island_idx += 1

            # reset the current island
            # no need to re-allocate "current_island" since it is going to be overwritten
            node_count = 0
        end-if
    end-for


The spirit of CIM
------------------------

If you've encountered CIM or CGMES, or participated in guild discussions, you've
likely heard about **node-breaker** and **bus-branch** modeling styles as distinct
approaches. ENTSO-e's introductory CGMES training has historically taught that
you can model using either **connectivity nodes** or **TopologicalNodes** (AKA Buses).
This guidance has been shared with hundreds of engineers accustomed to simpler
models of buses, lines, etc., only to face what seems to be gratuitous complexity.

After deep examination, one finds that this complexity is indeed unjustified.
The **node-breaker** and **bus-branch** philosophies are fundamentally the same,
as demonstrated through the processes described in this document.

.. note::

    - A ConnectivityNode is a **bus** before the topology processing.
    - A TopologyNode is a **bus** after the topology processing.

The modeling approaches are often thought of as follows:

- **Bus-branch modeling:** This style involves using **TopologicalNodes** and
  no switches.
- **Node-breaker modeling:** This style involves using **ConnectivityNodes**
  and switches.

**Debunking Misconceptions**

A common misconception is that bus-branch models lack switches, whereas node-
breaker models include them. In practice, both approaches can incorporate
switches. This fact is often emphasized in official CGMES trainings. If a
**ConnectivityNode** must have a N:1 association with a **TopologicalNode**, this
implies that any ConnectivityNode ultimately represents a TopologicalNode.
This reinforces the argument that both are two faces of the same coin,
**Making both styles fundamentally equal.**

**The Philosophy Behind CIM**

One would imagine that the intent behind CIM’s design philosophy is to model
grids using **ConnectivityNodes**, with **TopologicalNodes** emerging naturally
through topological reductions (e.g., simplifying branches).
This implies that we should not share TopologicalNodes, since those are
internal artifacts of a calculation software such as VeraGrid.

Over time, the practice of treating detailed models as node-breaker models
and processed, less-detailed models as bus-branch has created an
artificial divide that has proven impractical and needlessly complicated.

**Why the Complexity?**

One can understand that the lack of a properly clear topology processing method
has likely sparked this complexity, creating a middle ground that combines the
worst aspects of both approaches. Engineers attempting to reconcile the two
styles often encounter unnecessary confusion and inefficiency.

**Revisiting CIM’s Spirit**

If we examine the original spirit of CIM: **ConnectivityNodes are no different
from traditional Buses.** The distinction is a myth that adds unnecessary
complexity to modeling workflows. By adhering to this perspective, we can
simplify processes and focus on building more efficient and accurate models.


How is it done in VeraGrid?
------------------------------------

In VeraGrid, the **MultiCircuit** serves as the grid's in-memory database. It is
crucial that no topological processing is ever performed directly on the
MultiCircuit. Doing so risks altering the topology of elements, potentially
breaking the consistency of the original configuration.

**Why Avoid Topological Processing on the MultiCircuit?**

Consider the following example: Imagine a generator initially connected to
**Bus 1**. After performing topological processing, it might end up connected to
**Bus 2**. How could we recover the original connection to **Bus 1**? Simply put,
we cannot. Altering the MultiCircuit directly compromises its integrity,
making it impossible to restore the original topology. In CIM, this is probably why
there are two distinct sets of objects; ConnectivityNode to maintain the structure
and TopologicalNode to represent the final connectivity. This reinforces the idea
that we must only model with ConnectivityNodes, which for simplicity are always
buses in the end in VeraGrid.

**The Role of NumericalCircuit**

If topology processing should not occur over the database, then where should it
be done? The solution in VeraGrid is to provide the **NumericalCircuit**, a snapshot of
the MultiCircuit at a specific state. This snapshot is **fungible**, meaning any
modifications made to it will not impact the original MultiCircuit and will
vanish after the calculation. As such, all topology processing steps are
performed on the **NumericalCircuit**, as described earlier in this section.

**CIM Compatibility Adjustments**

To ensure compatibility with CIM standards, we have introduced a single
adjustment:

- Every **ConnectivityNode** must either create a bus or be associated with an
  existing bus.
- Similarly, every **BusBar** must either create a connectivity node or be
  associated with one.

This guarantees that no matter which object you use for modeling, the system
will ultimately rely on buses, maintaining consistency across all calculation
processes in every scenario and avoiding the superficial complexity of having two
sets of objects for the same thing; Representing a node in a graph.

By doing this, we also put an end to the node-breaker vs. bus-branch feud,
allowing for compatibility with the so-called legacy models.

.. figure:: ./../figures/TopologyRoundtrip.png
    :alt: Topology processing steps


Takeaways
^^^^^^^^^^

.. note::

    - Bus-branch and node-breaker modelling styles are the same thing.
    - In VeraGrid, always model with buses, you'll thank me later.
    - In CIM/CGMES, model always with ConnectivityNodes and forget
      about the TopologicalNodes, you'll thank me later.
    - In topology processing, we use the find-islands algorithm, combined
      with different compositions of adjacency matrices (A), element traversing
      should only happen when composing the adjacency matrices.
