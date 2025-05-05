
Net transfer capacity
========================

This is a linear program that describes how to compute the
maximum net transfer capacity achievable between two areas.


Injections
--------------

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

Power control mode
^^^^^^^^^^^^^^^^^^^^^^

This is the most common control mode of an HVDC
converter, where the active power send is controlled and fixed.
Hence, we just make the flow equal to a fixed control value:

.. math::

    P_f = P_f - flow_k

.. math::

    P_t = P_t + flow_k


Angle droop mode (AC emulation)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. math::

    flow_k = P0_k + k \cdot (\theta_f - \theta_t)


Now, we add the flows to the nodal balance summation, just like we would with the branches:

.. math::

    P_f = P_f - flow_k

.. math::

    P_t = P_t + flow_k




Nodal balance
----------------

Finally, we create constraints where every nodal power summation is equal to zero,
to fulfill the Bucherot theorem: All power summation at a node is zero.


.. math::

    \sum^Nodes_i {P_i =0 }