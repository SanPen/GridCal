from GridCal.Engine.Core.calculation_inputs import CalculationInputs
from GridCal.Engine.Simulations.PowerFlow.steady_state.power_flow_mp import PowerFlowMP
from GridCal.Engine.Simulations.PowerFlow.steady_state.power_flow_options import \
    PowerFlowOptions


def power_flow_worker(t, options: PowerFlowOptions, circuit: CalculationInputs, Vbus, Sbus, Ibus, return_dict):
    """
    Power flow worker to schedule parallel power flows
        **t: execution index
        **options: power flow options
        **circuit: circuit
        **Vbus: Voltages to initialize
        **Sbus: Power injections
        **Ibus: Current injections
        **return_dict: parallel module dictionary in wich to return the values
    :return:
    """

    instance = PowerFlowMP(None, options)
    return_dict[t] = instance.run_pf(circuit, Vbus, Sbus, Ibus)