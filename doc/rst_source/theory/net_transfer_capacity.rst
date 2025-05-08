
Net transfer capacity
========================

This is a linear program that describes how to compute the
maximum net transfer capacity achievable between two areas.


Nodal injections
--------------------

We decide to compute the injections per node directly.
We use a function to summ up all generation present at a
node and obtain the power injection limits of that node.


The power increment sent, must be equal to to power increment received:

.. math::

    \Delta P_{Send} = \Delta P_{Receive}

Where:

.. math::

    \Delta P_{Send} = \sum^{A_{send}}_i {\Delta P_i }

.. math::

    \Delta P_{Receive} = \sum^{A_{receive}}_i {\Delta P_i }

Finally, we add the nodal injection to the nodal balance summation

.. math::

    P_i = P_i + Pbase_i + share_i \cdot \Delta P_i



-:math:`A_{send}`: Node indices of the sending area.

-:math:`A_{receive}`: Node indices of the receiving area.

-:math:`\Delta P_i`: Power increment at the node i.

-:math:`P_i`: Power balance at the node i. In the end this will be a summation of terms.

-:math:`share_i`: scale for the increment at the node i. This is akin to the GLSK's.

-:math:`Pbase_i`: Power injection (generation - load) of the base situation at the node i.


Branches
--------------

The flow at the "from" node in a branch is:

.. math::

    flow_k = \frac{\theta_f - \theta_t}{x_k}


In case of a phase shifter transformer:

.. math::

    flow_k = \frac{\theta_f - \theta_t - \tau_k}{x_k}


We need to limit the flow to the line specified rating:

.. math::

    - rate_k \leq flow_k \leq rate_k


Finally, we add the flows to the nodal balance summation:

.. math::

    P_f = P_f - flow_k

.. math::

    P_t = P_t + flow_k


-:math:`f`: index of the node "from"

-:math:`t`: index of the node "to"

-:math:`\theta_f`: Nodal voltage angle at the node f.

-:math:`\theta_t`: Nodal voltage angle at the node t.

-:math:`x_k`: Branch k reactance.

-:math:`rate_k`: Branch k power rating.

-:math:`\tau_k`: Tap angle of the branch k.

-:math:`P_f`: Power balance at the node f.

-:math:`P_t`: Power balance at the node t.


HVDC converters
-----------------

For both control modes, we need to limit the flow to the converter rating:

.. math::

    - rate_k \leq flow_k \leq rate_k

Now, we add the flows to the nodal balance summation, just like we would with the branches:

.. math::

    P_f = P_f - flow_k

.. math::

    P_t = P_t + flow_k

The :math:`flow_k` value will differ depending on the control mode chosen:

Power control mode
^^^^^^^^^^^^^^^^^^^^^^

This is the most common control mode of an HVDC
converter, where the active power send is controlled and fixed.
For out optimization, the variable :math:`flow_k` is an optimization value
that moves freely between tha rating values.


Angle droop mode (AC emulation)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This is a very uncommon control decision solely used by the INELFE HVDC
between Spain and France. It is uncommon because the DC equipment is made
to vary depending on an AC magnitude measured as the difference between
the AC voltage angle at the AC sides of both converters.
This can only work because the two areas are also joined by AC lines already.

For the purpose of running an old fashioned ac power flow, this is very
convenient, since we don't need to come up with a proper DC formulation
using voltage magnitudes on top of using the classic linear formulations
based on susceptances and angles.

This mode, introduces some complexity; The angles are only coupled by the
expression ":math:`y`" when the converter power is within limits, otherwise
the converter flow is set to the maximum value and the angles are set free.
This is of course because of the artificial coupling imposed by the math,
since in reality the voltage angles are independent of this of that control
mode. To appropriately express this, we need to use a piece-wise function
formulation:

.. math::

    y = P0_k + K_k \cdot (\theta_f - \theta_t)

Conditional equality (:math:`flow_k = y`  only if :math`z_k=1`)

.. math::

    -M_k \cdot (1 - z_k)  \leq y - flow_k \leq M_k \cdot (1 - z_k)

- :math:`M_k`: is an arbitrary large quantity.
- :math:`z_k`: Binary variable (1 if using the angle droop control, 0 otherwise)
- :math:`K_k`: Arbitrary control parameter used.
- :math:`P0_k`: Base power (i.e. the given market exchange for the line).


Nodal balance
----------------

Finally, we create constraints where every nodal power summation is equal to zero,
to fulfill the Bucherot theorem: All power summation at a node is zero.


.. math::

    \sum^Nodes_i {P_i =0 }

The expressions contained in :math:`P_i` will be dependent on the angles
:math:`\theta` because of the branches and HVDC formulations.
Therefore the angles will be solved by the optimization too.
However, we must take care to set the slack angles to exactly zero:

.. math::

    \theta_{slack} = 0