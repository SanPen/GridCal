.. _3_phase_sc:

3-Phase Short Circuit
=====================

First, declare an array of zeros of size equal to the number of nodes in the
circuit.

.. math::

    \textbf{I} = \{0, 0, 0, 0, ..., 0\}

Then for single bus failure, compute the short circuit current at the selected bus :math:`i` and assign
that value in the :math:`i^{th}` position of the array :math:`\textbf{I}`.

.. math::

    \textbf{I}_i = - \frac{\textbf{V}_{pre-failure, i}}{\textbf{Z}_{i, i} + z_f}

Then, compute the voltage increment for all the circuit nodes as:

.. math::

    \Delta \textbf{V} = \textbf{Z} \times \textbf{I}

Finally, define the voltage at all the nodes as:

.. math::

    \textbf{V}_{post-failure} = \textbf{V}_{pre-failure} + \Delta \textbf{V}

Multiple bus failures
---------------------
The following requirements must be satisfied:

1. Fault currents of selected buses :math:`B` must have linear relationship with pre-failure voltages: for some :math:`\textbf{Z'}_B`,

.. math::

    \textbf{V}_{pre-failure, B} = \textbf{Z'}_B \times \textbf{I}_B

2. :math:`\textbf{V}_{post-failure, B} = -\textbf{z}_{f,B} \times \textbf{I}_B`.

Along with the above equations for :math:`\Delta \textbf{V}` and :math:`\textbf{V}_{post-failure}`, we get that

.. math::

    \textbf{Z'}_B = -(\textbf{Z}_B + \textbf{z}_{f,B})

wherein :math:`\textbf{z}_{f,B}` is added to the diagonals.

Short circuit currents :math:`\textbf{I}_B` can now be computed through the above equation for :math:`\textbf{V}_{pre-failure, B}`.

**Variables:**

- :math:`\textbf{I}`: Array of fault currents at the system nodes.
- :math:`\textbf{I}_B`: Subarray of :math:`\textbf{I}` wherein all entries for non-faulted buses are removed.
- :math:`\textbf{V}_{pre-failure}`: Array of system voltages prior to the failure. This is obtained from the power flow study.
- :math:`z_f`: Impedance of the failure itself. This is a given value, although you can set it to zero if you don't know.
- :math:`\textbf{Z}`: system impedance matrix. Obtained as the inverse of the complete system admittance matrix.
- :math:`\textbf{Z}_B`: submatrix of :math:`\textbf{Z}` wherein all rows and columns for non-faulted buses are removed.
