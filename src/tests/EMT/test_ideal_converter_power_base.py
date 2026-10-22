"""Verify ideal-converter initialization and periodic operation in network units."""
import numpy as np
import pytest

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Emt.converter_emt_template import get_emt_ideal_converter
from VeraGridEngine.Templates.Emt.converter_emt_multilinear_template import get_emt_ideal_converter_multilinear


@pytest.mark.parametrize('factory', [get_emt_ideal_converter, get_emt_ideal_converter_multilinear])
@pytest.mark.parametrize('active_power', [-.6, .6])
@pytest.mark.parametrize('reactive_power', [-.2, .2])
@pytest.mark.parametrize('sbase', [1., 100.])
def test_ideal_converter_initializes_on_periodic_power_flow_solution(factory, active_power, reactive_power, sbase):
    template = factory(VarFactory())
    block = template.block.children[0] if template.block.children else template.block
    voltage = .97
    phase_angle = .23
    omega = 2*np.pi*50.
    loss = .01
    ac_power = active_power + loss
    dc_voltage = 1.05
    bindings = {
        'sbase': sbase, 'omega_base': omega, 'P_loss': loss*sbase,
        'P0': active_power*sbase, 'control1': 5., 'control2': 4.,
        'control1_val': active_power, 'control2_val': reactive_power,
        'Vdc_nom': dc_voltage, 'Vdc_ref': dc_voltage, 'v_dc': dc_voltage,
        'phi_v': phase_angle, 'Vpk': np.sqrt(2.)*voltage,
        'P_ref': active_power*sbase, 'Q_ref': reactive_power*sbase,
        'P': ac_power, 'Q': reactive_power, 'i_dc': -active_power/dc_voltage,
        'i_d_cmd': -np.sqrt(2.)*reactive_power/voltage,
        'i_q_cmd': np.sqrt(2.)*ac_power/voltage,
    }
    phase_shifts = np.array([0., -2*np.pi/3., 2*np.pi/3.])
    # Independently derive network currents from S = V*conj(I).
    voltage_phasors = voltage*np.exp(1j*(phase_angle+phase_shifts))
    current_phasors = np.conj((ac_power+1j*reactive_power)/voltage_phasors)
    for time in np.linspace(0., 1/50., 17):
        angle = phase_angle+omega*time
        voltages = np.sqrt(2.)*np.imag(voltage_phasors*np.exp(1j*omega*time))
        currents = np.sqrt(2.)*np.imag(current_phasors*np.exp(1j*omega*time))
        bindings.update(theta=angle, u_cos=np.cos(angle), u_sin=np.sin(angle))
        for phase, v, i in zip('ABC', voltages, currents):
            bindings[f'v_{phase}'] = v
            bindings[f'i_{phase}'] = i
        for equation in block.algebraic_eqs:
            assert abs(float(equation.eval(**bindings))) < 1e-9
        expected_derivatives = {'theta': omega, 'u_cos': -omega*np.sin(angle), 'u_sin': omega*np.cos(angle)}
        for state, equation in zip(block.state_vars, block.state_eqs):
            assert float(equation.eval(**bindings)) == pytest.approx(expected_derivatives[state.name])
        assert np.dot(voltages, currents)/3. + dc_voltage*bindings['i_dc'] == pytest.approx(loss)
        if time == 0.:
            for variable, expression in block.init_eqs.items():
                assert float(expression.eval(**bindings)) == pytest.approx(bindings[variable.name], abs=1e-9)
