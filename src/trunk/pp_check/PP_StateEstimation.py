import pandapower as pp
from pandapower.estimation import estimate
import numpy as np


def CreateGrid(load = True):
    net1 = pp.create_empty_network()
    b1 = pp.create_bus(net1, name="bus 1", vn_kv=1., index=1)
    b2 = pp.create_bus(net1, name="bus 2", vn_kv=1., index=2)
    b3 = pp.create_bus(net1, name="bus 3", vn_kv=1., index=3)
    pp.create_ext_grid(net1, 1)  # set the slack bus to bus 1
    l1 = pp.create_line_from_parameters(net1, 1, 2, 1, r_ohm_per_km=.01, x_ohm_per_km=.03, c_nf_per_km=0., max_i_ka=1)
    l2 = pp.create_line_from_parameters(net1, 1, 3, 1, r_ohm_per_km=.02, x_ohm_per_km=.05, c_nf_per_km=0., max_i_ka=1)
    l3 = pp.create_line_from_parameters(net1, 2, 3, 1, r_ohm_per_km=.03, x_ohm_per_km=.08, c_nf_per_km=0., max_i_ka=1)
    if load :
        load1 = pp.create_load(net1, bus=b2, p_mw=0.5, q_mvar=0.3)
        load1 = pp.create_load(net1, bus=b3, p_mw=1.5, q_mvar=0.8)
    return net1, b1,b2, l1, l2


print("Creo una red con cargas")
net1,_,_,_,_ = CreateGrid(load=True)
pp.runpp(net1)

print("Creo una red con medidas de ejemplo")
net2, b1,b2, l1, l2 = CreateGrid(load=False)
pp.create_measurement(net2, "v", "bus",  1.006, 0.004, element=b1)        # V at bus 1
pp.create_measurement(net2, "v", "bus",  0.968, 0.004, element=b2)        # V at bus 2
pp.create_measurement(net2, "p", "bus",  0.501, 0.010, element=b2)         # P at bus 2
pp.create_measurement(net2, "q", "bus",  0.286, 0.010, element=b2)         # Q at bus 2
pp.create_measurement(net2, "p", "line", 0.888, 0.008, element=l1, side=b1)  # Pline (bus 1 -> bus 2) at bus 1
pp.create_measurement(net2, "p", "line", 1.173, 0.008, element=l2, side=b1)  # Pline (bus 1 -> bus 3) at bus 1
pp.create_measurement(net2, "q", "line", 0.568, 0.008, element=l1, side=b1)  # Qline (bus 1 -> bus 2) at bus 1
pp.create_measurement(net2, "q", "line", 0.663, 0.008, element=l2, side=b1)  # Qline (bus 1 -> bus 3) at bus 1
success = estimate(net2, init='flat')

print("creo una red con medidas basadas en la red con cargas más ruido aleatorio")
#now let's create a new noisy measurement
noise_percentage = 0.005
BV1 = net1.res_bus.loc[1,'vm_pu'] +  abs(np.random.randn(1)*noise_percentage*np.exp(0.1j*np.random.randn(1)))[0]
BV2 = net1.res_bus.loc[2,'vm_pu'] +  abs(np.random.randn(1)*noise_percentage*np.exp(0.1j*np.random.randn(1)))[0]
BP2 = net1.res_bus.loc[2,'p_mw'] +  abs(np.random.randn(1)*noise_percentage*np.exp(0.1j*np.random.randn(1)))[0]
BQ2 = net1.res_bus.loc[2,'q_mvar'] +  abs(np.random.randn(1)*noise_percentage*np.exp(0.1j*np.random.randn(1)))[0]
LP1 = net1.res_line.loc[0,'p_from_mw'] +  abs(np.random.randn(1)*noise_percentage*np.exp(0.1j*np.random.randn(1)))[0]
LQ1 = net1.res_line.loc[0,'q_from_mvar'] +  abs(np.random.randn(1)*noise_percentage*np.exp(0.1j*np.random.randn(1)))[0]
LP2 = net1.res_line.loc[1,'p_from_mw'] +  abs(np.random.randn(1)*noise_percentage*np.exp(0.1j*np.random.randn(1)))[0]
LQ2 = net1.res_line.loc[1,'q_from_mvar'] +  abs(np.random.randn(1)*noise_percentage*np.exp(0.1j*np.random.randn(1)))[0]
#now the network
net3, b1,b2, l1, l2 = CreateGrid(load=False)
pp.create_measurement(net3, "v", "bus", BV1, noise_percentage, element=b1)        # V at bus 1
pp.create_measurement(net3, "v", "bus", BV2, noise_percentage, element=b2)        # V at bus 2
pp.create_measurement(net3, "p", "bus", BP2, noise_percentage, element=b2)         # P at bus 2
pp.create_measurement(net3, "q", "bus", BQ2, noise_percentage, element=b2)         # Q at bus 2
pp.create_measurement(net3, "p", "line", LP1, noise_percentage, element=l1, side=b1)  # Pline (bus 1 -> bus 2) at bus 1
pp.create_measurement(net3, "p", "line", LP2, noise_percentage, element=l2, side=b1)  # Pline (bus 1 -> bus 3) at bus 1
pp.create_measurement(net3, "q", "line", LQ1, noise_percentage, element=l1, side=b1)  # Qline (bus 1 -> bus 2) at bus 1
pp.create_measurement(net3, "q", "line", LQ2, noise_percentage, element=l2, side=b1)  # Qline (bus 1 -> bus 3) at bus 1
success = estimate(net3, init='flat')


print("resultado PF de la red con cargas")
print(net1.res_bus)
print(net1.res_line[['p_from_mw',  'q_from_mvar',   'p_to_mw',  'q_to_mvar']])
print("resultado PF buses de la red con estimación de estado y medidas del ejemplo")
print(net2.res_bus_est)
print("resultado PF buses de la red con estimación de estado y medidas con error")
print(net3.res_bus_est)
#print("resultado PF líneas de la red con estimación de estado y medidas del ejemplo")
#print(net2.res_line_est['i_ka'])
#print("resultado PF líneas de la red con estimación de estado y medidas con error")
#print(net3.res_line_est['i_ka'])
