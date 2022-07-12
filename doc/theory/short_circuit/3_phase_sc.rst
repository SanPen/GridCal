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
For all bus :math:`i` in selected buses :math:`B`, :math:`\textbf{V}_{post-failure, i} = -\textbf{z}_{f,i} \textbf{I}_i`.
This, along with the equations for :math:`\Delta \textbf{V}` and :math:`\textbf{V}_{post-failure}` above,
and :math:`\textbf{I}_i = 0` for non-selected buses, gives the equation:

.. math::

    \textbf{V}_{pre-failure, B} = -(\textbf{Z}_B + \textbf{z}_{f,B}) \times \textbf{I}_B

in which :math:`\textbf{z}_{f, B}` is added to the diagonals of :math:`\textbf{Z}_B`.

Short circuit currents :math:`\textbf{I}_B` can now be computed through the equation for :math:`\textbf{V}_{pre-failure, B}` above.
Note that the single bus short circuit current computation above follows if :math:`B` has only one bus.

**Variables:**

- :math:`\textbf{I}`: Array of fault currents at the system nodes.
- :math:`\textbf{I}_B`: Subarray of :math:`\textbf{I}` such that all entries for non-selected buses are removed.
- :math:`\textbf{V}_{pre-failure}`: Array of system voltages prior to the failure. This is obtained from the power flow study.
- :math:`\textbf{V}_{pre-failure, B}`: Subarray of :math:`\textbf{V}_{pre-failure}` such that all entries for non-selected buses are removed.
- :math:`z_f`: Impedance of the failure itself. This is a given value, although you can set it to zero if you don't know.
- :math:`\textbf{z}_{f, B}`: Impedance of the failures of selected buses :math:`B`.
- :math:`\textbf{Z}`: system impedance matrix. Obtained as the inverse of the complete system admittance matrix.
- :math:`\textbf{Z}_B`: submatrix of :math:`\textbf{Z}` such that all rows and columns for non-selected buses are removed.
