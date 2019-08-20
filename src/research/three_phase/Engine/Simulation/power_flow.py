
from research.three_phase.Engine.circuit import *
from research.three_phase.Engine.Numerical import numerical_power_flow as Numerical


class PowerFlow:

    def __init__(self, circuit: Circuit):
        """
        Power Flow constructor
        :param circuit:
        """
        self.circuit = circuit

    def run(self, tol=1e-5, max_iter=100, method: PowerFlowMethods=PowerFlowMethods.GaussSeidel, verbose=False):
        """
        Run power flow simulation
        :param tol: Solution tolerance in MVA (p.u.)
        :param max_iter: Maximum number of iterations
        :param method: Power flow method to use
        :param verbose: Verbose?
        """
        # compile the circuit values
        data = self.circuit.compile()

        if method == PowerFlowMethods.GaussSeidel:

            V, converged, err = Numerical.gauss_seidel_power_flow(Vbus=data.Vbus,
                                                                  Sbus=data.Sbus,
                                                                  Ibus=data.Ibus,
                                                                  Ybus=data.Ybus,
                                                                  P0=data.P0,
                                                                  Q0=data.Q0,
                                                                  exp_p=data.exp_p,
                                                                  exp_q=data.exp_q,
                                                                  V0=data.V0,
                                                                  A=data.A,
                                                                  B=data.B,
                                                                  C=data.C,
                                                                  pq=data.pq,
                                                                  pv=data.pv,
                                                                  tol=tol,
                                                                  max_iter=max_iter,
                                                                  verbose=verbose)
        elif method == PowerFlowMethods.NewtonRaphson:

            V, converged, err = Numerical.newton_raphson_power_flow(Vbus=data.Vbus,
                                                                    Sbus=data.Sbus,
                                                                    Ibus=data.Ibus,
                                                                    Ybus=data.Ybus,
                                                                    P0=data.P0,
                                                                    Q0=data.Q0,
                                                                    exp_p=data.exp_p,
                                                                    exp_q=data.exp_q,
                                                                    V0=data.V0,
                                                                    A=data.A,
                                                                    B=data.B,
                                                                    C=data.C,
                                                                    pq=data.pq,
                                                                    pv=data.pv,
                                                                    tol=tol,
                                                                    max_iter=max_iter,
                                                                    verbose=verbose)

        elif method == PowerFlowMethods.GaussRaphson:

            V, converged, err = Numerical.gauss_raphson_power_flow(Vbus=data.Vbus,
                                                                   Sbus=data.Sbus,
                                                                   Ibus=data.Ibus,
                                                                   Ybus=data.Ybus,
                                                                   P0=data.P0,
                                                                   Q0=data.Q0,
                                                                   exp_p=data.exp_p,
                                                                   exp_q=data.exp_q,
                                                                   V0=data.V0,
                                                                   A=data.A,
                                                                   B=data.B,
                                                                   C=data.C,
                                                                   pq=data.pq,
                                                                   pv=data.pv,
                                                                   ref=data.ref,
                                                                   tol=tol,
                                                                   max_iter=max_iter,
                                                                   verbose=verbose)

        elif method == PowerFlowMethods.ZMatrix:

            V, converged, err = Numerical.z_matrix_power_flow(Vbus=data.Vbus,
                                                              Sbus=data.Sbus,
                                                              Ibus=data.Ibus,
                                                              Ybus=data.Ybus,
                                                              P0=data.P0,
                                                              Q0=data.Q0,
                                                              exp_p=data.exp_p,
                                                              exp_q=data.exp_q,
                                                              V0=data.V0,
                                                              A=data.A,
                                                              B=data.B,
                                                              C=data.C,
                                                              pq=data.pq,
                                                              pv=data.pv,
                                                              ref=data.ref,
                                                              tol=tol,
                                                              max_iter=max_iter,
                                                              verbose=verbose)

        elif method == PowerFlowMethods.LevenbergMarquardt:

            V, converged, err = Numerical.levenberg_marquardt_power_flow(Vbus=data.Vbus,
                                                                         Sbus=data.Sbus,
                                                                         Ibus=data.Ibus,
                                                                         Ybus=data.Ybus,
                                                                         P0=data.P0,
                                                                         Q0=data.Q0,
                                                                         exp_p=data.exp_p,
                                                                         exp_q=data.exp_q,
                                                                         V0=data.V0,
                                                                         A=data.A,
                                                                         B=data.B,
                                                                         C=data.C,
                                                                         pq=data.pq,
                                                                         pv=data.pv,
                                                                         tol=tol,
                                                                         max_iter=max_iter,
                                                                         verbose=verbose)
        elif method == PowerFlowMethods.LinearAC:

            V, converged, err = Numerical.linear_ac_power_flow(Ybus=data.Ybus,
                                                               Yseries=data.Yseries,
                                                               Sbus=data.Sbus,
                                                               Ibus=data.Ibus,
                                                               Vbus=data.Vbus,
                                                               pq=data.pq,
                                                               pv=data.pv)
        else:
            raise Exception('Power flow method not implemented')

        # compute the branch results
        results = data.compute_branch_results(V)
        results.converged = converged
        results.error = err

        return results

