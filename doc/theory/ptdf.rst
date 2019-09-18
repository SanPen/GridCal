

PTDF (Power Transmission Distribution Factors)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

GridCal features a PTDF simulation of the branches sensitivity to the generation variations.
This classic method is implemented in GridCal using two variants:


- Reducing power by generator by generator.
- Reducing power by generator technology group.

The simulation consists in:

A. Simulate a base power flow and collect the results.

B. Compute all the power variation vectors (:math:`Svaried`) either by generator or by group.
   These vector will have the same length as the number of nodes.

C. For every variation:

    C.1. run a power flow simulation with the varied power injections :math:`Sbus = Sbus_0 - Svaried`

    C.2. Collect the power flow results.

    C.3. Compute the branch sensitivity (:math:`\alpha`) as the power flow variation divided by the power generation variation.

    :math:`\alpha = \frac{Sbranch_0 - Sbranch}{power\_variation}`


This renders a simple method to identify how much power flow changed in a branch given the succesive
generation diminishings.

.. figure:: ../figures/ptdf_result.png
    :alt: PTDF results

    PTDF results for the Pegase 1354-bus grid.