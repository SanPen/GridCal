.. _generalized_power_flow:

Generalized Power Flow
=============================

This formulation of a generalized power flow was introduced in the Master Thesis
of Raiyan Bin Zulkifli in 2024 (Generalised AC/DC Power Flow at UPC university).

.. figure:: ./../../figures/generalized_branch_models.png
    :alt: Generalized branch models.
    :scale: 50 %

The linearized system is:

.. math::

    \left[
    \begin{matrix}
        \frac{\partial P}{\partial Vm} & \frac{\partial P}{\partial Va} & \frac{\partial P}{\partial P_f^{vsc}} & \frac{\partial P}{\partial P_t^{vsc}} & \frac{\partial P}{\partial Q_t^{vsc}} & \frac{\partial P}{\partial P_f^{hvdc}} & \frac{\partial P}{\partial P_t^{hvdc}} & \frac{\partial P}{\partial Q_f^{hvdc}} & \frac{\partial P}{\partial Q_t^{hvdc}} & \frac{\partial P}{\partial m} & \frac{\partial P}{\partial \tau} \\
        \frac{\partial Q}{\partial Vm} & \frac{\partial Q}{\partial Va} & \frac{\partial Q}{\partial P_f^{vsc}} & \frac{\partial Q}{\partial P_t^{vsc}} & \frac{\partial Q}{\partial Q_t^{vsc}} & \frac{\partial Q}{\partial P_f^{hvdc}} & \frac{\partial Q}{\partial P_t^{hvdc}} & \frac{\partial Q}{\partial Q_f^{hvdc}} & \frac{\partial Q}{\partial Q_t^{hvdc}} & \frac{\partial Q}{\partial m} & \frac{\partial Q}{\partial \tau} \\
        \frac{\partial loss_{vsc}}{\partial Vm} & \frac{\partial loss_{vsc}}{\partial Va} & \frac{\partial loss_{vsc}}{\partial P_f^{vsc}} & \frac{\partial loss_{vsc}}{\partial P_t^{vsc}} & \frac{\partial loss_{vsc}}{\partial Q_t^{vsc}} & \frac{\partial loss_{vsc}}{\partial P_f^{hvdc}} & \frac{\partial loss_{vsc}}{\partial P_t^{hvdc}} & \frac{\partial loss_{vsc}}{\partial Q_f^{hvdc}} & \frac{\partial loss_{vsc}}{\partial Q_t^{hvdc}} & \frac{\partial loss_{vsc}}{\partial m} & \frac{\partial loss_{vsc}}{\partial \tau} \\
        \frac{\partial loss_{hvdc}}{\partial Vm} & \frac{\partial loss_{hvdc}}{\partial Va} & \frac{\partial loss_{hvdc}}{\partial P_f^{vsc}} & \frac{\partial loss_{hvdc}}{\partial P_t^{vsc}} & \frac{\partial loss_{hvdc}}{\partial Q_t^{vsc}} & \frac{\partial loss_{hvdc}}{\partial P_f^{hvdc}} & \frac{\partial loss_{hvdc}}{\partial P_t^{hvdc}} & \frac{\partial loss_{hvdc}}{\partial Q_f^{hvdc}} & \frac{\partial loss_{hvdc}}{\partial Q_t^{hvdc}} & \frac{\partial loss_{hvdc}}{\partial m} & \frac{\partial loss_{hvdc}}{\partial \tau} \\
        \frac{\partial inj_{hvdc}}{\partial Vm} & \frac{\partial inj_{hvdc}}{\partial Va} & \frac{\partial inj_{hvdc}}{\partial P_f^{vsc}} & \frac{\partial inj_{hvdc}}{\partial P_t^{vsc}} & \frac{\partial inj_{hvdc}}{\partial Q_t^{vsc}} & \frac{\partial inj_{hvdc}}{\partial P_f^{hvdc}} & \frac{\partial inj_{hvdc}}{\partial P_t^{hvdc}} & \frac{\partial inj_{hvdc}}{\partial Q_f^{hvdc}} & \frac{\partial inj_{hvdc}}{\partial Q_t^{hvdc}} & \frac{\partial inj_{hvdc}}{\partial m} & \frac{\partial inj_{hvdc}}{\partial \tau} \\
        \frac{\partial P_f}{\partial Vm} & \frac{\partial P_f}{\partial Va} & \frac{\partial P_f}{\partial P_f^{vsc}} & \frac{\partial P_f}{\partial P_t^{vsc}} & \frac{\partial P_f}{\partial Q_t^{vsc}} & \frac{\partial P_f}{\partial P_f^{hvdc}} & \frac{\partial P_f}{\partial P_t^{hvdc}} & \frac{\partial P_f}{\partial Q_f^{hvdc}} & \frac{\partial P_f}{\partial Q_t^{hvdc}} & \frac{\partial P_f}{\partial m} & \frac{\partial P_f}{\partial \tau} \\
        \frac{\partial P_t}{\partial Vm} & \frac{\partial P_t}{\partial Va} & \frac{\partial P_t}{\partial P_f^{vsc}} & \frac{\partial P_t}{\partial P_t^{vsc}} & \frac{\partial P_t}{\partial Q_t^{vsc}} & \frac{\partial P_t}{\partial P_f^{hvdc}} & \frac{\partial P_t}{\partial P_t^{hvdc}} & \frac{\partial P_t}{\partial Q_f^{hvdc}} & \frac{\partial P_t}{\partial Q_t^{hvdc}} & \frac{\partial P_t}{\partial m} & \frac{\partial P_t}{\partial \tau} \\
        \frac{\partial Q_f}{\partial Vm} & \frac{\partial Q_f}{\partial Va} & \frac{\partial Q_f}{\partial P_f^{vsc}} & \frac{\partial Q_f}{\partial P_t^{vsc}} & \frac{\partial Q_f}{\partial Q_t^{vsc}} & \frac{\partial Q_f}{\partial P_f^{hvdc}} & \frac{\partial Q_f}{\partial P_t^{hvdc}} & \frac{\partial Q_f}{\partial Q_f^{hvdc}} & \frac{\partial Q_f}{\partial Q_t^{hvdc}} & \frac{\partial Q_f}{\partial m} & \frac{\partial Q_f}{\partial \tau} \\
        \frac{\partial Q_t}{\partial Vm} & \frac{\partial Q_t}{\partial Va} & \frac{\partial Q_t}{\partial P_f^{vsc}} & \frac{\partial Q_t}{\partial P_t^{vsc}} & \frac{\partial Q_t}{\partial Q_t^{vsc}} & \frac{\partial Q_t}{\partial P_f^{hvdc}} & \frac{\partial Q_t}{\partial P_t^{hvdc}} & \frac{\partial Q_t}{\partial Q_f^{hvdc}} & \frac{\partial Q_t}{\partial Q_t^{hvdc}} & \frac{\partial Q_t}{\partial m} & \frac{\partial Q_t}{\partial \tau}
    \end{matrix}
    \right]
    \times
    \left[
    \begin{matrix}
        \Delta Vm \quad \forall iu_{Vm}  \\
        \Delta Va \quad \forall iu_{Va} \\
        \Delta P_f_var_vsc \quad \forall u_vsc_{P_f}\\
        \Delta P_t_var_vsc \quad \forall u_vsc_{P_t}\\
        \Delta Q_t_var_vsc \quad \forall u_vsc_{Q_t}\\
        \Delta P_f^{hvdc} \quad \forall hvdc\\
        \Delta P_t^{hvdc} \quad \forall hvdc\\
        \Delta Q_f^{hvdc} \quad \forall hvdc\\
        \Delta Q_t^{hvdc} \quad \forall hvdc\\
        \Delta m \quad \forall u_cbr_{m}  \\
        \Delta \tau \quad \forall u_cbr_{\tau}
    \end{matrix}
    \right]
    =
    \left[
    \begin{matrix}
        \Delta P  \quad \forall ik_P\\
        \Delta Q \quad  \forall ik_Q\\
        \Delta loss_{vsc} \quad \forall vsc  \\
        \Delta loss_{hvdc} \quad \forall hvdc   \\
        \Delta inj_{hvdc} \quad \forall hvdc \\
        \Delta P_f \quad \forall k_cbr_{Pf}\\
        \Delta P_t \quad \forall k_cbr_{Pt}\\
        \Delta Q_f \quad \forall k_cbr_{Qf}\\
        \Delta Q_t \quad \forall k_cbr_{Qt}
    \end{matrix}
    \right]

Bus indices:

- :math:`iu_{Vm}` -> indices of buses where Vm is unknown.
- :math:`iu_{Va}` -> indices of buses where Va is unknown.
- :math:`ik_P` -> indices of nodes where P is set.
- :math:`ik_Q` -> indices of nodes where Q is set.

Controllable branch indices:

- :math:`cbr_{m}` -> Indices of the controllable branches that are using m to control.
- :math:`cbr_{\tau}` -> Indices of the controllable branches that are using tau to control.

- :math:`cbr=cbr_{m} \cup cbr_{\tau}` -> Indices of the controllable branches controlling with either m or tau.

- :math:`k_cbr_{Pf}` -> Indices of the controllable branches where Pf is controlled.
- :math:`k_cbr_{Pt}` -> Indices of the controllable branches where Pt is controlled.
- :math:`k_cbr_{Qt}` -> Indices of the controllable branches where Qf is controlled.
- :math:`k_cbr_{Qt}` -> Indices of the controllable branches where Qt is controlled.

VSC indices:

- :math:`vsc` -> Indices of the VSC converters.
- :math:`u_vsc_{Pf}` -> Indices of the VSC converters where Pf is unknown.
- :math:`u_vsc_{Pt}` -> Indices of the VSC converters where Pt is unknown.
- :math:`u_vsc_{Qt}` -> Indices of the VSC converters where Qt is unknown.
- :math:`k_vsc_{Pf}` -> Indices of the VSC converters where Pf is known.
- :math:`k_vsc_{Pt}` -> Indices of the VSC converters where Pt is known.
- :math:`k_vsc_{Qt}` -> Indices of the VSC converters where Qt is known.

HVDC indices:

- :math:`hvdc` -> Indices of the HVDC links.


Variables (unknowns):

- :math:`\Delta V_m` -> Voltage modules @ :math:`iu_{Vm}` -> indices of buses where Vm is unknown.
- :math:`\Delta V_a` -> Voltage angles @ :math:`iu_{Va}` -> indices of buses where Va is unknown.

- :math:`\Delta P_f^{vsc}` -> Active power "from" at VSC converters. @ :math:`u_vsc_{P_f}`
- :math:`\Delta P_t^{vsc}` -> Active power "to" at VSC converters. @ :math:`u_vsc_{P_t}`
- :math:`\Delta Q_t^{vsc}` -> Reactive power "to" at VSC converters. @ :math:`u_vsc_{Q_t}`

- :math:`\Delta P_f^{hvdc}` -> Active power "from" at HVDC lines. @ :math:`hvdc`.
- :math:`\Delta P_t^{hvdc}` -> Active power "to" at HVDC lines. @ :math:`hvdc`.
- :math:`\Delta Q_f^{hvdc}` -> Reactive power "from" at HVDC lines. @ :math:`hvdc`.
- :math:`\Delta Q_t^{hvdc}` -> Reactive power "to" at HVDC lines. @ :math:`hvdc`.

- :math:`\Delta m` -> Indices of the injection devices where the P is specified. @ :math:`u_cbr_{m}`
- :math:`\Delta \tau` -> Indices of the injection devices where the Q is specified. @ :math:`u_cbr_{\tau}`

Controls (knowns)

- :math:`\Delta P` -> Active power mismatch for the buses @ :math:`ik_P` -> indices of nodes where P is set.
- :math:`\Delta Q` -> Reactive power mismatch for buses @ :math:`ik_Q` -> indices of nodes where Q is set.

- :math:`\Delta loss_{vsc}` -> Power loss equation mismatch for the VSC devices @ :math:`vsc`

- :math:`\Delta loss_{hvdc}` -> Power loss equation mismatch for the HVDC devices @ :math:`hvdc`
- :math:`\Delta inj_{hvdc}` -> Power injected at the from or to side of HVDC devices depending on the HVDC angle droop eq. sign @ :math:`hvdc`

- :math:`\Delta {P_f}` -> Pf mismatch for controllable branches @ :math:`k_cbr_{Pf}`
- :math:`\Delta {P_t}` -> Pt mismatch for controllable branches @ :math:`k_cbr_{Pt}`
- :math:`\Delta {Q_f}` -> Qf mismatch for controllable branches @ :math:`k_cbr_{Qf}`
- :math:`\Delta {Q_t}` -> Qt mismatch for controllable branches @ :math:`k_cbr_{Qt}`

Set points
- :math:`S_{esp}`: array of nodal specified power
- :math:`P_f_set_cbr`: Controllable branch Pf set point
- :math:`P_t_set_cbr`: Controllable branch Pt set point
- :math:`Q_f_set_cbr`: Controllable branch Qf set point
- :math:`Q_t_set_cbr`: Controllable branch Qt set point

- :math:`P_f_set_vsc`: VSC Pf set point
- :math:`P_t_set_vsc`: VSC Pt set point
- :math:`Q_t_set_vsc`: VSC Qt set point

- :math:`P0_{hvdc}`: HVDC P set point


Equations:


Buses
_________________________

.. math::

    \Delta S = S_{esp} - S_{calc}

.. math::

    S_{calc} = V \cdot (Y \times V)^*
                + C_f^{cbr} \times S_f^{cbr} + C_t^{cbr} \times S_t^{cbr}
                + C_f^{vsc} \times P_f^{vsc} + C_t^{vsc} \times S_t^{vsc}
                + C_f^{hvdc} \times S_f^{hvdc} + C_t^{hvdc} \times S_t^{hvdc}


Controlable branches
_________________________

.. math::

    S_f^{cbr} = {{V_m}_f^2} \cdot {y_{ff}}_{k}^* + {V_m}_f^{\angle{\theta_f}} \cdot {V_m}_t^{\angle{-\theta_t}}  \cdot  {y_{ft}}_{k}^*

.. math::

    S_t^{cbr} = {{V_m}_t^2} \cdot {{y_{tt}}_{k}^*} + {V_m}_f^{\angle{-\theta_f}} \cdot {V_m}_t^{\angle{\theta_t}}  \cdot  {y_{tf}}_{k}^*

.. math::

    \Delta P_f = P_f_set_cbr - P_f^{cbr} \quad \forall k_cbr_{Pf}

.. math::

    \Delta P_t = P_t_set_cbr - P_t^{cbr} \quad \forall k_cbr_{Pt}

.. math::

    \Delta Q_f = Q_f_set_cbr - Q_f^{cbr} \quad \forall k_cbr_{Qf}

.. math::

    \Delta Q_t = Q_t_set_cbr - Q_t^{cbr} \quad \forall k_cbr_{Qt}


VSC
_____
We compose P_f^{vsc} and P_t^{vsc} and Q_t^{vsc} from the controlled values and the unknown values as follows:
.. math::

    P_f^{vsc}[k_vsc_{Pf}] = P_f_set_vsc
    P_t^{vsc}[k_vsc_{Pt}] = P_t_set_vsc
    Q_t^{vsc}[k_vsc_{Qt}] = Q_t_set_vsc

.. math::

    P_f^{vsc}[u_vsc_{Pf}] = P_f_var_vsc
    P_t^{vsc}[u_vsc_{Pt}] = P_t_var_vsc
    Q_t^{vsc}[u_vsc_{Qt}] = Q_t_var_vsc


.. math::

    P_f^{vsc} =  loss_{vsc} - P_t^{vsc}


.. math::

    loss_{vsc} = A + B \cdot \frac{\sqrt{{P_t^{vsc}}^2 + {Q_t^{vsc}}^2}}{Vm_t} + C \cdot \frac{{P_t^{vsc}}^2 + {Q_t^{vsc}}^2}{Vm_t^2}

.. math::

    S_t^{vsc} = P_t^{vsc} + 1j \cdot Q_t^{vsc}

.. math::

    \Delta loss_{vsc} = P_f^{vsc}  + P_t^{vsc} - loss_{vsc}



HVDC
__________

.. math::

    P_f^{hvdc} = loss_{hvdc} - P_t^{hvdc}

.. math::

    loss_{hvdc} = r \cdot {\frac{P_f^{hvdc}}{Vm_f}}^2

.. math::

    inj_{hvdc} = P0_{hvdc} + k_{hvdc} \cdot (Va_f - Va_t)


.. math::

    S_f^{hvdc} = P_f^{hvdc} + 1j \cdot Q_f^{hvdc}

.. math::

    S_t^{hvdc} = P_t^{hvdc} + 1j \cdot Q_t^{hvdc}

.. math::

    \Delta loss_{hvdc} = P_f^{hvdc} + P_t^{hvdc} - loss_{hvdc}

.. math::

    \Delta inj_{hvdc} = P_f^{hvdc} - inj_{hvdc}


