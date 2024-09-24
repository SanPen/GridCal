import numpy as np
import scipy.sparse as sp


class bbd_matrix:

    def __init__(self, block_dim, blocks=None):

        self.block_dim = int(block_dim)
        self.diag_blocks = {}
        self.lower_blocks = {}
        self.right_blocks = {}
        self.corner = None

        self.block_sizes = {}
        self.dimension = 0

        self.complete = False
        self.shape = (None, None)
        self.nnz = 0

        if blocks is not None:
            for block_tuple in blocks:
                if block_tuple[0] == self.block_dim - 1:
                    (idx, dblock) = block_tuple
                    self.corner = dblock
                else:
                    (idx, dblock, rblock, lblock) = block_tuple
                    self.diag_blocks[idx] = dblock
                    self.right_blocks[idx] = rblock
                    self.lower_blocks[idx] = lblock

        return

    def __getitem__(self, key):
        if type(key) != tuple:
            raise TypeError("Index must be a tuple not {}".format(type(key)))
        (row, col) = key
        return self.get_block(row, col)

    def __setitem__(self, key, item):
        if type(key) != tuple:
            raise TypeError("Index must be a tuple not {}".format(type(key)))
        (row, col) = key
        self.add_block(item, row, col)
        return

    def _check_row_size(self, row, p):
        if row in self.block_sizes.keys():
            err_str = "Dimension of row {} is set at {} but given array has {} rows"
            assert self.block_sizes[row] == p, err_str.format(row, self.block_sizes[row], p)
        else:
            assert p > 0, "Dimension of column {} given as {}. Must be > 0.".format(row, p)
            self.dimension += p
            self.block_sizes[row] = p
            if len(self.block_sizes) == self.block_dim:
                self.complete = True
        return

    def _check_col_size(self, col, q):
        if col in self.block_sizes.keys():
            err_str = "Dimension of column {} is set at {} but given array has {} columns"
            assert self.block_sizes[col] == q, err_str.format(col, self.block_sizes[col], q)
        else:
            assert q > 0, "Dimension of column {} given as {}. Must be > 0".format(col, q)
            self.dimension += q
            self.block_sizes[col] = q
            if len(self.block_sizes) == self.block_dim:
                self.complete = True
        return

    def add_diag_block(self, block_mat, idx):

        (p, q) = block_mat.shape
        assert p == q, "BBD matrix requires square matrices on the diagonal. Given matrix is ({},{})".format(p, q)
        self._check_row_size(idx, p)

        if self.complete:
            self.shape = (self.dimension, self.dimension)

        if idx == self.block_dim - 1:
            self.corner = block_mat
        else:
            assert idx not in self.diag_blocks.keys(), "BBD matrix already has entry at ({},{})".format(idx, idx)
            self.diag_blocks[idx] = block_mat

        self.nnz += block_mat.nnz

        return

    def add_lower_block(self, block_mat, idx):
        (p, q) = block_mat.shape
        self._check_row_size(self.block_dim - 1, p)
        self._check_col_size(idx, q)

        assert idx not in self.lower_blocks.keys(), "BBD matrix already has entry at ({},{})".format(
            self.block_dim - 1, idx)

        self.lower_blocks[idx] = block_mat
        self.nnz += block_mat.nnz

        return

    def add_right_block(self, block_mat, idx):
        (p, q) = block_mat.shape
        self._check_row_size(idx, p)
        self._check_col_size(self.block_dim - 1, q)

        assert idx not in self.right_blocks.keys(), "BBD matrix already has entry at ({},{})".format(
            idx, self.block_dim - 1)

        self.right_blocks[idx] = block_mat
        self.nnz += block_mat.nnz

        return

    def add_block(self, block_mat, row, col):
        if row == col:
            self.add_diag_block(block_mat, row)
        elif row == self.block_dim - 1:
            self.add_lower_block(block_mat, col)
        elif col == self.block_dim - 1:
            self.add_right_block(block_mat, row)
        else:
            raise IndexError("BBD matrix cannot contain an entry at ({},{})".format(row, col))
        return

    # def _update_block(self, idx, new_block, old_block, blocks):
    #     assert old_block.shape == new_block.shape, "Given block has shape {} but must have shape {}".format(
    #         new_block.shape,
    #         old_block.shape
    #     )
    #     blocks[idx] = new_block
    #     self.nnz += new_block.nnz - old_block.nnz

    #     return

    # def update_diag_block(self, mat, idx):
    #     assert idx in self.diag_blocks.keys(), "Block at ({},{}) does not exist".format(idx,idx)
    #     old_block = self.diag_blocks[idx]
    #     self._update_block(idx, mat, old_block, self.diag_blocks)
    #     return

    # def update_lower_block(self, mat, idx):
    #     assert idx in self.lower_blocks.keys(), "Block at ({},{}) does not exist".format(self.block_dim - 1, idx)
    #     old_block = self.lower_blocks[idx]
    #     self._update_block(idx, mat, old_block, self.lower_blocks)
    #     return

    # def update_right_block(self, mat, idx):
    #     assert idx in self.right_blocks.keys(), "Block at ({},{}) does not exist".format(idx, self.block_dim - 1)
    #     old_block = self.right_blocks[idx]
    #     self._update_block(idx, mat, old_block, self.right_blocks)
    #     return

    # def update_block(self, mat, row, col):
    #     if row > col:
    #         self.update_lower_block(mat, col)
    #     elif row < col:
    #         self.update_right_block(mat, row)
    #     else:
    #         self.update_diag_block(mat, row)
    #     return

    def get_diag_block(self, idx):
        if idx == self.block_dim - 1:
            block = self.corner
        elif idx not in self.diag_blocks.keys():
            raise IndexError("Block matrix does not contain an entry at ({},{})".format(idx, idx))
        else:
            block = self.diag_blocks[idx]
        return block

    def get_lower_block(self, idx):
        if idx not in self.lower_blocks.keys():
            raise IndexError("Block matrix does not contain an entry at ({},{})".format(self.block_dim - 1, idx))
        return self.lower_blocks[idx]

    def get_right_block(self, idx):
        if idx not in self.right_blocks.keys():
            raise IndexError("Block matrix does not contain an entry at ({},{})".format(idx, self.block_dim - 1))
        return self.right_blocks[idx]

    def get_block(self, row, col, suppress_error=False):
        if row == col:
            block = self.get_diag_block(row)
        elif row == self.block_dim - 1:
            block = self.get_lower_block(col)
        elif col == self.block_dim - 1:
            block = self.get_right_block(row)
        else:
            if suppress_error:
                block = None
            else:
                raise IndexError("BBD matrix does not contain an entry at ({},{})".format(row, col))
        return block

    def to_dense(self, order=None, out=None):
        return self.to_sparse().todense(order=order, out=out)

    def to_sparse(self, format=None):
        assert self.complete
        pattern = []
        for i in range(self.block_dim):
            rp = []
            for j in range(self.block_dim):
                if i == j:
                    rp.append(self.get_diag_block(i))
                elif i == self.block_dim - 1 and j in self.lower_blocks.keys():
                    rp.append(self.get_lower_block(j))
                elif j == self.block_dim - 1 and i in self.right_blocks.keys():
                    rp.append(self.get_right_block(i))
                else:
                    rp.append(None)
            pattern.append(rp)
        return sp.bmat(pattern, format=format)

    def summarize(self):

        # for (idx, size) in self.block_sizes.items():
        #     if idx == self.block_dim - 1:
        #         corner_size = size
        #     else:
        #         if size > max_block_size:
        #             max_block_size = size
        #         if size < min_block_size:
        #             min_block_size = size

        corner_size = self.corner.shape[0]
        if sp.issparse(self.corner):
            corner_nnz = self.corner.nnz
        else:
            corner_nnz = np.count_nonzero(self.corner)

        total_nnz = corner_nnz
        min_block_size = 2 ** 63 - 1
        min_block_nnz = 2 ** 63 - 1
        max_block_size = 0
        max_block_nnz = 0
        for (idx, blk) in self.diag_blocks.items():
            total_nnz += blk.nnz
            if blk.shape[0] > max_block_size:
                max_block_size = blk.shape[0]
            if blk.shape[0] < min_block_size:
                min_block_size = blk.shape[0]
            if blk.nnz > max_block_nnz:
                max_block_nnz = blk.nnz
            if blk.nnz < min_block_nnz:
                min_block_nnz = blk.nnz

        return np.array([
            total_nnz,
            min_block_size, min_block_nnz,
            max_block_size, max_block_nnz,
            corner_size, corner_nnz],
            dtype=int)

    def print_summary(self):

        sum_stats = self.summarize()

        bbd_str = """
        Partition Size: {:7d}
        Total NNZ:      {:7d}
        Min Block Size: {:7d}
        Min Block NNZ:  {:7d}
        Max Block Size: {:7d}
        Max Block NNZ:  {:7d}
        Corner Size:    {:7d}
        Corner NNZ:     {:7d}
        """.format(
            self.block_dim - 1,
            sum_stats[0],
            sum_stats[1],
            sum_stats[2],
            sum_stats[3],
            sum_stats[4],
            sum_stats[5],
            sum_stats[6],
        )

        print(bbd_str)

        return


class block_vector:

    def __init__(self, block_sizes, x_dense=None):

        self.nrows = len(block_sizes)
        self.sizes = block_sizes

        self.indices = {}
        dim = 0
        for i in range(self.nrows):
            self.indices[i] = dim
            dim += self.sizes[i]
        self.shape = (dim,)
        self.size = dim

        if x_dense is not None:
            assert x_dense.shape == self.shape, "Given vector has shape {} but expected shape {}".format(
                x_dense.shape,
                self.shape
            )
            self.vector = x_dense
        else:
            dim = 0
            for i in range(self.nrows):
                dim += self.sizes[i]
            self.vector = np.zeros(dim)
            self.shape = (dim,)

        return

    def __getitem__(self, key):
        if type(key) != int:
            raise TypeError("Index must be an int not {}".format(type(key)))
        return self.get_block(key)

    def __setitem__(self, key, item):
        if type(key) != int:
            raise TypeError("Index must be an int not {}".format(type(key)))
        self.set_block(key, item)
        return

    def _slice_bounds(self, row):
        start_idx = self.indices[row]
        end_idx = start_idx + self.sizes[row]
        return (start_idx, end_idx)

    def set_block(self, row, block_vect):
        dim = self.sizes[row]
        assert block_vect.shape[0] == dim, "Given vector has length {} but must have length {} for row {}".format(
            block_vect.shape[0],
            dim,
            row
        )
        (start_idx, end_idx) = self._slice_bounds(row)
        self.vector[start_idx:end_idx] = block_vect
        return

    def get_block(self, row):
        (start_idx, end_idx) = self._slice_bounds(row)
        return self.vector[start_idx:end_idx]

    def to_dense(self, out=None):
        if out is None:
            return self.vector
        else:
            out[:] = self.vector
            return
