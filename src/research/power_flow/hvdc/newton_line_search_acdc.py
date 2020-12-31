# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

from scipy.sparse.linalg import spsolve
import numpy as np
from GridCal.Engine import compile_snapshot_circuit, SnapshotData, TransformerControlType, ConverterControlType, FileOpen

import os
import time
from scipy.sparse import lil_matrix, diags
import scipy.sparse as sp


def determine_branch_indices(circuit: SnapshotData):
    """
    This function fills in the lists of indices to control different magnitudes

    :param circuit: Instance of AcDcSnapshotCircuit
    :returns idx_sh, idx_qz, idx_vf, idx_vt, idx_qt

    VSC Control modes:

    in the paper's scheme:
    from -> DC
    to   -> AC

    |   Mode    |   const.1 |   const.2 |   type    |
    -------------------------------------------------
    |   1       |   theta   |   Vac     |   I       |
    |   2       |   Pf      |   Qac     |   I       |
    |   3       |   Pf      |   Vac     |   I       |
    -------------------------------------------------
    |   4       |   Vdc     |   Qac     |   II      |
    |   5       |   Vdc     |   Vac     |   II      |
    -------------------------------------------------
    |   6       | Vdc droop |   Qac     |   III     |
    |   7       | Vdc droop |   Vac     |   III     |
    -------------------------------------------------

    Indices where each control goes:
    mismatch  →  |  ∆Pf	Qf	Q@f Q@t	∆Qt
    variable  →  |  Ɵsh	Beq	m	m	Beq
    Indices   →  |  Ish	Iqz	Ivf	Ivt	Iqt
    ------------------------------------
    VSC 1	     |  -	1	-	1	-   |   AC voltage control (voltage “to”)
    VSC 2	     |  1	1	-	-	1   |   Active and reactive power control
    VSC 3	     |  1	1	-	1	-   |   Active power and AC voltage control
    VSC 4	     |  -	-	1	-	1   |   Dc voltage and Reactive power flow control
    VSC 5	     |  -	-	-	1	1   |   Ac and Dc voltage control
    ------------------------------------
    Transformer 0|	-	-	-	-	-   |   Fixed transformer
    Transformer 1|	1	-	-	-	-   |   Phase shifter → controls power
    Transformer 2|	-	-	1	-	-   |   Control the voltage at the “from” side
    Transformer 3|	-	-	-	1	-   |   Control the voltage at the “to” side
    Transformer 4|	1	-	1	-	-   |   Control the power flow and the voltage at the “from” side
    Transformer 5|	1	-	-	1	-   |   Control the power flow and the voltage at the “to” side
    ------------------------------------

    """
        
    # indices in the global branch scheme
    iPfsh = list()  # indices of the branches controlling Pf flow
    iQfma = list()
    iBeqz = list()  # indices of the branches when forcing the Qf flow to zero (aka "the zero condition")
    iBeqv = list()  # indices of the branches when controlling Vf
    iVtma = list()  # indices of the branches when controlling Vt
    iQtma = list()  # indices of the branches controlling the Qt flow
    iPfdp = list()
    iVscL = list()  # indices of the converters

    for k, tpe in enumerate(circuit.branch_data.control_mode):

        if tpe == TransformerControlType.fixed:
            pass

        elif tpe == TransformerControlType.power:
            iPfsh.append(k)

        elif tpe == TransformerControlType.v_to:
            iVtma.append(k)

        elif tpe == TransformerControlType.power_v_to:
            iPfsh.append(k)
            iVtma.append(k)

        # VSC ----------------------------------------------------------------------------------------------------------
        elif tpe == ConverterControlType.type_1_free:  # 1a:Free
            iBeqz.append(k)
            iVscL.append(k)

        elif tpe == ConverterControlType.type_1_pf:  # 1b:Pflow
            iPfsh.append(k)
            iBeqz.append(k)

            iVscL.append(k)

        elif tpe == ConverterControlType.type_1_qf:  # 1c:Qflow
            iBeqz.append(k)
            iQtma.append(k)

            iVscL.append(k)

        elif tpe == ConverterControlType.type_1_vac:  # 1d:Vac
            iBeqz.append(k)
            iVtma.append(k)

            iVscL.append(k)

        elif tpe == ConverterControlType.type_2_vdc:  # 2a:Vdc
            iPfsh.append(k)
            iBeqv.append(k)

            iVscL.append(k)

        elif tpe == ConverterControlType.type_2_vdc_pf:  # 2b:Vdc+Pflow
            iPfsh.append(k)
            iBeqv.append(k)

            iVscL.append(k)

        elif tpe == ConverterControlType.type_3:  # 3a:Droop
            iPfsh.append(k)
            iBeqz.append(k)
            iPfdp.append(k)

            iVscL.append(k)

        elif tpe == ConverterControlType.type_4:  # 4a:Droop-slack
            iPfdp.append(k)

            iVscL.append(k)

        elif tpe == 0:
            pass  # required for the no-control case

        else:
            raise Exception('Unknown control type:' + str(tpe))

    # FUBM- Saves the "from" bus identifier for Vf controlled by Beq
    #  (Converters type II for Vdc control)
    VfBeqbus = circuit.F[iBeqv]

    # FUBM- Saves the "to"   bus identifier for Vt controlled by ma
    #  (Converters and Transformers)
    Vtmabus = circuit.T[iVtma]

    return iPfsh, iQfma, iBeqz, iBeqv, iVtma, iQtma, iPfdp, iVscL, VfBeqbus, Vtmabus


def compute_converter_losses(V, It, F, alpha1, alpha2, alpha3, iVscL):
    """
    Compute the converter losses according to the IEC 62751-2
    :param V:
    :param It:
    :param F:
    :param alpha1:
    :param alpha2:
    :param alpha3:
    :param iVscL:
    :return:
    """
    # FUBM- Standard IEC 62751-2 Ploss Correction for VSC losses
    Ivsc = np.abs(It[iVscL])
    PLoss_IEC = alpha3[iVscL] * np.power(Ivsc, 2)
    PLoss_IEC += alpha2[iVscL] * np.power(Ivsc, 2)
    PLoss_IEC += alpha1[iVscL]

    # compute G-switch
    Gsw = np.zeros(len(F))
    Gsw[iVscL] = PLoss_IEC / np.power(np.abs(V[F[iVscL]]), 2)  # FUBM- VSC Gsw

    return Gsw


def compile_y_acdc(branch_active, Cf, Ct, C_bus_shunt, shunt_admittance, shunt_active, ys, B, Sbase,
                   m, theta, Beq, Gsw):
    """
    Compile the admittance matrices using the variable elements
    :param branch_active:
    :param Cf:
    :param Ct:
    :param C_bus_shunt:
    :param shunt_admittance:
    :param shunt_active:
    :param ys:
    :param B:
    :param Sbase:
    :param m: array of tap modules (for all branches, regardless of their type)
    :param theta: array of tap angles (for all branches, regardless of their type)
    :param Beq: Array of equivalent susceptance
    :param Gsw: Array of branch (converter) losses
    :return: Ybus, Yf, Yt, tap
    """

    # form the connectivity matrices with the states applied -------------------------------------------------------
    br_states_diag = sp.diags(branch_active)
    Cf = br_states_diag * Cf
    Ct = br_states_diag * Ct

    # SHUNT --------------------------------------------------------------------------------------------------------
    Yshunt_from_devices = C_bus_shunt * (shunt_admittance * shunt_active / Sbase)
    yshunt_f = Cf * Yshunt_from_devices
    yshunt_t = Ct * Yshunt_from_devices

    # form the admittance matrices ---------------------------------------------------------------------------------
    bc2 = 1j * B / 2  # shunt conductance
    # mp = circuit.k * m  # k is already filled with the appropriate value for each type of branch

    tap = m * np.exp(1.0j * theta)

    """
    Beq= stat .* branch(:, BEQ);                                %%FUBM- VSC Equivalent Reactor for absorbing or supplying reactive power and zero constraint in DC side   
    Gsw= stat .* branch(:, GSW);                                %%FUBM- VSC Switching losses
    k2 = branch(:, K2);                                         %%FUBM- VSC constant depending of how many levels does the VSC is simulating. Default k2 for branches = 1, Default k2 for VSC = sqrt(3)/2
    
    Ytt = Ys + 1j*Bc/2;
    Yff = Gsw+( (Ytt+1j*Beq) ./ ((k2.^2).*tap .* conj(tap))  ); %%FUBM- FUBM formulation
    Yft = - Ys ./ ( k2.*conj(tap) );                            %%FUBM- FUBM formulation
    Ytf = - Ys ./ ( k2.*tap );  
    
    """

    # compose the primitives
    Yff = Gsw + (ys + bc2 + 1.0j * Beq + yshunt_f) / (m * m)
    Yft = -ys / np.conj(tap)
    Ytf = -ys / tap
    Ytt = ys + bc2 + yshunt_t

    # compose the matrices
    Yf = sp.diags(Yff) * Cf + sp.diags(Yft) * Ct
    Yt = sp.diags(Ytf) * Cf + sp.diags(Ytt) * Ct
    Ybus = sp.csc_matrix(Cf.T * Yf + Ct.T * Yt)

    return Ybus, Yf, Yt, tap


def dSbus_dV(Ybus, V):
    """
    Derivatives of the power injections w.r.t the voltage
    :param Ybus: Admittance matrix
    :param V: complex voltage arrays
    :return: dSbus_dVa, dSbus_dVm
    """
    diagV = diags(V)
    diagVnorm = diags(V / np.abs(V))
    Ibus = Ybus * V
    diagIbus = diags(Ibus)

    dSbus_dVa = 1j * diagV * np.conj(diagIbus - Ybus * diagV)  # dSbus / dVa
    dSbus_dVm = diagV * np.conj(Ybus * diagVnorm) + np.conj(diagIbus) * diagVnorm  # dSbus / dVm

    return dSbus_dVa, dSbus_dVm


def dSbr_dV(Yf, Yt, V, F, T, Cf, Ct):
    """
    Derivatives of the branch power w.r.t the branch voltage modules and angles
    :param Yf: Admittances matrix of the branches with the "from" buses
    :param Yt: Admittances matrix of the branches with the "to" buses
    :param V: Array of voltages
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Cf: Connectivity matrix of the branches with the "from" buses
    :param Ct: Connectivity matrix of the branches with the "to" buses
    :return: dSf_dVa, dSf_dVm, dSt_dVa, dSt_dVm
    """
    Yfc = np.conj(Yf)
    Ytc = np.conj(Yt)
    Vc = np.conj(V)
    Ifc = Yfc * Vc  # conjugate  of "from"  current
    Itc = Ytc * Vc  # conjugate of "to" current

    diagIfc = diags(Ifc)
    diagItc = diags(Itc)
    Vf = V[F]
    Vt = V[T]
    diagVf = diags(Vf)
    diagVt = diags(Vt)
    diagVc = diags(Vc)

    Vnorm = V / np.abs(V)
    diagVnorm = diags(Vnorm)
    diagV = diags(V)

    CVf = Cf * diagV
    CVt = Ct * diagV
    CVnf = Cf * diagVnorm
    CVnt = Ct * diagVnorm

    dSf_dVa = 1j * (diagIfc * CVf - diagVf * Yfc * diagVc)
    dSf_dVm = diagVf * np.conj(Yf * diagVnorm) + diagIfc * CVnf
    dSt_dVa = 1j * (diagItc * CVt - diagVt * Ytc * diagVc)
    dSt_dVm = diagVt * np.conj(Yt * diagVnorm) + diagItc * CVnt

    return dSf_dVa, dSf_dVm, dSt_dVa, dSt_dVm


def d_dsh(nb, nl, iPxsh, F, T, Ys, k2, tap, V):
    """
    This function computes the derivatives of Sbus, Sf and St w.r.t. Ɵsh
    - dSbus_dPfsh, dSf_dPfsh, dSt_dPfsh -> if iPxsh=iPfsh
    - dSbus_dPfdp, dSf_dPfdp, dSt_dPfdp -> if iPxsh=iPfdp

    :param nb: number of buses
    :param nl: number of branches
    :param iPxsh: array of indices {iPfsh or iPfdp}
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Ys: Array of branch series admittances
    :param k2: Array of "k2" parameters
    :param tap: Array of branch complex taps (ma * exp(1j * theta_sh)
    :param V: Array of complex voltages
    :return:
        - dSbus_dPfsh, dSf_dPfsh, dSt_dPfsh -> if iPxsh=iPfsh
        - dSbus_dPfdp, dSf_dPfdp, dSt_dPfdp -> if iPxsh=iPfdp
    """
    dSbus_dPxsh = lil_matrix((nb, len(iPxsh)), dtype=complex)
    dSf_dshx2 = lil_matrix((nl, len(iPxsh)), dtype=complex)
    dSt_dshx2 = lil_matrix((nl, len(iPxsh)), dtype=complex)

    for k, idx in enumerate(iPxsh):
        f = F[idx]
        t = T[idx]

        # Partials of Ytt, Yff, Yft and Ytf w.r.t. Ɵ shift
        ytt_dsh = 0.0
        yff_dsh = 0.0
        yft_dsh = -Ys[idx] / (-1j * k2[idx] * np.conj(tap[idx]))
        ytf_dsh = -Ys[idx] / (1j * k2[idx] * tap[idx])

        # Partials of S w.r.t. Ɵ shift
        val_f = V[f] * np.conj(yft_dsh * V[t])
        val_t = V[t] * np.conj(ytf_dsh * V[f])

        dSbus_dPxsh[f, k] = val_f
        dSbus_dPxsh[t, k] = val_t

        # Partials of Sf w.r.t. Ɵ shift (makes sense that this is ∂Sbus/∂Pxsh assigned to the "from" bus)
        dSf_dshx2[idx, k] = val_f

        # Partials of St w.r.t. Ɵ shift (makes sense that this is ∂Sbus/∂Pxsh assigned to the "to" bus)
        dSt_dshx2[idx, k] = val_t

    return dSbus_dPxsh.tocsc(), dSf_dshx2.tocsc(), dSt_dshx2.tocsc()


def d_dma(nb, nl, iXxma, F, T, Ys, k2, tap, ma, Bc, Beq, V):
    """
    Useful for the calculation of
    - dSbus_dQfma, dSf_dQfma, dSt_dQfma  -> wih iXxma=iQfma
    - dSbus_dQtma, dSf_dQtma, dSt_dQtma  -> wih iXxma=iQtma
    - dSbus_dVtma, dSf_dVtma, dSt_dVtma  -> wih iXxma=iVtma

    :param nb: Number of buses
    :param nl: Number of branches
    :param iXxma: Array of indices {iQfma, iQtma, iVtma}
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Ys: Array of branch series admittances
    :param k2: Array of "k2" parameters
    :param tap: Array of branch complex taps (ma * exp(1j * theta_sh)
    :param ma: Array of tap modules (this is to avoid extra calculations)
    :param Bc: Array of branch total shunt susceptance values (sum of the two legs)
    :param Beq: Array of regulation susceptance of the FUBM model
    :param V:Array of complex voltages

    :return:
    - dSbus_dQfma, dSf_dQfma, dSt_dQfma  -> if iXxma=iQfma
    - dSbus_dQtma, dSf_dQtma, dSt_dQtma  -> if iXxma=iQtma
    - dSbus_dVtma, dSf_dVtma, dSt_dVtma  -> if iXxma=iVtma
    """
    # Declare the derivative
    dSbus_dmax2 = lil_matrix((nb, len(iXxma)), dtype=complex)
    dSf_dmax2 = lil_matrix((nl, len(iXxma)), dtype=complex)
    dSt_dmax2 = lil_matrix((nl, len(iXxma)), dtype=complex)

    for k, idx in enumerate(iXxma):
        f = F[idx]
        t = T[idx]

        YttB = Ys[idx] + 1j * Bc[idx] / 2 + 1j * Beq[idx]

        # Partials of Ytt, Yff, Yft and Ytf w.r.t.ma
        dyff_dma = -2 * YttB / (np.power(k2[idx], 2) * np.power(ma[idx], 3))
        dyft_dma = Ys[idx] / (k2[idx] * ma[idx] * np.conj(tap[idx]))
        dytf_dma = Ys[idx] / (k2[idx] * ma[idx] * tap[idx])
        dytt_dma = 0

        # Partials of S w.r.t.ma
        val_f = V[f] * np.conj(dyff_dma * V[f] + dyft_dma * V[t])
        val_t = V[t] * np.conj(dytf_dma * V[f] + dytt_dma * V[t])
        dSbus_dmax2[f, k] = val_f
        dSbus_dmax2[t, k] = val_t

        dSf_dmax2[idx, k] = val_f
        dSt_dmax2[idx, k] = val_f

    return dSbus_dmax2.tocsc(), dSf_dmax2.tocsc(), dSt_dmax2.tocsc()


def d_dBeq(nb, nl, iBeqx, F, T, V, ma, k2):
    """
    Compute the derivatives of:
    - dSbus_dBeqz, dSf_dBeqz, dSt_dBeqz -> iBeqx=iBeqz
    - dSbus_dBeqv, dSf_dBeqv, dSt_dBeqv -> iBeqx=iBeqv

    :param nb: Number of buses
    :param nl: Number of branches
    :param iBeqx: array of indices {iBeqz, iBeqv}
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param V:Array of complex voltages
    :param ma: Array of branch taps modules
    :param k2: Array of "k2" parameters

    :return:
    - dSbus_dBeqz, dSf_dBeqz, dSt_dBeqz -> if iBeqx=iBeqz
    - dSbus_dBeqv, dSf_dBeqv, dSt_dBeqv -> if iBeqx=iBeqv
    """
    # Declare the derivative
    dSbus_dBeqx = lil_matrix((nb, len(iBeqx)), dtype=complex)
    dSf_dBeqx = lil_matrix((nl, len(iBeqx)), dtype=complex)
    dSt_dBeqx = lil_matrix((nl, len(iBeqx)), dtype=complex)

    for k, idx in enumerate(iBeqx):
        f = F[idx]
        t = T[idx]

        # Partials of Ytt, Yff, Yft and Ytf w.r.t.Beq
        dyff_dBeq = 1j / np.power(k2[idx] * ma[idx], 2.0)
        dyft_dBeq = 0
        dytf_dBeq = 0
        dytt_dBeq = 0

        # Partials of S w.r.t.Beq
        val_f = V[f] * np.conj(dyff_dBeq * V[f] + dyft_dBeq * V[t])
        val_t = V[t] * np.conj(dytf_dBeq * V[f] + dytt_dBeq * V[t])

        dSbus_dBeqx[f, k] = val_f
        dSbus_dBeqx[t, k] = val_t

        # Partials of Sf w.r.t.Beq
        dSf_dBeqx[idx, k] = val_f

        # Partials of St w.r.t.Beq
        dSt_dBeqx[idx, k] = val_t

    return dSbus_dBeqx.tocsc(), dSf_dBeqx.tocsc(), dSt_dBeqx.tocsc()


def fubm_jacobian(nb, nl, iPfsh, iPfdp, iQfma, iQtma, iVtma, iBeqz, iBeqv, VfBeqbus, Vtmabus,
                  F, T, Ys, k2, tap, ma, Bc, Beq, Kdp, V, Ybus, Yf, Yt, Cf, Ct, pvpq, pq):
    """
    Compute the FUBM jacobian
    :param nb: number of buses
    :param nl: Number of lines
    :param iPfsh: indices of the Pf controlled branches
    :param iPfdp: indices of the droop controlled branches
    :param iQfma: indices of the Qf controlled branches
    :param iQtma: Indices of the Qt controlled branches
    :param iVtma: Indices of the Vt controlled branches
    :param iBeqz: Indices of the Qf controlled branches
    :param iBeqv: Indices of the Vf Controlled branches
    :param F: Array of "from" bus indices
    :param T: Array of "to" bus indices
    :param Ys: Array of branch series admittances
    :param k2: Array of branch converter losses
    :param tap: Array of complex tap values {remember tap = ma * exp(1j * theta) }
    :param ma: Array of tap modules
    :param Bc: Array of branch full susceptances
    :param Beq: Array of brach equivalent (variable) susceptances
    :param Kdp: Array of branch converter droop constants
    :param V: Array of complex bus voltages
    :param Ybus: Admittance matrix
    :param Yf: Admittances matrix of the branches with the "from" buses
    :param Yt: Admittances matrix of the branches with the "to" buses
    :param Cf: Connectivity matrix of the branches with the "from" buses
    :param Ct: Connectivity matrix of the branches with the "to" buses
    :param pvpq: Array of pv and then pq bus indices (not sorted)
    :param pq: Array of PQ bus indices
    :return: FUBM Jacobian matrix
    """

    # compose the derivatives of the power injections w.r.t Va and Vm
    dSbus_dVa, dSbus_dVm = dSbus_dV(Ybus, V)

    # compose the derivatives of the branch flow w.r.t Va and Vm
    dSf_dVa, dSf_dVm, dSt_dVa, dSt_dVm = dSbr_dV(Yf, Yt, V, F, T, Cf, Ct)

    # compose the derivatives w.r.t theta sh
    dSbus_dPfsh, dSf_dPfsh, dSt_dPfsh = d_dsh(nb, nl, iPfsh, F, T, Ys, k2, tap, V)
    dSbus_dPfdp, dSf_dPfdp, dSt_dPfdp = d_dsh(nb, nl, iPfdp, F, T, Ys, k2, tap, V)

    # compose the derivative w.r.t ma
    dSbus_dQfma, dSf_dQfma, dSt_dQfma = d_dma(nb, nl, iQfma, F, T, Ys, k2, tap, ma, Bc, Beq, V)
    dSbus_dQtma, dSf_dQtma, dSt_dQtma = d_dma(nb, nl, iQtma, F, T, Ys, k2, tap, ma, Bc, Beq, V)
    dSbus_dVtma, dSf_dVtma, dSt_dVtma = d_dma(nb, nl, iVtma, F, T, Ys, k2, tap, ma, Bc, Beq, V)

    # compose the derivatives w.r.t Beq
    dSbus_dBeqz, dSf_dBeqz, dSt_dBeqz = d_dBeq(nb, nl, iBeqz, F, T, V, ma, k2)
    dSbus_dBeqv, dSf_dBeqv, dSt_dBeqv = d_dBeq(nb, nl, iBeqv, F, T, V, ma, k2)

    # Voltage Droop Control Partials (it is more convenient to have them here...) --------------

    # Partials of Pfdp w.r.t. Va
    dPfdp_dVa = -dSf_dVa.real

    # Partials of Pfdp w.r.t. Vm
    dVmf_dVm = lil_matrix((nl, nb))
    dVmf_dVm[iPfdp, :] = Cf[iPfdp, :]
    dPfdp_dVm = -dSf_dVm.real + diags(Kdp) * dVmf_dVm

    # Partials of Pfdp w.r.t. ThetaSh for PST, VSCI and VSCII
    dPfdp_dPfsh = -dSf_dPfsh.real

    # Partials of Pfdp w.r.t. ma
    dPfdp_dQfma = -dSf_dQfma.real
    dPfdp_dQtma = -dSf_dQtma.real
    dPfdp_dVtma = -dSf_dVtma.real

    # Partials of Pfdp w.r.t. Beq
    dPfdp_dBeqz = -dSf_dBeqz.real
    dPfdp_dBeqv = -dSf_dBeqv.real

    # Partials of Pfdp w.r.t. ThetaSh for VSCIII
    dPfdp_dPfdp = -dSf_dPfdp.real

    # Compose the Jacobian sub-matrices (slicing) ---------------

    j11 = dSbus_dVa[np.ix_(pvpq, pvpq)].real  # avoid Slack
    j12 = dSbus_dVm[np.ix_(pvpq, pq)].real  # avoid Slack
    j13 = dSbus_dPfsh[pvpq, :].real  # avoid Slack
    j14 = dSbus_dQfma[pvpq, :].real  # avoid Slack
    j15 = dSbus_dBeqz[pvpq, :].real  # avoid Slack
    j16 = dSbus_dBeqv[pvpq, :].real  # avoid Slack
    j17 = dSbus_dVtma[pvpq, :].real  # avoid Slack
    j18 = dSbus_dQtma[pvpq, :].real  # avoid Slack
    j19 = dSbus_dPfdp[pvpq, :].real  # avoid Slack

    j21 = dSbus_dVa[np.ix_(pq, pvpq)].imag  # avoid Slack and pv
    j22 = dSbus_dVm[np.ix_(pq, pq)].imag  # avoid Slack and pv
    j23 = dSbus_dPfsh[pq, :].imag  # avoid Slack and pv
    j24 = dSbus_dQfma[pq, :].imag  # avoid Slack and pv
    j25 = dSbus_dBeqz[pq, :].imag  # avoid Slack and pv
    j26 = dSbus_dBeqv[pq, :].imag  # avoid Slack and pv
    j27 = dSbus_dVtma[pq, :].imag  # avoid Slack and pv
    j28 = dSbus_dQtma[pq, :].imag  # avoid Slack and pv
    j29 = dSbus_dPfdp[pq, :].imag  # avoid Slack and pv

    j31 = dSf_dVa[np.ix_(iPfsh, pvpq)].real  # Only Pf control elements iPfsh
    j32 = dSf_dVm[np.ix_(iPfsh, pq)].real  # Only Pf control elements iPfsh
    j33 = dSf_dPfsh[iPfsh, :].real  # Only Pf control elements iPfsh
    j34 = dSf_dQfma[iPfsh, :].real  # Only Pf control elements iPfsh
    j35 = dSf_dBeqz[iPfsh, :].real  # Only Pf control elements iPfsh
    j36 = dSf_dBeqv[iPfsh, :].real  # Only Pf control elements iPfsh
    j37 = dSf_dVtma[iPfsh, :].real  # Only Pf control elements iPfsh
    j38 = dSf_dQtma[iPfsh, :].real  # Only Pf control elements iPfsh
    j39 = dSf_dPfdp[iPfsh, :].real  # Only Pf control elements iPfsh

    j41 = dSf_dVa[np.ix_(iQfma, pvpq)].imag  # Only Qf control elements iQfma
    j42 = dSf_dVm[np.ix_(iQfma, pq)].imag  # Only Qf control elements iQfma
    j43 = dSf_dPfsh[iQfma, :].imag  # Only Qf control elements iQfma
    j44 = dSf_dQfma[iQfma, :].imag  # Only Qf control elements iQfma
    j45 = dSf_dBeqz[iQfma, :].imag  # Only Qf control elements iQfma
    j46 = dSf_dBeqv[iQfma, :].imag  # Only Qf control elements iQfma
    j47 = dSf_dVtma[iQfma, :].imag  # Only Qf control elements iQfma
    j48 = dSf_dQtma[iQfma, :].imag  # Only Qf control elements iQfma
    j49 = dSf_dPfdp[iQfma, :].imag  # Only Qf control elements iQfma

    j51 = dSf_dVa[np.ix_(iBeqz, pvpq)].imag  # Only Qf control elements iQfbeq
    j52 = dSf_dVm[np.ix_(iBeqz, pq)].imag  # Only Qf control elements iQfbeq
    j53 = dSf_dPfsh[iBeqz, :].imag  # Only Qf control elements iQfbeq
    j54 = dSf_dQfma[iBeqz, :].imag  # Only Qf control elements iQfbeq
    j55 = dSf_dBeqz[iBeqz, :].imag  # Only Qf control elements iQfbeq
    j56 = dSf_dBeqv[iBeqz, :].imag  # Only Qf control elements iQfbeq
    j57 = dSf_dVtma[iBeqz, :].imag  # Only Qf control elements iQfbeq
    j58 = dSf_dQtma[iBeqz, :].imag  # Only Qf control elements iQfbeq
    j59 = dSf_dPfdp[iBeqz, :].imag  # Only Qf control elements iQfbeq

    j61 = dSbus_dVa[np.ix_(VfBeqbus, pvpq)].imag  # Only Vf control elements iVfbeq
    j62 = dSbus_dVm[np.ix_(VfBeqbus, pq)].imag  # Only Vf control elements iVfbeq
    j63 = dSbus_dPfsh[VfBeqbus, :].imag  # Only Vf control elements iVfbeq
    j64 = dSbus_dQfma[VfBeqbus, :].imag  # Only Vf control elements iVfbeq
    j65 = dSbus_dBeqz[VfBeqbus, :].imag  # Only Vf control elements iVfbeq
    j66 = dSbus_dBeqv[VfBeqbus, :].imag  # Only Vf control elements iVfbeq
    j67 = dSbus_dVtma[VfBeqbus, :].imag  # Only Vf control elements iVfbeq
    j68 = dSbus_dQtma[VfBeqbus, :].imag  # Only Vf control elements iVfbeq
    j69 = dSbus_dPfdp[VfBeqbus, :].imag  # Only Vf control elements iVfbeq

    j71 = dSbus_dVa[np.ix_(Vtmabus, pvpq)].imag  # Only Vt control elements iVtma
    j72 = dSbus_dVm[np.ix_(Vtmabus, pq)].imag  # Only Vt control elements iVtma
    j73 = dSbus_dPfsh[Vtmabus, :].imag  # Only Vt control elements iVtma
    j74 = dSbus_dQfma[Vtmabus, :].imag  # Only Vt control elements iVtma
    j75 = dSbus_dBeqz[Vtmabus, :].imag  # Only Vt control elements iVtma
    j76 = dSbus_dBeqv[Vtmabus, :].imag  # Only Vt control elements iVtma
    j77 = dSbus_dVtma[Vtmabus, :].imag  # Only Vt control elements iVtma
    j78 = dSbus_dQtma[Vtmabus, :].imag  # Only Vt control elements iVtma
    j79 = dSbus_dPfdp[Vtmabus, :].imag  # Only Vt control elements iVtma

    j81 = dSt_dVa[np.ix_(iQtma, pvpq)].imag  # Only Qt control elements iQtma
    j82 = dSt_dVm[np.ix_(iQtma, pq)].imag  # Only Qt control elements iQtma
    j83 = dSt_dPfsh[iQtma, :].imag  # Only Qt control elements iQtma
    j84 = dSt_dQfma[iQtma, :].imag  # Only Qt control elements iQtma
    j85 = dSt_dBeqz[iQtma, :].imag  # Only Qt control elements iQtma
    j86 = dSt_dBeqv[iQtma, :].imag  # Only Qt control elements iQtma
    j87 = dSt_dVtma[iQtma, :].imag  # Only Qt control elements iQtma
    j88 = dSt_dQtma[iQtma, :].imag  # Only Qt control elements iQtma
    j89 = dSt_dPfdp[iQtma, :].imag  # Only Droop control elements iPfdp

    j91 = dPfdp_dVa[np.ix_(iPfdp, pvpq)]  # Only Droop control elements iPfdp
    j92 = dPfdp_dVm[np.ix_(iPfdp, pq)]  # Only Droop control elements iPfdp
    j93 = dPfdp_dPfsh[iPfdp, :]  # Only Droop control elements iPfdp
    j94 = dPfdp_dQfma[iPfdp, :]  # Only Droop control elements iPfdp
    j95 = dPfdp_dBeqz[iPfdp, :]  # Only Droop control elements iPfdp
    j96 = dPfdp_dBeqv[iPfdp, :]  # Only Droop control elements iPfdp
    j97 = dPfdp_dVtma[iPfdp, :]  # Only Droop control elements iPfdp
    j98 = dPfdp_dQtma[iPfdp, :]  # Only Droop control elements iPfdp
    j99 = dPfdp_dPfdp[iPfdp, :]  # Only Droop control elements iPfdp

    # Jacobian
    J = sp.vstack((
        sp.hstack((j11, j12, j13, j14, j15, j16, j17, j18, j19)),
        sp.hstack((j21, j22, j23, j24, j25, j26, j27, j28, j29)),
        sp.hstack((j31, j32, j33, j34, j35, j36, j37, j38, j39)),
        sp.hstack((j41, j42, j43, j44, j45, j46, j47, j48, j49)),
        sp.hstack((j51, j52, j53, j54, j55, j56, j57, j58, j59)),
        sp.hstack((j61, j62, j63, j64, j65, j66, j67, j68, j69)),
        sp.hstack((j71, j72, j73, j74, j75, j76, j77, j78, j79)),
        sp.hstack((j81, j82, j83, j84, j85, j86, j87, j88, j89)),
        sp.hstack((j91, j92, j93, j94, j95, j96, j97, j98, j99))
    ))  # FUBM-Jacobian Matrix

    return J


def compute_fx(Ybus, V, Vm, Sbus, Sf, St, Pfset, Qfset, Qtset, Vmfset, Kdp, F,
               pvpq, pq, iPfsh, iQfma, iBeqz, iQtma, iPfdp, VfBeqbus, Vtmabus):
    """
    Compute the increments vector
    :param Ybus: Admittance matrix
    :param V: Voltages array
    :param Vm: Voltages module array
    :param Sbus: Array of bus power matrix
    :param Pfset: Array of Pf set values per branch
    :param Qfset: Array of Qf set values per branch
    :param Qtset: Array of Qt set values per branch
    :param Vmfset: Array of Vf set values per branch
    :param Kdp: Array of branch droop value per branch
    :param F:
    :param T:
    :param pvpq:
    :param pq:
    :param iPfsh:
    :param iQfma:
    :param iBeqz:
    :param iQtma:
    :param iPfdp:
    :param iBeqv:
    :param iVtma:
    :return:
    """

    mis = V * np.conj(Ybus * V) - Sbus  # FUBM- F1(x0) & F2(x0) Power balance mismatch

    misPbus = mis[pvpq].real  # FUBM- F1(x0) Power balance mismatch - Va
    misQbus = mis[pq].imag  # FUBM- F2(x0) Power balance mismatch - Vm
    misPfsh = Sf[iPfsh].real - Pfset[iPfsh]  # FUBM- F3(x0) Pf control mismatch
    misQfma = Sf[iQfma].imag - Qfset[iQfma]  # FUBM- F4(x0) Qf control mismatch
    misBeqz = Sf[iBeqz].imag - 0  # FUBM- F5(x0) Qf control mismatch
    misBeqv = mis[VfBeqbus].imag  # FUBM- F6(x0) Vf control mismatch
    misVtma = mis[Vtmabus].imag  # FUBM- F7(x0) Vt control mismatch
    misQtma = St[iQtma].imag - Qtset[iQtma]  # FUBM- F8(x0) Qt control mismatch
    misPfdp = -Sf[iPfdp].real + Pfset[iPfdp] + Kdp[iPfdp] * (Vm[F[iPfdp]] - Vmfset[iPfdp])  # FUBM- F9(x0) Pf control mismatch, Droop Pf - Pfset = Kdp*(Vmf - Vmfset)
    # -------------------------------------------------------------------------

    #  Create F vector
    # FUBM----------------------------------------------------------------------
    df = np.r_[misPbus,  # FUBM- F1(x0) Power balance mismatch - Va
               misQbus,  # FUBM- F2(x0) Power balance mismatch - Vm
               misPfsh,  # FUBM- F3(x0) Pf control    mismatch - Theta_shift
               misQfma,  # FUBM- F4(x0) Qf control    mismatch - ma
               misBeqz,  # FUBM- F5(x0) Qf control    mismatch - Beq
               misBeqv,  # FUBM- F6(x0) Vf control    mismatch - Beq
               misVtma,  # FUBM- F7(x0) Vt control    mismatch - ma
               misQtma,  # FUBM- F8(x0) Qt control    mismatch - ma
               misPfdp]  # FUBM- F9(x0) Pf control    mismatch - Theta_shift Droop

    return df


def nr_acdc(nc: SnapshotData, tolerance=1e-6, max_iter=4):
    """

    :param nc:
    :param tolerance:
    :param max_iter:
    :return:
    """
    # compute the indices of the converter/transformer variables from their control strategies
    iPfsh, iQfma, iBeqz, iBeqv, iVtma, iQtma, iPfdp, iVscL, VfBeqbus, Vtmabus = determine_branch_indices(circuit=nc)

    # initialize the variables
    nb = nc.nbus
    nl = nc.nbr
    V = nc.Vbus
    S0 = nc.Sbus
    Va = np.angle(V)
    Vm = np.abs(V)
    Vmfset = nc.branch_data.vf_set[:, 0]
    m = nc.branch_data.m[:, 0].copy()
    theta = nc.branch_data.theta[:, 0].copy() * 0
    Beq = nc.branch_data.Beq[:, 0].copy() * 0
    Gsw = nc.branch_data.G0[:, 0]
    Pfset = nc.branch_data.Pfset[:, 0] / nc.Sbase
    Qfset = nc.branch_data.Qfset[:, 0] / nc.Sbase
    Qtset = nc.branch_data.Qfset[:, 0] / nc.Sbase
    Kdp = nc.branch_data.Kdp
    k2 = nc.branch_data.k
    Cf = nc.Cf
    Ct = nc.Ct
    F = nc.F
    T = nc.T
    Ys = 1.0 / (nc.branch_data.R + 1j * nc.branch_data.X)
    Bc = nc.branch_data.B
    pq = nc.pq.copy().astype(int)
    pvpq_orig = np.r_[nc.pv, pq].astype(int)
    pvpq_orig.sort()

    # the elements of PQ that exist in the control indices Ivf and Ivt must be passed from the PQ to the PV list
    # otherwise those variables would be in two sets of equations
    i_ctrl_v = np.unique(np.r_[VfBeqbus, Vtmabus])
    for val in pq:
        if val in i_ctrl_v:
            pq = pq[pq != val]

    # compose the new pvpq indices à la NR
    pv = np.unique(np.r_[i_ctrl_v, nc.pv]).astype(int)
    pv.sort()
    pvpq = np.r_[pv, pq].astype(int)
    npv = len(pv)
    npq = len(pq)

    # --------------------------------------------------------------------------

    # variables dimensions in Jacobian
    a0 = 0
    a1 = a0 + npq + npv
    a2 = a1 + npq
    a3 = a2 + len(iPfsh)
    a4 = a3 + len(iQfma)
    a5 = a4 + len(iBeqz)
    a6 = a5 + len(VfBeqbus)
    a7 = a6 + len(Vtmabus)
    a8 = a7 + len(iQtma)
    a9 = a8 + len(iPfdp)
    # -------------------------------------------------------------------------
    # compute initial admittances
    Ybus, Yf, Yt, tap = compile_y_acdc(branch_active=nc.branch_data.branch_active[:, 0],
                                       Cf=Cf, Ct=Ct,
                                       C_bus_shunt=nc.shunt_data.C_bus_shunt,
                                       shunt_admittance=nc.shunt_data.shunt_admittance[:, 0],
                                       shunt_active=nc.shunt_data.shunt_active[:, 0],
                                       ys=Ys,
                                       B=Bc,
                                       Sbase=nc.Sbase,
                                       m=m, theta=theta, Beq=Beq, Gsw=Gsw)

    #  compute branch power flows
    If = Yf * V  # complex current injected at "from" bus
    It = Yt * V  # complex current injected at "to" bus
    Sf = V[F] * np.conj(If)  # complex power injected at "from" bus
    St = V[T] * np.conj(It)  # complex power injected at "to" bus

    # compute converter losses
    Gsw = compute_converter_losses(V=V, It=It, F=F,
                                   alpha1=nc.branch_data.alpha1,
                                   alpha2=nc.branch_data.alpha2,
                                   alpha3=nc.branch_data.alpha3,
                                   iVscL=iVscL)

    # compute total mismatch
    fx = compute_fx(Ybus=Ybus,
                    V=V,
                    Vm=Vm,
                    Sbus=S0,
                    Sf=Sf,
                    St=St,
                    Pfset=Pfset,
                    Qfset=Qfset,
                    Qtset=Qtset,
                    Vmfset=Vmfset,
                    Kdp=Kdp,
                    F=F,
                    pvpq=pvpq,
                    pq=pq,
                    iPfsh=iPfsh,
                    iQfma=iQfma,
                    iBeqz=iBeqz,
                    iQtma=iQtma,
                    iPfdp=iPfdp,
                    VfBeqbus=VfBeqbus,
                    Vtmabus=Vtmabus)
    norm_f = np.max(np.abs(fx))

    # -------------------------------------------------------------------------
    converged = norm_f < tolerance
    iterations = 0
    while not converged and iterations < max_iter:

        # compute the Jacobian
        J = fubm_jacobian(nb, nl, iPfsh, iPfdp, iQfma, iQtma, iVtma, iBeqz, iBeqv, VfBeqbus, Vtmabus,
                          F, T, Ys, k2, tap, m, Bc, Beq, Kdp, V, Ybus, Yf, Yt, Cf, Ct, pvpq, pq)

        print("fx:\n", fx)
        print("J:\n", J.toarray())

        dx = sp.linalg.spsolve(J, -fx)

        dVa = dx[:a1]
        dVm = dx[a1:a2]
        dtheta_Pf = dx[a2:a3]
        dma_Qf = dx[a3:a4]
        dBeq_z = dx[a4:a5]
        dBeq_v = dx[a5:a6]
        dma_Vt = dx[a6:a7]
        dma_Qt = dx[a7:a8]
        dtheta_Pd = dx[a8:a9]

        # Assign the values
        mu = 1.0
        Va[pvpq] += dVa * mu
        Vm[pq] += dVm * mu
        theta[iPfsh] += dtheta_Pf * mu
        theta[iPfdp] += dtheta_Pd * mu
        m[iQfma] += dma_Qf * mu
        m[iQtma] += dma_Qt * mu
        m[iVtma] += dma_Vt * mu
        Beq[iBeqz] += dBeq_z * mu
        Beq[iBeqv] += dBeq_v * mu

        V = Vm * np.exp(1j * Va)

        print('dx:', dx)
        print('Va:', Va)
        print('Vm:', Vm)
        print('theta:', theta)
        print('ma:', m)
        print('Beq:', Beq)
        print('norm_f:', norm_f)

        # compute initial admittances
        Ybus, Yf, Yt, tap = compile_y_acdc(branch_active=nc.branch_data.branch_active[:, 0],
                                           Cf=Cf, Ct=Ct,
                                           C_bus_shunt=nc.shunt_data.C_bus_shunt,
                                           shunt_admittance=nc.shunt_data.shunt_admittance[:, 0],
                                           shunt_active=nc.shunt_data.shunt_active[:, 0],
                                           ys=Ys,
                                           B=Bc,
                                           Sbase=nc.Sbase,
                                           m=m, theta=theta, Beq=Beq, Gsw=Gsw)

        #  compute branch power flows
        If = Yf * V  # complex current injected at "from" bus
        It = Yt * V  # complex current injected at "to"   bus
        Sf = V[F] * np.conj(If)  # complex power injected at "from" bus
        St = V[T] * np.conj(It)  # complex power injected at "to"   bus

        # compute converter losses
        Gsw = compute_converter_losses(V=V, It=It, F=F,
                                       alpha1=nc.branch_data.alpha1,
                                       alpha2=nc.branch_data.alpha2,
                                       alpha3=nc.branch_data.alpha3,
                                       iVscL=iVscL)

        # compute total mismatch
        fx = compute_fx(Ybus=Ybus,
                        V=V,
                        Vm=Vm,
                        Sbus=S0,
                        Sf=Sf,
                        St=St,
                        Pfset=Pfset,
                        Qfset=Qfset,
                        Qtset=Qtset,
                        Vmfset=Vmfset,
                        Kdp=Kdp,
                        F=F,
                        pvpq=pvpq,
                        pq=pq,
                        iPfsh=iPfsh,
                        iQfma=iQfma,
                        iBeqz=iBeqz,
                        iQtma=iQtma,
                        iPfdp=iPfdp,
                        VfBeqbus=VfBeqbus,
                        Vtmabus=Vtmabus)

        norm_f = np.max(np.abs(fx))

        iterations += 1
        converged = norm_f <= tolerance

    return norm_f, V, m, theta, Beq


if __name__ == "__main__":
    np.set_printoptions(precision=4, linewidth=100000)
    # np.set_printoptions(linewidth=10000)

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/LineHVDCGrid.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE57+IEEE14 DC grid.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/ACDC_example_grid.gridcal'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/fubm_caseHVDC_vt.gridcal'
    grid = FileOpen(fname).open()

    ####################################################################################################################
    # Compile
    ####################################################################################################################
    nc_ = compile_snapshot_circuit(grid)

    res = nr_acdc(nc=nc_, tolerance=1e-4, max_iter=20)

