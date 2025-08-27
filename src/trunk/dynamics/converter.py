import cmath

r = 0.00501
x = 0.05001

denominator = r + 1j * (x + 1.0e-8) + 1.0e-8
yhk = 1.0 / denominator
ghk = yhk.real
bhk = yhk.imag

print(f"g: {ghk}")
print(f"b: {bhk}")