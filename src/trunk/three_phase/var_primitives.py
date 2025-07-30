import numpy as np

def var_compensation_admittance(connection: str,
                                G: float,
                                B: float,
                                Unom: float
                                ):

    Yphase = ((G - 1j * B) * 1e6) / (Unom * 1e3)**2

    if connection == 'D':
        Yphase = 3 * Yphase

    Y = np.array([Yphase, Yphase, Yphase])

    return Y