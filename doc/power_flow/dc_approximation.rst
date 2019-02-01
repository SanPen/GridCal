.. _dc_approximation:

DC approximation
================

The so called direct current power flow (or just DC power flow) is a convenient
oversimplification of the power flow procedure.

It assumes that in any branch the reactive part of the impedance is much larger than
the resistive part, hence the resistive part is neglected, and that all the voltages
modules are the nominal per unit values. This is, :math:`|v|=1` for load nodes and
:math:`|v|=v_{set}` for the generator nodes, where $v_{set}$ is the generator set
point value.

In order to compute the DC approximation we must perform a transformation. The slack
nodes are removed from the grid, and their influence is maintained by introducing
equivalent currents in all the nodes. The equivalent admittance matrix
(:math:`\textbf{Y}_{red}`) is obtained by removing the rows and columns corresponding
to the slack nodes. Likewise the removed elements conform the
(:math:`\textbf{Y}_{slack}`) matrix.

.. figure:: ../figures/matrix-reduction.png
    :alt: Matrix reduction (VD: Slack, PV: Voltage controlled, PQ: Power controlled)

    Matrix reduction (VD: Slack, PV: Voltage controlled, PQ: Power controlled)

.. math::

    \textbf{P} = real(\textbf{S}_{red}) + (- imag(\textbf{Y}_{slack}) \cdot angle(\textbf{V}_{slack}) + real(\textbf{I}_{red})) \cdot |\textbf{V}_{red}|

The previous equation computes the DC power injections as the sum of the different factors mentioned:

- :math:`real(\textbf{S}_{red})`: Real part of the reduced power injections.
- :math:`imag(\textbf{Y}_{slack}) \cdot angle(\textbf{V}_{slack}) \cdot |v_{red}|`: Currents that appear by removing the slack nodes while keeping their influence, multiplied by the voltage module to obtain power.
- :math:`real(\textbf{I}_{red}) \cdot |v_{red}|`: Real part of the grid reduced current injections, multiplied by the voltage module to obtain power.

Once the power injections are computed, the new voltage angles are obtained by:

.. math::

    \textbf{V}_{angles} = imag(\textbf{Y}_{red})^{-1} \times \textbf{P}

The new voltage is then:

.. math::

    \textbf{V}_{red} = |\textbf{V}_{red}| \cdot e^{1j \cdot  \textbf{V}_{angles}}

This solution does usually produces a large power mismatch. That is to be expected
because the method is an oversimplification with no iterative convergence criteria,
just a straight forward set of operations.
