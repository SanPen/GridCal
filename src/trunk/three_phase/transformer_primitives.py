import sympy as sp
import numpy as np

yff = sp.symbols('yff')
yft = sp.symbols('yft')
ytf = sp.symbols('ytf')
ytt = sp.symbols('ytt')

conn = 'Yy'

if conn == 'Yy':
    Yff = np.array([
        [yff, 0, 0],
        [0, yff, 0],
        [0, 0, yff]
    ])
    Yft = np.array([
        [yft, 0, 0],
        [0, yft, 0],
        [0, 0, yft]
    ])
    Ytf = np.array([
        [ytf, 0, 0],
        [0, ytf, 0],
        [0, 0, ytf]
    ])
    Ytt = np.array([
        [ytt, 0, 0],
        [0, ytt, 0],
        [0, 0, ytt]
    ])

elif conn == 'Yd':
    Yff = np.array([
        [yff, 0, 0],
        [0, yff, 0],
        [0, 0, yff]
    ])
    Yft = np.array([
        [yft/np.sqrt(3), -yft/np.sqrt(3), 0],
        [0, yft/np.sqrt(3), -yft/np.sqrt(3)],
        [-yft/np.sqrt(3), 0, yft/np.sqrt(3)]
    ])
    Ytf = np.array([
        [ytf/np.sqrt(3), 0, -ytf/np.sqrt(3)],
        [-ytf/np.sqrt(3), ytf/np.sqrt(3), 0],
        [0, -ytf/np.sqrt(3), ytf/np.sqrt(3)]
    ])
    Ytt = np.array([
        [2*ytt/3, -ytt/3, -ytt/3],
        [-ytt/3, 2*ytt/3, -ytt/3],
        [-ytt/3, -ytt/3, 2*ytt/3]
    ])

if conn == 'Yz':
    Yff = np.array([
        [yff/2, 0, 0],
        [0, yff/2, 0],
        [0, 0, yff/2]
    ])
    Yft = np.array([
        [yft/4, 0, -yft/4],
        [-yft/4, yft/4, 0],
        [0, -yft/4, yft/4]
    ])
    Ytf = np.array([
        [ytf/4, -ytf/4, 0],
        [0, ytf/4, -ytf/4],
        [-ytf/4, 0, ytf/4]
    ])
    Ytt = np.array([
        [ytt/2, 0, 0],
        [0, ytt/2, 0],
        [0, 0, ytt/2]
    ])

elif conn == 'Dy':
    Yff = np.array([
        [2*yff/3, -yff/3, -yff/3],
        [-yff/3, 2*yff/3, -yff/3],
        [-yff/3, -yff/3, 2*yff/3]
    ])
    Yft = np.array([
        [yft/np.sqrt(3), 0, -yft/np.sqrt(3)],
        [-yft/np.sqrt(3), yft/np.sqrt(3), 0],
        [0, -yft/np.sqrt(3), yft/np.sqrt(3)]
    ])
    Ytf = np.array([
        [ytf/np.sqrt(3), -ytf/np.sqrt(3), 0],
        [0, ytf/np.sqrt(3), -ytf/np.sqrt(3)],
        [-ytf/np.sqrt(3), 0, ytf/np.sqrt(3)]
    ])
    Ytt = np.array([
        [ytt, 0, 0],
        [0, ytt, 0],
        [0, 0, ytt]
    ])

elif conn == 'Dd':
    Yff = np.array([
        [2*yff/3, -yff/3, -yff/3],
        [-yff/3, 2*yff/3, -yff/3],
        [-yff/3, -yff/3, 2*yff/3]
    ])
    Yft = np.array([
        [2*yft/3, -yft/3, -yft/3],
        [-yft/3, 2*yft/3, -yft/3],
        [-yft/3, -yft/3, 2*yft/3]
    ])
    Ytf = np.array([
        [2*ytf/3, -ytf/3, -ytf/3],
        [-ytf/3, 2*ytf/3, -ytf/3],
        [-ytf/3, -ytf/3, 2*ytf/3]
    ])
    Ytt = np.array([
        [2*ytt/3, -ytt/3, -ytt/3],
        [-ytt/3, 2*ytt/3, -ytt/3],
        [-ytt/3, -ytt/3, 2*ytt/3]
    ])

elif conn == 'Dz':
    Yff = np.array([
        [yff, -yff/2, -yff/2],
        [-yff/2, yff, -yff/2],
        [-yff/2, -yff/2, yff]
    ])
    Yft = np.array([
        [yft/4, yft/4, -yft/2],
        [-yft/2, yft/4, yft/4],
        [yft/4, -yft/2, yft/4]
    ])
    Ytf = np.array([
        [ytf/4, -ytf/2, ytf/4],
        [ytf/4, ytf/4, -ytf/2],
        [-ytf/2, ytf/4, ytf/4]
    ])
    Ytt = np.array([
        [ytt/2, 0, 0],
        [0, ytt/2, 0],
        [0, 0, ytt/2]
    ])

elif conn == 'Zy':
    Yff = np.array([
        [yff/2, 0, 0],
        [0, yff/2, 0],
        [0, 0, yff/2]
    ])
    Yft = np.array([
        [yft/4, -yft/4, 0],
        [0, yft/4, -yft/4],
        [-yft/4, 0, yft/4]
    ])
    Ytf = np.array([
        [ytf/4, 0, -ytf/4],
        [-ytf/4, ytf/4, 0],
        [0, -ytf/4, ytf/4]
    ])
    Ytt = np.array([
        [ytt/2, 0, 0],
        [0, ytt/2, 0],
        [0, 0, ytt/2]
    ])

elif conn == 'Zd':
    Yff = np.array([
        [yff/2, 0, 0],
        [0, yff/2, 0],
        [0, 0, yff/2]
    ])
    Yft = np.array([
        [yft/4, -yft/2, yft/4],
        [yft/4, yft/4, -yft/2],
        [-yft/2, yft/4, yft/4]
    ])
    Ytf = np.array([
        [ytf/4, ytf/4, -ytf/2],
        [-ytf/2, ytf/4, ytf/4],
        [ytf/4, -ytf/2, ytf/4]
    ])
    Ytt = np.array([
        [ytt, -ytt/2, -ytt/2],
        [-ytt/2, ytt, -ytt/2],
        [-ytt/2, -ytt/2, ytt]
    ])

elif conn == 'Zz':
    Yff = np.array([
        [yff/2, 0, 0],
        [0, yff/2, 0],
        [0, 0, yff/2]
    ])
    Yft = np.array([
        [yft/2, 0, 0],
        [0, yft/2, 0],
        [0, 0, yft/2]
    ])
    Ytf = np.array([
        [ytf/2, 0, 0],
        [0, ytf/2, 0],
        [0, 0, ytf/2]
    ])
    Ytt = np.array([
        [ytt/2, 0, 0],
        [0, ytt/2, 0],
        [0, 0, ytt/2]
    ])