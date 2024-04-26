# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
from typing import Tuple
import matplotlib.pyplot as plt
import numpy as np
import sys
sys.path.append('C:/Users/raiya/Documents/8. eRoots/thesis/code/GridCal/src')
import GridCalEngine.api as gce
import scipy.sparse as sp
import numba as nb
from GridCalEngine.basic_structures import Vec, CscMat, CxVec, IntVec
import GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions as cf
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.ac_jacobian import AC_jacobian
from GridCalEngine.Utils.NumericalMethods.common import ConvexFunctionResult, ConvexMethodResult
from GridCalEngine.Utils.NumericalMethods.newton_raphson import newton_raphson
from GridCalEngine.Utils.NumericalMethods.powell import powell_dog_leg
from GridCalEngine.Utils.NumericalMethods.levenberg_marquadt import levenberg_marquardt
from GridCalEngine.enumerations import SolverType
from sympy import symbols, diff, exp, re, im
import time
import numpy as np
from typing import Callable, Any
from GridCalEngine.basic_structures import Vec
from GridCalEngine.Utils.NumericalMethods.common import (ConvexMethodResult, ConvexFunctionResult,
                                                         check_function_and_args)
from GridCalEngine.Utils.NumericalMethods.sparse_solve import get_linear_solver
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Devices.Branches import VSC, Transformer2W
from scipy.sparse import csc_matrix
from typing import Tuple, Union
from GridCalEngine.basic_structures import Vec, CxVec, IntVec
from scipy.sparse import csr_matrix, csc_matrix
import prettytable as pt

a = 0.01
b = 0.02
c = 0.04

class MultiCircuitRaiyan(gce.MultiCircuit):
    def __init__(self):
        super().__init__()
        self.Vm_map = {}
        self.Va_map = {}
        self.Pfrom_map = {}
        self.Pto_map = {}
        self.Qfrom_map = {}
        self.Qto_map = {}
        self.VSCinstances = {}
        self.GENinstances = {}
        self.ContTrafoinstances = {}
        self.edgeList = []

    def add_vsc(self, vsc):
        #get the from and to buses
        from_bus = vsc.bus_from
        to_bus = vsc.bus_to

        #get the index of the buses
        from_bus_index = self.buses.index(from_bus)
        to_bus_index = self.buses.index(to_bus)
        
        VSC_Series._instances_count += 1
        VSC_Series._instances.append(vsc)  
        VSC_Series._vsc_connection_index_dcside.append(from_bus_index)
        VSC_Series._vsc_connection_index_acside.append(to_bus_index)
        self.VSCinstances[vsc] = (from_bus, to_bus)

    def add_generator(self, bus, gen):
        if bus.is_dc:
            #make sure that control2 of the generator is None
            assert gen.control2 is None, "DC generator cannot have 2 controls"
        super().add_generator(bus, gen)
        self.GENinstances[gen] = bus

    def add_contTrafo(self, busFrom, busTo, trafo):
        self.ContTrafoinstances[trafo] = (busFrom, busTo)
        #add to edgeList
        self.edgeList.append((self.buses.index(busFrom), self.buses.index(busTo)))

    def add_line(self, line):
        #call the super method
        super().add_line(line)
        #get the from and to bus
        from_bus = self.buses.index(line.bus_from)
        to_bus = self.buses.index(line.bus_to)
        #add to edgeList
        self.edgeList.append((from_bus, to_bus))

    def add_dc_line(self, dc_line):
        #call the super method
        super().add_dc_line(dc_line)
        #get the from and to bus
        from_bus = self.buses.index(dc_line.bus_from)
        to_bus = self.buses.index(dc_line.bus_to)
        #add to edgeList
        self.edgeList.append((from_bus, to_bus))

    def get_vsc_connection_matrices(self):
        noOfBuses = len(self.buses)
        noOfVSCs = len(self.VSCinstances)
        m_dc = np.zeros((noOfBuses, noOfVSCs), dtype=int)
        m_ac = np.zeros((noOfBuses, noOfVSCs), dtype=int)

        for i, vsc in enumerate(self.VSCinstances):
            busFromIndex = self.buses.index(vsc.bus_from)
            busToIndex = self.buses.index(vsc.bus_to)
            m_dc[busFromIndex, i] = 1
            m_ac[busToIndex, i] = 1

        return m_dc, m_ac

    def get_trafo_connection_matrices(self):
        noOfBuses = len(self.buses)
        noOfControlledTrafos = len(self.ContTrafoinstances)
        m_from = np.zeros((noOfBuses, noOfControlledTrafos), dtype=int)
        m_to = np.zeros((noOfBuses, noOfControlledTrafos), dtype=int)

        for i, trafo in enumerate(self.ContTrafoinstances):
            busFromIndex = self.buses.index(trafo.bus_from)
            busToIndex = self.buses.index(trafo.bus_to)
            m_from[busFromIndex, i] = 1
            m_to[busToIndex, i] = 1

        return m_from, m_to


    def get_vsc_frombus(self):
        return [self.buses.index(vsc.bus_from) for vsc in self.VSCinstances]
    
    def get_vsc_tobus(self):
        return [self.buses.index(vsc.bus_to) for vsc in self.VSCinstances]

    def get_controllable_trafo_frombus(self):
        return [self.buses.index(trafo.bus_from) for trafo in self.ContTrafoinstances]
    
    def get_controllable_trafo_tobus(self):
        return [self.buses.index(trafo.bus_to) for trafo in self.ContTrafoinstances]
    
    def get_controllable_trafo_yshunt(self):
        return [trafo.yshunt for trafo in self.ContTrafoinstances]
    
    def get_controllable_trafo_yseries(self):
        return [trafo.yseries for trafo in self.ContTrafoinstances]

    def update_var_maps(self):
        """
        Method keeps track of which variables need to be updated and which are important for solving the power flow
        """
        pass

class ControlRaiyan:
    _instancesList = []
    _controlDict = {}
    _bus_voltage_known = {}
    _bus_angle_known = {}
    def __init__(self, grid, busFrom, controlType, setPoint, busTo = None):
        self.runLogicCheck(grid, busFrom, controlType, setPoint, busTo)
        self.busFrom = grid.buses.index(busFrom)
        self.busTo = None if busTo is None else grid.buses.index(busTo)
        self.controlType = controlType
        self.setPoint = setPoint
        self.isBranchControl = True if busTo is not None else False
        self.activeElement = None
        ControlRaiyan.collisionDetection(self)

    @classmethod
    def collisionDetection(cls, controlInstance):
        #print everything
        # print("controlInstance.busFrom", controlInstance.busFrom)
        # print("controlInstance.busTo", controlInstance.busTo)
        # print("controlInstance.controlType", controlInstance.controlType)
        # print("controlInstance.setPoint", controlInstance.setPoint)
        #add the control instance to the controlDict
        if controlInstance.busTo is None:
            _key = (controlInstance.busFrom, controlInstance.controlType)
            _value = controlInstance.setPoint

            #if the key already exists, throw an error and destroy the instance
            if _key in cls._controlDict:
                errorMsg = f"{controlInstance.controlType} control already exists for bus indexed {controlInstance.busFrom}"
                del controlInstance
                raise Exception(errorMsg)
            
            else:
                cls._controlDict[_key] = _value
                cls._instancesList.append(controlInstance)

        else:
            _key = (controlInstance.busFrom, controlInstance.busTo, controlInstance.controlType)
            _value = controlInstance.setPoint

            #if the key already exists, throw an error and destroy the instance
            if _key in cls._controlDict:
                errorMsg = f"{controlInstance.controlType} control already exists for branch indexed {controlInstance.busFrom} to {controlInstance.busTo}"
                del controlInstance
                raise Exception(errorMsg)
            
            else:
                cls._controlDict[_key] = _value
                cls._instancesList.append(controlInstance)
    
    @classmethod
    def deleteAllControls(cls):
        cls._instancesList = []
        cls._controlDict = {}
        cls._bus_voltage_known = {}
        cls._bus_angle_known = {}


    @classmethod
    def update_instances(cls, activeElement, *args):
        #unpack args
        for arg in args:
            if arg.activeElement is not None:
                #raise exception that says this control is already attached to an active element in the grid
                raise Exception(f"This control is already attached to an active element in the grid {arg.activeElement.name}")
            
            else:
                arg.activeElement = activeElement

    @classmethod
    def ruleAssertion(cls, grid, verbose=0, strict=0):
        """
        Asserts the rule that each subsystem of a given grid must have exactly one slack bus.

        This method analyzes the electrical grid's structure to identify its subsystems (separated by DC links or not directly connected) and checks for the presence of exactly one slack bus per subsystem. Slack buses are determined based on known voltage magnitude and angle for AC buses or known voltage for DC buses.

        Parameters
        ----------
        grid : Grid object
            The grid to be analyzed, containing all bus and edge information.
        verbose : int, optional
            If set to 1, prints a summary table of each subsystem with its slack buses and a remark on whether the rule is met. Default is 0, which does not print the table.
        strict : int, optional
            If set to 1, the function will assert an error if any subsystem does not have exactly one slack bus. Default is 0, which does not enforce this check strictly.

        Returns
        -------
        None

        Raises
        ------
        AssertionError
            If `strict` is set to 1 and any subsystem does not have exactly one slack bus, an assertion error is raised.

        """

        #return all the grid edges
        edges = grid.edgeList
        systems = HelperFunctions.depth_first_search(edges)
        subSystemSlacks = np.zeros(len(systems), dtype=bool)

        #initialise pretty table
        table = pt.PrettyTable()
        #add some headers
        table.field_names = ["System", "Slack Buses", "Remarks"]

        for i, system in enumerate(systems):
            isSlack = []
            isDC = False
            for busIndex in system:
                #get bus object from index using grid object
                bus = grid.buses[busIndex]
                if bus.is_dc:
                    if busIndex in cls._bus_voltage_known:
                        isSlack.append(busIndex)
                else:
                    if busIndex in cls._bus_voltage_known and busIndex in cls._bus_angle_known:
                        isSlack.append(busIndex)


            #add the system to the table
            table.add_row([f"Subsystem {i+1}", isSlack, "All good" if len(isSlack)  == 1 else "No good"])
            #true is there is exactly one slack, false otherwise
            subSystemSlacks[i] = len(isSlack) == 1

        if verbose:
            print(table)

        if strict:
            #if adding up lengthwise does not equal the length of the buses, then assert an error
            assert sum(subSystemSlacks) == len(systems), "You do not have exactly one slack bus for each subsystem"


    @classmethod
    def findingIndices(cls, grid, output_mode = 0, verbose = 0):
        """
        Identifies and categorizes the known and unknown parameters of a grid's components into dictionaries.

        This method processes the electrical grid's components, such as buses, generators, VSCs (Voltage Source Converters), and controllable transformers, to classify their parameters (e.g., voltage, angle, power injections) as known or unknown. It also identifies the parameters under control by generating units or VSCs and updates their status accordingly.

        Parameters
        ----------
        grid : Grid object
            The grid containing the components to be analyzed.
        output_mode : int, optional
            Controls the return of the method. If set to 1, the method returns dictionaries of known and unknown parameters and additional passive branch controls that may need equations. Default is 0, which does not return anything.
        verbose : int, optional
            If set to 1, prints detailed tables of the number of unknown parameters and potentially missing equations for passive branches. Default is 0, which suppresses detailed output.

        Returns
        -------
        tuple of (dict, dict, dict), optional
            Returns three dictionaries (known_dict, unknown_dict, passive_branch_dict) mapping parameter types to their known and unknown statuses, along with any passive branch controls requiring additional equations. Only returns if `output_mode` is set to 1.

        """
        bus_voltage_known = {}
        bus_angle_known = {}
        bus_pzip_known = {}
        bus_qzip_known = {}
        branch_tapRatio_known = {}
        branch_phaseShift_known = {}
        branch_pto_known = {}
        branch_qto_known = {}
        branch_pfrom_known = {}
        branch_qfrom_known = {}

        known_dict =  {
            "Voltage": bus_voltage_known,
            "Angle": bus_angle_known, 
            "Pzip": bus_pzip_known, 
            "Qzip": bus_qzip_known,
            "Pfrom": branch_pfrom_known, 
            "Pto": branch_pto_known,
            "Qfrom": branch_qfrom_known, 
            "Qto": branch_qto_known,
            "Modulation": branch_tapRatio_known,
            "Tau": branch_phaseShift_known
        }

        bus_voltage_un = {}
        bus_angle_un = {}
        bus_pzip_un = {}
        bus_qzip_un = {}
        branch_tapRatio_un = {}
        branch_phaseShift_un = {}
        branch_pto_un = {}
        branch_qto_un = {}
        branch_pfrom_un = {}
        branch_qfrom_un = {}

        unknown_dict =  {
            "Voltage": bus_voltage_un,
            "Angle": bus_angle_un,
            "Pzip": bus_pzip_un,
            "Qzip": bus_qzip_un,
            "Pfrom": branch_pfrom_un,
            "Pto": branch_pto_un,
            "Qfrom": branch_qfrom_un,
            "Qto": branch_qto_un,
            "Modulation": branch_tapRatio_un,
            "Tau": branch_phaseShift_un
        }

        for bus in grid.buses:
            i = grid.buses.index(bus)
            if bus.is_dc:
                bus_voltage_un[i] = ""
                bus_pzip_known[i] = 0
                
            else:
                bus_angle_un[i] = ""
                bus_voltage_un[i] = ""
                bus_pzip_known[i] = 0
                bus_qzip_known[i] = 0

        for gen in grid.GENinstances:
            #add bus.index to Pzip_unknown
            if gen.bus.is_dc:
                unknown_dict["Pzip"][grid.buses.index(gen.bus)] = ""
                known_dict["Pzip"].pop(grid.buses.index(gen.bus))
            else:
                unknown_dict["Pzip"][grid.buses.index(gen.bus)] = ""
                unknown_dict["Qzip"][grid.buses.index(gen.bus)] = ""
                known_dict["Pzip"].pop(grid.buses.index(gen.bus))
                known_dict["Qzip"].pop(grid.buses.index(gen.bus))


        for vsc in grid.VSCinstances:
            # print("vsc", vsc)
            # add branch(busFrom,busTo).index to from_activePower_unknown
            unknown_dict["Pfrom"][(grid.buses.index(vsc.bus_from), grid.buses.index(vsc.bus_to))] = ""
            unknown_dict["Pto"][(grid.buses.index(vsc.bus_from), grid.buses.index(vsc.bus_to))] = ""
            unknown_dict["Qto"][(grid.buses.index(vsc.bus_from), grid.buses.index(vsc.bus_to))] = ""

        for trafo in grid.ContTrafoinstances:
            # print("trafo", trafo)
            # add branch(busFrom,busTo).index to from_activePower_unknown
            unknown_dict["Pfrom"][(grid.buses.index(trafo.bus_from), grid.buses.index(trafo.bus_to))] = ""
            unknown_dict["Qfrom"][(grid.buses.index(trafo.bus_from), grid.buses.index(trafo.bus_to))] = ""
            unknown_dict["Pto"][(grid.buses.index(trafo.bus_from), grid.buses.index(trafo.bus_to))] = ""
            unknown_dict["Qto"][(grid.buses.index(trafo.bus_from), grid.buses.index(trafo.bus_to))] = ""
            unknown_dict["Tau"][(grid.buses.index(trafo.bus_from), grid.buses.index(trafo.bus_to))] = ""
            unknown_dict["Modulation"][(grid.buses.index(trafo.bus_from), grid.buses.index(trafo.bus_to))] = ""


        passive_branch_dict =  {
            "Pfrom": {},
            "Pto": {},
            "Qfrom": {},
            "Qto": {},
        }


        for i, controlInstance in enumerate(cls._instancesList):
            # print everything
            # print("control number", i+1)
            # print("controlInstance.busFrom", controlInstance.busFrom)
            # print("controlInstance.busTo", controlInstance.busTo)
            # print("controlInstance.controlType", controlInstance.controlType)
            # print("controlInstance.setPoint", controlInstance.setPoint)
            # print("controlInstance.isBranchControl", controlInstance.isBranchControl)

            if not controlInstance.isBranchControl: #this is to say, you are dealing with a bus magnitude
                busIndex = controlInstance.busFrom
                controlType = controlInstance.controlType
                setPoint = controlInstance.setPoint

                #print the types of the above variables
                # print("busIndex", type(busIndex))
                # print("controlType", type(controlType))
                # print("setPoint", type(setPoint))
                
                #remove from the unknown_dict
                unknown_dict[controlType].pop(busIndex)
                known_dict[controlType][busIndex] = setPoint

            
            else:
                busFromIndex = controlInstance.busFrom
                busToIndex = controlInstance.busTo
                controlType = controlInstance.controlType
                setPoint = controlInstance.setPoint

                #print the types of the above variables
                # print("busFromIndex", type(busFromIndex))
                # print("busToIndex", type(busToIndex))
                # print("controlType", type(controlType))
                # print("setPoint", type(setPoint))

                #remove from the unknown_dict
                try:
                    unknown_dict[controlType].pop((busFromIndex, busToIndex))
                except:
                    #in this case, we know that the element is trying to control a line power, so we tell the user that you will need to add more equations later
                    passive_branch_dict[controlType][(busFromIndex, busToIndex)] = setPoint
                    #print
                    # print("passive branch control added")
                    # print("controlType", controlType)
                    # print("busFromIndex", busFromIndex)
                    # print("busToIndex", busToIndex)

                known_dict[controlType][(busFromIndex, busToIndex)] = setPoint



        cls._bus_voltage_known = known_dict["Voltage"]
        cls._bus_angle_known = known_dict["Angle"]
        #print everything that is non empty
        # print("bus_voltage_known", bus_voltage_known)
        # print("bus_angle_known", bus_angle_known)
        # print("bus_pzip_known", bus_pzip_known)
        # print("bus_qzip_known", bus_qzip_known)
        # print("branch_tapRatio_known", branch_tapRatio_known)
        # print("branch_phaseShift_known", branch_phaseShift_known)
        # print("branch_pto_known", branch_pto_known)
        # print("branch_qto_known", branch_qto_known)
        # print("branch_pfrom_known", branch_pfrom_known)
        # print("branch_qfrom_known", branch_qfrom_known)
        
        # print("bus_voltage_un", bus_voltage_un)
        # print("bus_angle_un", bus_angle_un)
        # print("bus_pzip_un", bus_pzip_un)
        # print("bus_qzip_un", bus_qzip_un)
        # print("branch_tapRatio_un", branch_tapRatio_un)
        # print("branch_phaseShift_un", branch_phaseShift_un)
        # print("branch_pto_un", branch_pto_un)
        # print("branch_qto_un", branch_qto_un)
        # print("branch_pfrom_un", branch_pfrom_un)
        # print("branch_qfrom_un", branch_qfrom_un)


        #use pretty table to print the above information
        if verbose == 1:
            table = pt.PrettyTable()
            table.field_names = ["Type", "Number of Unknowns"]
            table.add_row(["Voltage", len(bus_voltage_un)])
            table.add_row(["Angle", len(bus_angle_un)])
            table.add_row(["Pzip", len(bus_pzip_un)])
            table.add_row(["Qzip", len(bus_qzip_un)])
            table.add_row(["Pfrom", len(branch_pfrom_un)])
            table.add_row(["Pto", len(branch_pto_un)])
            table.add_row(["Qfrom", len(branch_qfrom_un)])
            table.add_row(["Qto", len(branch_qto_un)])
            table.add_row(["Modulation", len(branch_tapRatio_un)])
            table.add_row(["Tau", len(branch_phaseShift_un)])
            table.add_row(["Total", len(bus_voltage_un) 
                        + len(bus_angle_un) + len(bus_pzip_un) + len(bus_qzip_un) 
                        + len(branch_tapRatio_un) + len(branch_phaseShift_un) + len(branch_pto_un) 
                        + len(branch_qto_un) + len(branch_pfrom_un) + len(branch_qfrom_un)])
            print(table)

        if len(passive_branch_dict["Pfrom"]) + len(passive_branch_dict["Pto"]) + len(passive_branch_dict["Qfrom"]) + len(passive_branch_dict["Qto"]) > 0:
            print("You may have some branch equations that need to be added to your mismatches")
            
            #make a pretty table
            table = pt.PrettyTable()
            table.field_names = ["Type", "Number of Unknowns"]
            table.add_row(["Pfrom", len(passive_branch_dict["Pfrom"])])
            table.add_row(["Pto", len(passive_branch_dict["Pto"])])
            table.add_row(["Qfrom", len(passive_branch_dict["Qfrom"])])
            table.add_row(["Qto", len(passive_branch_dict["Qto"])])
            table.add_row(["Total New Equations Needed", len(passive_branch_dict["Pfrom"]) + len(passive_branch_dict["Pto"]) + len(passive_branch_dict["Qfrom"]) + len(passive_branch_dict["Qto"])])
            print(table)


        #print out all the dictionaries
        if output_mode:
           return known_dict, unknown_dict, passive_branch_dict


    def runLogicCheck(self, grid, busFrom, controlType, setPoint, busTo):
        if busTo is None:
            checkList = ["Voltage", "Angle", "Pzip", "Qzip"]
            if controlType not in checkList:
                raise Exception("Control type not recognized for bus")
            if controlType == "Angle" and busFrom.is_dc:
                raise Exception("DC bus cannot have an angle control")
            
        else:
            #make sure that the index of the bus is not the same
            assert grid.buses.index(busFrom) != grid.buses.index(busTo), "Bus from and bus to cannot be the same"
            checkList = ["Pfrom", "Pto", "Qfrom", "Qto", "Tau", "Modulation"]
            if controlType not in checkList:
                raise Exception("Control type not recognized for branch")
            
        #ensure that setPoint is a float
        assert isinstance(setPoint, float), "Set point must be a float"

    @staticmethod
    def get_numberOfEquations(grid, verbose = 0):
        """
        Calculates and optionally displays the total number of equations for a given electrical grid configuration.

        This method tallies the equations based on the count of AC buses, DC buses, Voltage Source Converters (VSCs), and controllable transformers within the grid. Each type of component contributes a specific number of equations to the system.

        Parameters
        ----------
        grid : Grid object
            The electrical grid for which the number of equations is being calculated. This grid should contain attributes for buses, VSC instances, and controllable transformer instances.
        verbose : int, optional
            A flag to control the verbosity of the output. If set to 1, a detailed breakdown of the number of equations per component type is printed using PrettyTable. The default is 0, which means no detailed output is printed.

        Returns
        -------
        None
            This method does not return a value. Instead, it prints a summary table of the equations when `verbose` is set to 1.
        """
        #get the number of ac buses
        ac_buses = [bus for bus in grid.buses if not bus.is_dc]
        num_ac_buses = len(ac_buses)

        #get the number of dc buses
        dc_buses = [bus for bus in grid.buses if bus.is_dc]
        num_dc_buses = len(dc_buses)

        #get the number of vscs
        num_vsc = len(grid.VSCinstances)

        #get the number of transformers
        num_trafo = len(grid.ContTrafoinstances)

        total = num_ac_buses*2 + num_dc_buses + num_vsc + num_trafo*4

        # print(f"{num_ac_buses} AC Buses gives you {num_ac_buses*2} equations")
        # print(f"{num_dc_buses} DC Buses gives you {num_dc_buses} equations")
        # print(f"{num_vsc} VSCs gives you {num_vsc} equations")
        # print(f"{num_trafo} Controllable Trafo gives you {num_trafo*4} equations")
        # print(f"Total number of equations is {total}"	)

        #use pretty table to represent the above information

        if verbose == 1:
            table = pt.PrettyTable()
            table.field_names = ["Type", "Number of Instances", "Number of Equations"]
            table.add_row(["AC Bus", num_ac_buses, num_ac_buses*2])
            table.add_row(["DC Bus", num_dc_buses, num_dc_buses])
            table.add_row(["VSC", num_vsc, num_vsc])
            table.add_row(["Controllable Trafo", num_trafo, num_trafo*4])
            table.add_row(["Total", "", total])
            print(table)


class BusRaiyan(gce.Bus):
    def __init__(self, name: str, vnom: float):
        super().__init__(name, vnom)


class HelperFunctions:
    @staticmethod
    def update_Vm0(Vm0, m_vsc_connection_dc, m_vsc_connection_ac):
        print("VSC_Series.get_vsc_vmt_value", VSC_Series.get_vsc_vmt_value())
        print("VSC_Series.get_vsc_vmf_value", VSC_Series.get_vsc_vmf_value())
        print("(m_vsc_connection_dc * VSC_Series.get_vsc_vmt_value()", (m_vsc_connection_dc * VSC_Series.get_vsc_vmt_value()).sum(axis=1))
        print("(m_vsc_connection_ac * VSC_Series.get_vsc_vmf_value()", (m_vsc_connection_ac * VSC_Series.get_vsc_vmf_value()).sum(axis=1))
        print("(m_vsc_connection_dc * VSC_Series.get_vsc_vmf_isControlled()", (m_vsc_connection_dc * VSC_Series.get_vsc_vmf_isControlled()).sum(axis=1))
        print("(m_vsc_connection_ac * VSC_Series.get_vsc_vmt_isControlled()", (m_vsc_connection_ac * VSC_Series.get_vsc_vmt_isControlled()).sum(axis=1))

        #create the masks for the controlled and uncontrolled Vms
        __a = (m_vsc_connection_dc * VSC_Series.get_vsc_vmf_isControlled()).sum(axis=1)
        __a = np.where(__a == 1, 0, 1)
        __b = (m_vsc_connection_ac * VSC_Series.get_vsc_vmt_isControlled()).sum(axis=1)
        __b = np.where(__b == 1, 0, 1)

        # elementwise Vm0 and __a
        __c = Vm0 * __a
        # print("__c", __c)
        # elementwise Vm0 and __b
        __d = Vm0 * __b
        # print("__d", __d)

        Vm0 = Vm0 * __c + (m_vsc_connection_dc * VSC_Series.get_vsc_vmf_value()).sum(axis=1)
        Vm0 = Vm0 * __d + (m_vsc_connection_ac * VSC_Series.get_vsc_vmt_value()).sum(axis=1)
        
        
        return Vm0

    @staticmethod
    def test_myCalc_vs_Original(ac_buses, dc_buses, Ybus, S0, I0, Y0, Va, Vm):
        import random
        Vm = np.array([random.uniform(0.9, 1.1) for i in range(len(ac_buses) + len(dc_buses))], dtype=np.complex128)
        V = Vm * np.exp(1j * Va)

        print("Vm: ", Vm)
        print("S0: ", S0)
        print("I0: ", I0)
        print("Y0: ", Y0)
        Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)
        print("Sbus: ", Sbus)
        Scalc1 = cf.compute_power(Ybus, V)
        Scalc2 = HelperFunctions.compute_power(Ybus, V, ac_buses, dc_buses)

        print("Scalc1: ", Scalc1)
        print("Scalc2: ", Scalc2)
        print("Scalc1 - Scalc2: ", Scalc1 - Scalc2)

    @staticmethod
    def compute_power(Ybus: csc_matrix, V: CxVec, ac_buses, dc_buses) -> CxVec:
        """
        Compute the power from the admittance matrix and the voltage
        :param Ybus: Admittance matrix
        :param V: Voltage vector
        :return: Calculated power injections
        """
        ac_calculation =  V * np.conj(Ybus * V)

        ac_mask = np.zeros(len(ac_buses) + len(dc_buses), dtype=bool)
        ac_mask[ac_buses] = True
        ac_calculation = ac_calculation * ac_mask

        dc_calculation = V * np.conj(Ybus * V)
        # print("Ybusdense", Ybusdense)
        # print("Ybus 4-6", Ybusdense[3,5]) 
        # print("Ybus 6-4", Ybusdense[5,3])
        # print("66 diag", Ybusdense[5,5])
        # print("44 diag", Ybusdense[3,3])
        # print("dc_calculation", dc_calculation)
        dc_mask = np.zeros(len(ac_buses) + len(dc_buses), dtype=bool)
        dc_mask[dc_buses] = True
        dc_calculation = dc_calculation * dc_mask

        return ac_calculation + dc_calculation

    @staticmethod
    def create_vsc_connection_lists(grid: gce.MultiCircuit):
        """
        Create index lists representing the connections of VSCs to DC and AC buses.

        This method generates two index lists: one for the DC side connections and
        another for the AC side connections of VSCs in the grid.

        Parameters:
        - grid (gce.MultiCircuit): The multi-circuit grid object containing VSC devices.

        Returns:
        - vsc_connection_dc (list): Index list representing the DC side connections
        of VSCs. Each element corresponds to the index of the DC bus connected to the VSC.
        - vsc_connection_ac (list): Index list representing the AC side connections
        of VSCs. Each element corresponds to the index of the AC bus connected to the VSC.
        """
        vsc_connection_dc = []
        vsc_connection_ac = []

        # Fill the lists with the connections of the VSCs
        for vsc in grid.vsc_devices:
            vsc_connection_dc.append(grid.buses.index(vsc.bus_from))
            vsc_connection_ac.append(grid.buses.index(vsc.bus_to))
        
        return vsc_connection_dc, vsc_connection_ac


    @staticmethod
    def create_vsc_connection_dicts(vsc_connection_index_dcside, vsc_connection_index_acside):
        """
        Create dictionaries representing the connections of VSCs.

        This method generates two dictionaries: one for the DC side connections and
        another for the AC side connections of VSCs. Each dictionary maps a bus index
        to a list of indices representing the connected buses on the opposite side.

        Parameters:
        - vsc_connection_index_dcside (list): List of indices representing the DC side connections of VSCs.
        - vsc_connection_index_acside (list): List of indices representing the AC side connections of VSCs.

        Returns:
        - vsc_connection_dc (dict): Dictionary mapping DC side bus indices to lists of AC side bus indices.
        - vsc_connection_ac (dict): Dictionary mapping AC side bus indices to lists of DC side bus indices.
        """
        vsc_connection_dc = {}
        vsc_connection_ac = {}

        # Create dictionaries for DC and AC connections
        for i in range(len(vsc_connection_index_dcside)):
            # Add DC side connections to the dictionary
            if vsc_connection_index_dcside[i] in vsc_connection_dc:
                vsc_connection_dc[vsc_connection_index_dcside[i]].append(vsc_connection_index_acside[i])
            else:
                vsc_connection_dc[vsc_connection_index_dcside[i]] = [vsc_connection_index_acside[i]]

            # Add AC side connections to the dictionary
            if vsc_connection_index_acside[i] in vsc_connection_ac:
                vsc_connection_ac[vsc_connection_index_acside[i]].append(vsc_connection_index_dcside[i])
            else:
                vsc_connection_ac[vsc_connection_index_acside[i]] = [vsc_connection_index_dcside[i]]

        return vsc_connection_dc, vsc_connection_ac



    @staticmethod
    def create_tct_connection_lists(grid: gce.MultiCircuit):
        """
        Create index lists representing the connections of transformers to buses.

        This method generates index lists for transformers in the grid,
        including 2-winding and 3-winding transformers.

        Parameters:
        - grid (gce.MultiCircuit): The multi-circuit grid object containing transformers.

        Returns:
        - tct2w_conn_from (list): Index list representing the 'from' bus connections
        of 2-winding transformers.
        - tct2w_conn_to (list): Index list representing the 'to' bus connections
        of 2-winding transformers.
        - tct3w_conn_bus1 (list): Index list representing the 'bus1' connections
        of 3-winding transformers.
        - tct3w_conn_bus2 (list): Index list representing the 'bus2' connections
        of 3-winding transformers.
        - tct3w_conn_bus3 (list): Index list representing the 'bus3' connections
        of 3-winding transformers.
        """
        tct2w_conn_from = []
        tct2w_conn_to = []
        tct3w_conn_bus1 = []
        tct3w_conn_bus2 = []
        tct3w_conn_bus3 = []

        # Fill the lists with the connections of the transformers
        for tct in grid.transformers2w:
            tct2w_conn_from.append(grid.buses.index(tct.bus_from))
            tct2w_conn_to.append(grid.buses.index(tct.bus_to))

        for tct in grid.transformers3w:
            tct3w_conn_bus1.append(grid.buses.index(tct.bus1))
            tct3w_conn_bus2.append(grid.buses.index(tct.bus2))
            tct3w_conn_bus3.append(grid.buses.index(tct.bus3))

        return tct2w_conn_from, tct2w_conn_to, tct3w_conn_bus1, tct3w_conn_bus2, tct3w_conn_bus3


    @staticmethod
    def bus_types(grid: gce.MultiCircuit):
        """
        Create lists of bus indices based on their types.

        This method generates separate lists for DC buses, AC buses, and slack buses
        based on the bus types in the provided grid.

        Parameters:
        - grid (gce.MultiCircuit): The multi-circuit grid object containing buses.

        Returns:
        - dc_buses (list): Indices of DC buses in the grid.
        - ac_buses (list): Indices of AC buses in the grid.
        - slack_buses (list): Indices of slack buses in the grid.
        """
        dc_buses = []
        ac_buses = []
        slack_buses = []

        # Iterate through each bus in the grid
        for bus in grid.buses:
            if bus.is_slack:
                slack_buses.append(grid.buses.index(bus))
            if bus.is_dc:
                dc_buses.append(grid.buses.index(bus))
            else:
                ac_buses.append(grid.buses.index(bus))

        return dc_buses, ac_buses, slack_buses


    @staticmethod
    def create_vsc_connection_matrices(dc_buses, ac_buses, vsc_dc_indices, vsc_ac_indices):
        total_buses = len(dc_buses) + len(ac_buses)
        num_vsc = len(vsc_dc_indices)
        
        # Initialize the 'from AC to VSC' and 'to DC from VSC' matrices with zeros
        from_ac_matrix = np.zeros((total_buses, num_vsc), dtype=int)
        to_dc_matrix = np.zeros((total_buses, num_vsc), dtype=int)
        
        # Map the VSC connections onto the matrices
        for vsc_idx in range(num_vsc):

            dc_bus_idx = vsc_dc_indices[vsc_idx] 
            ac_bus_idx = vsc_ac_indices[vsc_idx] 
            
            # Set the corresponding matrix entries to 1 to indicate a connection
            to_dc_matrix[dc_bus_idx, vsc_idx] = 1  # Offset by the number of AC buses
            from_ac_matrix[ac_bus_idx, vsc_idx] = 1
            
        return to_dc_matrix, from_ac_matrix


    
    @staticmethod
    def breadth_first_search(edges):

        """
        Perform a breadth-first search on a graph and return the connected components.
        """
        from collections import deque
        graph = {}
        for edge in edges:
            u, v = edge
            if u not in graph:
                graph[u] = []
            if v not in graph:
                graph[v] = []
            graph[u].append(v)
            graph[v].append(u)
        
        visited = set()
        connected_components = []

        for vertex in graph:
            if vertex not in visited:
                component = []
                queue = deque([vertex])
                visited.add(vertex)
                while queue:
                    current_vertex = queue.popleft()
                    component.append(current_vertex)
                    for neighbor in graph[current_vertex]:
                        if neighbor not in visited:
                            queue.append(neighbor)
                            visited.add(neighbor)
                connected_components.append(component)

        return connected_components

    @staticmethod
    def depth_first_search(edges):
        """
        Perform a depth-first search on a graph and return the connected components.
        """
        graph = {}
        for edge in edges:
            u, v = edge
            if u not in graph:
                graph[u] = []
            if v not in graph:
                graph[v] = []
            graph[u].append(v)
            graph[v].append(u)
        
        visited = set()
        connected_components = []

        def dfs(vertex, component):
            visited.add(vertex)
            component.append(vertex)
            for neighbor in graph[vertex]:
                if neighbor not in visited:
                    dfs(neighbor, component)

        for vertex in graph:
            if vertex not in visited:
                component = []
                dfs(vertex, component)
                connected_components.append(component)

        return connected_components


    @staticmethod
    def assert_symmetrical(matrix):
        """
        Asserts that a given sparse matrix is symmetric.
        """
        if not sp.isspmatrix(matrix):
            raise ValueError("Input matrix must be a sparse matrix.")

        dense_matrix = matrix.toarray()  # Convert to dense matrix
        if not np.allclose(dense_matrix, dense_matrix.T):
            raise AssertionError("Input matrix is not symmetric.")

        return matrix  # Return the original sparse matrix


    @staticmethod
    def check_VSC_control(grid: gce.MultiCircuit, dc_buses: list, ac_buses:list, vsc_connection_index_dcside: list, vsc_connection_index_acside: list, debug =1):
        """
        Check the VSC control in the grid.
        """

        print("check_VSC_control: Checking VSC Control")
        #using the objects grid.dc_lines, make a list of edges of the dc graph
        dc_edges = []
        # i need a boolean numpy array of length dc_buses
        dc_visited = np.zeros(len(grid.buses), dtype=bool)
        for dc_line in grid.dc_lines:
            dc_edges.append((grid.buses.index(dc_line.bus_from), grid.buses.index(dc_line.bus_to)))
            dc_visited[grid.buses.index(dc_line.bus_from)] = True
            dc_visited[grid.buses.index(dc_line.bus_to)] = True
        
        #for which ever bus is not visited, make an edge that points to itself and then add it to the dc_edges
        for i in range(len(dc_visited)):
            if dc_visited[i] == False and i in dc_buses:
                dc_edges.append((i,i))

        
        mtdc_systems = HelperFunctions.depth_first_search(dc_edges)
        print("mtdc_systems", mtdc_systems)       

        # #iterate through each mtdc_system
        # for mtdc_system in mtdc_systems:
        #     non_slack_list = []
        #     for vsc in mtdc_system:
        #         #get the index of 

        Vdc_isControlled = np.zeros(len(dc_buses) + len(ac_buses), dtype=bool)
        Vac_isControlled = np.zeros(len(dc_buses) + len(ac_buses), dtype=bool)
        Pdc_isControlled =  np.zeros(len(dc_buses) + len(ac_buses), dtype=bool)
        Pac_isControlled =  np.zeros(len(dc_buses) + len(ac_buses), dtype=bool)
        Qac_isControlled = np.zeros(len(dc_buses) + len(ac_buses), dtype=bool)


        for i, vsc in enumerate(VSC_Series._instances):
            _a, _b, _d, _e, _f = vsc.all_isControlled()
            Vdc_isControlled[vsc_connection_index_dcside[i]] = _a
            Vac_isControlled[vsc_connection_index_acside[i]] = _b
            Pdc_isControlled[vsc_connection_index_dcside[i]] = _d
            Pac_isControlled[vsc_connection_index_acside[i]] = _e
            Qac_isControlled[vsc_connection_index_acside[i]] = _f

        if debug:
            print("Vdc_isControlled", Vdc_isControlled)
            print("Vac_isControlled", Vac_isControlled)
            print("Pdc_isControlled", Pdc_isControlled)
            print("Pac_isControlled", Pac_isControlled)
            print("Qac_isControlled", Qac_isControlled)


        Vdc_valueControlled = np.zeros(len(dc_buses) + len(ac_buses), dtype=float)
        Vac_valueControlled = np.zeros(len(dc_buses) + len(ac_buses), dtype=float)
        Pdc_valueControlled =  np.zeros(len(dc_buses) + len(ac_buses), dtype=float)
        Pac_valueControlled =  np.zeros(len(dc_buses) + len(ac_buses), dtype=float)
        Qac_valueControlled = np.zeros(len(dc_buses) + len(ac_buses), dtype=float)



        for i, vsc in enumerate(VSC_Series._instances):
            _a, _b, _d, _e, _f = vsc.all_values()
            Vdc_valueControlled[vsc_connection_index_dcside[i]] = _a
            Vac_valueControlled[vsc_connection_index_acside[i]] = _b
            Pdc_valueControlled[vsc_connection_index_dcside[i]] = _d
            Pac_valueControlled[vsc_connection_index_acside[i]] = _e
            Qac_valueControlled[vsc_connection_index_acside[i]] = _f


        if debug:
            print("Vdc_valueControlled", Vdc_valueControlled)
            print("Vac_valueControlled", Vac_valueControlled)
            print("Pdc_valueControlled", Pdc_valueControlled)
            print("Pac_valueControlled", Pac_valueControlled)
            print("Qac_valueControlled", Qac_valueControlled)
        
        return Vdc_isControlled, Vac_isControlled, Pdc_isControlled, Pac_isControlled, Qac_isControlled



    @staticmethod
    def acdc_5bus():
        grid = MultiCircuitRaiyan()
        grid.change_base(1000)


        bus1 = gce.Bus('Bus 1', vnom=20)
        grid.add_bus(bus1)
        gen1_control1 = ControlRaiyan(grid, bus1, "Voltage", 1.01)
        gen1_control2 = ControlRaiyan(grid, bus1, "Angle", 0.0)
        gen1 = GeneratorRaiyan('Some random generator 1', gen1_control1, gen1_control2, vset=1.0, Pmin=0, Pmax=1000,
                            Qmin=-1000, Qmax=1000, Cost=15, Cost2=0.0)
        

        grid.add_generator(bus1, gen1)
        bus2 = gce.Bus('Bus 2', vnom=20)
        grid.add_bus(bus2)
        grid.add_load(bus2, gce.Load('load 2', P=300, Q=100))

        line12 = gce.Line(bus1, bus2, 'line 1-2', r=0.1, x=0.3, b=0.0)
        grid.add_line(line12)

        bus3 = gce.Bus('Bus 3', vnom=20)
        bus3.is_dc = True
        grid.add_bus(bus3)

        bus4 = gce.Bus('Bus 4', vnom=20)
        bus4.is_dc = True
        grid.add_bus(bus4)
        grid.add_load(bus4, gce.Load('load 2', P=300, Q=0))

        bus5 = gce.Bus('Bus 5', vnom=20)
        bus5.is_dc = True
        grid.add_bus(bus5)

        line34 = gce.DcLine(bus3, bus4, 'DC line 3-4', r=0.1)
        line45 = gce.DcLine(bus4, bus5, 'DC line 4-5', r=0.1)
        line35 = gce.DcLine(bus3, bus5, 'DC line 3-5', r=0.1)

        grid.add_dc_line(line34)
        grid.add_dc_line(line45)
        grid.add_dc_line(line35)

        #add vsc
        VSC1_control1 = ControlRaiyan(grid, bus4, "Voltage", 1.0)
        VSC1_control2 = ControlRaiyan(grid, bus3, "Qto", 0.01, bus2)
        vsc1 = VSC_Series(bus2, bus3, 'VSC 3-4', 0.1, {'Qt': 0.05, 'Vmf': 1.00}, VSC1_control1, VSC1_control2)
        grid.add_vsc(vsc1)

        return grid



    @staticmethod
    def pure_dc_3bus():
        # declare a circuit object
        grid = MultiCircuitRaiyan()
        grid.change_base(1000)

        # Add the buses and the generators and loads attached
        bus1 = gce.Bus('Bus 1', vnom=20)
        bus1.is_dc = True
        grid.add_bus(bus1)

        # add bus 2 with a load attached
        bus2 = gce.Bus('Bus 2', vnom=20)
        bus2.is_dc = True
        grid.add_bus(bus2)
        grid.add_load(bus2, gce.Load('load 2', P=300, Q=0))

        # add bus 3 with a load attached
        bus3 = gce.Bus('Bus 3', vnom=20)
        bus3.is_dc = True
        grid.add_bus(bus3)
        grid.add_load(bus3, gce.Load('load 3', P=200, Q=0))



        #add lines
        line12 = gce.DcLine(bus1, bus2, 'line 1-2', r=0.1)
        line13 = gce.DcLine(bus1, bus3, 'line 1-3', r=0.1)
        line23 = gce.DcLine(bus2, bus3, 'line 2-3', r=0.1)

        grid.add_dc_line(line12)
        grid.add_dc_line(line13)
        grid.add_dc_line(line23)


        gen1_control1 = ControlRaiyan(grid, bus1, "Voltage", 1.01)
        gen1 = GeneratorRaiyan('Some random generator 1', gen1_control1, None, vset=1.0, Pmin=0, Pmax=1000,
                            Qmin=-1000, Qmax=1000, Cost=15, Cost2=0.0)
        grid.add_generator(bus1, gen1)

        #return the grid
        return grid

    @staticmethod
    def ieee14_example():
        grid = MultiCircuitRaiyan()
        bus1 = gce.Bus('Bus 1', vnom=20)
        grid.add_bus(bus1)

        gen1_control1 = ControlRaiyan(grid, bus1, "Voltage", 1.06)
        gen1_control2 = ControlRaiyan(grid, bus1, "Angle", 0.0)
        gen1 = GeneratorRaiyan('Some random generator 1', gen1_control1, gen1_control2, vset=1.0, Pmin=0, Pmax=1000,
                            Qmin=-1000, Qmax=1000, Cost=15, Cost2=0.0)
        grid.add_generator(bus1, gen1)
        
        bus2 = gce.Bus('Bus 2', vnom=20)
        grid.add_bus(bus2)
        bus3 = gce.Bus('Bus 3', vnom=20)
        grid.add_bus(bus3)
        bus4 = gce.Bus('Bus 4', vnom=20)
        grid.add_bus(bus4)
        bus5 = gce.Bus('Bus 5', vnom=20)
        grid.add_bus(bus5)
        bus6 = gce.Bus('Bus 6', vnom=20)
        grid.add_bus(bus6)
        bus7 = gce.Bus('Bus 7', vnom=20)
        grid.add_bus(bus7)
        bus8 = gce.Bus('Bus 8', vnom=20)
        grid.add_bus(bus8)
        bus9 = gce.Bus('Bus 9', vnom=20)
        grid.add_bus(bus9)
        bus10 = gce.Bus('Bus 10', vnom=20)
        grid.add_bus(bus10)
        bus11 = gce.Bus('Bus 11', vnom=20)
        grid.add_bus(bus11)
        bus12 = gce.Bus('Bus 12', vnom=20)
        grid.add_bus(bus12)
        bus13 = gce.Bus('Bus 13', vnom=20)
        grid.add_bus(bus13)
        bus14 = gce.Bus('Bus 14', vnom=20)
        grid.add_bus(bus14)

        #add generators 
        gen2_control1 = ControlRaiyan(grid, bus2, "Voltage", 1.045)
        gen2_control2 = ControlRaiyan(grid, bus2, "Pzip", 40.0/100.0) #remember that we use pu, you have to convert from MW
        gen2 = GeneratorRaiyan('Some random generator 2', gen2_control1, gen2_control2, vset=1.045, Pmin=0, Pmax=1000,
                            Qmin=-1000, Qmax=1000, Cost=15, Cost2=0.0)
        grid.add_generator(bus2, gen2)


        gen3_control1 = ControlRaiyan(grid, bus3, "Voltage", 1.01)
        gen3_control2 = ControlRaiyan(grid, bus3, "Pzip", 0.0)
        gen3 = GeneratorRaiyan('Some random generator 3', gen3_control1, gen3_control2, vset=1.0, Pmin=0, Pmax=1000,
                            Qmin=-1000, Qmax=1000, Cost=15, Cost2=0.0)
        grid.add_generator(bus3, gen3)

        gen6_control1 = ControlRaiyan(grid, bus6, "Voltage", 1.07)
        gen6_control2 = ControlRaiyan(grid, bus6, "Pzip", 0.0)
        gen6 = GeneratorRaiyan('Some random generator 6', gen6_control1, gen6_control2, vset=1.0, Pmin=0, Pmax=1000,
                            Qmin=-1000, Qmax=1000, Cost=15, Cost2=0.0)
        grid.add_generator(bus6, gen6)

        gen8_control1 = ControlRaiyan(grid, bus8, "Voltage", 1.09)
        gen8_control2 = ControlRaiyan(grid, bus8, "Pzip", 0.0)
        gen8 = GeneratorRaiyan('Some random generator 8', gen8_control1, gen8_control2, vset=1.0, Pmin=0, Pmax=1000,
                            Qmin=-1000, Qmax=1000, Cost=15, Cost2=0.0)
        grid.add_generator(bus8, gen8)

        #lets add loads next
        grid.add_load(bus2, gce.Load('load 2', P=21.7, Q=12.7))
        grid.add_load(bus3, gce.Load('load 3', P=94.2, Q=19.0))
        grid.add_load(bus4, gce.Load('load 4', P=47.8, Q=-3.9))
        grid.add_load(bus5, gce.Load('load 5', P=7.6, Q=1.6))
        grid.add_load(bus6, gce.Load('load 6', P=11.2, Q=7.5))
        grid.add_load(bus9, gce.Load('load 9', P=29.5, Q=16.6))
        grid.add_load(bus10, gce.Load('load 10', P=9.0, Q=5.8))
        grid.add_load(bus11, gce.Load('load 11', P=3.5, Q=1.8))
        grid.add_load(bus12, gce.Load('load 12', P=6.1, Q=1.6))
        grid.add_load(bus13, gce.Load('load 13', P=13.5, Q=5.8))
        grid.add_load(bus14, gce.Load('load 14', P=14.9, Q=5.0))


        #lets add the shunt at bus 9
        grid.add_shunt(bus9, gce.Shunt('shunt 9', G=0.0, B=19.0))

        #lets add the lines next
        line12 = gce.Line(bus1, bus2, 'line 1-2', r=0.01938, x=0.05917, b=0.0528)
        line15 = gce.Line(bus1, bus5, 'line 1-5', r=0.05403, x=0.22304, b=0.0492)
        line23 = gce.Line(bus2, bus3, 'line 2-3', r=0.04699, x=0.19797, b=0.0438)
        line24 = gce.Line(bus2, bus4, 'line 2-4', r=0.05811, x=0.17632, b=0.034)
        line25 = gce.Line(bus2, bus5, 'line 2-5', r=0.05695, x=0.17388, b=0.0346)
        line34 = gce.Line(bus3, bus4, 'line 3-4', r=0.06701, x=0.17103, b=0.0128)
        line45 = gce.Line(bus4, bus5, 'line 4-5', r=0.01335, x=0.04211, b=0.0)
        line6_11 = gce.Line(bus6, bus11, 'line 6-11', r=0.09498, x=0.19890, b=0.0)
        line6_12 = gce.Line(bus6, bus12, 'line 6-12', r=0.12291, x=0.25581, b=0.0)
        line6_13 = gce.Line(bus6, bus13, 'line 6-13', r=0.06615, x=0.13027, b=0.0) 
        line78 = gce.Line(bus7, bus8, 'line 7-8', r=0.0, x=0.17615, b=0.0)
        line79 =  gce.Line(bus7, bus9, 'line 7-9', r=0.0, x=0.11001, b=0.0)
        line9_10 = gce.Line(bus9, bus10, 'line 9-10', r=0.03181, x=0.08450, b=0.0)
        line9_14 = gce.Line(bus9, bus14, 'line 9-14', r=0.12711, x=0.27038, b=0.0)
        line10_11 = gce.Line(bus10, bus11, 'line 10-11', r=0.08205, x=0.19207, b=0.0)
        line12_13 = gce.Line(bus12, bus13, 'line 12-13', r=0.22092, x=0.19988, b=0.0)
        line13_14 = gce.Line(bus13, bus14, 'line 13-14', r=0.17093, x=0.34802, b=0.0)

        grid.add_line(line12)
        grid.add_line(line15)
        grid.add_line(line23)
        grid.add_line(line24)
        grid.add_line(line25)
        grid.add_line(line34)
        grid.add_line(line45)
        grid.add_line(line6_11)
        grid.add_line(line6_12)
        grid.add_line(line6_13)
        grid.add_line(line78)
        grid.add_line(line79)
        grid.add_line(line9_10)
        grid.add_line(line9_14)
        grid.add_line(line10_11)
        grid.add_line(line12_13)
        grid.add_line(line13_14)

        #lets add transformers
        tct4_7 = gce.Transformer2W(bus4, bus7, 'Transformer 4-7', r=0.0, x=0.20912, tap_module=0.978)
        tct4_9 = gce.Transformer2W(bus4, bus9, 'Transformer 4-9', r=0.0, x=0.55618, tap_module=0.969)
        tct5_6 = gce.Transformer2W(bus5, bus6, 'Transformer 5-6', r=0.0, x=0.25202, tap_module=0.932)

        grid.add_transformer2w(tct4_7)
        grid.add_transformer2w(tct4_9)
        grid.add_transformer2w(tct5_6)

        return grid
    

    @staticmethod
    def linn5bus_example2():
        """
        Grid from Lynn Powel's book
        """
        # declare a circuit object
        grid = MultiCircuitRaiyan()
        # Add the buses and the generators and loads attached
        bus1 = gce.Bus('Bus 1', vnom=20)
        grid.add_bus(bus1)



        # add bus 2 with a load attached
        bus2 = gce.Bus('Bus 2', vnom=20)
        grid.add_bus(bus2)
        grid.add_load(bus2, gce.Load('load 2', P=40, Q=20))
        # add bus 3 with a load attached
        bus3 = gce.Bus('Bus 3', vnom=20)
        grid.add_bus(bus3)
        grid.add_load(bus3, gce.Load('load 3', P=25, Q=15))
        # add bus 4 with a load attached
        bus4 = gce.Bus('Bus 4', vnom=20)
        grid.add_bus(bus4)
        grid.add_load(bus4, gce.Load('load 4', P=40, Q=20))
        # add bus 5 with a load attached
        bus5 = gce.Bus('Bus 5', vnom=20)
        grid.add_bus(bus5)
        grid.add_load(bus5, gce.Load('load 5', P=50, Q=20))

        # add Lines connecting the buses
        grid.add_line(gce.Line(bus1, bus2, name='line 1-2', r=0.05, x=0.11, b=0.02, rate=1000))
        grid.add_line(gce.Line(bus1, bus3, name='line 1-3', r=0.05, x=0.11, b=0.02, rate=1000))
        grid.add_line(gce.Line(bus1, bus5, name='line 1-5', r=0.03, x=0.08, b=0.02, rate=1000))
        grid.add_line(gce.Line(bus2, bus3, name='line 2-3', r=0.04, x=0.09, b=0.02, rate=1000))
        grid.add_line(gce.Line(bus2, bus5, name='line 2-5', r=0.04, x=0.09, b=0.02, rate=1000))
        grid.add_line(gce.Line(bus3, bus4, name='line 3-4', r=0.06, x=0.13, b=0.03, rate=1000))
        grid.add_line(gce.Line(bus4, bus5, name='line 4-5', r=0.04, x=0.09, b=0.02, rate=1000))


        gen1_control1 = ControlRaiyan(grid, bus1, "Voltage", 1.0)
        gen1_control2 = ControlRaiyan(grid, bus1, "Angle", 0.1)
        gen1 = GeneratorRaiyan('Some random generator 1', gen1_control1, gen1_control2, vset=1.0, Pmin=0, Pmax=1000,
                            Qmin=-1000, Qmax=1000, Cost=15, Cost2=0.0)
        
        gen2_control1 = ControlRaiyan(grid, bus2, "Pzip", 0.3)
        # gen2_control2 = ControlRaiyan(grid, bus2, "Qzip", 0.3)
        gen2_control2 = ControlRaiyan(grid, bus2, "Voltage", 1.01)
        gen2 = GeneratorRaiyan('Some random generator 2', gen2_control1, gen2_control2, vset=1.0, Pmin=0, Pmax=1000,
                            Qmin=-1000, Qmax=1000, Cost=15, Cost2=0.0)
        

        grid.add_generator(bus1, gen1)
        grid.add_generator(bus2, gen2)

        
        return grid       

    @staticmethod
    def linn5bus_example():
        """
        Grid from Lynn Powel's book
        """
        # declare a circuit object
        grid = MultiCircuitRaiyan()
        # Add the buses and the generators and loads attached
        bus1 = gce.Bus('Bus 1', vnom=20)
        grid.add_bus(bus1)

        gen1_control1 = ControlRaiyan(grid, bus1, "Voltage", 1.00)
        gen1_control2 = ControlRaiyan(grid, bus1, "Angle", 0.0)
        gen1 = GeneratorRaiyan('Some random generator 1', gen1_control1, gen1_control2, vset=1.0, Pmin=0, Pmax=1000,
                            Qmin=-1000, Qmax=1000, Cost=15, Cost2=0.0)
        

        grid.add_generator(bus1, gen1)

        # add bus 2 with a load attached
        bus2 = gce.Bus('Bus 2', vnom=20)
        grid.add_bus(bus2)
        grid.add_load(bus2, gce.Load('load 2', P=40, Q=20))
        # add bus 3 with a load attached
        bus3 = gce.Bus('Bus 3', vnom=20)
        grid.add_bus(bus3)
        grid.add_load(bus3, gce.Load('load 3', P=25, Q=15))
        # add bus 4 with a load attached
        bus4 = gce.Bus('Bus 4', vnom=20)
        grid.add_bus(bus4)
        grid.add_load(bus4, gce.Load('load 4', P=40, Q=20))
        # add bus 5 with a load attached
        bus5 = gce.Bus('Bus 5', vnom=20)
        grid.add_bus(bus5)
        grid.add_load(bus5, gce.Load('load 5', P=50, Q=20))

        # add Lines connecting the buses
        grid.add_line(gce.Line(bus1, bus2, name='line 1-2', r=0.05, x=0.11, b=0.02, rate=1000))
        grid.add_line(gce.Line(bus1, bus3, name='line 1-3', r=0.05, x=0.11, b=0.02, rate=1000))
        grid.add_line(gce.Line(bus1, bus5, name='line 1-5', r=0.03, x=0.08, b=0.02, rate=1000))
        grid.add_line(gce.Line(bus2, bus3, name='line 2-3', r=0.04, x=0.09, b=0.02, rate=1000))
        grid.add_line(gce.Line(bus2, bus5, name='line 2-5', r=0.04, x=0.09, b=0.02, rate=1000))
        grid.add_line(gce.Line(bus3, bus4, name='line 3-4', r=0.06, x=0.13, b=0.03, rate=1000))
        grid.add_line(gce.Line(bus4, bus5, name='line 4-5', r=0.04, x=0.09, b=0.02, rate=1000))

        return grid


    @staticmethod
    def pure_ac_2bus():

        grid = MultiCircuitRaiyan()
        grid.change_base(1000)


        bus1 = gce.Bus('Bus 1', vnom=20)
        grid.add_bus(bus1)
        gen1_control1 = ControlRaiyan(grid, bus1, "Voltage", 1.01)
        gen1_control2 = ControlRaiyan(grid, bus1, "Angle", 0.0)
        gen1 = GeneratorRaiyan('Some random generator 1', gen1_control1, gen1_control2, vset=1.0, Pmin=0, Pmax=1000,
                            Qmin=-1000, Qmax=1000, Cost=15, Cost2=0.0)
        

        grid.add_generator(bus1, gen1)
        bus2 = gce.Bus('Bus 2', vnom=20)
        grid.add_bus(bus2)
        grid.add_load(bus2, gce.Load('load 2', P=300, Q=100))

        line12 = gce.Line(bus1, bus2, 'line 1-2', r=0.1, x=0.3, b=0.0)
        grid.add_line(line12)

        return grid
    

    @staticmethod
    def pure_ac_3bus_trafo():

        grid = MultiCircuitRaiyan()
        grid.change_base(1000)

        bus1 = gce.Bus('Bus 1', vnom=20)
        grid.add_bus(bus1)
        gen1_control1 = ControlRaiyan(grid, bus1, "Voltage", 1.01)
        gen1_control2 = ControlRaiyan(grid, bus1, "Angle", 0.0)
        gen1 = GeneratorRaiyan('Some random generator 1', gen1_control1, gen1_control2, vset=1.0, Pmin=0, Pmax=1000,
                            Qmin=-1000, Qmax=1000, Cost=15, Cost2=0.0)

        grid.add_generator(bus1, gen1)
        bus2 = gce.Bus('Bus 2', vnom=20)
        grid.add_bus(bus2)
        grid.add_load(bus2, gce.Load('load 2', P=300, Q=100))

        bus3 = gce.Bus('Bus 3', vnom=20)
        grid.add_bus(bus3)  
        grid.add_load(bus3, gce.Load('load 3', P=200, Q=50))

        trafo1_control1 = ControlRaiyan(grid, bus3, "Pto", 0.1, bus1)
        trafo2_control2 = ControlRaiyan(grid, bus3, "Qto", 0.1, bus1)    
        trafo1 = Controlled_Trafo(bus3, bus1, 'Trafo 1-3', trafo1_control1, trafo2_control2)
        grid.add_contTrafo(bus3, bus1, trafo1)

        line12 = gce.Line(bus1, bus2, 'line 1-2', r=0.1, x=0.3, b=0.0)
        line23 = gce.Line(bus2, bus3, 'line 2-3', r=0.1, x=0.3, b=0.0)
        grid.add_line(line12)
        grid.add_line(line23)

        return grid

    @staticmethod
    def acdc_10bus_branchcontrol():
        # declare a circuit object
        grid = MultiCircuitRaiyan()
        grid.change_base(1000)

        # Add the buses and the generators and loads attached
        bus1 = gce.Bus('Bus 1', vnom=20)
        grid.add_bus(bus1)

        # add bus 2 with a load attached
        bus2 = gce.Bus('Bus 2', vnom=20)
        grid.add_bus(bus2)
        grid.add_load(bus2, gce.Load('load 2', P=300, Q=100))

        # add bus 3 with a load attached
        bus3 = gce.Bus('Bus 3', vnom=20)
        grid.add_bus(bus3)
        grid.add_load(bus3, gce.Load('load 3', P=200, Q=50))

        # add bus 4 with a load attached
        bus4 = gce.Bus('Bus 4', vnom=20)
        bus4.is_dc = True
        grid.add_bus(bus4)
        grid.add_load(bus4, gce.Load('load 4', P=200))

        # add bus 5 with a load attached
        bus5 = gce.Bus('Bus 5', vnom=20)
        bus5.is_dc = True
        grid.add_bus(bus5)
        grid.add_load(bus5, gce.Load('load 5', P=100))

        # add bus 6
        bus6 = gce.Bus('Bus 6', vnom=150)
        bus6.is_dc = True
        grid.add_bus(bus6)
        grid.add_load(bus6, gce.Load('load 6', P=150))

        #add bus 7 with a load attached
        bus7 = gce.Bus('Bus 7', vnom=20)
        grid.add_bus(bus7)
        grid.add_load(bus7, gce.Load('load 7', P=100, Q=100))


        #add bus 8 with a load attached
        bus8 = gce.Bus('Bus 8', vnom=20)
        grid.add_bus(bus8)
        #add load 0.2 + 0.05 * 1j pu
        grid.add_load(bus8, gce.Load('load 8', P=200, Q=50))


        #add bus 9 with a load attached
        bus9 = gce.Bus('Bus 9', vnom=20)
        grid.add_bus(bus9)
        grid.add_load(bus9, gce.Load('load 9', P=300, Q=100))


        #add bus 10 as a slack bus
        bus10 = gce.Bus('Bus 10', vnom=20) 
        grid.add_bus(bus10)


        #add lines
        line12 = gce.Line(bus1, bus2, 'line 1-2', r=0.1, x=0.3, b=0.0)
        line13 = gce.Line(bus1, bus3, 'line 1-3', r=0.1, x=0.3, b=0.0)
        line23 = gce.Line(bus2, bus3, 'line 2-3', r=0.1, x=0.3, b=0.0)
        line45 = gce.DcLine(bus4, bus5, 'DC line 4-5', r=0.1)
        line56 = gce.DcLine(bus5, bus6, 'DC line 5-6', r=0.1)
        line46 = gce.DcLine(bus4, bus6, 'DC line 4-6', r=0.1)
        line78 = gce.Line(bus7, bus8, 'line 7-8', r=0.1, x=0.3, b=0.0)
        line89 = gce.Line(bus8, bus9, 'line 8-9', r=0.1, x=0.3, b=0.0)
        line910 = gce.Line(bus9, bus10, 'line 9-10', r=0.1, x=0.3, b=0.0)
        grid.add_line(line12)
        grid.add_line(line13)
        grid.add_line(line23)
        grid.add_dc_line(line45)
        grid.add_dc_line(line56)
        grid.add_dc_line(line46)
        grid.add_line(line78)
        grid.add_line(line89)
        grid.add_line(line910)    

        #use gen 1 control to set bus 1 as slack
        gen1_control1 = ControlRaiyan(grid, bus1, "Voltage", 1.1)
        gen1_control2 = ControlRaiyan(grid, bus1, "Angle", 0.0)
        gen1 = GeneratorRaiyan('Some random generator 1', gen1_control1, gen1_control2, vset=1.0, Pmin=0, Pmax=1000,
                            Qmin=-1000, Qmax=1000, Cost=15, Cost2=0.0)
        grid.add_generator(bus1, gen1)

        
        #use gen 10 control to set bus 10 as slack, same as gen1
        gen10_control1 = ControlRaiyan(grid, bus10, "Voltage", 0.98)
        gen10_control2 = ControlRaiyan(grid, bus10, "Angle", 0.0)
        gen10 = GeneratorRaiyan('Some random generator 2', gen10_control1, gen10_control2, vset=1.0, Pmin=0, Pmax=1000,
                            Qmin=-1000, Qmax=1000, Cost=15, Cost2=0.0)
        grid.add_generator(bus10, gen10)

        #add vsc
        VSC1_control1 = ControlRaiyan(grid, bus4, "Voltage", 1.0)
        VSC1_control2 = ControlRaiyan(grid, bus4, "Qto", 0.1, bus3)
        # VSC2_control1 = ControlRaiyan(grid, bus6, "Qto", 0.1, bus7)
        # VSC2_control1 = ControlRaiyan(grid, bus2, "Pto", 0.3, bus1)
        # VSC2_control1 = ControlRaiyan(grid, bus4, "Pto", 0.0, bus6)
        VSC2_control1 = ControlRaiyan(grid, bus6, "Voltage", 1.03)
        VSC2_control2 = ControlRaiyan(grid, bus7, "Voltage", 1.05)
        vsc1 = VSC_Series(bus3, bus4, 'VSC 3-4', 0.1, {'Qt': 0.05, 'Vmf': 1.00}, VSC1_control1, VSC1_control2)
        vsc2 = VSC_Series(bus6, bus7, 'VSC 6-7', 0.1, {'Pf': 0.12, 'Vmt': 0.99}, VSC2_control1, VSC2_control2)
        grid.add_vsc(vsc1)
        grid.add_vsc(vsc2)


        trafo1_control1 = ControlRaiyan(grid, bus9, "Tau", 0.05, bus10)
        trafo2_control2 = ControlRaiyan(grid, bus9, "Pto", 0.5, bus10)    
        trafo1 = Controlled_Trafo(bus9, bus10, 'Trafo 9-10', trafo1_control1, trafo2_control2)
        grid.add_contTrafo(bus9, bus10, trafo1)


        #return the grid
        return grid


    @staticmethod
    def acdc_10bus():
        # declare a circuit object
        grid = MultiCircuitRaiyan()
        grid.change_base(1000)

        # Add the buses and the generators and loads attached
        bus1 = gce.Bus('Bus 1', vnom=20)
        grid.add_bus(bus1)

        # add bus 2 with a load attached
        bus2 = gce.Bus('Bus 2', vnom=20)
        grid.add_bus(bus2)
        grid.add_load(bus2, gce.Load('load 2', P=300, Q=100))

        # add bus 3 with a load attached
        bus3 = gce.Bus('Bus 3', vnom=20)
        grid.add_bus(bus3)
        grid.add_load(bus3, gce.Load('load 3', P=200, Q=50))

        # add bus 4 with a load attached
        bus4 = gce.Bus('Bus 4', vnom=20)
        bus4.is_dc = True
        grid.add_bus(bus4)
        grid.add_load(bus4, gce.Load('load 4', P=200))

        # add bus 5 with a load attached
        bus5 = gce.Bus('Bus 5', vnom=20)
        bus5.is_dc = True
        grid.add_bus(bus5)
        grid.add_load(bus5, gce.Load('load 5', P=100))

        # add bus 6
        bus6 = gce.Bus('Bus 6', vnom=150)
        bus6.is_dc = True
        grid.add_bus(bus6)
        grid.add_load(bus6, gce.Load('load 6', P=150))

        #add bus 7 with a load attached
        bus7 = gce.Bus('Bus 7', vnom=20)
        grid.add_bus(bus7)
        grid.add_load(bus7, gce.Load('load 7', P=100, Q=100))


        #add bus 8 with a load attached
        bus8 = gce.Bus('Bus 8', vnom=20)
        grid.add_bus(bus8)
        #add load 0.2 + 0.05 * 1j pu
        grid.add_load(bus8, gce.Load('load 8', P=200, Q=50))


        #add bus 9 with a load attached
        bus9 = gce.Bus('Bus 9', vnom=20)
        grid.add_bus(bus9)
        grid.add_load(bus9, gce.Load('load 9', P=300, Q=100))


        #add bus 10 as a slack bus
        bus10 = gce.Bus('Bus 10', vnom=20) 
        grid.add_bus(bus10)


        #add lines
        line12 = gce.Line(bus1, bus2, 'line 1-2', r=0.1, x=0.3, b=0.0)
        line13 = gce.Line(bus1, bus3, 'line 1-3', r=0.1, x=0.3, b=0.0)
        line23 = gce.Line(bus2, bus3, 'line 2-3', r=0.1, x=0.3, b=0.0)
        line45 = gce.DcLine(bus4, bus5, 'DC line 4-5', r=0.1)
        line56 = gce.DcLine(bus5, bus6, 'DC line 5-6', r=0.1)
        line46 = gce.DcLine(bus4, bus6, 'DC line 4-6', r=0.1)
        line78 = gce.Line(bus7, bus8, 'line 7-8', r=0.1, x=0.3, b=0.0)
        line89 = gce.Line(bus8, bus9, 'line 8-9', r=0.1, x=0.3, b=0.0)
        line910 = gce.Line(bus9, bus10, 'line 9-10', r=0.1, x=0.3, b=0.0)
        grid.add_line(line12)
        grid.add_line(line13)
        grid.add_line(line23)
        grid.add_dc_line(line45)
        grid.add_dc_line(line56)
        grid.add_dc_line(line46)
        grid.add_line(line78)
        grid.add_line(line89)
        grid.add_line(line910)    

        #use gen 1 control to set bus 1 as slack
        gen1_control1 = ControlRaiyan(grid, bus1, "Voltage", 1.1)
        gen1_control2 = ControlRaiyan(grid, bus1, "Angle", 0.0)
        gen1 = GeneratorRaiyan('Some random generator 1', gen1_control1, gen1_control2, vset=1.0, Pmin=0, Pmax=1000,
                            Qmin=-1000, Qmax=1000, Cost=15, Cost2=0.0)
        grid.add_generator(bus1, gen1)

        
        #use gen 10 control to set bus 10 as slack, same as gen1
        gen10_control1 = ControlRaiyan(grid, bus10, "Voltage", 0.98)
        gen10_control2 = ControlRaiyan(grid, bus10, "Angle", 0.0)
        gen10 = GeneratorRaiyan('Some random generator 2', gen10_control1, gen10_control2, vset=1.0, Pmin=0, Pmax=1000,
                            Qmin=-1000, Qmax=1000, Cost=15, Cost2=0.0)
        grid.add_generator(bus10, gen10)

        #add vsc
        VSC1_control1 = ControlRaiyan(grid, bus4, "Voltage", 1.0)
        VSC1_control2 = ControlRaiyan(grid, bus4, "Qto", 0.1, bus3)
        # VSC2_control1 = ControlRaiyan(grid, bus6, "Qto", 0.1, bus7)
        VSC2_control1 = ControlRaiyan(grid, bus6, "Pto", -0.1, bus7)
        VSC2_control2 = ControlRaiyan(grid, bus7, "Voltage", 1.05)
        vsc1 = VSC_Series(bus3, bus4, 'VSC 3-4', 0.1, {'Qt': 0.05, 'Vmf': 1.00}, VSC1_control1, VSC1_control2)
        vsc2 = VSC_Series(bus6, bus7, 'VSC 6-7', 0.1, {'Pf': 0.12, 'Vmt': 0.99}, VSC2_control1, VSC2_control2)
        grid.add_vsc(vsc1)
        grid.add_vsc(vsc2)


        trafo1_control1 = ControlRaiyan(grid, bus9, "Tau", 0.05, bus10)
        trafo2_control2 = ControlRaiyan(grid, bus9, "Pto", 0.5, bus10)    
        trafo1 = Controlled_Trafo(bus9, bus10, 'Trafo 9-10', trafo1_control1, trafo2_control2)
        grid.add_contTrafo(bus9, bus10, trafo1)


        #return the grid
        return grid
    
class GeneratorRaiyan(gce.Generator):
    def __init__(self,
                 name: str,
                 control1: ControlRaiyan,
                 control2: ControlRaiyan,
                 vset: float,
                    Pmin: float,
                    Pmax: float,
                    Qmin: float,
                    Qmax: float,
                    Cost: float,
                    Cost2: float):
                 
        super().__init__(name, vset=vset, Pmin=Pmin, Pmax=Pmax, Qmin=Qmin, Qmax=Qmax, Cost=Cost, Cost2=Cost2)
        self.control1 = control1
        self.control2 = control2
        if control2 is not None:
            ControlRaiyan.update_instances(self, self.control1, self.control2)
        else:
            ControlRaiyan.update_instances(self, self.control1)

class VSC_Series(VSC):
    _instances_count = 0
    _instances = []
    _vsc_connection_index_dcside = []
    _vsc_connection_index_acside = []


    def __init__(self, bus_from: str, 
                 bus_to: str, 
                 name: str, 
                 value: float, 
                 control: dict,
                 control1 = None,
                 control2 = None):
        
        bus_from, bus_to = self.switch_buses(bus_from, bus_to)
        super().__init__(bus_from, bus_to, name)
        self._bus_from = bus_from
        self._bus_to = bus_to
        self.control = control
        self._Vmf_isControlled = 0
        self._Vmt_isControlled = 0
        self._Vat_isControlled = 0
        self._Pf_isControlled = 0
        self._Pt_isControlled = 0
        self._Qt_isControlled = 0
        self._Vmf = 0.0
        self._Vmt = 0.0
        self._Vat = 0.0
        self._Pf = 0.0
        self._Pt = 0.0
        self._Qt = 0.0
        self.set_all_controls()
        self.control1 = control1
        self.control2 = control2
        if control1 is not None and control2 is not None:
            ControlRaiyan.update_instances(self, control1, control2)

    def __str__(self):
        return f'{self.name}:Bus from: {self.bus_from}, Bus to: {self.bus_to}'

    def __repr__(self):
        return f'{self.name}:Bus from: {self.bus_from}, Bus to: {self.bus_to}'
    
    def switch_buses(self, bus_from, bus_to):
        if not bus_from.is_dc:
            return bus_to, bus_from
        else:
            return bus_from, bus_to

    def set_all_controls(self):
        #if the length of control is not exactly two, raise error
        if len(self.control) != 2:
            raise ValueError("You must control exactly two variables")
        
        for key, value in self.control.items():
            if key == 'Vmf':
                self.Vmf_isControlled = 1
                self.Vmf = value
            elif key == 'Vmt':
                self.Vmt_isControlled = 1
                self.Vmt = value
            elif key == 'Vat':
                self.Vat_isControlled = 1
                self.Vat = value
            elif key == 'Pf':
                self.Pf_isControlled = 1
                self.Pf = value
            elif key == 'Pt':
                self.Pt_isControlled = 1
                self.Pt = value
            elif key == 'Qt':
                self.Qt_isControlled = 1
                self.Qt = value
            else:
                raise ValueError("You gave me a strange control string, I don't know what to do with it.")
            
        
    def all_isControlled(self):
        _a = self.Vmf_isControlled
        _b = self.Vmt_isControlled
        # _c = self.Vat_isControlled
        _d = self.Pf_isControlled
        _e = self.Pt_isControlled
        _f = self.Qt_isControlled
        return _a, _b, _d, _e, _f
    
    def all_values(self):
        _a = self.Vmf
        _b = self.Vmt
        # _c = self.Vat
        _d = self.Pf
        _e = self.Pt
        _f = self.Qt
        return _a, _b, _d, _e, _f
    
   


    @classmethod
    def get_vsc_p_from_value(cls):
        return np.array([vsc.Pf for vsc in cls._instances])
    
    @classmethod
    def get_vsc_p_to_value(cls):
        return np.array([vsc.Pt for vsc in cls._instances])
    
    @classmethod
    def get_vsc_q_to_value(cls):
        return np.array([vsc.Qt for vsc in cls._instances])
    
    @classmethod
    def get_vsc_vmf_value(cls):
        return np.array([vsc.Vmf for vsc in cls._instances])
    
    @classmethod
    def get_vsc_vmt_value(cls):
        return np.array([vsc.Vmt for vsc in cls._instances])
    
    @classmethod
    def get_vsc_p_from_isControlled(cls):
        return np.array([vsc.Pf_isControlled for vsc in cls._instances])
    
    @classmethod
    def get_vsc_p_to_isControlled(cls):
        return np.array([vsc.Pt_isControlled for vsc in cls._instances])
    
    @classmethod
    def get_vsc_q_to_isControlled(cls):
        return np.array([vsc.Qt_isControlled for vsc in cls._instances])
    
    @classmethod
    def get_vsc_vmf_isControlled(cls):
        return np.array([vsc.Vmf_isControlled for vsc in cls._instances])
    
    @classmethod
    def get_vsc_vmt_isControlled(cls):
        return np.array([vsc.Vmt_isControlled for vsc in cls._instances])

    @classmethod
    def get_count(cls):
        return cls._instances_count

    @classmethod
    def get_instances(cls):
        return cls._instances
    
    @classmethod
    def get_vsc_connection_index_dcside(cls):
        return cls._vsc_connection_index_dcside
    
    @classmethod
    def get_vsc_connection_index_acside(cls):
        return cls._vsc_connection_index_acside

    @property   
    def Vmf_isControlled(self):
        return self._Vmf_isControlled
    
    @Vmf_isControlled.setter
    def Vmf_isControlled(self, value):
        self._Vmf_isControlled = value
    
    @property
    def Vmt_isControlled(self):
        return self._Vmt_isControlled
    
    @Vmt_isControlled.setter
    def Vmt_isControlled(self, value):
        self._Vmt_isControlled = value

    @property
    def Vat_isControlled(self):
        return self._Vat_isControlled
    
    @Vat_isControlled.setter
    def Vat_isControlled(self, value):
        self._Vat_isControlled = value

    @property
    def Pf_isControlled(self):
        return self._Pf_isControlled
    
    @Pf_isControlled.setter
    def Pf_isControlled(self, value):
        self._Pf_isControlled = value

    @property
    def Pt_isControlled(self):
        return self._Pt_isControlled
    
    @Pt_isControlled.setter
    def Pt_isControlled(self, value):
        self._Pt_isControlled = value

    @property
    def Qt_isControlled(self):
        return self._Qt_isControlled
    
    @Qt_isControlled.setter
    def Qt_isControlled(self, value):
        self._Qt_isControlled = value

    @property
    def Vmf(self):
        return self._Vmf
    
    @Vmf.setter
    def Vmf(self, value):
        self._Vmf = value

    @property
    def Vmt(self):
        return self._Vmt
    
    @Vmt.setter
    def Vmt(self, value):
        self._Vmt = value

    @property
    def Vat(self):
        return self._Vat
    
    @Vat.setter
    def Vat(self, value):
        self._Vat = value

    @property
    def Pf(self):
        return self._Pf
    
    @Pf.setter
    def Pf(self, value):
        self._Pf = value

    @property
    def Pt(self):
        return self._Pt
    
    @Pt.setter
    def Pt(self, value):
        self._Pt = value

    @property
    def Qt(self):
        return self._Qt
    
    @Qt.setter
    def Qt(self, value):
        self._Qt = value

class Controlled_Trafo(Transformer2W):
    def __init__(self, bus_from: str, bus_to: str, name: str, control1, control2, y_series = 1.0 / (0.0 + 0.1 * 1j), y_shunt = 0.0):
        super().__init__(bus_from, bus_to, name)
        self.bus_from = bus_from
        self.bus_to = bus_to
        self.control1 = control1
        self.control2 = control2
        self.yseries = y_series
        self.yshunt = y_shunt
        ControlRaiyan.update_instances(self, self.control1, self.control2)

    def __str__(self):
        return f'{self.name}, Bus from: {self.bus_from}, Bus to: {self.bus_to}'

    def __repr__(self):
        return f'{self.name}, Bus from: {self.bus_from}, Bus to: {self.bus_to}'


def update_setpoints(known_dict, 
                    grid,
                    Vm0, 
                    Va0, 
                    S0, 
                    I0, 
                    Y0, 
                    p_from, 
                    p_to, 
                    q_from, 
                    q_to,
                    p_zip, 
                    q_zip,
                    modulations,
                    taus,
                    verbose = 0):
    """
    Updates the initial setpoints for various grid parameters based on the known values.

    This function takes a dictionary of known setpoints for different parameters (such as voltage magnitude, voltage angle, power flows, and others) and updates the corresponding initial guess arrays/lists for these parameters.

    Parameters
    ----------
    known_dict : dict
        A dictionary containing known setpoints for various parameters like 'Voltage', 'Angle', 'Pto', etc.
    grid : Grid object
        The electrical grid object. Currently not used directly but required for future extensions or checks.
    Vm0, Va0 : list or np.array
        Initial guesses for voltage magnitudes and angles, respectively.
    S0, I0, Y0 : list or np.array
        Not directly updated but included for consistency and future use.
    p_from, p_to, q_from, q_to : list or np.array
        Lists containing initial guesses for active and reactive power flows from and to connected buses.
    p_zip, q_zip : list or np.array
        Lists containing initial guesses for active and reactive ZIP load injections at buses.
    modulations, taus : list or np.array
        Lists containing initial guesses for modulation values and time constants associated with dynamic components.
    verbose : int, optional
        If set to 1, prints updated arrays/lists after applying known setpoints.

    Returns
    -------
    tuple
        Returns a tuple containing updated arrays/lists for all input parameters, reflecting the known setpoints.
    """
    
    # Check and update 'Voltage' if it's present in known_dict
    if 'Voltage' in known_dict:
        for bus_index, voltage in known_dict['Voltage'].items():
            Vm0[bus_index] = voltage  # Update the voltage magnitude at the specified bus index
    
    # Check and update 'Angle' if it's present in known_dict
    if 'Angle' in known_dict:
        for bus_index, angle in known_dict['Angle'].items():
            Va0[bus_index] = angle  # Convert angle to radians and update

    if 'Pto' in known_dict:
        for bus_index, pto in known_dict['Pto'].items():
            #add the pto setpoint to the p_to list using the index
            p_to[bus_index[1]] = pto

    if 'Pfrom' in known_dict:
        for bus_index, pfrom in known_dict['Pfrom'].items():
            #add the pfrom setpoint to the p_from list using the index
            p_from[bus_index[0]] = pfrom

    if 'Qto' in known_dict:
        for bus_index, qto in known_dict['Qto'].items():
            #add the qto setpoint to the q_to list using the index
            q_to[bus_index[1]] = qto

    if 'Qfrom' in known_dict:
        for bus_index, qfrom in known_dict['Qfrom'].items():
            #add the qfrom setpoint to the q_from list using the index
            q_from[bus_index[0]] = qfrom

    if 'Pzip' in known_dict:	
        for bus_index, pzip in known_dict['Pzip'].items():	
            #add the pzip setpoint to the p_zip list using the index	
            p_zip[bus_index] = pzip

    if 'Qzip' in known_dict:
        for bus_index, qzip in known_dict['Qzip'].items():
            #add the qzip setpoint to the q_zip list using the index
            q_zip[bus_index] = qzip

    if 'Modulation' in known_dict:
        for bus_index, modulation in known_dict['Modulation'].items():
            modulations[bus_index[0]] = modulation

    if 'Tau' in known_dict:
        for bus_index, tau in known_dict['Tau'].items():
            taus[bus_index[0]] = tau

    if verbose:
        print('Vm0 after updating known Voltage setpoints:', Vm0)
        print('Va0 after updating known Angle setpoints:', Va0)
        print('Pto after updating known Pto setpoints:', p_to)
        print('Pfrom after updating known Pfrom setpoints:', p_from)
        print('Qto after updating known Qto setpoints:', q_to)
        print('Qfrom after updating known Qfrom setpoints:', q_from)    
        print('Pzip after updating known Pzip setpoints:', p_zip)
        print('Qzip after updating known Qzip setpoints:', q_zip)
        print('Modulation after updating known Modulation setpoints:', modulations)
        print('Tau after updating known Tau setpoints:', taus)
    return Vm0, Va0, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus


def var2x(Va: Vec, Vm: Vec) -> Vec:
    """
    Compose the unknowns vector
    :param Va: Array of voltage angles for the PV and PQ nodes
    :param Vm: Array of voltage modules for the PQ nodes
    :return: [Va | Vm]
    """
    return np.r_[Va, Vm]

def var2x_raiyan_ver2(unknown_dict, Vm0, Va0, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus, verbose=0):
    """
    Converts variable parameters into a vector form based on a dictionary of unknowns.

    This function takes various electrical network parameters and a dictionary specifying which of these parameters are unknown. It then constructs a vector `x` that contains the values of these unknown parameters for use in optimization or analysis processes. Additionally, it generates a list of names `x_names` corresponding to each entry in `x` for identification.

    Parameters
    ----------
    unknown_dict : dict
        A dictionary with keys corresponding to parameter types (e.g., 'Voltage', 'Angle') and values being lists of indices or tuples indicating which parameters are unknown.
    Vm0, Va0 : list or np.array
        Lists containing initial guesses or values for voltage magnitudes and angles, respectively.
    S0, I0, Y0 : list or np.array
        Lists containing initial values for power, current, and admittance injections at buses (not directly used but included for completeness and future extensions).
    p_to, p_from, q_to, q_from : list or np.array
        Lists containing power flow values to and from connected buses.
    p_zip, q_zip : list or np.array
        Lists containing ZIP load injections at buses.
    modulations, taus : list or np.array
        Lists containing modulation variables and time constants associated with dynamic elements of the network.
    verbose : int, optional
        If set to 1, prints detailed information about the constructed vector `x` and its identifiers `x_names`.

    Returns
    -------
    list
        The vector `x` containing values for the unknown parameters as specified in `unknown_dict`.
    """


    x = []
    x_names = []

      
    if 'Voltage' in unknown_dict:
        for bus_index in unknown_dict['Voltage']:
            x.append(Vm0[bus_index])
            x_names.append(f'Voltage_{bus_index}')
    
    if 'Angle' in unknown_dict:
        for bus_index in unknown_dict['Angle']:
            x.append(Va0[bus_index])
            x_names.append(f'Angle_{bus_index}')

    if 'Pzip' in unknown_dict:
        for bus_index in unknown_dict['Pzip']:
            x.append(p_zip[bus_index])
            x_names.append(f'Pzip_{bus_index}')

    if 'Qzip' in unknown_dict:
        for bus_index in unknown_dict['Qzip']:
            x.append(q_zip[bus_index])
            x_names.append(f'Qzip_{bus_index}')

    if 'Pfrom' in unknown_dict:
        for bus_indices in unknown_dict['Pfrom']:
            x.append(p_from[bus_indices[0]])
            x_names.append(f'Pfrom_{bus_indices[0]}')

    if 'Pto' in unknown_dict:
        for bus_indices in unknown_dict['Pto']:
            x.append(p_to[bus_indices[1]])
            x_names.append(f'Pto_{bus_indices[1]}')

    if 'Qfrom' in unknown_dict:
        for bus_indices in unknown_dict['Qfrom']:
            x.append(q_from[bus_indices[0]])
            x_names.append(f'Qfrom_{bus_indices[0]}')

    if 'Qto' in unknown_dict:
        for bus_indices in unknown_dict['Qto']:
            x.append(q_to[bus_indices[1]])
            x_names.append(f'Qto_{bus_indices[1]}')

    if 'Modulation' in unknown_dict:
        for bus_indices in unknown_dict['Modulation']:
            x.append(modulations[bus_indices[0]])
            x_names.append(f'Modulation_{bus_indices[0]}')

    if 'Tau' in unknown_dict:
        for bus_indices in unknown_dict['Tau']:
            x.append(taus[bus_indices[0]])
            x_names.append(f'Tau_{bus_indices[0]}')


    if verbose:
        print('Unknowns vector x:', x)
        print('Identifiers of x:', x_names)
        print('Length of x:', len(x))
    
    return x
                                                                                                              



def var2x_raiyan(Va: Vec,
                 Vm0: Vec, 
                 npvpq : int,
                 vsc_p_dc: Vec, 
                 vsc_p_ac: Vec, 
                 vsc_q_ac: Vec, 
                 vsc_isControlled_p_dc: Vec, 
                 vsc_isControlled_p_ac: Vec, 
                 vsc_isControlled_q_ac: Vec, 
                 vsc_isControlled_vmf: Vec, 
                 vsc_isControlled_vmt: Vec, 
                 m_vsc_connection_ac: IntVec, 
                 m_vsc_connection_dc: IntVec,
                 pv: IntVec, 
                 pq: IntVec, 
                 dc_buses: IntVec, 
                 ac_buses: IntVec, 
                 slack_buses: IntVec,
                 vmt_control_idx: IntVec,
                 vmf_control_idx: IntVec, 
                 p_ac_control_idx: IntVec, 
                 p_dc_control_idx: IntVec, 
                 q_ac_control_idx: IntVec) -> Tuple[Vec, list, list, list, list, list]:
    
    # print("Va: ", Va)
    # print("Vm0: ", Vm0)
    # print("npvpq: ", npvpq)
    # print("vsc_p_dc: ", vsc_p_dc)
    # print("vsc_p_ac: ", vsc_p_ac)
    # print("vsc_q_ac: ", vsc_q_ac)
    # print("vsc_isControlled_p_dc: ", vsc_isControlled_p_dc)
    # print("vsc_isControlled_p_ac: ", vsc_isControlled_p_ac)
    # print("vsc_isControlled_q_ac: ", vsc_isControlled_q_ac)
    # print("vsc_isControlled_vmf: ", vsc_isControlled_vmf)
    # print("vsc_isControlled_vmt: ", vsc_isControlled_vmt)
    # print("m_vsc_connection_ac: ", m_vsc_connection_ac)
    # print("m_vsc_connection_dc: ", m_vsc_connection_dc)
    # print("vmt_control_idx", vmt_control_idx)
    # print("vmf_control_idx", vmf_control_idx)
    # print("p_ac_control_idx", p_ac_control_idx)
    # print("p_dc_control_idx", p_dc_control_idx)
    # print("q_ac_control_idx", q_ac_control_idx)


    x = []

    # Voltage angles for all PV and PQ AC buses
    angles_unknown_idx = np.r_[pv, pq]
    print("Angles for PV and PQ buses:", angles_unknown_idx)
    angles_pv_pq = Va[angles_unknown_idx].tolist()
    print("Angles for PV and PQ buses:", angles_pv_pq)
    x.extend(angles_pv_pq)

    # Voltage magnitude for all PQ AC buses and all DC buses
    mags_unknown_idx = np.r_[pq, dc_buses]
    combined_list = vmt_control_idx + vmf_control_idx
    for int_to_remove in combined_list:
        #remove the value not the index
        mask = mags_unknown_idx != int_to_remove
        mags_unknown_idx = mags_unknown_idx[mask]
    mag_pq_dc = Vm0[mags_unknown_idx].tolist()
    print("Magnitudes for PQ buses and DC buses:", mag_pq_dc)
    x.extend(mag_pq_dc)

    # Initializing lists to hold indices
    p_dc_unknown_idx = []
    p_ac_unknown_idx = []
    q_ac_unknown_idx = []

    # Real power from as long as that VSC is not controlling it (P DC)
    p_dc_unknown = []
    for i in range(len(vsc_p_dc)):
        if vsc_isControlled_p_dc[i] == 0:
            p_dc_unknown.append(vsc_p_dc[i])
            p_dc_unknown_idx.append(i)
    print("Real power from for uncontrolled P DC:", p_dc_unknown)

    # Real power to as long as that VSC is not controlling it (P AC)
    p_ac_unknown = []
    for i in range(len(vsc_p_ac)):
        if vsc_isControlled_p_ac[i] == 0:
            p_ac_unknown.append(vsc_p_ac[i])
            p_ac_unknown_idx.append(i)
    print("Real power to for uncontrolled P AC:", p_ac_unknown)

    # Reactive power to as long as that VSC is not controlling it (Q AC)
    q_ac_unknown = []
    for i in range(len(vsc_q_ac)):
        if vsc_isControlled_q_ac[i] == 0:
            q_ac_unknown.append(vsc_q_ac[i])
            q_ac_unknown_idx.append(i)
    print("Reactive power to for uncontrolled Q AC:", q_ac_unknown)

    print("Indices for uncontrolled P DC:", p_dc_unknown_idx)
    print("Indices for uncontrolled P AC:", p_ac_unknown_idx)
    print("Indices for uncontrolled Q AC:", q_ac_unknown_idx)

    # Extend x with the values
    x.extend(p_dc_unknown)
    x.extend(p_ac_unknown)
    x.extend(q_ac_unknown)

    return x, angles_unknown_idx, mags_unknown_idx, p_dc_unknown_idx, p_ac_unknown_idx, q_ac_unknown_idx



def x2var_raiyan_ver2(x0, 
                      unknown_dict, 
                      Vm0, Va0, 
                      S0, I0, Y0, 
                      p_to, p_from, q_to, q_from, 
                      p_zip, q_zip, 
                      modulations, 
                      taus, 
                      verbose=1):
    """
    Arrange the unknowns vector into the physical variables
    """

    # Initialize an index for x0
    x0_index = 0
    
    # Process Voltage and Angle which are directly indexed
    if 'Voltage' in unknown_dict:
        for bus_index in unknown_dict['Voltage']:
            Vm0[bus_index] = x0[x0_index]
            x0_index += 1
    if 'Angle' in unknown_dict:
        for bus_index in unknown_dict['Angle']:
            Va0[bus_index] = x0[x0_index]
            x0_index += 1

    # Assuming similar direct indexing for Pzip, Qzip, Modulation, and Tau
    if 'Pzip' in unknown_dict:
        for bus_index in unknown_dict['Pzip']:
            p_zip[bus_index] = x0[x0_index]
            x0_index += 1
    if 'Qzip' in unknown_dict:
        for bus_index in unknown_dict['Qzip']:
            q_zip[bus_index] = x0[x0_index]
            x0_index += 1


    # Process other parameters which might involve tuple keys
    # For tuples, use the specified index for p_from/p_to and q_from/q_to
    for category, items in unknown_dict.items():
        if category in ['Pfrom', 'Pto', 'Qfrom', 'Qto', 'Modulation', 'Tau']:
            for bus_indices in items:
                if category == 'Pfrom':
                    p_from[bus_indices[0]] = x0[x0_index]
                elif category == 'Pto':
                    p_to[bus_indices[1]] = x0[x0_index]
                elif category == 'Qfrom':
                    q_from[bus_indices[0]] = x0[x0_index]
                elif category == 'Qto':
                    q_to[bus_indices[1]] = x0[x0_index]
                elif category == 'Modulation':
                    modulations[bus_indices[0]] = x0[x0_index]
                elif category == 'Tau':
                    taus[bus_indices[0]] = x0[x0_index]
                    #raise an aerror
                x0_index += 1



    if verbose:
        # Print updated values
        print("Updated Vm0: ", Vm0)
        print("Updated Va0: ", Va0)
        print("Updated p_to: ", p_to)
        print("Updated p_from: ", p_from)
        print("Updated q_to: ", q_to)
        print("Updated q_from: ", q_from)
        print("Updated p_zip: ", p_zip)
        print("Updated q_zip: ", q_zip)
        print("Updated modulations: ", modulations)
        print("Updated taus: ", taus)

    # Return the updated arrays
    return Vm0, Va0, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus


def compute_g(V, Ybus, S0, I0, Y0, Vm, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus, grid, dc_buses, ac_buses, passive_branch_dict, known_dict) -> Vec:
    """
    Compose the power flow function
    :param V:
    :param Ybus:
    :param S0:
    :param I0:
    :param Y0:
    :param Vm:
    :param pq:
    :param pvpq:
    :return:
    """
    Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)
    Scalc = cf.compute_power(Ybus, V)



    # mapping of bus-VSC and bus-trafo
    vsc_frombus = grid.get_vsc_frombus()
    vsc_tobus = grid.get_vsc_tobus()
    controllable_trafo_frombus = grid.get_controllable_trafo_frombus()
    controllable_trafo_tobus = grid.get_controllable_trafo_tobus()
    controllable_trafo_yshunt = grid.get_controllable_trafo_yshunt()
    controllable_trafo_yseries = grid.get_controllable_trafo_yseries()



    g = compute_fx_raiyan(Scalc, Sbus, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus, dc_buses, ac_buses, vsc_frombus, vsc_tobus, controllable_trafo_frombus, controllable_trafo_tobus, controllable_trafo_yshunt, controllable_trafo_yseries, V, passive_branch_dict, known_dict, Ybus)
    return g


# @nb.njit(cache=True, fastmath=True)
def compute_fx_raiyan(Scalc, Sbus, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus, dc_buses, ac_buses, vsc_frombus, vsc_tobus, controllable_trafo_frombus, controllable_trafo_tobus, controllable_trafo_yshunt, controllable_trafo_yseries, V, passive_branch_dict, known_dict, Ybus) -> Vec:
    """
    Compute the NR-like error function
    :param Scalc: Calculated power injections
    :param Sbus: Specified power injections
    :return: error
    """
    global a
    global b
    global c

    fx = []
    listOfFuncs = []

    '''
    DC bus active power balance
    '''
    for bus in dc_buses:
        fx.append(Scalc[bus].real - Sbus[bus].real + p_to[bus] + p_from[bus] - p_zip[bus])
        listOfFuncs.append("DC Real Bus:" + str(bus))

    '''
    AC bus active and reactive power balance
    '''
    for bus in ac_buses:
        fx.append(Scalc[bus].real - Sbus[bus].real + p_to[bus] + p_from[bus] - p_zip[bus])
        fx.append(Scalc[bus].imag - Sbus[bus].imag + q_to[bus] + q_from[bus] - q_zip[bus])
        listOfFuncs.append("AC Real Bus:" + str(bus))
        listOfFuncs.append("AC Imag Bus:" + str(bus))

    '''
    VSC active power balance
    '''
    Vm = np.abs(V)
    for busfrom, busTo in zip(vsc_frombus, vsc_tobus):
        _loss = (p_to[busTo]**2 + q_to[busTo]**2)**0.5 / Vm[busTo]
        fx.append(a + b * _loss + c * _loss**2 - p_to[busTo] - p_from[busfrom])
        listOfFuncs.append("VSC Active Power Balance:" + str(busfrom) + str(busTo))

    '''
    Trafo from and to bus active and reactive power balance
    '''
    for i in range(len(controllable_trafo_frombus)):
        # right what are we going to do here, we need to form four equations
        _a = Vm[controllable_trafo_frombus[i]]**2 * (np.conj(controllable_trafo_yseries[i]) + np.conj(controllable_trafo_yshunt[i])) / modulations[controllable_trafo_frombus[i]]**2
        _b = V[controllable_trafo_frombus[i]] * np.conj(V[controllable_trafo_tobus[i]]) * np.conj(controllable_trafo_yseries[i]) / (modulations[controllable_trafo_frombus[i]] * np.exp(1j * taus[controllable_trafo_frombus[i]]))
        Sfrom =  _a - _b
        _c = Vm[controllable_trafo_tobus[i]]**2 * (np.conj(controllable_trafo_yseries[i]) + np.conj(controllable_trafo_yshunt[i]))
        _d = V[controllable_trafo_tobus[i]] * np.conj(V[controllable_trafo_frombus[i]]) * np.conj(controllable_trafo_yseries[i]) / (modulations[controllable_trafo_frombus[i]] * np.exp(-1j * taus[controllable_trafo_frombus[i]]))
        Sto = _c - _d

        fx.append(Sfrom.real - p_from[controllable_trafo_frombus[i]])
        fx.append(Sto.real - p_to[controllable_trafo_tobus[i]])
        fx.append(Sfrom.imag - q_from[controllable_trafo_frombus[i]])
        fx.append(Sto.imag - q_to[controllable_trafo_tobus[i]])

        listOfFuncs.append("Trafo Active Power From:" + str(controllable_trafo_frombus[i]))
        listOfFuncs.append("Trafo Active Power From:" + str(controllable_trafo_frombus[i]))
        listOfFuncs.append("Trafo Reactive Power To:" + str(controllable_trafo_tobus[i]))	
        listOfFuncs.append("Trafo Reactive Power To:" + str(controllable_trafo_tobus[i]))

    if len(passive_branch_dict["Pfrom"]):
        for key, value in passive_branch_dict["Pfrom"].items():
            print("Passive Branch Active Power From:")
            print("Key: ", key)
            print("Value: ", value)
            from_bus = key[0]
            to_bus = key[1]
            _a = value - (V[from_bus] * (V[from_bus] - V[to_bus]) * np.conj(Ybus[from_bus, to_bus])).real
            fx.append(_a)
    
    if len(passive_branch_dict["Pto"]):
        for key, value in passive_branch_dict["Pto"].items():
            print("Passive Branch Active Power To:")
            print("Key: ", key)
            print("Value: ", value)
            from_bus = key[0]
            to_bus = key[1]
            _a = value - (V[to_bus] * (V[to_bus] - V[from_bus]) * np.conj(Ybus[to_bus, from_bus])).real
            fx.append(_a)

    if len(passive_branch_dict["Qfrom"]):
        for key, value in passive_branch_dict["Qfrom"].items():
            print("Passive Branch Reactive Power From:")
            print("Key: ", key)
            print("Value: ", value)
            from_bus = key[0]
            to_bus = key[1]
            _a = value - (V[from_bus] * (V[from_bus] - V[to_bus]) * np.conj(Ybus[from_bus, to_bus])).imag
            fx.append(_a)
    
    if len(passive_branch_dict["Qto"]):
        for key, value in passive_branch_dict["Qto"].items():
            print("Passive Branch Reactive Power To:")
            print("Key: ", key)
            print("Value: ", value)
            from_bus = key[0]
            to_bus = key[1]
            _a = value - (V[to_bus] * (V[to_bus] - V[from_bus]) * np.conj(Ybus[to_bus, from_bus])).imag
            fx.append(_a)


    # DO NOT DELETE THIS LINE: nb has does not do well with loops
    for i in range(1):
        pass

    return np.array(fx)


def compute_zip_power_wrtVm_raiyan(I0: CxVec, Y0: CxVec, Vm: Vec) -> CxVec:
    """
    Compute the derivative of the equivalent power injection
    :param Vm: voltage module
    :param Y0: Base admittance (G + jB)
    :return: complex power injection
    """
    return 2 * np.conj(Y0) * np.conj(Vm) + np.conj(I0)


def compute_zip_power_wrtVa_raiyan(I0: CxVec, Y0: CxVec, Vm: Vec) -> CxVec:
    """
    Compute the derivative of the equivalent power injection
    :param Vm: voltage module
    :param Y0: Base admittance (G + jB)
    :return: complex power injection
    """
    #make a copy of the Y0
    Szip = Y0.copy()
    #set the entire array to zero
    Szip[:] = 0
    print("Szip: ", Szip)
    return Szip

def compute_gx(x, fx, Vm, Va, Ybus, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus, grid, dc_buses, ac_buses, unknown_dict, passive_branch_dict, known_dict) -> CscMat:

    delta = 1e-6
    x1 = x.copy()
    J = np.zeros((len(x), len(x)), dtype=float)
    for i in range(len(x)):


        '''
        Make a deepcopy and alter the ith element
        '''
        x1 = np.array(x.copy())
        Va_after = np.array(Va.copy())
        Vm_after = np.array(Vm.copy())
        p_to_after = np.array(p_to.copy())
        p_from_after = np.array(p_from.copy())
        q_to_after = np.array(q_to.copy())
        q_from_after = np.array(q_from.copy())
        p_zip_after = np.array(p_zip.copy())
        q_zip_after = np.array(q_zip.copy())
        modulations_after = np.array(modulations.copy())
        taus_after = np.array(taus.copy())
        x1[i] += delta

        '''
        Put the unknowns back into their vectors
        '''
        Vm_after, Va_after, S0, I0, Y0, p_to_after, p_from_after, q_to_after, q_from_after, p_zip_after, q_zip_after, modulations_after, taus_after = x2var_raiyan_ver2(x1, unknown_dict, Vm_after, Va_after, S0, I0, Y0, p_to_after, p_from_after, q_to_after, q_from_after, p_zip_after, q_zip_after, modulations_after, taus_after, verbose = 0)
        
        '''
        Calculate powers
        '''
        V = Vm_after * np.exp(1j * Va_after)
        Sbus = cf.compute_zip_power(S0, I0, Y0, Vm)
        Scalc = cf.compute_power(Ybus, V)


        '''
        Get the difference in the vectors and append to J
        '''
        #move this outside maybe? get mapping between bus-vsc and bus-trafo
        vsc_frombus = grid.get_vsc_frombus()
        vsc_tobus = grid.get_vsc_tobus()
        controllable_trafo_frombus = grid.get_controllable_trafo_frombus()
        controllable_trafo_tobus = grid.get_controllable_trafo_tobus()
        controllable_trafo_yshunt = grid.get_controllable_trafo_yshunt()
        controllable_trafo_yseries = grid.get_controllable_trafo_yseries()

        fx_altered = compute_fx_raiyan(Scalc, Sbus, p_to_after, p_from_after, q_to_after, q_from_after, p_zip_after, q_zip_after, modulations_after, taus_after, dc_buses, ac_buses, vsc_frombus, vsc_tobus, controllable_trafo_frombus, controllable_trafo_tobus, controllable_trafo_yshunt, controllable_trafo_yseries, V, passive_branch_dict, known_dict, Ybus)
        diff = (fx_altered - fx) / delta
        J[:, i] = diff


    #make a df of J
    # import pandas as pd
    # df = pd.DataFrame(J)
    # listOfFuncs =  ['DC Real Bus:3', 'DC Real Bus:4', 'DC Real Bus:5', 'AC Real Bus:0', 'AC Imag Bus:0', 'AC Real Bus:1', 'AC Imag Bus:1', 'AC Real Bus:2', 'AC Imag Bus:2', 'AC Real Bus:6', 'AC Imag Bus:6', 'AC Real Bus:7', 'AC Imag Bus:7', 'AC Real Bus:8', 'AC Imag Bus:8', 'AC Real Bus:9', 'AC Imag Bus:9', 'VSC Active Power Balance:32', 'VSC Active Power Balance:56', 'Trafo Active Power From:8', 'Trafo Active Power From:8', 'Trafo Reactive Power To:9', 'Trafo Reactive Power To:9']
    # df.index = listOfFuncs
    # df.columns = ['V_1', 'V_2', 'V_4', 'V_5', 'V_7', 'V_8', 'Angle_1', 'Angle_2', 'Angle_6', 'Angle_7', 'Angle_8', 'Pzip_0', 'Pzip_9', 'Qzip_0', 'Qzip_9', 'Pfrom_3', 'Pfrom_5', 'Pfrom_8', 'Pto_2', 'Pto_6', 'Qfrom_8', 'Qto_9', 'Mod_8']

    return csr_matrix((J), shape=(len(x), len(x))).tocsc()


def pf_function_raiyan(x: Vec,
                compute_jac: bool,
                # these are the args:
                unknown_dict: dict,
                passive_branch_dict: dict,
                known_dict: dict,
                Vm0: Vec, 
                Va0: Vec, 
                S0: CxVec, 
                I0: CxVec, 
                Y0: CxVec, 
                p_to: Vec, 
                p_from: Vec, 
                q_to: Vec, 
                q_from: Vec, 
                p_zip: Vec, 
                q_zip: Vec, 
                modulations: Vec, 
                taus: Vec, 
                Ybus: CscMat, 
                grid: MultiCircuitRaiyan, 
                dc_buses: IntVec, 
                ac_buses) -> ConvexFunctionResult:

    Va = Va0.copy()
    Vm = Vm0.copy()
    Vm, Va, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus = x2var_raiyan_ver2(x, unknown_dict, Vm0, Va0, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus, verbose = 0)
    V = Vm * np.exp(1j * Va)

    g = compute_g(V, Ybus, S0, I0, Y0, Vm, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus, grid, dc_buses, ac_buses, passive_branch_dict, known_dict)

    if compute_jac:
        Gx = compute_gx(x, g, Vm, Va, Ybus, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus, grid, dc_buses, ac_buses, unknown_dict, passive_branch_dict, known_dict)
    else:
        Gx = None

    return ConvexFunctionResult(f=g, J=Gx)



def isolate_AC_DC(grid, Ybus) -> csc_matrix:
    """
    Isolates the AC and DC components of a power grid within its admittance matrix.

    This function modifies the admittance matrix (Ybus) of a power grid to isolate the contributions of DC lines. It zeroes out the admittance values directly associated with DC lines and adjusts the matrix to account for the DC lines' resistances as conductances. This operation helps in analyzing the AC network components separately from DC elements.

    Parameters
    ----------
    grid : Grid object
        An object representing the power grid, which includes AC and DC buses and lines.
    Ybus : csc_matrix
        The original sparse column-compressed admittance matrix of the grid.

    Returns
    -------
    csc_matrix
        The modified admittance matrix with the AC and DC components isolated.

    """
    _matrix = Ybus.copy()
    n = _matrix.shape[0]  # Assuming Ybus is square

    #iterate through and first delete anything that has to do with the dc_lines
    for elm in grid.dc_lines:
        # Get indices for the buses
        from_idx = grid.buses.index(elm.bus_from)
        to_idx = grid.buses.index(elm.bus_to)
      
        _matrix[from_idx, to_idx] = 0
        _matrix[to_idx, from_idx] = 0
        
        _matrix[from_idx, from_idx] = 0
        _matrix[to_idx, to_idx] = 0


    for elm in grid.dc_lines:
        # Get indices for the buses
        from_idx = grid.buses.index(elm.bus_from)
        to_idx = grid.buses.index(elm.bus_to)

        # print("from_idx: ", from_idx)
        # print("to_idx: ", to_idx)
        # print("R", elm.R)
        
        # Convert resistance to conductance?
        G = 1 / elm.R
        # G = elm.R
        
        # Subtract conductance from off-diagonal elements
        _matrix[from_idx, to_idx] -= G
        _matrix[to_idx, from_idx] -= G
        
        # Add conductance to diagonal elements
        _matrix[from_idx, from_idx] += G
        _matrix[to_idx, to_idx] += G
    
    # print("altered Ybus: ", _matrix.copy().todense())

    return _matrix

def run_pf_ver2(grid: gce.MultiCircuit, pf_options: gce.PowerFlowOptions, debug = 1):
    nc = gce.compile_numerical_circuit_at(grid, t_idx=None)
    Ybus = nc.Ybus
    S0 = nc.Sbus
    I0 = nc.Ibus
    Y0 = nc.YLoadBus
    Vm0 = np.abs(nc.Vbus)
    Va0 = np.angle(nc.Vbus)

    '''
    Perform control checks, obtain known and unknown indices
    '''
    ControlRaiyan.get_numberOfEquations(grid, verbose = 1)
    known_dict, unknown_dict, passive_branch_dict = ControlRaiyan.findingIndices(grid, output_mode = 1, verbose = 1)
    ControlRaiyan.ruleAssertion(grid, verbose = 1, strict = 0)

    print("Known dict: ", known_dict)	
    print("Unknown dict: ", unknown_dict)
    print("Passive branch dict: ", passive_branch_dict)


    '''
    Return bus types
    '''
    dc_buses, ac_buses, slack_buses = HelperFunctions.bus_types(grid)
    print("DC buses: ", dc_buses)
    print("AC buses: ", ac_buses)


    '''
    Split the AC and DC subsystems
    '''
    Ybus = isolate_AC_DC(grid, Ybus)


    '''
    Initialising from and to powers, and tau and modulation
    '''
    p_from = np.zeros(len(grid.buses))
    p_to = np.zeros(len(grid.buses))
    q_from = np.zeros(len(grid.buses))
    q_to = np.zeros(len(grid.buses))
    p_zip = np.zeros(len(grid.buses))
    q_zip = np.zeros(len(grid.buses))
    modulations = np.ones(len(grid.buses))
    taus = np.zeros(len(grid.buses))


    '''
    Using known values, update setpoints
    '''
    Vm0, Va0, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus  = update_setpoints(known_dict, grid, Vm0, Va0, S0, I0, Y0, p_from, p_to, q_from, q_to, p_zip, q_zip, modulations, taus, verbose = 0)


    '''
    Create unknowns vector
    '''
    x0 = var2x_raiyan_ver2(unknown_dict, Vm0, Va0, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus, verbose = 1)


    logger = gce.Logger()


    if pf_options.solver_type == SolverType.NR:
        ret: ConvexMethodResult = newton_raphson(func=pf_function_raiyan,
                                                 func_args=(unknown_dict, passive_branch_dict, known_dict, Vm0, Va0, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus, Ybus, grid, dc_buses, ac_buses),
                                                 x0=x0,
                                                 tol=pf_options.tolerance,
                                                 max_iter=pf_options.max_iter,
                                                 trust=pf_options.trust_radius,
                                                 verbose=pf_options.verbose,
                                                 logger=logger)

    Vm0, Va0, S0, I0, Y0, p_to, p_from, q_to, q_from, p_zip, q_zip, modulations, taus  = update_setpoints(known_dict, grid, Vm0, Va0, S0, I0, Y0, p_from, p_to, q_from, q_to, p_zip, q_zip, modulations, taus, verbose = 0)



if __name__ == '__main__':
    import os
    # grid_ = HelperFunctions.linn5bus_example()    #converges true, and same as traditional powerflow
    # grid_ = HelperFunctions.linn5bus_example2()   #converges true
    # grid_ = HelperFunctions.ieee14_example()      #converges true, and same as traditional powerflow
    # grid_ = HelperFunctions.pure_dc_3bus()        #converges true
    # grid_ = HelperFunctions.pure_ac_2bus()        #converges true
    # grid_ = HelperFunctions.pure_ac_3bus_trafo()  #converges true, your trafo is not broken maybe?
    # grid_ = HelperFunctions.acdc_5bus()           #converges true 
    grid_ = HelperFunctions.acdc_10bus()          #converges true, you must be very careful when you are settings powers

    # grid_ = HelperFunctions.acdc_10bus_branchcontrol() #converges true, but not every remote branch control will converge so

    
    pf_options_ = gce.PowerFlowOptions(solver_type=gce.SolverType.NR,
                                       max_iter=10,
                                       trust_radius=5.0,
                                       tolerance=1e-10,
                                       verbose=1)
    run_pf_ver2(grid=grid_, pf_options=pf_options_, debug = 1)