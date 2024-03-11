
import numpy as np


def get_psse_transformer_impedances(CW, CZ, CM, V1, V2, sbase, logger, code,
                                    MAG1, MAG2, WINDV1, WINDV2, ANG1, NOMV1, NOMV2,
                                    R1_2, X1_2, SBASE1_2):
    """

    :param CW:
    :param CZ:
    :param CM:
    :param V1:
    :param V2:
    :param sbase:
    :param logger:
    :param code:
    :param MAG1:
    :param MAG2:
    :param WINDV1:
    :param WINDV2:
    :param ANG1:
    :param NOMV1:
    :param NOMV2:
    :param R1_2:
    :param X1_2:
    :param SBASE1_2:
    :return:
    """

    """
    CW	Winding I/O code
    1	Turns ratio (pu on bus base kV)
    2	Winding voltage kV
    3	Turns ratio (pu on nominal winding kV)

    CZ	Impedance I/O code
    1	Z pu (winding kV system MVA)
    2	Z pu (winding kV winding MVA)
    3	Load loss (W) & |Z| (pu)

    CM	Admittance I/O code
    1	Y pu (system base)
    2	No load loss (W) & Exciting I (pu)
    """

    g = MAG1
    b = MAG2
    tap_mod = WINDV1 / WINDV2
    tap_angle = np.deg2rad(ANG1)

    # if self.CW == 2 or self.CW == 3:
    #     tap_mod *= bus_to.Vnom / bus_from.Vnom
    #
    # if self.CW == 3:
    #     tap_mod *= self.NOMV1 / self.NOMV2

    """
    CW	Winding I/O code
    1	Turns ratio (pu on bus base kV)
    2	Winding voltage kV
    3	Turns ratio (pu on nominal winding kV)        
    """

    if CW == 1:
        tap_mod = WINDV1 / WINDV2

    elif CW == 2:
        tap_mod = (WINDV1 / V1) / (WINDV2 / V2)

    elif CW == 3:
        tap_mod = (WINDV1 / WINDV2) * (NOMV1 / NOMV2)

    """
    CZ	Impedance I/O code
    1	Z pu (winding kV system MVA)
    2	Z pu (winding kV winding MVA)
    3	Load loss (W) & |Z| (pu)
    """
    r = 1e-20
    x = 1e-20
    if CZ == 1:
        # the transformer values are in system base
        r = R1_2
        x = X1_2

    elif CZ == 2:
        # pu on Winding 1 to 2 MVA base (SBASE1-2) and winding voltage base
        logger.add_warning('Transformer not in system base', code)

        if SBASE1_2 > 0:
            zb = sbase / SBASE1_2
            r = R1_2 * zb
            x = X1_2 * zb

        else:
            logger.add_error('Transformer SBASE1_2 is zero', code)

    elif CZ == 3:
        # R1-2 is the load loss in watts, and X1-2 is the impedance magnitude
        # in pu on Winding 1 to 2 MVA base (SBASE1-2) and winding voltage base
        r = R1_2 * 1e-6 / SBASE1_2 / sbase
        x = np.sqrt(X1_2 * X1_2 - r * r)
        logger.add_warning('Transformer not in system base', code)

    else:
        raise Exception('Unknown impedance combination CZ=' + str(CZ))

    return r, x, g, b, tap_mod, tap_angle