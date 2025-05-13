
z_pos = 1
z_mid = 0
z_neg = 0

rate = 1000.0
P0 = 0
k = 360.0
theta_f = 25.0
theta_t = 20.0
epsilon = 1e-4
M = 2 * rate

# 1. Region selector:
z_neg + z_mid + z_pos == 1

# 2. Linear flow equation:
flow_lin = P0 + k * (theta_f - theta_t)

if flow_lin > rate:
    z_pos = 1
    z_mid = 0
    z_neg = 0
    flow = rate

elif flow_lin < -rate:
    z_pos = 0
    z_mid = 0
    z_neg = 1
    flow = -rate

elif -rate < flow_lin < rate:
    z_pos = 0
    z_mid = 1
    z_neg = 0
    flow = flow_lin

# 3. Lower region:  flow = -rate if z_neg == 1
ok3a = flow <= -rate + M * (1 - z_neg)
ok3b = flow >= -rate - M * (1 - z_neg)
ok3c = flow <= -rate + M * (1 - z_neg)

# 4. Mid region:    flow = flow_lin if z_mid == 1
ok4a = flow <= flow_lin + M * (1 - z_mid)
ok4b = flow >= flow_lin - M * (1 - z_mid)
ok4c = flow_lin <= rate - epsilon + M * (1 - z_mid)
ok4d = flow_lin >= -rate + epsilon - M * (1 - z_mid)

# 5. Upper region:  flow = rate if z_pos == 1
ok5a = flow <= rate + M * (1 - z_pos)
ok5b = flow >= rate - M * (1 - z_pos)
ok5c = flow >= rate - M * (1 - z_pos)

print()