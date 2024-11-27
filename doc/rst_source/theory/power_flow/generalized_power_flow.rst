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
            \Delta Va \in cx_va \\
            \Delta Vm \in cx_vm \\
            \Delta P^{zip_{calc}} \in cx_{pinj}\\
            \Delta Q^{zip_{calc}} \in cx_{qinj}\\
            \Delta P_f \in cx_{pf} \\
            \Delta P_t \in cx_{pt} \\
            \Delta Q_f \in cx_{qf} \\
            \Delta Q_t \in cx_{qt} \\
            \Delta m \in cx_m\\
            \Delta \tau \in cx_{\tau}\\
        \end{bmatrix}
        =
        \begin{bmatrix}
            \Delta P \in cg_{acdc} \\
            \Delta Q \in cg_{ac} \\
            vsc_{loss} \in cg_{vsc}\\
            hvdc_{loss} \in cg_{hvdc} \\
            \Delta Pdroop_{hvdc} \in cg_{hvdc} \\
            \Delta TapP_f \in k\_controllable\_branches \\
            \Delta TapQ_f \in k\_controllable\_branches \\
            \Delta TapP_t \in k\_controllable\_branches \\
            \Delta TapQ_t \in k\_controllable\_branches
        \end{bmatrix}
    \end{equation}


Indices of the variables (X):

- :math:`cx_{va}` -> Indices of the buses where the voltage angles are unknown.
- :math:`cx_{vm}` -> Indices of the buses where the voltage modules are unknown.
- :math:`cx_{pinj}` -> Indices of the buses (with injection devices) where the active power injection are unknown.
- :math:`cx_{qinj}` -> Indices of the buses (with injection devices) where the reactive power injection are unknown.
- :math:`cx_{pf}` -> Indices of the controllable branches where Pf is unknown.
- :math:`cx_{pt}` -> Indices of the controllable branches where Pt is unknown.
- :math:`cx_{qf}` -> Indices of the controllable branches where Qf is unknown.
- :math:`cx_{qt}` -> Indices of the controllable branches where Qt is unknown.
- :math:`cx_{\tau}` -> Indices of the controllable branches where the tap angles are unknown.
- :math:`cx_{m}` -> Indices of the controllable branches where the tap modules are unknown.

Indices of the controls (RHS):
- :math:`cg_{acdc}` -> All the buses (AC and DC)
- :math:`ac` -> Indices of the ac buses.
- :math:`cg_{vsc}` -> all VSC converters.
- :math:`cg_{hvdc}` -> all Hvdc lines.
- :math:`k\_controllable\_branches` -> indices of the branches with impedance that are controllable using the tap.

.. math::

    S_{zip} = S0 + I0^* \cdot Vm + Y0^* \cdot Vm^2 + P_{zip_{calc}} + 1j \cdot Q_{zip_{calc}}


.. math::

    \Delta S = V \cdot (Y \times V)^* - S_{zip}
                + {S_f}[cg_{vsc}] \times C_{vsc_f} + {S_t}[cg_{vsc}] \times C_{vsc_t}
                + {S_f}[cg_{hvdc}] \times C_{hvdc_f} + {S_t}[cg_{hvdc}] \times C_{hvdc_t}
                + {S_f}[k\_controllable\_branches] \times C_f[k\_controllable\_branches, :]
                + {S_t}[k\_controllable\_branches] \times C_t[k\_controllable\_branches, :]


.. math::

    \Delta P = real(\Delta S)

.. math::

    \Delta P = imag(\Delta S)

.. math::

    vsc_{loss} =


- :math:`P0` -> Specified nodal active power (p.u.)
- :math:`Q0` -> Specified nodal reactive power (p.u.)

