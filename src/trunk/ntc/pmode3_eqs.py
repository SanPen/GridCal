Delta_down_0 = 199900
Delta_up_0 = 199900
hvdc_flow_0_0 = 199900
hvdc_flow_lin_0_0 = -100
th_0_0 = 0
th_0_1 = -0.4848136811098
hvdc_z1_0_0 = 1
hvdc_z2_0_0 = 0

# Minimize
OBJ = Delta_down_0 - Delta_up_0 - hvdc_flow_0_0

# Subject To

deltas_equality_0 = - Delta_down_0 + Delta_up_0 == 0

kirchhoff_0_0 = - Delta_down_0 + hvdc_flow_0_0 == 0
kirchhoff_0_1 = Delta_up_0 - hvdc_flow_0_0 == 0

flow_lin_def_0_0 = hvdc_flow_lin_0_0 + 206.264806247 * th_0_0 - 206.264806247 * th_0_1 == 0

upper_bound_flow_ge_0_0 = hvdc_flow_0_0 - 200000 * hvdc_z1_0_0 >= -199900
upper_bound_flow_le_0_0 = hvdc_flow_0_0 - 200000 * hvdc_z1_0_0 <= 1
upper_bound_flowlin_le_0_0 = hvdc_flow_lin_0_0 + 200000 * hvdc_z1_0_0 <= 200100

intermediate_always_true_0_0 = - hvdc_z1_0_0 - hvdc_z2_0_0 <= 0
intermediate_flow_ge_0_0 = hvdc_flow_0_0 - hvdc_flow_lin_0_0 + 200000 * hvdc_z1_0_0 + 200000 * hvdc_z2_0_0 >= 0
intermediate_flow_le_0_0 = hvdc_flow_0_0 - hvdc_flow_lin_0_0 - 200000 * hvdc_z1_0_0 - 200000 * hvdc_z2_0_0 <= 0

lower_bound_flow_ge_0_0 = hvdc_flow_0_0 + 200000 * hvdc_z2_0_0 >= -1
lower_bound_flow_le_0_0 = hvdc_flow_0_0 + 200000 * hvdc_z2_0_0 <= 199900
lower_bound_flowlin_ge_0_0 = - hvdc_flow_lin_0_0 + 200000 * hvdc_z2_0_0 <= 200100

single_case_active_0_0 = hvdc_z1_0_0 + hvdc_z2_0_0 <= 1

print("deltas_equality_0:", deltas_equality_0)
print("kirchhoff_0_0:", kirchhoff_0_0)
print("kirchhoff_0_1:", kirchhoff_0_1)
print("upper_bound_flow_ge_0_0:", upper_bound_flow_ge_0_0)
print("upper_bound_flow_le_0_0:", upper_bound_flow_le_0_0)
print("upper_bound_flowlin_le_0_0:", upper_bound_flowlin_le_0_0)
print("intermediate_always_true_0_0:", intermediate_always_true_0_0)
print("intermediate_flow_ge_0_0:", intermediate_flow_ge_0_0)
print("intermediate_flow_le_0_0:", intermediate_flow_le_0_0)
print("lower_bound_flow_ge_0_0:", lower_bound_flow_ge_0_0)
print("lower_bound_flow_le_0_0:", lower_bound_flow_le_0_0)
print("lower_bound_flowlin_ge_0_0:", lower_bound_flowlin_ge_0_0)
print("single_case_active_0_0:", single_case_active_0_0)
