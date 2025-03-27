"""
Overhead Line Constants Calculation Library

Reference:
    [1] Dommel, H. W., "Electromagnetic Transients Program Reference Manual (EMTP Theory Book)", Chapter 4, "Overhead Transmission Lines".
    [2] Arrillaga, J., and Watson, N. R., "Computer Modelling of Electrical Power Systems", 2nd Edition, Wiley, 2005, Chapter 2.6

Functions:
    calc_L_int          Calculates internal inductance of solid or tubular conductor
    calc_GMR            Calculates geometric mean radius (GMR) of solid or tubular conductor
    carsons             Calculates Carson's earth return correction factors Rp and Xp for self or mutual terms
    calc_self_Z         Calculates self impedance term (in Ohm/km)
    calc_mutual_Z       Calculates mutual impedance term (in Ohm/km)
    calc_Dubanton_Z     Calculates Dubanton approximation for self or mutual impedance (in Ohm/km)
    calc_Z_matrix       Calculates primitive impedance matrix
    calc_Y_matrix       Calculates primitive admittance matrix
    calc_kron_Z         Calculates Kron reduced matrix
"""

import numpy as np

def calc_L_int(type, r, q):
    """
    Calculates internal inductance of solid or tubular conductor
    Note that calculations assume uniform current distribution in the conductor, thus conductor stranding is not taken into account.

    Usage:
        L_int = calc_L_int(type, r, q)

    where:
       type is 'solid' or 'tube'
        r is the radius of the conductor [m]
        q is the radius of the inner tube [m]

    Returns:
        L_int the internal inductance of the conductor [H/m]
    """
    mu_0 = 4 * np.pi * 1e-7 # Permeability of free space [H/m]

    if type == 'solid':
        L_int = mu_0 / 8 / np.pi # Solid conductor internal inductance [H/m]
    else:
        L_int = mu_0 / 2 / np.pi * (q ** 4 / (r ** 2 - q ** 2) ** 2 * np.log(r / q) - (3 * q ** 2 - r ** 2) / (4 * (r ** 2 - q ** 2))) # Tubular conductor internal inductance [H/m]

    return L_int


def calc_GMR(type, r, q):
    """
    Calculates geometric mean radius (GMR) of solid or tubular conductor
    Note that calculations assume uniform current distribution in the conductor, thus conductor stranding is not taken into account.

    Usage:
        GMR = calc_GMR(type, r, q)

    where   type is 'solid' or 'tube'
            r is the radius of the conductor [m]
            q is the radius of the inner tube [m]

    Returns:
            GMR the geometric mean radius [m]
    """
    if type == 'solid':
        GMR = r * np.exp(-0.25) # Solid conductor GMR [m]
    else:
        GMR = r * np.exp((3 * q ** 2 - r ** 2) / (4 * (r ** 2 - q ** 2)) - q ** 4 / (r ** 2 - q ** 2) ** 2 * np.log(r / q)) # Tubular conductor GMR [m]

    return GMR


def carsons(type, h_i, h_k, x_ik, f, rho, err_tol=1e-6):
    """
    Calculates Carson's earth return correction factors Rp and Xp for both self and mutual terms.
    The number of terms evaluated in the infinite loop is based on convergence to the desired error tolerance.

    Usage:
        Rp, Xp = carsons(type, h_i, h_k, x_ik, f, rho, err_tol)

    where   type is 'self' or 'mutual'
            h_i is the height of conductor i above ground (m)
            h_k is the height of conductor k above ground (m)
            x_ik is the horizontal distance between conductors i and k (m)
            f is the frequency (Hz)
            rho is the earth resistivity (Ohm.m)
            err_tol is the error tolerance for the calculation (default = 1e-6)

    Returns:
            Rp, Xp the Carson earth return correction factors (in Ohm/km)
    """
    # Geometrical calculations - See Figure 4.4. of EMTP Theory Book
    if type == 'self':
        D = 2 * h_i # Distance between conductor i and its image [m]
        cos_phi = 1
        sin_phi = 0
        phi = 0
    else:
        D = np.sqrt((h_i + h_k) ** 2 + x_ik ** 2)  # Distance between conductor i and image of conductor k [m]
        cos_phi = (h_i + h_k) / D
        sin_phi = (x_ik) / D
        phi = np.arccos(cos_phi)

    # Initialise parameters
    i = 1
    err = 1
    sgn = 1

    # Initial values and constants for calculation
    omega = 2 * np.pi * f
    a = 4 * np.pi * np.sqrt(5) * 1e-4 * D * np.sqrt(f / rho) # Equation 4.10 EMTP
    acosphi = a * cos_phi
    asinphi = a * sin_phi
    b = np.array([np.sqrt(2) / 6, 1 / 16]) # Equation 4.12 EMTP
    c = np.array([0, 1.3659315])
    d = np.pi / 4 * b

    # First two terms of carson correction factor
    Rp = np.pi / 8 - b[0] * acosphi
    Xp = 0.5 * (0.6159315 - np.log(a)) + b[0] * acosphi

    # Loop through carson coefficient terms starting with i = 2
    while (err > err_tol):
        term = np.mod(i, 4)
        # Check sign for b term
        if term == 0:
            sgn = -1 * sgn

        # Calculate coefficients
        bi = b[i - 1] * sgn / ((i + 1) * (i + 3))
        ci = c[i - 1] + 1 / (i + 1) + 1 / (i + 3)
        di = np.pi / 4 * bi
        b = np.append(b, bi)
        c = np.append(c, ci)
        d = np.append(d, di)

        # Recursively calculate powers of acosphi and asinphi
        acosphi_prev = acosphi
        asinphi_prev = asinphi
        acosphi = (acosphi_prev * cos_phi - asinphi_prev * sin_phi) * a
        asinphi = (acosphi_prev * sin_phi + asinphi_prev * cos_phi) * a

        Rp_prev = Rp
        Xp_prev = Xp

        # First term
        if term == 0:
            Rp = Rp - bi * acosphi
            Xp = Xp + bi * acosphi

        # Second term
        elif term == 1:
            Rp = Rp + bi * ((ci - np.log(a)) * acosphi + phi * asinphi)
            Xp = Xp - di * acosphi

        # Third term
        elif term == 1:
            Rp = Rp + bi * acosphi
            Xp = Xp + bi * acosphi

        # Fourth term
        else:
            Rp = Rp - di * acosphi
            Xp = Xp - bi * ((ci - np.log(a)) * acosphi + phi * asinphi)

        i = i = 1
        err = np.sqrt((Rp - Rp_prev) ** 2 + (Xp - Xp_prev) ** 2)

    Rp = 4 * omega * 1e-04 * Rp
    Xp = 4 * omega * 1e-04 * Xp
    return Rp, Xp


def calc_self_Z(R_int, cond_type, r, q, h_i, f, rho, err_tol=1e-6):
    """
    Calculates self impedance term [Ohm/km]
    NOTE: No allowance has been made for skin effects

    Usage:
        self_Z = calc_self_Z(R_int, cond_type, r, q, h_i, f, rho, err_tol=1e-6)

    where   R_int is the AC conductor resistance [Ohm/km]
            cond_type is the conductor type ('solid' or 'tube')
            r is the radius of the conductor [m]
            q is the radius of the inner tube [m]
            h_i is the height of conductor i above ground [m]
            f is the frequency [Hz]
            rho is the earth resistivity [Ohm.m]
            err_tol is the error tolerance for the calculation (default = 1e-6)

    Returns:
            self_Z the self impedance term of line impedance matrix [Ohm/km]
    """
    # Constants
    omega = 2 * np.pi * f  # Nominal angular frequency [rad/s]
    mu_0 = 4 * np.pi * 1e-7  # Permeability of free space [H/m]

    # Calculate internal conductor reactance (in Ohm/km)
    X_int = 1000 * omega * calc_L_int(cond_type, r, q)

    # Calculate geometrical reactance (in Ohm/km) - Equation 4.15 EMTP
    X_geo = 1000 * omega * mu_0 / 2 / np.pi * np.log(2 * h_i / r)

    # Calculate Carson's correction factors (in Ohm/km)
    Rp, Xp = carsons('self', h_i, 0, 0, f, rho, err_tol)

    self_Z = complex(R_int + Rp, X_int + X_geo + Xp)

    return self_Z


def calc_mutual_Z(cond_type, r, q, h_i, h_k, x_ik, f, rho, err_tol=1e-6):
    """
    Calculates mutual impedance term [Ohm/km]

    Usage:
        mutual_Z = calc_mutual_Z(cond_type, r, q, h_i, h_k, x_ik, f, rho, err_tol=1e-6)

    where   cond_type is the conductor type ('solid' or 'tube')
            r is the radius of the conductor [m]
            q is the radius of the inner tube [m]
            h_i is the height of conductor i above ground [m]
            h_k is the height of conductor k above ground [m]
            x_ik is the horizontal distance between conductors i and k [m]
            f is the frequency [Hz]
            rho is the earth resistivity [Ohm.m]
            err_tol is the error tolerance for the calculation (default = 1e-6)

    Returns:
            mutual_Z the self impedance term of line impedance matrix (Ohm/km)
    """
    # Constants
    omega = 2 * np.pi * f  # Nominal angular frequency [rad/s]
    mu_0 = 4 * np.pi * 1e-7  # Permeability of free space [H/m]
    # See Figure 4.4. EMTP
    D = np.sqrt((h_i + h_k) ** 2 + x_ik ** 2)  # Distance between conductor i and image of conductor k [m]
    d = np.sqrt((h_i - h_k) ** 2 + x_ik ** 2)  # Distance between conductors i and k [m]

    # Calculate geometrical mutual reactance (in Ohm/km)
    X_geo = 1000 * omega * mu_0 / 2 / np.pi * np.log(D / d)

    # Calculate Carson's correction factors (in Ohm/km)
    Rp, Xp = carsons('mutual', h_i, h_k, x_ik, f, rho, err_tol)

    mutual_Z = complex(Rp, X_geo + Xp)

    return mutual_Z


def calc_Dubanton_Z(type, R_int, cond_type, r, q, h_i, h_k, x_ik, f, rho):
    """
    Calculates Dubanton approximation for self or mutual impedance (in Ohm/km)

    Usage:
        Dubanton_Z = calc_Dubanton_Z(type, R_int, cond_type, r, q, h_i, h_k, x_ik, f, rho)

    where   type is 'self' or 'mutual'
            cond_type is the conductor type ('solid' or 'tube')
            r is the radius of the conductor [m]
            q is the radius of the inner tube [m]
            h_i is the height of conductor i above ground [m]
            h_k is the height of conductor k above ground [m]
            x_ik is the horizontal distance between conductors i and k [m]
            f is the frequency [Hz]
            rho is the earth resistivity [Ohm.m]

    Returns:
            Dubanton_Z the self or mutual impedance term of line impedance matrix (Ohm/km)
    """
    # Constants
    omega = 2 * np.pi * f  # Nominal angular frequency [rad/s]
    mu_0 = 4 * np.pi * 1e-7  # Permeability of free space [H/m]
    p = np.sqrt(rho / omega / mu_0)  # Complex depth below earth

    if type == 'self':
        # Self impedance
        # Calculate internal conductor reactance (in Ohm/km)
        X_int = 1000 * omega * calc_L_int(cond_type, r, q)

        # Calculate geometrical reactance (in Ohm/km)
        X_geo = 1000 * omega * mu_0 / 2 / np.pi * np.log((h_i + p) / r)

        Dubanton_Z = complex(R_int, X_int + X_geo)

    else:
        # Mutual impedance
        d = np.sqrt((h_i - h_k) ** 2 + x_ik ** 2)  # Distance between conductors i and k [m]
        X_geo = 1000 * omega * mu_0 / 2 / np.pi * np.log(np.sqrt((h_i + h_k + 2 * p) ** 2 + x_ik ** 2) / d)

        Dubanton_Z = complex(0, X_geo)

    return Dubanton_Z


def calc_Z_matrix(line_dict):
    """
    Calculates primitive impedance matrix
    NOTE: all phase conductor vectors must be the same size. No checks are made to enforce this. Same goes for earth conductor vectors.

    Usage:
        Z = calc_Z_matrix(line_dict)

    where   line_dict is a dictionary of overhead line parameters:
                'mode' is the calculate mode ('carson' or 'dubanton')
                'f' is the nominal frequency (Hz)
                'rho' is the earth resistivity (Ohm.m)
                'err_tol' is the error tolerance for the calculation (default = 1e-6)
                'phase_h' is a vector of phase conductor heights above ground (m)
                'phase_x' is a vector of phase conductor horizontal spacings with arbitrary reference point (m)
                'phase_cond' is a vector of phase conductor types ('solid' or 'tube')
                'phase_R' is a vector of phase conductor AC resistances (Ohm/km)
                'phase_r' is a vector of phase conductor radii [m]
                'phase_q' is a vector of phase conductor inner tube radii [m] - use 0 for solid conductors
                'earth_h' is a vector of earth conductor heights above ground (m)
                'earth_x' is a vector of earth conductor horizontal spacings with arbitrary reference point (m)
                'earth_cond' is a vector of earth conductor types ('solid' or 'tube')
                'earth_R' is a vector of earth conductor AC resistances (Ohm/km)
                'earth_r' is a vector of earth conductor radii [m]
                'earth_q' is a vector of earth conductor inner tube radii [m] - use 0 for solid conductors

    Returns:
            Z is the primitive impedance matrix (with earth conductors shown first)
            n_p is the number of phase conductors
            n_e is the number of earth conductors
    """
    # Unpack line dictionary
    mode = line_dict['mode']
    f = line_dict['f']
    rho = line_dict['rho']
    cond_h = line_dict['earth_h'] + line_dict['phase_h']
    cond_x = line_dict['earth_x'] + line_dict['phase_x']
    cond_type = line_dict['earth_cond'] + line_dict['phase_cond']
    cond_R = line_dict['earth_R'] + line_dict['phase_R']
    cond_r = line_dict['earth_r'] + line_dict['phase_r']
    cond_q = line_dict['earth_q'] + line_dict['phase_q']

    # Set error tolerance for carsons equations
    if 'err_tol' in line_dict:
        err_tol = line_dict['err_tol']
    else:
        err_tol = 1e-6

    # Number of phase and earth conductors
    n_p = len(line_dict['phase_h'])
    n_e = len(line_dict['earth_h'])
    n_c = n_p + n_e

    # Set up primitive Z matrix
    Z = np.asmatrix(np.zeros((n_c, n_c)), dtype='complex') # [Ohm/km]
    if mode == 'carson':
        for i in range(n_c):
            for j in range(n_c):
                if i == j:
                    Z[i, j] = calc_self_Z(cond_R[i], cond_type[i], cond_r[i], cond_q[i], cond_h[i], f, rho, err_tol)
                else:
                    Z[i, j] = calc_mutual_Z(cond_type[i], cond_r[i], cond_q[i], cond_h[i], cond_h[j], cond_x[i] - cond_x[j], f, rho, err_tol)
    else:
        for i in range(n_c):
            for j in range(n_c):
                if i == j:
                    Z[i, j] = calc_Dubanton_Z('self', cond_R[i], cond_type[i], cond_r[i], cond_q[i], cond_h[i], cond_h[j], cond_x[i] - cond_x[j], f, rho)
                else:
                    Z[i, j] = calc_Dubanton_Z('mutual', cond_R[i], cond_type[i], cond_r[i], cond_q[i], cond_h[i], cond_h[j], cond_x[i] - cond_x[j], f, rho)

    return Z, n_p, n_e


def calc_Y_matrix(line_dict):
    """
    Calculates primitive admittance matrix
    Assumes that conductance of air is zero.
    NOTE: all phase conductor vectors must be the same size. No checks are made to enforce this. Same goes for earth conductor vectors.

    Usage:
        Y = calc_Y_matrix(line_dict)

    where   line_dict is a dictionary of overhead line parameters:
                'f' is the nominal frequency [Hz]
                'rho' is the earth resistivity [Ohm.m]
                'phase_h' is a vector of phase conductor heights above ground [m]
                'phase_x' is a vector of phase conductor horizontal spacings with arbitrary reference point [m]
                'phase_r' is a vector of phase conductor radii [m]
                'earth_h' is a vector of earth conductor heights above ground [m]
                'earth_x' is a vector of earth conductor horizontal spacings with arbitrary reference point [m]
                'earth_r' is a vector of earth conductor radii [m]

    Returns:
            Y is the primitive admittance matrix (with earth conductors shown first)
            n_p is the number of phase conductors
            n_e is the number of earth conductors
    """
    # Unpack line dictionary
    f = line_dict['f']
    rho = line_dict['rho']
    cond_h = line_dict['earth_h'] + line_dict['phase_h']
    cond_x = line_dict['earth_x'] + line_dict['phase_x']
    cond_r = line_dict['earth_r'] + line_dict['phase_r']

    # Number of phase and earth conductors
    n_p = len(line_dict['phase_h'])
    n_e = len(line_dict['earth_h'])
    n_c = n_p + n_e

    # Constants
    omega = 2 * np.pi * f  # Nominal angular frequency [rad/s]
    e_0 = 8.85418782 * 1e-12  # Permittivity of free space [F/m]

    # Set up primitive Y matrix
    Y = np.asmatrix(np.zeros((n_c, n_c)), dtype='complex')
    # Build up potential coefficients
    for i in range(n_c):
        for j in range(n_c):
            if i == j:
                # Self potential coefficient
                Y[i, j] = (1 / 2 / np.pi / e_0) * np.log(2 * cond_h[i] / cond_r[i])
            else:
                # Mutual potential coefficient
                D = np.sqrt((cond_h[i] + cond_h[j]) ** 2 + (
                            cond_x[i] - cond_x[j]) ** 2)  # Distance between conductor i and image of conductor k [m]
                d = np.sqrt(
                    (cond_h[i] - cond_h[j]) ** 2 + (cond_x[i] - cond_x[j]) ** 2)  # Distance between conductors i and k [m]
                Y[i, j] = (1 / 2 / np.pi / e_0) * np.log(D / d)

    Y = 1000j * omega * Y.I # [S/km]

    return Y, n_p, n_e


def kron_reduction(mat, keep, embed):
    """
    Perform the Kron reduction
    :param mat: primitive matrix
    :param keep: indices to keep
    :param embed: indices to remove / embed
    :return:
    """
    Zaa = mat[np.ix_(keep, keep)]
    Zag = mat[np.ix_(keep, embed)]
    Zga = mat[np.ix_(embed, keep)]
    Zgg = mat[np.ix_(embed, embed)]

    return Zaa - Zag.dot(np.linalg.inv(Zgg)).dot(Zga)


def wire_bundling_shunt(phases_set, primitive, phases_vector):
    """
    Algorithm to bundle wires per phase for a shunt admittance matrix
    :param phases_set: set of phases (list with unique occurrences of each phase values, i.e. [0, 1, 2, 3])
    :param primitive: Primitive matrix to reduce by bundling wires
    :param phases_vector: Vector that contains the phase of each wire
    :return: reduced primitive matrix, corresponding phases
    """
    # Convert phases_vector to numpy array to ensure consistent type handling
    phases_vector = np.array(phases_vector)
    
    # Create a new empty matrix
    nph = len(phases_set)
    bundled_matrix = np.zeros((nph, nph), dtype=primitive.dtype)
    
    for r_idx, phase_r in enumerate(phases_set):
        # get the row indices
        r_indices = np.where(phases_vector == phase_r)[0]
        
        if len(r_indices) == 0:
            print(f"Warning: No wires found for phase {phase_r}")
            continue
        
        # get the column indices
        for c_idx, phase_c in enumerate(phases_set):
            c_indices = np.where(phases_vector == phase_c)[0]
            
            if len(c_indices) == 0:
                print(f"Warning: No wires found for phase {phase_c}")
                continue
            
            # Calculate the bundled admittance for this phase pair
            total_admittance = 0.0
            for r_wire in r_indices:
                for c_wire in c_indices:
                    total_admittance += primitive[r_wire, c_wire]
            
            # Store the total admittance in the bundled matrix
            bundled_matrix[r_idx, c_idx] = total_admittance
    
    # Create a phases vector for the bundled matrix
    bundled_phases = np.array(list(phases_set))
    
    return bundled_matrix, bundled_phases


def wire_bundling(phases_set, primitive, phases_vector):
    """
    Algorithm to bundle wires per phase
    :param phases_set: set of phases (list with unique occurrences of each phase values, i.e. [0, 1, 2, 3])
    :param primitive: Primitive matrix to reduce by bundling wires
    :param phases_vector: Vector that contains the phase of each wire
    :return: reduced primitive matrix, corresponding phases
    """

    phases_vector = np.array(phases_vector)

    for phase in phases_set:

        # get the list of wire indices
        wires_indices = np.where(phases_vector == phase)[0]

        if len(wires_indices) > 1:

            # get the first wire and remove it from the wires list
            i = wires_indices[0]

            # wires to keep
            a = np.r_[i, np.where(phases_vector != phase)[0]]

            # wires to reduce
            g = wires_indices[1:]

            # column subtraction
            for k in g:
                primitive[:, k] -= primitive[:, i]

            # row subtraction
            for k in g:
                primitive[k, :] -= primitive[i, :]

            # kron - reduction to Zabcn
            primitive = kron_reduction(mat=primitive, keep=a, embed=g)

            # reduce the phases too
            phases_vector = phases_vector[a]

        else:
            # only one wire in this phase: nothing to do
            pass

    return primitive, phases_vector

"""
# 12 conductors
bundle = 0.46  # [m]
Rdc = 0.1363  # [Ohm/km]
r_ext = 10.5e-3  # [m]
r_int = 4.5e-3  # [m]

Ya = 27.5
Yb = 27.5
Yc = 27.5

Xa = -12.65
Xb = 0
Xc = 12.65

line_dict = {
    'mode': 'carson',
    'f': 50,  # Nominal frequency [Hz]
    'rho': 100,  # Earth resistivity [Ohm.m]
    'phase_h': [Ya + bundle / 2, Ya + bundle / 2, Ya - bundle / 2, Ya - bundle / 2, Yb + bundle / 2,
                Yb + bundle / 2, Yb - bundle / 2, Yb - bundle / 2, Yc + bundle / 2, Yc + bundle / 2,
                Yc - bundle / 2, Yc - bundle / 2],  # Phase conductor heights [m]
    'phase_x': [Xa - bundle / 2, Xa + bundle / 2, Xa - bundle / 2, Xa + bundle / 2, Xb - bundle / 2,
                Xb + bundle / 2, Xb - bundle / 2, Xb + bundle / 2, Xc - bundle / 2, Xc + bundle / 2,
                Xc - bundle / 2, Xc + bundle / 2],  # Phase conductor x-axis coordinates [m]
    'phase_cond': ['tube', 'tube', 'tube', 'tube', 'tube', 'tube', 'tube', 'tube', 'tube', 'tube', 'tube', 'tube'],
    # Phase conductor types ('tube' or 'solid')
    'phase_R': [Rdc, Rdc, Rdc, Rdc, Rdc, Rdc, Rdc, Rdc, Rdc, Rdc, Rdc, Rdc],  # Phase conductor resistances [Ohm/km]
    'phase_r': [r_ext, r_ext, r_ext, r_ext, r_ext, r_ext, r_ext, r_ext, r_ext, r_ext, r_ext, r_ext],
    # Phase conductor radi [m]
    'phase_q': [r_int, r_int, r_int, r_int, r_int, r_int, r_int, r_int, r_int, r_int, r_int, r_int],
    # Phase conductor inner tube radii [m]
    'earth_h': [],  # Earth conductor heights [m]
    'earth_x': [],  # Earth conductor x-axis coordinates [m]
    'earth_cond': [],  # Earth conductor types ('tube' or 'solid')
    'earth_R': [],  # Earth conductor AC resistances [Ohm/km]
    'earth_r': [],  # Earth conductor radi [m]
    'earth_q': []  # Earth conductor inner tube radii [m]
}

# Impedance matrix
Zprimitive, n_p, n_e = calc_Z_matrix(line_dict)
Zreduced, phases_vector = wire_bundling([1,2,3], Zprimitive, [1,1,1,1,2,2,2,2,3,3,3,3])

print()
print()
print(Zreduced)

# Admittance matrix
Yprimitive, n_p, n_e = calc_Y_matrix(line_dict)
Yreduced, phases_vector = wire_bundling_shunt([1,2,3], Yprimitive, [1,1,1,1,2,2,2,2,3,3,3,3])

print()
print()
print(Yreduced * 1e6)
"""




"""
# 3 conductors
bundle = 0.46  # [m]
Rdc = 0.1363  # [Ohm/km]
r_ext = 10.5e-3  # [m]
r_int = 4.5e-3  # [m]

Ya = 27.5
Yb = 27.5
Yc = 27.5

Xa = -12.65
Xb = 0
Xc = 12.65

# Overhead line parameters (Single circuit tower with an overhead earth wire)
line_dict = {
    'mode': 'carson', # carson or dubanton
    'f': 50,  # Nominal frequency [Hz]
    'rho': 100,  # Earth resistivity [Ohm.m]
    'phase_h': [27.5, 27.5, 27.5],  # Phase conductor heights [m]
    'phase_x': [-12.65, 0, 12.65],  # Phase conductor x-axis coordinates [m]
    'phase_cond': ['tube', 'tube', 'tube'],  # Phase conductor types ('tube' or 'solid')
    'phase_R': [0.1363, 0.1363, 0.1363],  # Phase conductor AC resistances [Ohm/km]
    'phase_r': [0.0105, 0.0105, 0.0105],  # Phase conductor radi [m]
    'phase_q': [0.0045, 0.0045, 0.0045],  # Phase conductor inner tube radii [m]
    'earth_h': [],  # Earth conductor heights [m]
    'earth_x': [],  # Earth conductor x-axis coordinates [m]
    'earth_cond': [],  # Earth conductor types ('tube' or 'solid')
    'earth_R': [],  # Earth conductor AC resistances [Ohm/km]
    'earth_r': [],  # Earth conductor radi [m]
    'earth_q': []  # Earth conductor inner tube radii [m]
}

# Impedance matrix
Zprimitive, n_p, n_e = calc_Z_matrix(line_dict)
Zreduced, phases_vector = wire_bundling([1,2,3], Zprimitive, [1,2,3])

print()
print()
print(Zreduced)

# Admittance matrix
Yprimitive, n_p, n_e = calc_Y_matrix(line_dict)
Yreduced, phases_vector = wire_bundling_shunt([1,2,3], Yprimitive, [1,2,3])

print()
print()
print(Yreduced * 1e6)
"""

# """
# 6 conductors
bundle = 0.4  # [m]
Rdc = 0.0857  # [Ohm/km]
r_ext = 25.38e-3 / 2 # [m]
r_int = 8.46e-3 / 2 # [m]

Ya = 19.5
Yb = 19.5
Yc = 19.5

Xa = -9
Xb = 0
Xc = 9

line_dict = {
    'mode': 'carson',
    'f': 50,  # Nominal frequency [Hz]
    'rho': 100,  # Earth resistivity [Ohm.m]
    'phase_h': [Ya, Ya, Yb, Yb, Yc, Yc],  # Phase conductor heights [m]
    'phase_x': [Xa - bundle / 2, Xa + bundle / 2, Xb - bundle / 2, Xb + bundle / 2, Xc - bundle / 2, Xc + bundle / 2],  # Phase conductor x-axis coordinates [m]
    'phase_cond': ['tube', 'tube', 'tube', 'tube', 'tube', 'tube'],
    # Phase conductor types ('tube' or 'solid')
    'phase_R': [Rdc, Rdc, Rdc, Rdc, Rdc, Rdc],  # Phase conductor resistances [Ohm/km]
    'phase_r': [r_ext, r_ext, r_ext, r_ext, r_ext, r_ext],
    # Phase conductor radi [m]
    'phase_q': [r_int, r_int, r_int, r_int, r_int, r_int],
    # Phase conductor inner tube radii [m]
    'earth_h': [],  # Earth conductor heights [m]
    'earth_x': [],  # Earth conductor x-axis coordinates [m]
    'earth_cond': [],  # Earth conductor types ('tube' or 'solid')
    'earth_R': [],  # Earth conductor AC resistances [Ohm/km]
    'earth_r': [],  # Earth conductor radi [m]
    'earth_q': []  # Earth conductor inner tube radii [m]
}

# Impedance matrix
Zprimitive, n_p, n_e = calc_Z_matrix(line_dict)
Zreduced, phases_vector = wire_bundling([1,2,3], Zprimitive, [1,1,2,2,3,3])

print()
print()
print(Zreduced)

# Admittance matrix
Yprimitive, n_p, n_e = calc_Y_matrix(line_dict)
Yreduced, phases_vector = wire_bundling_shunt([1,2,3], Yprimitive, [1,1,2,2,3,3])

print()
print()
print(Yreduced * 1e6)
# """