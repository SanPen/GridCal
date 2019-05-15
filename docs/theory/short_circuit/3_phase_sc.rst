.. _3_phase_sc:

3-Phase Short Circuit
=====================

First, declare an array of zeros of size equal to the number of nodes in the
circuit.

.. math::

    \textbf{I} = \{0, 0, 0, 0, ..., 0\}

Then, compute the short circuit current at the selected bus :math:`i` and assign
that value in the :math:`i^{th}` position of the array :math:`\textbf{I}`.

.. math::

    \textbf{I}_i = - \frac{\textbf{V}_{pre-failure, i}}{\textbf{Z}_{i, i} + z_f}

Then, compute the voltage increment for all the circuit nodes as:

.. math::

    \Delta \textbf{V} = \textbf{Z} \times \textbf{I}

Finally, define the voltage at all the nodes as:

.. math::

    \textbf{V}_{post-failure} = \textbf{V}_{pre-failure} + \Delta \textbf{V}

Magnitudes:

- :math:`\textbf{I}`: Array of fault currents at the system nodes.
- :math:`\textbf{V}_{pre-failure}`: Array of system voltages prior to the failure. This is obtained from the power flow study.
- :math:`z_f`: Impedance of the failure itself. This is a given value, although you can set it to zero if you don't know.
- :math:`\textbf{Z}`: system impedance matrix. Obtained as the inverse of the complete system admittance matrix.
