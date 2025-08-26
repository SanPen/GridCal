import numpy as np

U1 = np.array([1.0420 * np.exp(1j * (-121.72*np.pi/180)),
               1.0174 * np.exp(1j * (117.83*np.pi/180))])

U2 = np.array([1.03708067 * np.exp(1j * (-122.37639793*np.pi/180)),
               1.01011028 * np.exp(1j * (117.39995434*np.pi/180))])

U3 = np.array([1.03793653 * np.exp(1j * (-122.73882911*np.pi/180)),
               1.00489104 * np.exp(1j * (117.16776906*np.pi/180))])

Ys12 = np.array([[0.75018946-0.68996668j, -0.25000302+0.10376509j],
                 [-0.25000302+0.10376509j, 0.74501133-0.6931314j]])

Ysh12 = np.array([[0.+0.07718218j, 0.-0.01474749j],
                  [0.-0.01474749j, 0.+0.07646275j]])/2

Ys23 = np.array([[1.25031577-1.14994447j, -0.4166717 +0.17294182j],
                 [-0.4166717 +0.17294182j, 1.24168554-1.15521901j]])


Zs_23_ohm = np.array([[0.07550123653174592+0.07650648091764325j, 0.011733530515615096+0.026073881218387662j],
                    [0.011733530515615096+0.026073881218387662j, 0.0751831931102191+0.07706305690531522j]])

Zs_12_ohm = 5/3 * Zs_23_ohm

Zbase = 4160**2 / 100e6

Ys_23_pu = np.linalg.inv(Zs_23_ohm) * Zbase
Ys_12_pu = np.linalg.inv(Zs_12_ohm) * Zbase

yshsh_603 = np.array([
    [1j * 4.7097, 1j * -0.8999],
    [1j * -0.8999, 1j * 4.6658]
], dtype=complex) / 10**6 / 1.60934 * 300 * 0.0003048

Ysh_23_siemens = np.array([[2.6759725601799494e-07j, -5.1130808903028556e-08j],
                      [-5.1130808903028556e-08j, 2.6510293163657147e-07j]])

Ysh_12_siemens = 5/3 * Ysh_23_siemens

Ysh_23_pu = Ysh_23_siemens * Zbase
Ysh_12_pu = Ysh_12_siemens * Zbase


# ------------

Ysh23 = np.array([[0.+0.04630931j, 0.-0.00884849j],
                  [0.-0.00884849j, 0.+0.04587765j]])/2

Sb = 170e3 / (100e6 / 3) + 1j * 125e3 / (100e6 / 3)

Sbc = 230e3 / (100e6 / 3) + 1j * 132e3 / (100e6 / 3)

"""
Currents
"""
I2_b = np.conj(Sb / U2[0])

Is32 = Ys_23_pu @ (U3 - U2)
Is12 = Ys_12_pu @ (U1 - U2)

Ish2_1 = Ysh_12_pu @ U2
Ish2_3 = Ysh_23_pu @ U2

I2_load = Is32 + Is12 - Ish2_3 - Ish2_1

print(f"I2_load: {I2_load[0]}")
print(f"I2_b: {I2_b}")

errorr = abs(I2_load[0] - I2_b)
print(f"Error: {errorr}")


I3_b = np.conj( Sbc / (U3[0] - U3[1]) )
I3_c = np.conj( Sbc / (U3[1] - U3[0]) )

Ish23 = Ysh23 @ U3

Is23 = Ys23 @ (U2 - U3)

I3 = Is23 - Ish23
# print(I3)
# print()
# print(I3_b)
# print(I3_c)