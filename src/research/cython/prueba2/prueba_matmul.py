from matmul_package import matmul


import numpy as np
a=np.arange(4, dtype=float)

res = matmul.matmul(a,a)

print(res)  # 14.0 as expected!