import numpy as np

def transformer_admittance(vector_group: str,
                           clock_notation: int,
                           yff: complex,
                           yft: complex,
                           ytf: complex,
                           ytt: complex
                           ):

    phase_displacement = (np.exp(1j + np.deg2rad(clock_notation * 30)))

    if vector_group == 'Yy':
        Yff = np.array([
            [yff, 0, 0],
            [0, yff, 0],
            [0, 0, yff]
        ])
        Yft = np.array([
            [yft/np.conj(phase_displacement), 0, 0],
            [0, yft/np.conj(phase_displacement), 0],
            [0, 0, yft/np.conj(phase_displacement)]
        ])
        Ytf = np.array([
            [ytf/phase_displacement, 0, 0],
            [0, ytf/phase_displacement, 0],
            [0, 0, ytf/phase_displacement]
        ])
        Ytt = np.array([
            [ytt, 0, 0],
            [0, ytt, 0],
            [0, 0, ytt]
        ])

    elif vector_group == 'Yd':
        Yff = np.array([
            [yff, 0, 0],
            [0, yff, 0],
            [0, 0, yff]
        ])
        Yft = np.array([
            [yft/np.conj(phase_displacement)/np.sqrt(3), -yft/np.conj(phase_displacement)/np.sqrt(3), 0],
            [0, yft/np.conj(phase_displacement)/np.sqrt(3), -yft/np.conj(phase_displacement)/np.sqrt(3)],
            [-yft/np.conj(phase_displacement)/np.sqrt(3), 0, yft/np.conj(phase_displacement)/np.sqrt(3)]
        ])
        Ytf = np.array([
            [ytf/phase_displacement/np.sqrt(3), 0, -ytf/phase_displacement/np.sqrt(3)],
            [-ytf/phase_displacement/np.sqrt(3), ytf/phase_displacement/np.sqrt(3), 0],
            [0, -ytf/phase_displacement/np.sqrt(3), ytf/phase_displacement/np.sqrt(3)]
        ])
        Ytt = np.array([
            [2*ytt/3, -ytt/3, -ytt/3],
            [-ytt/3, 2*ytt/3, -ytt/3],
            [-ytt/3, -ytt/3, 2*ytt/3]
        ])

    if vector_group == 'Yz':
        Yff = np.array([
            [yff/2, 0, 0],
            [0, yff/2, 0],
            [0, 0, yff/2]
        ])
        Yft = np.array([
            [yft/np.conj(phase_displacement)/4, 0, -yft/np.conj(phase_displacement)/4],
            [-yft/np.conj(phase_displacement)/4, yft/np.conj(phase_displacement)/4, 0],
            [0, -yft/np.conj(phase_displacement)/4, yft/np.conj(phase_displacement)/4]
        ])
        Ytf = np.array([
            [ytf/phase_displacement/4, -ytf/phase_displacement/4, 0],
            [0, ytf/phase_displacement/4, -ytf/phase_displacement/4],
            [-ytf/phase_displacement/4, 0, ytf/phase_displacement/4]
        ])
        Ytt = np.array([
            [ytt/2, 0, 0],
            [0, ytt/2, 0],
            [0, 0, ytt/2]
        ])

    elif vector_group == 'Dy':
        Yff = np.array([
            [2*yff/3, -yff/3, -yff/3],
            [-yff/3, 2*yff/3, -yff/3],
            [-yff/3, -yff/3, 2*yff/3]
        ])
        Yft = np.array([
            [yft/np.conj(phase_displacement)/np.sqrt(3), 0, -yft/np.conj(phase_displacement)/np.sqrt(3)],
            [-yft/np.conj(phase_displacement)/np.sqrt(3), yft/np.conj(phase_displacement)/np.sqrt(3), 0],
            [0, -yft/np.conj(phase_displacement)/np.sqrt(3), yft/np.conj(phase_displacement)/np.sqrt(3)]
        ])
        Ytf = np.array([
            [ytf/phase_displacement/np.sqrt(3), -ytf/phase_displacement/np.sqrt(3), 0],
            [0, ytf/phase_displacement/np.sqrt(3), -ytf/phase_displacement/np.sqrt(3)],
            [-ytf/phase_displacement/np.sqrt(3), 0, ytf/phase_displacement/np.sqrt(3)]
        ])
        Ytt = np.array([
            [ytt, 0, 0],
            [0, ytt, 0],
            [0, 0, ytt]
        ])

    elif vector_group == 'Dd':
        Yff = np.array([
            [2*yff/3, -yff/3, -yff/3],
            [-yff/3, 2*yff/3, -yff/3],
            [-yff/3, -yff/3, 2*yff/3]
        ])
        Yft = np.array([
            [2*yft/np.conj(phase_displacement)/3, -yft/np.conj(phase_displacement)/3, -yft/np.conj(phase_displacement)/3],
            [-yft/np.conj(phase_displacement)/3, 2*yft/np.conj(phase_displacement)/3, -yft/np.conj(phase_displacement)/3],
            [-yft/np.conj(phase_displacement)/3, -yft/np.conj(phase_displacement)/3, 2*yft/np.conj(phase_displacement)/3]
        ])
        Ytf = np.array([
            [2*ytf/phase_displacement/3, -ytf/phase_displacement/3, -ytf/phase_displacement/3],
            [-ytf/phase_displacement/3, 2*ytf/phase_displacement/3, -ytf/phase_displacement/3],
            [-ytf/phase_displacement/3, -ytf/phase_displacement/3, 2*ytf/phase_displacement/3]
        ])
        Ytt = np.array([
            [2*ytt/3, -ytt/3, -ytt/3],
            [-ytt/3, 2*ytt/3, -ytt/3],
            [-ytt/3, -ytt/3, 2*ytt/3]
        ])

    elif vector_group == 'Dz':
        Yff = np.array([
            [yff, -yff/2, -yff/2],
            [-yff/2, yff, -yff/2],
            [-yff/2, -yff/2, yff]
        ])
        Yft = np.array([
            [yft/np.conj(phase_displacement)/4, yft/np.conj(phase_displacement)/4, -yft/np.conj(phase_displacement)/2],
            [-yft/np.conj(phase_displacement)/2, yft/np.conj(phase_displacement)/4, yft/np.conj(phase_displacement)/4],
            [yft/np.conj(phase_displacement)/4, -yft/np.conj(phase_displacement)/2, yft/np.conj(phase_displacement)/4]
        ])
        Ytf = np.array([
            [ytf/phase_displacement/4, -ytf/phase_displacement/2, ytf/phase_displacement/4],
            [ytf/phase_displacement/4, ytf/phase_displacement/4, -ytf/phase_displacement/2],
            [-ytf/phase_displacement/2, ytf/phase_displacement/4, ytf/phase_displacement/4]
        ])
        Ytt = np.array([
            [ytt/2, 0, 0],
            [0, ytt/2, 0],
            [0, 0, ytt/2]
        ])

    elif vector_group == 'Zy':
        Yff = np.array([
            [yff/2, 0, 0],
            [0, yff/2, 0],
            [0, 0, yff/2]
        ])
        Yft = np.array([
            [yft/np.conj(phase_displacement)/4, -yft/np.conj(phase_displacement)/4, 0],
            [0, yft/np.conj(phase_displacement)/4, -yft/np.conj(phase_displacement)/4],
            [-yft/np.conj(phase_displacement)/4, 0, yft/np.conj(phase_displacement)/4]
        ])
        Ytf = np.array([
            [ytf/phase_displacement/4, 0, -ytf/phase_displacement/4],
            [-ytf/phase_displacement/4, ytf/phase_displacement/4, 0],
            [0, -ytf/phase_displacement/4, ytf/phase_displacement/4]
        ])
        Ytt = np.array([
            [ytt/2, 0, 0],
            [0, ytt/2, 0],
            [0, 0, ytt/2]
        ])

    elif vector_group == 'Zd':
        Yff = np.array([
            [yff/2, 0, 0],
            [0, yff/2, 0],
            [0, 0, yff/2]
        ])
        Yft = np.array([
            [yft/np.conj(phase_displacement)/4, -yft/np.conj(phase_displacement)/2, yft/np.conj(phase_displacement)/4],
            [yft/np.conj(phase_displacement)/4, yft/np.conj(phase_displacement)/4, -yft/np.conj(phase_displacement)/2],
            [-yft/np.conj(phase_displacement)/2, yft/np.conj(phase_displacement)/4, yft/np.conj(phase_displacement)/4]
        ])
        Ytf = np.array([
            [ytf/phase_displacement/4, ytf/phase_displacement/4, -ytf/phase_displacement/2],
            [-ytf/phase_displacement/2, ytf/phase_displacement/4, ytf/phase_displacement/4],
            [ytf/phase_displacement/4, -ytf/phase_displacement/2, ytf/phase_displacement/4]
        ])
        Ytt = np.array([
            [ytt, -ytt/2, -ytt/2],
            [-ytt/2, ytt, -ytt/2],
            [-ytt/2, -ytt/2, ytt]
        ])

    elif vector_group == 'Zz':
        Yff = np.array([
            [yff/2, 0, 0],
            [0, yff/2, 0],
            [0, 0, yff/2]
        ])
        Yft = np.array([
            [yft/np.conj(phase_displacement)/2, 0, 0],
            [0, yft/np.conj(phase_displacement)/2, 0],
            [0, 0, yft/np.conj(phase_displacement)/2]
        ])
        Ytf = np.array([
            [ytf/phase_displacement/2, 0, 0],
            [0, ytf/phase_displacement/2, 0],
            [0, 0, ytf/phase_displacement/2]
        ])
        Ytt = np.array([
            [ytt/2, 0, 0],
            [0, ytt/2, 0],
            [0, 0, ytt/2]
        ])

    return Yff, Yft, Ytf, Ytt