.. _generalized_power_flow:

Generalized Power Flow
=============================

This formulation of a generalized power flow was introduced in the Master Thesis
of Raiyan Bin Zulkifli in 2024 (Generalised AC/DC Power Flow at UPC university).

.. figure:: ../figures/generalized_branch_models.png
    :alt: Generalized branch models.
    :scale: 50 %

The linearized system is:

.. math::

    \begin{equation}
        \left[
        \begin{matrix}
            \frac{\partial \Delta P}{\partial Vm} & \frac{\partial \Delta P}{\partial Va} & \frac{\partial \Delta P}{\partial P^{\text{zip}}} & \frac{\partial \Delta P}{\partial Q^{\text{zip}}} & \frac{\partial \Delta P}{\partial P_f} & \frac{\partial \Delta P}{\partial P_t} & \frac{\partial \Delta P}{\partial Q_f} & \frac{\partial \Delta P}{\partial Q_t} & \frac{\partial \Delta P}{\partial m} & \frac{\partial \Delta P}{\partial \tau} \\
            \frac{\partial \Delta Q}{\partial Vm} & \frac{\partial \Delta Q}{\partial Va} & \frac{\partial \Delta Q}{\partial P^{\text{zip}}} & \frac{\partial \Delta Q}{\partial Q^{\text{zip}}} & \frac{\partial \Delta Q}{\partial P_f} & \frac{\partial \Delta Q}{\partial P_t} & \frac{\partial \Delta Q}{\partial Q_f} & \frac{\partial \Delta Q}{\partial Q_t} & \frac{\partial \Delta Q}{\partial m} & \frac{\partial \Delta Q}{\partial \tau} \\
            \frac{\partial g_{\text{lossACDC}}}{\partial Vm} & \frac{\partial g_{\text{lossACDC}}}{\partial Va} & \frac{\partial g_{\text{lossACDC}}}{\partial P^{\text{zip}}} & \frac{\partial g_{\text{lossACDC}}}{\partial Q^{\text{zip}}} & \frac{\partial g_{\text{lossACDC}}}{\partial P_f} & \frac{\partial g_{\text{lossACDC}}}{\partial P_t} & \frac{\partial g_{\text{lossACDC}}}{\partial Q_f} & \frac{\partial g_{\text{lossACDC}}}{\partial Q_t} & \frac{\partial g_{\text{lossACDC}}}{\partial m} & \frac{\partial g_{\text{lossACDC}}}{\partial \tau} \\
            \frac{\partial g_{\text{lossHVDC}}}{\partial Vm} & \frac{\partial g_{\text{lossHVDC}}}{\partial Va} & \frac{\partial g_{\text{lossHVDC}}}{\partial P^{\text{zip}}} & \frac{\partial g_{\text{lossHVDC}}}{\partial Q^{\text{zip}}} & \frac{\partial g_{\text{lossHVDC}}}{\partial P_f} & \frac{\partial g_{\text{lossHVDC}}}{\partial P_t} & \frac{\partial g_{\text{lossHVDC}}}{\partial Q_f} & \frac{\partial g_{\text{lossHVDC}}}{\partial Q_t} & \frac{\partial g_{\text{lossHVDC}}}{\partial m} & \frac{\partial g_{\text{lossHVDC}}}{\partial \tau} \\
            \frac{\partial g_{\text{injHVDC}}}{\partial Vm} & \frac{\partial g_{\text{injHVDC}}}{\partial Va} & \frac{\partial g_{\text{injHVDC}}}{\partial P^{\text{zip}}} & \frac{\partial g_{\text{injHVDC}}}{\partial Q^{\text{zip}}} & \frac{\partial g_{\text{injHVDC}}}{\partial P_f} & \frac{\partial g_{\text{injHVDC}}}{\partial P_t} & \frac{\partial g_{\text{injHVDC}}}{\partial Q_f} & \frac{\partial g_{\text{injHVDC}}}{\partial Q_t} & \frac{\partial g_{\text{injHVDC}}}{\partial m} & \frac{\partial g_{\text{injHVDC}}}{\partial \tau} \\
            \frac{\partial P_f}{\partial Vm} & \frac{\partial P_f}{\partial Va} & \frac{\partial P_f}{\partial P^{\text{zip}}} & \frac{\partial P_f}{\partial Q^{\text{zip}}} & \frac{\partial P_f}{\partial P_f} & \frac{\partial P_f}{\partial P_t} & \frac{\partial P_f}{\partial Q_f} & \frac{\partial P_f}{\partial Q_t} & \frac{\partial P_f}{\partial m} & \frac{\partial P_f}{\partial \tau} \\
            \frac{\partial P_t}{\partial Vm} & \frac{\partial P_t}{\partial Va} & \frac{\partial P_t}{\partial P^{\text{zip}}} & \frac{\partial P_t}{\partial Q^{\text{zip}}} & \frac{\partial P_t}{\partial P_f} & \frac{\partial P_t}{\partial P_t} & \frac{\partial P_t}{\partial Q_f} & \frac{\partial P_t}{\partial Q_t} & \frac{\partial P_t}{\partial m} & \frac{\partial P_t}{\partial \tau} \\
            \frac{\partial Q_f}{\partial Vm} & \frac{\partial Q_f}{\partial Va} & \frac{\partial Q_f}{\partial P^{\text{zip}}} & \frac{\partial Q_f}{\partial Q^{\text{zip}}} & \frac{\partial Q_f}{\partial P_f} & \frac{\partial Q_f}{\partial P_t} & \frac{\partial Q_f}{\partial Q_f} & \frac{\partial Q_f}{\partial Q_t} & \frac{\partial Q_f}{\partial m} & \frac{\partial Q_f}{\partial \tau} \\
            \frac{\partial Q_t}{\partial Vm} & \frac{\partial Q_t}{\partial Va} & \frac{\partial Q_t}{\partial P^{\text{zip}}} & \frac{\partial Q_t}{\partial Q^{\text{zip}}} & \frac{\partial Q_t}{\partial P_f} & \frac{\partial Q_t}{\partial P_t} & \frac{\partial Q_t}{\partial Q_f} & \frac{\partial Q_t}{\partial Q_t} & \frac{\partial Q_t}{\partial m} & \frac{\partial Q_t}{\partial \tau}
        \end{matrix}
        \right]
        \times
        \left[
        \begin{matrix}
            \textcolor{orange}{\Delta Vm \;\; \forall iu_{Vm}}  \\
            \textcolor{orange}{\Delta Va \;\; \forall iu_{Va}} \\
            \Delta P_f^{vsc} \;\; \forall u_vsc_{P_f}\\
            \Delta P_t^{vsc} \;\; \forall u_vsc_{P_t}\\
            \Delta Q_t^{vsc} \;\; \forall u_vsc_{Q_t}\\
            \Delta P_f^{hvdc} \;\; \forall hvdc\\
            \Delta P_t^{hvdc} \;\; \forall hvdc\\
            \Delta Q_f^{hvdc} \;\; \forall hvdc\\
            \Delta Q_t^{hvdc} \;\; \forall hvdc\\
            \textcolor{orange}{\Delta m \;\; \forall ku_{m}}  \\
            \textcolor{orange}{\Delta \tau \;\; \forall ku_{\tau}}
        \end{matrix}
        \right]
        =
        \left[
        \begin{matrix}
            \Delta P  \;\; \forall ik_P\\
            \Delta Q \;\;  \forall ik_Q\\
            \Delta gloss_{vsc} \;\; \forall vsc}  \\
            \Delta gloss_{hvdc} \;\; \forall hvdc}   \\
            \Delta ginj_{hvdc} \;\; \forall hvdc} \\
            \Delta P_f \;\; \forall k_cbr_{Pf}\\
            \Delta P_t \;\; \forall k_cbr_{Pt}\\
            \Delta Q_f \;\; \forall k_cbr_{Qf}\\
            \Delta Q_t \;\; \forall k_cbr_{Qt}
        \end{matrix}
        \right]
    \end{equation}

Global Sets:

- :math:`cbr_{m}` -> Indices of the controllable branches that are using m to control.
- :math:`cbr_{\tau}` -> Indices of the controllable branches that are using tau to control.

- :math:`cbr=cbr_{m} \cup cbr_{\tau}` -> Indices of the controllable branches controlling with either m or tau.

- :math:`k_cbr_{Pf}` -> Indices of the controllable branches where Pf is controlled.
- :math:`k_cbr_{Pt}` -> Indices of the controllable branches where Pt is controlled.
- :math:`k_cbr_{Qt}` -> Indices of the controllable branches where Qf is controlled.
- :math:`k_cbr_{Qt}` -> Indices of the controllable branches where Qt is controlled.

- :math:`vsc` -> Indices of the VSC converters.
- :math:`u_vsc_{Pf}` -> Indices of the VSC converters where Pf is unknown.
- :math:`u_vsc_{Pt}` -> Indices of the VSC converters where Pt is unknown.
- :math:`u_vsc_{Qt}` -> Indices of the VSC converters where Qt is unknown.

- :math:`hvdc` -> Indices of the HVDC links.

- :math:`Inj_P` -> Indices of the injection devices where P is specified.
- :math:`Inj_Q` -> Indices of the injection devices where Q is specified.

Variable sets (unknowns):

- :math:`\Delta V_m` -> Voltage modules @ :math:`iu_{Vm}` -> indices of buses where Vm is unknown.
- :math:`\Delta V_a` -> Voltage angles @ :math:`iu_{Va}` -> indices of buses where Va is unknown.

- :math:`\Delta P_f^{vsc}` -> Active power "from" at VSC converters. @ :math:`u_vsc_{P_f}`
- :math:`\Delta P_t^{vsc}` -> Active power "to" at VSC converters. @ :math:`u_vsc_{P_t}`
- :math:`\Delta Q_t^{vsc}` -> Reactive power "to" at VSC converters. @ :math:`u_vsc_{Q_t}`

- :math:`\Delta P_f^{hvdc}` -> Active power "from" at HVDC lines. @ :math:`hvdc`.
- :math:`\Delta P_t^{hvdc}` -> Active power "to" at HVDC lines. @ :math:`hvdc`.
- :math:`\Delta Q_f^{hvdc}` -> Reactive power "from" at HVDC lines. @ :math:`hvdc`.
- :math:`\Delta Q_t^{hvdc}` -> Reactive power "to" at HVDC lines. @ :math:`hvdc`.

- :math:`\Delta m` -> Indices of the injection devices where the P is specified. @ :math:`ku_{m}` -> :math:`cbr_{m}`
- :math:`\Delta \tau` -> Indices of the injection devices where the Q is specified. @ :math:`ku_{\tau}` -> :math:`cbr_{\tau}`

Controls (knowns)

- :math:`\Delta P` -> Active power mismatch for the buses @ :math:`ik_P` -> indices of nodes where P is set.
- :math:`\Delta Q` -> Reactive power mismatch for buses @ :math:`ik_Q` -> indices of nodes where Q is set.

- :math:`\Delta gloss_{vsc}` -> Power loss equation mismatch for the VSC devices @ :math:`vsc`

- :math:`\Delta gloss_{hvdc}` -> Power loss equation mismatch for the HVDC devices @ :math:`hvdc`
- :math:`\Delta ginj_{hvdc}` -> Power injected at the from or to side of HVDC devices depending on the HVDC angle droop eq. sign @ :math:`hvdc`

- :math:`\Delta {P_f}` -> Pf mismatch for controllable branches @ :math:`k_cbr_{Pf}`
- :math:`\Delta {P_t}` -> Pt mismatch for controllable branches @ :math:`k_cbr_{Pt}`
- :math:`\Delta {Q_f}` -> Qf mismatch for controllable branches @ :math:`k_cbr_{Qf}`
- :math:`\Delta {Q_t}` -> Qt mismatch for controllable branches @ :math:`k_cbr_{Qt}`


Equations:


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

    \Delta P_f = P_f_set - P_f^{cbr} \quad \forall k_cbr_{Pf}

.. math::

    \Delta P_t = P_t_set - P_t^{cbr} \quad \forall k_cbr_{Pt}

.. math::

    \Delta Q_f = Q_f_set - Q_f^{cbr} \quad \forall k_cbr_{Qf}

.. math::

    \Delta Q_t = Q_t_set - Q_t^{cbr} \quad \forall k_cbr_{Qt}


VSC
_____

.. math::

    P_f^{vsc} =  gloss_{vsc} - P_t^{vsc}


.. math::

    gloss_{vsc} = A + B \cdot \frac{\sqrt{{P_t^{vsc}}^2 + {Q_t^{vsc}}^2}}{Vm_t} + C \cdot \frac{{P_t^{vsc}}^2 + {Q_t^{vsc}}^2}{Vm_t^2}

.. math::

    S_t^{vsc} = P_t^{vsc} + 1j \cdot Q_t^{vsc}

.. math::

    \Delta gloss_{vsc} = P_f^{vsc}  + P_t^{vsc} - gloss_{vsc}


HVDC
__________

.. math::

    P_f^{hvdc} = gloss_{hvdc} - P_t^{hvdc}

.. math::

    gloss_{hvdc} = r \cdot {\frac{P_f^{hvdc}}{Vm_f}}^2

.. math::

    ginj_{hvdc} = P0_{hvdc} + k_{hvdc} \cdot (Va_f - Va_t)


.. math::

    S_f^{hvdc} = P_f^{hvdc} + 1j \cdot Q_f^{hvdc}

.. math::

    S_t^{hvdc} = P_t^{hvdc} + 1j \cdot Q_t^{hvdc}

.. math::

    \Delta gloss_{hvdc} = P_f^{hvdc} + P_t^{hvdc} - gloss_{hvdc}

.. math::

    \Delta ginj_{hvdc} = P_f^{hvdc} - ginj_{hvdc}


