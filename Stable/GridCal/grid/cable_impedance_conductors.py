'''
Santiago Penate Vera 2015
'''

import math
import numpy as np
import matplotlib.pyplot as plt


def abc2seq(Z):
    '''
    Converts the ABC impedances to 012 Impedances    
    '''
    ang = 2.0*math.pi/3.0 #120 deg in radians
    a = math.cos(ang) + math.sin(ang)*1j
    mat = np.matrix([[1,1,1],[1,a, a**2],[1, a**2, a]])
    mat_inv = 1.0/3.0 * np.matrix([[1,1,1],[1,a**2, a],[1, a, a**2]])
    
    return mat_inv * Z * mat

class CarsonEquations():
    '''
    Carsosn's equations to compute a line impedance   
    
    See kersting pag 83, 84
    '''
    def __init__(self, frequency, earth_resistivity):
        self.G = 0.1609347e-3 #Ohm/mile
        self.freq = frequency # Hz
        self.ro = earth_resistivity #ohm m
        
        self.C1 = math.pi**2 * self.freq * self.G #Ohm/mile
        self.C2 = 4 * math.pi * self.freq * self.G #Ohm/mile
        self.C3 = 7.6786 + 0.5 * math.log(self.ro / self.freq) #?


    def zii(self, r_i, GMR_i):
        '''
        Auto impedance        
        '''
        return r_i + self.C1 + (self.C2*(math.log(1.0/GMR_i)+self.C3))*1j
        
    def zij(self, Dij):
        '''
        Mutual impedance        
        '''
        return self.C1 + (self.C2*(math.log(1.0/Dij)+self.C3))*1j   
        

class conductor:
    '''
    Simple metalic conductor  
    
    When a conductor is displayes in duplex, triplex or cuadruplex
    configurations, the GMR changes and of course the resistance
    '''
    def __init__(self, name, geometric_mean_radius, resistance, diameter, 
                 capacity):
        self.Name = name
        self.GMR = float(geometric_mean_radius)
        self.r = float(resistance)
        self.d = float(diameter)
        self.Capacity = float(capacity)
        
        
class cable_concentric_neutral:
    '''
    Cable containing distributed embeeded neutral    
    '''
    def __init__(self, phase_conductor, neutral_conductor, number_of_neutrals,
                 cable_diameter):
        self.phase = phase_conductor
        self.neutro = neutral_conductor
        self.k = float(number_of_neutrals) 
        self.d_od = float(cable_diameter)
        
        #calculated parameters
        self.R = (self.d_od - self.neutro.d) / 24.0 #ft (el 24 es 2*12)
        
        #the neutral cable is recalculated as an equivalent neutral 
        #given the number of neutrals (k)
        
        #See Kersting pag 102
        self.neutro.GMR = (self.neutro.GMR * self.k * self.R **(self.k-1))**(1.0/self.k) #ft
        self.neutro.r = self.neutro.r / self.k #ohm/mile
        
        
class cable_tape_shield:
    '''
    Cable with no neutral and with a metal innner shield    
    '''
    def __init__(self, phase_conductor, tape_diameter, tape_thickness, earth_resistivity):
        self.phase = phase_conductor
        self.d_s = float(tape_diameter) #inches
        self.T = float(tape_thickness) #milimeters
        self.ro = earth_resistivity #Ohm-m
        
        #calculated parameters        
        self.GMR_shield = ((self.d_s/2.0) - (self.T/2000.0))/12.0 #ft
        self.r_shield = 7.9385e-8*self.ro / (self.T*self.d_s) #ohm/mile
        
        #generate the neutral equivalent to the tape
        self.neutro = conductor('tape', self.GMR_shield, self.r_shield, 0, 0)

class UndergroundLine:
    '''
    line composed of 3 phases and one neutral    
    '''
    def __init__(self):
        self.conductors = list()
        self.neutrals = list()
        self.conductors_positions = list()    
        self.neutrals_positions = list()   
        
    def addCable_concentric_neutral(self, cable, x, y):
        '''
        Add the phase and equiv. neutral conductors to the line set up       
        '''
        self.conductors.append(cable.phase)
        self.conductors_positions.append(x + y*1j) # the position is stored as a complex number
        
        self.neutrals.append(cable.neutro)
        self.neutrals_positions.append(x + (y+cable.R)*1j)    
        
    def addCable_tape_shield(self, cable, x, y):
        '''
        Add the phase and equiv. neutral conductors to the line set up       
        '''
        self.conductors.append(cable.phase)
        self.conductors_positions.append(x + y*1j) # the position is stored as a complex number
        
        self.neutrals.append(cable.neutro)
        self.neutrals_positions.append(x + y*1j) 
        
        
class Trench:
    '''
    Trench that can contain many parallel circuits
    '''    
    def __init__(self, frequency, earth_resistivity):
        self.freq = frequency
        self.ro = earth_resistivity
        
        self.lines = list()
        
        #phases of the cables        
        self.phases = list()
        self.phases_pos = list()
        #neutrals of the cables
        self.neutrals = list()  
        self.neutrals_pos = list()
        
        #single extra neutral
        self.neutral = None
        self.neutral_pos = None
        
        #all the conductors and their positions ordered
        self.conductors = list()
        self.positions = list()
        
    def addLine(self, cable):
        '''
        Add an underground line to the trench (A line is suposed to be 3-phase)        
        '''
        self.lines.append(cable)
        
        
    def addNeutral(self, cond, x, y):
        '''
        The trench can host a single separated neutral      
        '''
        self.neutral = cond
        self.neutral_pos = x + y*1j #the position is stored as a complex number
        
        
    def Compile(self):
        '''
        compose the conductors in a structured manner;
        first the phase circuitr conductors and at last the neutral
        '''        
        self.conductors = list()
        self.positions = list()
        
        if self.neutral is not None:
            self.neutrals.append(self.neutral)
            self.neutrals_pos.append(self.neutral_pos)
            
        for line in self.lines:
            self.phases += line.conductors
            self.phases_pos += line.conductors_positions
            self.neutrals += line.neutrals
            self.neutrals_pos += line.neutrals_positions         
        
        self.conductors += self.phases
        self.positions += self.phases_pos
        self.conductors += self.neutrals
        self.positions += self.neutrals_pos
            
    def draw(self):
        self.Compile()
        for p in self.positions:
            plt.plot(p.real, p.imag, 'o')           
                
        
    def Kron(self, z):
        '''
        The neutrals are grouped after the phases     
        '''
        n = len(self.conductors)
        m = len(self.neutrals)
        
        zij = z[0:n-m, 0:n-m]
        zin = z[n-m:n, 0:n-m]        
        znj = z[0:n-m, n-m:n]
        znn = np.matrix(z[n-m:n, n-m:n])
        return zij - zin*np.linalg.inv(znn) * znj
        
        
    def D(self, i, j):
        '''
        Distace between conductors        
        '''
        d = abs(self.positions[i] - self.positions[j])
        if d == 0: #evalueation of a tapeshield vs conductor in the same cable
            if self.conductors[i].Name == 'tape':
                d =self.conductors[i].GMR
            else:
                d =self.conductors[j].GMR
        return d
    
        
    def Z(self):
        '''
        Returns the ABC impedance matrix of the lines set up        
        '''
        self.Compile()
        
        eq = CarsonEquations(self.freq, self.ro)
        n = len(self.conductors)
        m = len(self.neutrals)
        z = np.zeros((n,n),'complex')
        for i in range(n):
            for j in range(n):
                if i==j:
                    z[i,j] = eq.zii(self.conductors[i].r,self.conductors[i].GMR)
                else:
                    z[i,j] = eq.zij(self.D(i,j))
        
        return z
        
        if m > 0:
            return self.kron(z)
        else:
            return z
    
    

class OverheadLine:
    '''
    line composed of 3 phases and one neutral    
    '''
    def __init__(self):
        self.conductors = list()
        self.positions = list()
        
    def addConductor(self, cond, x, y):
        '''
        Add a conductor to the line set up  (Overhead line)      
        '''
        self.conductors.append(cond)
        self.positions.append(x + y*1j) # the position is stored as a complex number
        
  
class Tower:
    '''
    Tower that can contain many parallel circuits
    '''    
    def __init__(self, frequency, earth_resistivity):
        self.freq = frequency
        self.ro = earth_resistivity
        self.lines = list()
        self.conductors = list()
        self.positions = list()
        self.neutral = None
        self.neutral_pos = None
        
    def addLine(self, line):
        '''
        Add a line to the tower (A line is suposed to be 3-phase)        
        '''
        self.lines.append(line)
        
    def addNeutral(self, cond, x, y):
        '''
        The towers usualli have a single neutral common to all the lines hosted
        hence, only one neutral is needed per tower        
        '''
        self.neutral = cond
        self.neutral_pos = x + y*1j #the position is stored as a complex number
        
        
    def draw(self):
        self.Compile()
        for p in self.positions:
            plt.plot(p.real, p.imag, 'o')           
        
        
        
    def Kron(self, z):
        '''
        The neutral is assumed to be the last one added        
        '''
        n = len(self.conductors)
        zij = z[0:n-1, 0:n-1]
        zin = z[n-1:n, 0:n-1]
        znn = z[n-1, n-1]
        znj = z[0:n-1, n-1]
        return zij - zin*(1/znn) * znj

    def D(self, i, j):
        '''
        Distace between conductors        
        '''
        return abs(self.positions[i] - self.positions[j])

    def Compile(self):
        '''
        compose the conductors in a structured manner;
        first the phase circuitr conductors and at last the neutral
        '''        
        self.conductors = list()
        self.positions = list()
        for line in self.lines:
            self.conductors += line.conductors
            self.positions += line.positions
            
        if self.neutral is not None:
            self.conductors.append(self.neutral)
            self.positions.append(self.neutral_pos)

    def Z(self):
        '''
        Returns the ABC impedance matrix of the lines set up        
        '''
        self.Compile()
        
        eq = CarsonEquations(self.freq, self.ro)
        n = len(self.conductors)
        z = np.zeros((n,n),'complex')
        for i in range(n):
            for j in range(n):
                if i==j:
                    z[i,j] = eq.zii(self.conductors[i].r,self.conductors[i].GMR)
                else:
                    z[i,j] = eq.zij(self.D(i,j))
        
        if self.neutral is not None:
            return self.Kron(z)
        else:
            return z


if __name__ == '__main__':
    ###############################################################################
    # General values
    ###############################################################################
    freq = 60 #Hz
    earth_resistivity = 100 #ohm-m

    ###############################################################################
    # Example 1, one line (3 phases + neutral)
    ###############################################################################
    print ("Example 1: 1 circuit in a tower")

    conductor1 = conductor('336,400 26/7 ACSR', 0.0244, 0.306, 0.721, 530)
    neutro = conductor('4/0 6/1 ACSR', 0.00814, 0.5920, 0.563, 340)

    line = OverheadLine()
    line.addConductor(conductor1, 0.0, 29.0)
    line.addConductor(conductor1, 2.5, 29.)
    line.addConductor(conductor1, 7.0, 29.0)

    tower1 = Tower(freq, earth_resistivity)
    tower1.addLine(line)
    tower1.addNeutral(neutro, 4.0, 25.0)
    Z1 = tower1.Z()
    print(Z1)


    ###############################################################################
    # Example 2, one tower with two lines (3 + 3 phases + 1 neutral)
    ###############################################################################
    print ("\n\nExample 2: 2 circuits per tower with a common neutral")

    conductor1 = conductor('336,400 26/7 ACSR', 0.0244, 0.306, 0.721, 530)
    conductor2 = conductor('250,000 AA', 0.0171, 0.41, 0.567, 329)
    neutro = conductor('4/0 6/1 ACSR', 0.00814, 0.5920, 0.563, 340)

    line1 = OverheadLine()
    line1.addConductor(conductor1, 0.0, 35.0)
    line1.addConductor(conductor1, 2.5, 35.)
    line1.addConductor(conductor1, 7.0, 35.0)

    line2 = OverheadLine()
    line2.addConductor(conductor2, 2.5, 33.0)
    line2.addConductor(conductor2, 7.0, 33.)
    line2.addConductor(conductor2, 0.0, 33.0)


    tower1 = Tower(freq, earth_resistivity)
    tower1.addLine(line1)
    tower1.addLine(line2)
    tower1.addNeutral(neutro, 4.0, 29.0)

    Z2 = tower1.Z()
    print(Z2)



    ###############################################################################
    # Example 3, three cables in a trench
    ###############################################################################

    print ("\n\nExample 3: three cables in a trench")

    phase = conductor('250,000 AA', 0.0171, 0.41, 0.567, 329)
    neutro = conductor('14 AWG SLD copper', 0.00208, 14.8722, 0.0641, 20)

    cable1 = cable_concentric_neutral(phase, neutro, 13, 1.29)
    cable2 = cable1
    cable3 = cable1

    trench_line = UndergroundLine()
    trench_line.addCable_concentric_neutral(cable1, 0, 0)
    trench_line.addCable_concentric_neutral(cable1, 0.5, 0)
    trench_line.addCable_concentric_neutral(cable1, 1, 0)

    trench = Trench(freq, earth_resistivity)
    trench.addLine(trench_line)

    Z3 = trench.Z()
    print(Z3)


    ###############################################################################
    # Example 4, one cable in a trench with neutral
    ###############################################################################

    print ("\n\nExample 4: one cable in a trench with neutral")

    phase = conductor('1/0 AA', 0.0111, 0.97, 0.368, 202)
    neutro = conductor('1/0 copper 7 strand', 0.01113, 0.607, 0.368, 310)

    #phase_conductor, tape_diameter, tape_thickness, earth_resistivit
    cable1 = cable_tape_shield(phase, 0.88, 5, earth_resistivity)

    trench_line = UndergroundLine()
    trench_line.addCable_tape_shield(cable1, 0, 0)

    trench = Trench(freq, earth_resistivity)
    trench.addLine(trench_line)
    trench.addNeutral(neutro, 0.25, 0)

    Z4 = trench.Z()
    print(abc2seq(Z4))