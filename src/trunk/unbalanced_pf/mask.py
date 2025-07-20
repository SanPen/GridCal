import numpy as np
from scipy.sparse import csr_matrix

# --- Example setup (you already have a CSR, so skip this in your code) ---
# Let’s say n = 21, and A is very sparse:
n = 21
# Create a toy sparse matrix just for illustration:
# (in your case, A already exists as csr_matrix)
random_data = np.random.randn(50)           # 50 nonzero entries
row_idx   = np.random.randint(0, n, size=50)
col_idx   = np.random.randint(0, n, size=50)
A = csr_matrix((random_data, (row_idx, col_idx)), shape=(n, n))

# Suppose this is your final 0/1 mask of length n:
binary = np.array([1, 0, 1, 1, 0, 1, 0, 1, 1, 0,
                   1, 1, 1, 0, 1, 1, 0, 1, 1, 1, 0], dtype=int)
# Convert to boolean array (True = keep, False = drop):
keep = binary.astype(bool)

# --- Filtering rows and columns ---
# 1. Extract the indices of rows/cols you want to keep:
idx = np.nonzero(keep)[0]    # an integer array of “kept” positions

# 2. First slice rows, then slice columns:
A_reduced = A[idx, :][:, idx]

# A_reduced is still a CSR matrix of shape (k, k), where k = keep.sum().
# Any row i (or column i) for which mask[i]==0 has been dropped completely.
print("Original shape:", A.shape)           # (21, 21)
print("Kept indices:", idx)                 # e.g. array([0,2,3,5,7,8,10,...])
print("Reduced shape:", A_reduced.shape)    # (sum(mask), sum(mask))
print("Format still:", A_reduced.getformat())  # 'csr'
