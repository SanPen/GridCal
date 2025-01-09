import numpy as np


def calc1(r, x, g, b, tau, m, mf, mt, Vf, Vt):
    ys = 1 / (r + 1j * x)
    bc2 = (g + 1j * b) / 2.0

    yff = (ys + bc2) / (m ** 2 * mf ** 2 * np.exp(2j * tau))
    yft = -ys / (m * mf * mt)
    ytf = -ys / (m * mf * mt * np.exp(2j * tau))
    ytt = (ys + bc2) / (mt * mt)

    If = Vf * yff + Vt * yft
    It = Vf * ytf + Vt * ytt

    Sf = Vf * np.conj(If)
    St = Vt * np.conj(It)

    return Sf, St


def calc_cost(r, x, g, b, tau_set, m_set, mf, mt, Vf, Vt):
    ys = 1 / (r + 1j * x)
    bc2 = (g + 1j * b) / 2.0
    # mp = m * np.exp(1j * tau)

    yff = (ys + bc2) / (m_set ** 2 * mf ** 2 * np.exp(2j * tau_set))
    yft = -ys / (m_set * mf * mt)
    ytf = -ys / (m_set * mf * mt * np.exp(2j * tau_set))
    ytt = (ys + bc2) / (mt * mt)

    If = Vf * yff + Vt * yft
    It = Vf * ytf + Vt * ytt

    Sf = Vf * np.conj(If)
    St = Vt * np.conj(It)

    return Sf, St


def calc_var(r, x, g, b, tau, tau_set, m, m_set, mf, mt, Vf, Vt):

    ys = 1 / (r + 1j * x)
    bc2 = (g + 1j * b) / 2.0

    yff_c = (ys + bc2) / (m_set ** 2 * mf ** 2 * np.exp(2j * tau_set))
    yft_c = -ys / (m_set * mf * mt)
    ytf_c = -ys / (m_set * mf * mt * np.exp(2j * tau_set))
    ytt_c = (ys + bc2) / (mt * mt)

    yff_v = (ys + bc2) / (m ** 2 * mf ** 2 * np.exp(2j * tau))
    yft_v = -ys / (m * mf * mt)
    ytf_v = -ys / (m * mf * mt * np.exp(2j * tau))
    ytt_v = (ys + bc2) / (mt * mt)

    If = Vf * (yff_v - yff_c) + Vt * (yft_v - yft_c)
    It = Vf * (ytf_v - ytf_c) + Vt * (ytt_v - ytt_c)

    Sf = Vf * np.conj(If)
    St = Vt * np.conj(It)

    return Sf, St


Sf1, St1 = calc1(r=0.01, x=0.05, g=0.0, b=0.002, tau=0.1, m=0.98, mf=1.0, mt=1.0,
                 Vf=complex(1, 0), Vt=complex(0.98, 0.1))

print(f"Base Sf:{Sf1}, St:{St1}")

Sfc2, Stc2 = calc_cost(r=0.01, x=0.05, g=0.0, b=0.002, tau_set=0.1, m_set=1.0, mf=1.0, mt=1.0,
                       Vf=complex(1, 0), Vt=complex(0.98, 0.1))

Sfv2, Stv2 = calc_var(r=0.01, x=0.05, g=0.0, b=0.002, tau=0.1, tau_set=0.1, m=0.98, m_set=1.0, mf=1.0, mt=1.0,
                      Vf=complex(1, 0), Vt=complex(0.98, 0.1))

Sf2 = Sfc2 + Sfv2
St2 = Stc2 + Stv2

print(f"Split Sf:{Sf2}, St:{St2}")

print(f"diff Sf:{Sf1 - Sf2}, St:{St1 - St2}")
