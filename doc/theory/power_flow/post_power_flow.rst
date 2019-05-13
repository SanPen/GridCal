.. _post_power_flow:

Post Power Flow (Loading and Losses)
====================================

As we have seen, the power flow routines compute the voltage at every bus of an island
grid. However we do not get from those routines the "power flow" values, this is the
power that flows through the branches of the grid. In this section I show how the
*post power flow* values are computed.

First we compute the branches per unit currents:

.. math::

    {\textbf{I}_f = \textbf{Y}_f \times \textbf{V}}

.. math::

    {\textbf{I}_t = \textbf{Y}_t \times \textbf{V}}

These are matrix-vector multiplications. The result is the per unit currents flowing
through a branch seen from the *from* bus or from the *to* bus.

Then we compute the power values:

.. math::

    {\textbf{S}_f = \textbf{V}_f \cdot \textbf{I}_f^*}

.. math::

    {\textbf{S}_t = \textbf{V}_t \cdot \textbf{I}_t^*}

These are element-wise multiplications, resulting in the per unit power flowing
through a branch seen from the *from* bus or from the *to* bus.

Now we can compute the losses in MVA as:

.. math::

    {\textbf{losses} = |\textbf{S}_f - \textbf{S}_t| \cdot Sbase}

And also the branches loading in per unit as:

.. math::

    {\textbf{loading} = \frac{max(|\textbf{S}_f|, |\textbf{S}_t|) \cdot Sbase}{ \textbf{rate}}}

The variables are:

- :math:`\textbf{Y}_f, \textbf{Y}_t`: *From* and *To* bus-branch admittance matrices
- :math:`\textbf{I}_f`: Array of currents at the *from* buses in p.u.
- :math:`\textbf{I}_t`: Array of currents at the *to* buses in p.u.
- :math:`\textbf{S}_f`: Array of powers at the *from* buses in p.u.
- :math:`\textbf{S}_t`: Array of powers at the *to* buses in p.u.
- :math:`\textbf{V}_f`: Array of voltages at the *from* buses in p.u.
- :math:`\textbf{V}_t`: Array of voltages at the *to* buses in p.u.
- :math:`\textbf{rate}`: Array of branch ratings in MVA.
