__author__ = 'Santiago Peñate Vera'

# from numba import double, int16, boolean, vectorize, complex128
import numpy as np
# from numba.decorators import jit
from itertools import product
from matplotlib import pyplot as plt

np.set_printoptions(linewidth=200)
from scipy.spatial import cKDTree as KDTree

# http://docs.scipy.org/doc/scipy/reference/spatial.html


class InvDistTree:
    """
    As seen in http://stackoverflow.com/questions/3104781/inverse-distance-weighted-idw-interpolation-with-python
    inverse-distance-weighted interpolation using KDTree:
    invdisttree = Invdisttree( X, z )  -- data points, values
    interpol = invdisttree( q, nnear=3, eps=0, p=1, weights=None, stat=0 )
        interpolates z from the 3 points nearest each query point q;
        For example, interpol[ a query point q ]
        finds the 3 data points nearest q, at distances d1 d2 d3
        and returns the IDW average of the values z1 z2 z3
            (z1/d1 + z2/d2 + z3/d3)
            / (1/d1 + 1/d2 + 1/d3)
            = .55 z1 + .27 z2 + .18 z3  for distances 1 2 3

        q may be one point, or a batch of points.
        eps: approximate nearest, dist <= (1 + eps) * true nearest
        p: use 1 / distance**p
        weights: optional multipliers for 1 / distance**p, of the same shape as q
        stat: accumulate wsum, wn for average weights

    How many nearest neighbors should one take ?
    a) start with 8 11 14 .. 28 in 2d 3d 4d .. 10d; see Wendel's formula
    b) make 3 runs with nnear= e.g. 6 8 10, and look at the results --
        |interpol 6 - interpol 8| etc., or |f - interpol*| if you have f(q).
        I find that runtimes don't increase much at all with nnear -- ymmv.

    p=1, p=2 ?
        p=2 weights nearer points more, farther points less.
        In 2d, the circles around query points have areas ~ distance**2,
        so p=2 is inverse-area weighting. For example,
            (z1/area1 + z2/area2 + z3/area3)
            / (1/area1 + 1/area2 + 1/area3)
            = .74 z1 + .18 z2 + .08 z3  for distances 1 2 3
        Similarly, in 3d, p=3 is inverse-volume weighting.

    Scaling:
        if different X coordinates measure different things, Euclidean distance
        can be way off.  For example, if X0 is in the range 0 to 1
        but X1 0 to 1000, the X1 distances will swamp X0;
        rescale the data, i.e. make X0.std() ~= X1.std() .

    A nice property of IDW is that it's scale-free around query points:
    if I have values z1 z2 z3 from 3 points at distances d1 d2 d3,
    the IDW average
        (z1/d1 + z2/d2 + z3/d3)
        / (1/d1 + 1/d2 + 1/d3)
    is the same for distances 1 2 3, or 10 20 30 -- only the ratios matter.
    In contrast, the commonly-used Gaussian kernel exp( - (distance/h)**2 )
    is exceedingly sensitive to distance and to h.

    """
    # anykernel( dj / av dj ) is also scale-free
    # error analysis, |f(x) - idw(x)| ?

    def __init__(self, measured_points, measured_values, leafsize=10, stat=0):
        """

        @param measured_points:
        @param measured_values:
        @param leafsize:
        @param stat:
        """
        assert len(measured_points) == len(measured_values), "len(X) %d != len(z) %d" % (len(measured_points), len(measured_values))
        self.tree = KDTree(measured_points, leafsize=leafsize)  # build the tree
        self.z = measured_values
        self.stat = stat
        self.wn = 0
        self.wsum = None

    def __call__(self, new_points, num_near=6, eps=0, p=1, weights=None):
        """
        Call an interpolation with the trained data
        @param new_points:
        @param num_near: Number of near-by points
        @param eps: Tolerance
        @param p: 1<=p<=infinity. Which Minkowski p-norm to use. 1 is the sum-of-absolute-values "Manhattan" distance 2
                  is the usual Euclidean distance infinity is the maximum-coordinate-difference distance
        @param weights:
        @return:
        """

        # num_near nearest neighbours of each query point --
        new_points = np.asarray(new_points, dtype=complex)
        qdim = new_points.ndim
        if qdim == 1:
            new_points = np.array([new_points], dtype=complex)
        if self.wsum is None:
            self.wsum = np.zeros(num_near)

        # get the nearest neighbours of each point
        '''
        self.distances : array of floats. The distances to the nearest neighbors. If x has shape tuple+(self.m,), then
                         d has shape tuple+(k,). Missing neighbors are indicated with infinite distances.

        self.ix : ndarray of ints. The locations of the neighbors in self.data. If x has shape tuple+(self.m,), then i
                  has shape tuple+(k,). Missing neighbors are indicated with self.n.
        '''
        self.distances, self.ix = self.tree.query(new_points, k=num_near, eps=eps)

        # declare the interpolation array
        interpol = np.empty((len(self.distances),) + np.shape(self.z[0]), dtype=complex)

        # Perform the interpolation
        idx = 0
        for dist, ix in zip(self.distances, self.ix):
            if num_near == 1:
                wz = self.z[ix]
            elif dist[0] < 1e-10:
                wz = self.z[ix[0]]
            else:  # weight z s by 1/dist --
                w = 1 / np.power(dist, p)
                if weights is not None:
                    w *= weights[ix]  # >= 0
                w /= np.sum(w)
                wz = np.dot(w, self.z[ix])
                if self.stat:
                    self.wn += 1
                    self.wsum += w
            interpol[idx] = wz
            idx += 1

        return interpol if qdim > 1 else interpol[0]


def KDTreeInterp(measured_points, new_points, measured_voltages):
    """
    KD-Tree interpolation
    @param measured_points: Measured Power points (row: points, cols: nodes)
    @param new_points: New Power points (row: points, cols: nodes) to get the Voltage values with
    @param measured_voltages: Measured voltage values, the response of S
    @return: THe new Voltage values matching Snew
    """
    Nnear = 18  # 8 2d, 11 3d => 5 % chance one-sided -- Wendel, mathoverflow.com
    leafsize = 25
    eps = 1e-3  # approximate nearest, dist <= (1 + eps) * true nearest
    p = 1  # weights ~ 1 / distance**p

    # Create the tree
    print('Training KDTree...')
    invdisttree = InvDistTree(measured_points, measured_voltages, leafsize=leafsize, stat=1)

    # RInterpolate the sample
    print('Interpolating...')
    Vnew = invdisttree(new_points, num_near=Nnear, eps=eps, p=p)

    print('done!')
    return Vnew


# @jit(argtypes=[double, double], target='cpu')
# @vectorize(['double(double, double)'], target='cpu')
def fast_normal(x, s):
    """
    Function that returns the area of the two tails of the Normal law with the mean equal to zero
    x: point
    s: standard deviation

    returns: 1 - probability of x.
    """
    #    if x > (8*s):
    #        qx = 0.0
    #
    #    else:
    xm = 0
    # define coefficients B[i)
    B = np.array([1.330274429, -1.821255978, 1.781477937, -0.356563782, 0.319381530])
    pp = 0.2316419
    y = (x - xm) / s  # reduced variable
    zy = np.exp(-y * y / 2.0) / 2.506628275
    # fx = zy / s;
    # calculate qx by Horner's method
    t = 1.0 / (1.0 + pp * y)
    po = 0.0
    for Bi in B:
        po = po * t + Bi
    po *= t
    qx = zy * po  # 1-probability = tail
    # *px = 1.0 - *qx; #probability

    return 2 * qx  # twice the tail


def euclidean_distance_nd(point1, point2, dim):
    """
    Euclidean distance in N dimensions
    @param point1: Array of coordinates of the Point P
    @param point2: Array of coordinates of the point S (must agree the dimensions of P)
    @param dim: number of dimensions (provided for speed)
    @return: Euclidean distance between the points P and S
    """
    sum_ = 0
    for i in range(dim):
        sum_ += np.power(point1[i] - point2[i], dim)

    d = np.power(sum_, 1.0 / dim)
    return d


# @jit(argtypes=[double[:], double[:], double[:], double[:], double[:]], target='cpu')
def create_distance_matrix(sigma, measured_points, new_points):
    """
    Calculates the probability given the sensor position {sx, sy} and the
    particle position {px, py} and a certain standard deviation of the normal
    law used
    @param sigma: standard deviation (parameter of choice) after 6sigma, the distance is zero
    @param measured_points: 2D array containing the measured points coordinates (row: point index, col: dimension index)
    @param new_points: 2D array containing the new points coordinates (row: point index, col: dimension index)

    @return: Distance matrix (rows: measured point index, cols: new point index)
    """

    new_num, dim_new = np.shape(new_points)
    measured_num, dim = np.shape(measured_points)

    assert dim_new == dim

    d_matrix = np.empty((measured_num, new_num), dtype=type(measured_points[0, 0]))
    for i, j in product(range(measured_num), range(new_num)):
        d = euclidean_distance_nd(measured_points[i, :], new_points[j, :], dim)
        d_matrix[i, j] = fast_normal(d, sigma)

    return d_matrix, measured_num, new_num


# @jit(argtypes=[double[:, :], double[:], int16, int16], target='cpu')
def interpolate_(d_matrix, measured_values, measured_num, new_num):
    """
    Compute the particles irradiation level and weight based on the probabilistic
    smoothing of the sensor measurements.
    @param d_matrix: Distance matrix
    @param measured_values: 2D array containing the values of the measured points
    @param measured_num: number of measured values -> number of columns of d_matrix
    @param new_num: number of new values -> number of rows of d_matrix

    @return:
    """

    values_num, dim_vals = np.shape(measured_values)

    assert values_num == measured_num

    interpolated_values = np.empty((new_num, dim_vals), dtype=type(measured_values[0, 0]))
    for i in range(new_num):
        # sum_d = 0.0
        # sum_d_val = 0.0
        # for j in range(measured_num):
        #     sum_d += d_matrix[j, i]
        #     sum_d_val += measured_values[j, :] * d_matrix[j, i]
        sum_d = np.sum(d_matrix[:, i])
        sum_d_val = np.dot(measured_values.transpose(), d_matrix[:, i])

        if sum_d != 0:
            interpolated_values[i, :] = sum_d_val / sum_d
        else:
            interpolated_values[i, :] = 0

    return interpolated_values


def interpolate(measured_points, new_points, measured_values, sigma_):
    """
    Interpolation using the bayesian estimation technique
    @param measured_points: 2D array containing the measured points coordinates (row: point index, col: dimension index)
    @param new_points: 2D array containing the new points coordinates (row: point index, col: dimension index)
    @param measured_values: 2D array containing the values of the measured points
    @param sigma_: per unit standard deviation to consider
    @return: Interpolated points as 2D array (row: point index, col: dimension index)
    """

    # compute the value of sigma
    dim = len(measured_points.transpose())
    p_min = [np.min(measured_points[:, i]) for i in range(dim)]
    p_max = [np.max(measured_points[:, i]) for i in range(dim)]
    sigma = euclidean_distance_nd(p_min, p_max, dim) * sigma_

    # create the distance matrix
    d_mat, measured_num, new_num = create_distance_matrix(sigma, measured_points, new_points)

    # interpolate the new points
    new_values = interpolate_(d_mat, measured_values, measured_num, new_num)

    return new_values

if __name__ == '__main__':
    print('Test')
    res = np.load('Bus6_stochastic_voltages.npz')

    V = res['V']
    S = res['S']

    # pick the first Power point to interpolate (because we know that the solution is V[0, :])
    Snew = np.array([S[0, :]])

    # interpolate
    Vnew = interpolate(S, Snew, V, 0.01)

    # compute the difference
    diff = Vnew[0, :] - V[0, :]

    print('Error: ', max(abs(diff)))

    ####################################################################################################################
    # Again with a new point
    ####################################################################################################################
    dim = len(S.transpose())
    p_min = np.array([np.min(S[:, i]) for i in range(dim)])
    p_max = np.array([np.max(S[:, i]) for i in range(dim)])

    Snew = list()
    rnd = np.random.random_sample(100).transpose()
    for r in rnd:
        Snew.append(p_min + (p_max - p_min) * r)
    Snew = np.array(Snew)

    Vnew = interpolate(S, Snew, V, 0.1)

    Vnew.sort(axis=0)  # no need to sort
    print('|V|\n', abs(Vnew))

    # plt.plot(abs(Vnew))
    # plt.show()