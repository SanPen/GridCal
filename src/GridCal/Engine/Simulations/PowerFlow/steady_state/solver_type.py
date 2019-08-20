from enum import Enum


class SolverType(Enum):
    """
    Refer to the :ref:`Power Flow section<power_flow>` for details about the different
    algorithms supported by **GridCal**.
    """

    # Power Flow Solvers
    CONTINUATION_NR = 'Continuation-Newton-Raphson'
    GAUSS = 'Gauss-Seidel'
    HELM = 'Holomorphic Embedding'
    HELM_CHENGXI_VANILLA = 'HELM-Chengxi-Vanilla'
    HELM_CHENGXI_2 = 'HELM-Chengxi-2'
    HELM_CHENGXI_CORRECTED = 'HELM-Chengxi-Corrected'
    HELM_PQ = 'HELM-PQ'
    HELM_VECT_ASU = 'HELM-Vect-ASU'
    HELM_WALLACE = 'HELM-Wallace'
    HELM_Z_PV = 'HELM-Z-PV'
    HELM_Z_PQ = 'HELM-Z-PQ'
    IWAMOTO = 'Iwamoto-Newton-Raphson'
    LACPF = 'Linear AC'
    LM = 'Levenberg-Marquardt'
    NR = 'Newton Raphson'
    NRI = 'Newton-Raphson in current'
    ZBUS = 'Z-Gauss-Seidel'

    # Dealternated Current Power Flow

    DC = 'Linear DC'

    # Fast Decoupled

    FASTDECOUPLED = 'Fast decoupled'
    NRFD_XB = 'Fast decoupled XB'
    NRFD_BX = 'Fast decoupled BX'

    # Optimal Power Flow

    AC_OPF = 'Linear AC OPF'
    DC_OPF = 'Linear DC OPF'
    DYCORS_OPF = 'DYCORS OPF'
    GA_OPF = 'Genetic Algorithm OPF'
    NELDER_MEAD_OPF = 'Nelder Mead OPF'
