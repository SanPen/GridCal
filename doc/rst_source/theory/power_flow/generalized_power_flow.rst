.. _generalized_power_flow:

Generalized Power Flow
=============================

This formulation of a generalized power flow was introduced in the Master Thesis
of Raiyan Bin Zulkifli in 2024 (Generalised AC/DC Power Flow at UPC university).

.. figure:: ../figures/generalized_branch_models.png
    :alt: Generalized branch models.
    :scale: 50 %


.. math::

    \Delta S = S_calc - S_esp

.. math::

    S_zip = S_zip0 + V \cdot (Ire_zip - j \cdot Iim_zip + V \cdot (G_zip - j \cdot B_zip))

    S_calc = V \cdot (I)^* = V \cdot (Y \times V - I_zip)^*


.. math::

    \begin{equation}
        \begin{bmatrix}
            \frac{\partial \Delta P}{\partial Va} & \frac{\partial \Delta P}{\partial Vm} & \frac{\partial \Delta P}{\partial \tau} & \frac{\partial \Delta P}{\partial m} & \frac{\partial \Delta P}{\partial P^{zip}} & \frac{\partial \Delta P}{\partial Q^{zip}} & \frac{\partial \Delta P}{\partial P_f} & \frac{\partial \Delta P}{\partial P_t} & \frac{\partial \Delta P}{\partial Q_f} & \frac{\partial \Delta P}{\partial Q_t} \\
            \frac{\partial \Delta Q}{\partial Va} & \frac{\partial \Delta Q}{\partial Vm} & \frac{\partial \Delta Q}{\partial \tau} & \frac{\partial \Delta Q}{\partial m} & \frac{\partial \Delta Q}{\partial P^{zip}} & \frac{\partial \Delta Q}{\partial Q^{zip}} & \frac{\partial \Delta Q}{\partial P_f} & \frac{\partial \Delta Q}{\partial P_t} & \frac{\partial \Delta Q}{\partial Q_f} & \frac{\partial \Delta Q}{\partial Q_t} \\
            \frac{\partial g_loss}{\partial Va} & \frac{\partial g_loss}{\partial Vm} & \frac{\partial g_loss}{\partial \tau} & \frac{\partial g_loss}{\partial m} & \frac{\partial g_loss}{\partial P^{zip}} & \frac{\partial g_loss}{\partial Q^{zip}} & \frac{\partial g_loss}{\partial P_f} & \frac{\partial g_loss}{\partial P_t} & \frac{\partial g_loss}{\partial Q_f} & \frac{\partial g_loss}{\partial Q_t} \\
            \frac{\partial P_f}{\partial Va} & \frac{\partial P_f}{\partial Vm} & \frac{\partial P_f}{\partial \tau} & \frac{\partial P_f}{\partial m} & \frac{\partial P_f}{\partial P^{zip}} & \frac{\partial P_f}{\partial Q^{zip}} & \frac{\partial P_f}{\partial P_f} & \frac{\partial P_f}{\partial P_t} & \frac{\partial P_f}{\partial Q_f} & \frac{\partial P_f}{\partial Q_t} \\
            \frac{\partial P_t}{\partial Va} & \frac{\partial P_t}{\partial Vm} & \frac{\partial P_t}{\partial \tau} & \frac{\partial P_t}{\partial m} & \frac{\partial P_t}{\partial P^{zip}} & \frac{\partial P_t}{\partial Q^{zip}} & \frac{\partial P_t}{\partial P_f} & \frac{\partial P_t}{\partial P_t} & \frac{\partial P_t}{\partial Q_f} & \frac{\partial P_t}{\partial Q_t} \\
            \frac{\partial Q_f}{\partial Va} & \frac{\partial Q_f}{\partial Vm} & \frac{\partial Q_f}{\partial \tau} & \frac{\partial Q_f}{\partial m} & \frac{\partial Q_f}{\partial P^{zip}} & \frac{\partial Q_f}{\partial Q^{zip}} & \frac{\partial Q_f}{\partial P_f} & \frac{\partial Q_f}{\partial P_t} & \frac{\partial Q_f}{\partial Q_f} & \frac{\partial Q_f}{\partial Q_t} \\
            \frac{\partial Q_t}{\partial Va} & \frac{\partial Q_t}{\partial Vm} & \frac{\partial Q_t}{\partial \tau} & \frac{\partial Q_t}{\partial m} & \frac{\partial Q_t}{\partial P^{zip}} & \frac{\partial Q_t}{\partial Q^{zip}} & \frac{\partial Q_t}{\partial P_f} & \frac{\partial Q_t}{\partial P_t} & \frac{\partial Q_t}{\partial Q_f} & \frac{\partial Q_t}{\partial Q_t}
        \end{bmatrix}
        \times
        \begin{bmatrix}
            \Delta Va \in iu_Va \\
            \Delta Vm \in iu_Vm \\
            \Delta \tau \in ku_{\tau}\\
            \Delta m \in ku_m\\
            \Delta P^{zip} \in iu_{P_zip}\\
            \Delta Q^{zip} \in iu_{Q_zip}\\
            \Delta P_f \in ku_{P_f} \\
            \Delta P_t \in ku_{P_t} \\
            \Delta Q_f \in ku_{Q_f} \\
            \Delta Q_t \in ku_{Q_t}
        \end{bmatrix}
        =
        \begin{bmatrix}
            \Delta P \in in_P \\
            \Delta Q \in in_Q \\
            g_loss \in kn_acdc \\
            \Delta P_f \in kn_{P_f} \\
            \Delta P_t \in kn_{P_t} \\
            \Delta Q_f \in kn_{Q_f} \\
            \Delta Q_t \in kn_{Q_t}
        \end{bmatrix}
    \end{equation}



Specified variables' sets:

- :math:`\mathcal{C}_{Va}` -> Indices of the buses where the voltage angles are specified.
- :math:`\mathcal{C}_{Vm}` -> Indices of the buses where the voltage modules are specified.
- :math:`\mathcal{C}_{\tau}` -> Indices of the controllable branches where the phase shift angles are specified.
- :math:`\mathcal{C}_{m}` -> Indices of the controllable branches where the tap ratios are specified.
- :math:`\mathcal{C}_{P_zip}` -> Indices of the buses where the ZIP active power injection are specified.
- :math:`\mathcal{C}_{Q_zip}` -> Indices of the buses where the ZIP reactive power injection are specified.
- :math:`\mathcal{C}{P_f}` -> Indices of the controllable branches where Pf is specified.
- :math:`\mathcal{C}{P_t}` -> Indices of the controllable branches where Pt is specified.
- :math:`\mathcal{C}{Q_f}` -> Indices of the controllable branches where Qf is specified.
- :math:`\mathcal{C}{Q_t}` -> Indices of the controllable branches where Qt is specified.
- :math:`\mathcal{C}{Inj_P}` -> Indices of the injection devices where the P is specified.
- :math:`\mathcal{C}{Inj_Q}` -> Indices of the injection devices where the Q is specified.

Global sets:

- :math:`ac` -> Indices of the ac buses.
- :math:`dc` -> Indices of the dc buses.
- :math:`cbr` -> Indices of the controllable branches.
- :math:`vsc` -> Indices of the ACDC converters.
- :math:`Inj_P` -> Indices of the injection devices where the P is specified.
- :math:`Inj_Q` -> Indices of the injection devices where the Q is specified.


Set operations:

- :math:`\cup` : Set union.
- :math:`\setminus` : Set exclusion.

Unknowns:

The indices of the unknowns are found by obtaining the

- :math:`iu_Va = ac \setminus \mathcal{C}_{Va}` -> Voltage angle increments for the AC buses where Va is not specified.
- :math:`iu_Vm = (ac \cup dc) \setminus \mathcal{C}_{Vm}` -> Voltage angle increments for the AC & DC buses where Vm is not specified.
- :math:`ku_{\tau} = cbr \setminus \mathcal{C}_{\tau}` -> Set of controllable branches where the phase shift angles are not specified.
- :math:`ku_m = cbr \setminus \mathcal{C}_{m}` -> Set of controllable branches where the tap ratios are not specified.
- :math:`iu_{P_zip} = Inj_P \setminus \mathcal{C}{Inj_P}` -> Set of injections where :math:`P_{zip}` is not specified.
- :math:`iu_{Q_zip} = Inj_q \setminus \mathcal{C}{Inj_q}` -> Set of injections where :math:`Q_{zip}` is not specified.
- :math:`ku_{P_f} = cbr \setminus \mathcal{C}{P_f}` -> Set of branch indices where :math:`P_f` is not specified.
- :math:`ku_{P_t} = cbr \setminus \mathcal{C}{P_t}` -> Set of branch indices where :math:`P_t` is not specified.
- :math:`ku_{Q_f} = cbr \setminus \mathcal{C}{Q_f}` -> Set of branch indices where :math:`Q_f` is not specified.
- :math:`ku_{Q_t} = cbr \setminus \mathcal{C}{Q_t}` -> Set of branch indices where :math:`Q_t` is not specified.

Knowns:

- :math:`in_P = ac \cup dc` -> Active power mismatch for the set of all AC and DC
- :math:`in_Q = ac` -> Reactive power mismatch for Ac buses
- :math:`kn_acdc = vsc` -> Power loss equation mismatch for the VSC devices
- :math:`kn_{P_f} = cbr` -> Pf mismatch for all controllable branches (without ACDC converters)
- :math:`kn_{P_t} = cbr` -> Pt mismatch for all controllable branches (without ACDC converters)
- :math:`kn_{Q_f} = cbr` -> Qf mismatch for all controllable branches (without ACDC converters)
- :math:`kn_{Q_t} = cbr` -> Qt mismatch for all controllable branches (without ACDC converters)