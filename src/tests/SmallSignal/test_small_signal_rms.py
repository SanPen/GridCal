# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import os
import numpy as np
import scipy.sparse as sp

from VeraGridEngine.enumerations import VarPowerFlowReferenceType, DynamicIntegrationMethod, RmsInitializationMethod
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Branches.line import Line

from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template

from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.genrow1_rms_template import get_genrow1_rms_template
from VeraGridEngine.Templates.Rms.genrow2_rms_template import get_genrow2_rms_template
from VeraGridEngine.Templates.Rms.genrow3_rms_template import get_genrow3_rms_template
from VeraGridEngine.Templates.Rms.genrow4_rms_template import get_genrow4_rms_template
from VeraGridEngine.Utils.Symbolic import Block
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms

from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_driver import SmallSignalStabilityRmsDriver
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_options import RmsSmallSignalStabilityOptions
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions

from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver

import VeraGridEngine.api as gce
import time


def stability_kundur_no_shunt():
    t_start_total = time.perf_counter()
    ###########################################################################################################################
    # Build VeraGrid object
    ###########################################################################################################################

    grid = gce.MultiCircuit(fbase=60.0)

    # Buses
    bus1 = Bus(name="Bus1", Vnom=20)
    bus2 = Bus(name="Bus2", Vnom=20)
    bus3 = Bus(name="Bus3", Vnom=20, is_slack=True)
    bus4 = Bus(name="Bus4", Vnom=20)
    bus5 = Bus(name="Bus5", Vnom=230)
    bus6 = Bus(name="Bus6", Vnom=230)
    bus7 = Bus(name="Bus7", Vnom=230)
    bus8 = Bus(name="Bus8", Vnom=230)
    bus9 = Bus(name="Bus9", Vnom=230)
    bus10 = Bus(name="Bus10", Vnom=230)
    bus11 = Bus(name="Bus11", Vnom=230)

    grid.add_bus(bus1)
    grid.add_bus(bus2)
    grid.add_bus(bus3)
    grid.add_bus(bus4)
    grid.add_bus(bus5)
    grid.add_bus(bus6)
    grid.add_bus(bus7)
    grid.add_bus(bus8)
    grid.add_bus(bus9)
    grid.add_bus(bus10)
    grid.add_bus(bus11)

    for bus in grid.buses:
        initialize_bus_rms(bus, vf=grid.var_factory)

    # Line

    line0 = gce.Line(name="line 5-6-1", bus_from=bus5, bus_to=bus6,
                     r=0.00500, x=0.05000, b=0.02187, rate=750.0)

    line1 = gce.Line(name="line 5-6-2", bus_from=bus5, bus_to=bus6,
                     r=0.00500, x=0.05000, b=0.02187, rate=750.0)

    line2 = gce.Line(name="line 6-7-1", bus_from=bus6, bus_to=bus7,
                     r=0.00300, x=0.03000, b=0.00583, rate=700.0)

    line3 = gce.Line(name="line 6-7-2", bus_from=bus6, bus_to=bus7,
                     r=0.00300, x=0.03000, b=0.00583, rate=700.0)

    line4 = gce.Line(name="line 6-7-3", bus_from=bus6, bus_to=bus7,
                     r=0.00300, x=0.03000, b=0.00583, rate=700.0)

    line5 = gce.Line(name="line 7-8-1", bus_from=bus7, bus_to=bus8,
                     r=0.01100, x=0.11000, b=0.19250, rate=400.0)

    line6 = gce.Line(name="line 7-8-2", bus_from=bus7, bus_to=bus8,
                     r=0.01100, x=0.11000, b=0.19250, rate=400.0)

    line7 = gce.Line(name="line 8-9-1", bus_from=bus8, bus_to=bus9,
                     r=0.01100, x=0.11000, b=0.19250, rate=400.0)

    line8 = gce.Line(name="line 8-9-2", bus_from=bus8, bus_to=bus9,
                     r=0.01100, x=0.11000, b=0.19250, rate=400.0)

    line9 = gce.Line(name="line 9-10-1", bus_from=bus9, bus_to=bus10,
                     r=0.00300, x=0.03000, b=0.00583, rate=700.0)

    line10 = gce.Line(name="line 9-10-2", bus_from=bus9, bus_to=bus10,
                      r=0.00300, x=0.03000, b=0.00583, rate=700.0)

    line11 = gce.Line(name="line 9-10-3", bus_from=bus9, bus_to=bus10,
                      r=0.00300, x=0.03000, b=0.00583, rate=700.0)

    line12 = gce.Line(name="line 10-11-1", bus_from=bus10, bus_to=bus11,
                      r=0.00500, x=0.05000, b=0.02187, rate=750.0)

    line13 = gce.Line(name="line 10-11-2", bus_from=bus10, bus_to=bus11,
                      r=0.00500, x=0.05000, b=0.02187, rate=750.0)

    # Transformers
    xt1 = 0.15 * (100.0 / 900.0)
    trafo_G1 = Line(name="trafo 5-1", bus_from=bus5, bus_to=bus1,
                    r=0.00000, x=0.15 * (100.0 / 900.0), b=0.0, rate=900.0)

    trafo_G2 = gce.Line(name="trafo 6-2", bus_from=bus6, bus_to=bus2,
                        r=0.00000, x=0.15 * (100.0 / 900.0), b=0.0, rate=900.0)

    trafo_G3 = gce.Line(name="trafo 11-3", bus_from=bus11, bus_to=bus3,
                        r=0.00000, x=0.15 * (100.0 / 900.0), b=0.0, rate=900.0)

    trafo_G4 = gce.Line(name="trafo 10-4", bus_from=bus10, bus_to=bus4,
                        r=0.00000, x=0.15 * (100.0 / 900.0), b=0.0, rate=900.0)

    # load
    load1 = gce.Load(name="load1", P=967.0, Q=100.0)

    load2 = gce.Load(name="load2", P=1767.0, Q=100.0)

    # Generators
    fn_1 = 60.0
    M_1 = 13.0 * 9.0
    D_1 = 10.0 * 9.0
    ra_1 = 0.0
    xd_1 = 0.3 * 100.0 / 900.0
    omega_ref_1 = 1.0
    Kp_1 = 0.0
    Ki_1 = 0.0

    fn_2 = 60.0
    M_2 = 13.0 * 9.0
    D_2 = 10.0 * 9.0
    ra_2 = 0.0
    xd_2 = 0.3 * 100.0 / 900.0
    omega_ref_2 = 1.0
    Kp_2 = 0.0
    Ki_2 = 0.0

    fn_3 = 60.0
    M_3 = 12.35 * 9.0
    D_3 = 10.0 * 9.0
    ra_3 = 0.0
    xd_3 = 0.3 * 100.0 / 900.0
    omega_ref_3 = 1.0
    Kp_3 = 0.0
    Ki_3 = 0.0

    fn_4 = 60.0
    M_4 = 12.35 * 9.0
    D_4 = 10.0 * 9.0
    ra_4 = 0.0
    xd_4 = 0.3 * 100.0 / 900.0
    omega_ref_4 = 1.0
    Kp_4 = 0.0
    Ki_4 = 0.0

    # Generators
    gen1 = Generator(
        name="Gen1", P=700.0, vset=1.03, Snom=900.0,
        x1=xd_1, r1=ra_1, freq=fn_1,
    )

    gen2 = Generator(
        name="Gen2", P=700.0, vset=1.01, Snom=900.0,
        x1=xd_2, r1=ra_2, freq=fn_2,
    )

    gen3 = Generator(
        name="Gen3", P=719.091, vset=1.03, Snom=900.0,
        x1=xd_3, r1=ra_3, freq=fn_3,
    )

    gen4 = Generator(
        name="Gen4", P=700.0, vset=1.01, Snom=900.0,
        x1=xd_4, r1=ra_4, freq=fn_4,
    )

    ######################################################################################################
    # Build Rms models
    ######################################################################################################

    # Build rms models from template
    # generators
    genrow_mdl1 = get_genrow1_rms_template(grid.var_factory).block
    genrow_mdl2 = get_genrow2_rms_template(grid.var_factory).block
    genrow_mdl3 = get_genrow3_rms_template(grid.var_factory).block
    genrow_mdl4 = get_genrow4_rms_template(grid.var_factory).block

    # lines
    line0_mdl = get_line_rms_template(grid.var_factory).block
    line1_mdl = get_line_rms_template(grid.var_factory).block
    line2_mdl = get_line_rms_template(grid.var_factory).block
    line3_mdl = get_line_rms_template(grid.var_factory).block
    line4_mdl = get_line_rms_template(grid.var_factory).block
    line5_mdl = get_line_rms_template(grid.var_factory).block
    line6_mdl = get_line_rms_template(grid.var_factory).block
    line7_mdl = get_line_rms_template(grid.var_factory).block
    line8_mdl = get_line_rms_template(grid.var_factory).block
    line9_mdl = get_line_rms_template(grid.var_factory).block
    line10_mdl = get_line_rms_template(grid.var_factory).block
    line11_mdl = get_line_rms_template(grid.var_factory).block
    line12_mdl = get_line_rms_template(grid.var_factory).block
    line13_mdl = get_line_rms_template(grid.var_factory).block

    # trafos
    trafo1_mdl = get_line_rms_template(grid.var_factory).block
    trafo2_mdl = get_line_rms_template(grid.var_factory).block
    trafo3_mdl = get_line_rms_template(grid.var_factory).block
    trafo4_mdl = get_line_rms_template(grid.var_factory).block

    # loads
    load1_mdl = get_load_rms_template(grid.var_factory).block
    load2_mdl = get_load_rms_template(grid.var_factory).block

    # set models parameters
    load1_mdl.set_parameter_in_model(var_name="Pl0", new_value=-9.670000000007317)
    load1_mdl.set_parameter_in_model(var_name="Ql0", new_value=-0.9999999999967969)

    load2_mdl.set_parameter_in_model(var_name="Pl0", new_value=-17.6699999999199)
    load2_mdl.set_parameter_in_model(var_name="Ql0", new_value=-0.999999999989467)

    # connection with buses

    grid.var_factory.add_connections([genrow_mdl1.in_vars[0]], [bus1.rms_model.out_vars[0]])
    grid.var_factory.add_connections([genrow_mdl1.in_vars[1]], [bus1.rms_model.out_vars[1]])

    grid.var_factory.add_connections([genrow_mdl2.in_vars[0]], [bus2.rms_model.out_vars[0]])
    grid.var_factory.add_connections([genrow_mdl2.in_vars[1]], [bus2.rms_model.out_vars[1]])

    grid.var_factory.add_connections([genrow_mdl3.in_vars[0]], [bus3.rms_model.out_vars[0]])
    grid.var_factory.add_connections([genrow_mdl3.in_vars[1]], [bus3.rms_model.out_vars[1]])

    grid.var_factory.add_connections([genrow_mdl4.in_vars[0]], [bus4.rms_model.out_vars[0]])
    grid.var_factory.add_connections([genrow_mdl4.in_vars[1]], [bus4.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line0_mdl.in_vars[0]], [bus5.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line0_mdl.in_vars[1]], [bus5.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line0_mdl.in_vars[2]], [bus6.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line0_mdl.in_vars[3]], [bus6.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line1_mdl.in_vars[0]], [bus5.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line1_mdl.in_vars[1]], [bus5.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line1_mdl.in_vars[2]], [bus6.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line1_mdl.in_vars[3]], [bus6.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line2_mdl.in_vars[0]], [bus6.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line2_mdl.in_vars[1]], [bus6.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line2_mdl.in_vars[2]], [bus7.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line2_mdl.in_vars[3]], [bus7.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line3_mdl.in_vars[0]], [bus6.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line3_mdl.in_vars[1]], [bus6.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line3_mdl.in_vars[2]], [bus7.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line3_mdl.in_vars[3]], [bus7.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line4_mdl.in_vars[0]], [bus6.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line4_mdl.in_vars[1]], [bus6.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line4_mdl.in_vars[2]], [bus7.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line4_mdl.in_vars[3]], [bus7.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line5_mdl.in_vars[0]], [bus7.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line5_mdl.in_vars[1]], [bus7.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line5_mdl.in_vars[2]], [bus8.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line5_mdl.in_vars[3]], [bus8.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line6_mdl.in_vars[0]], [bus7.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line6_mdl.in_vars[1]], [bus7.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line6_mdl.in_vars[2]], [bus8.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line6_mdl.in_vars[3]], [bus8.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line7_mdl.in_vars[0]], [bus8.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line7_mdl.in_vars[1]], [bus8.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line7_mdl.in_vars[2]], [bus9.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line7_mdl.in_vars[3]], [bus9.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line8_mdl.in_vars[0]], [bus8.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line8_mdl.in_vars[1]], [bus8.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line8_mdl.in_vars[2]], [bus9.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line8_mdl.in_vars[3]], [bus9.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line9_mdl.in_vars[0]], [bus9.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line9_mdl.in_vars[1]], [bus9.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line9_mdl.in_vars[2]], [bus10.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line9_mdl.in_vars[3]], [bus10.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line10_mdl.in_vars[0]], [bus9.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line10_mdl.in_vars[1]], [bus9.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line10_mdl.in_vars[2]], [bus10.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line10_mdl.in_vars[3]], [bus10.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line11_mdl.in_vars[0]], [bus9.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line11_mdl.in_vars[1]], [bus9.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line11_mdl.in_vars[2]], [bus10.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line11_mdl.in_vars[3]], [bus10.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line12_mdl.in_vars[0]], [bus10.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line12_mdl.in_vars[1]], [bus10.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line12_mdl.in_vars[2]], [bus11.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line12_mdl.in_vars[3]], [bus11.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line13_mdl.in_vars[0]], [bus10.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line13_mdl.in_vars[1]], [bus10.rms_model.out_vars[1]])

    grid.var_factory.add_connections([line13_mdl.in_vars[2]], [bus11.rms_model.out_vars[0]])
    grid.var_factory.add_connections([line13_mdl.in_vars[3]], [bus11.rms_model.out_vars[1]])

    grid.var_factory.add_connections([trafo1_mdl.in_vars[0]], [bus5.rms_model.out_vars[0]])
    grid.var_factory.add_connections([trafo1_mdl.in_vars[1]], [bus5.rms_model.out_vars[1]])

    grid.var_factory.add_connections([trafo1_mdl.in_vars[2]], [bus1.rms_model.out_vars[0]])
    grid.var_factory.add_connections([trafo1_mdl.in_vars[3]], [bus1.rms_model.out_vars[1]])

    grid.var_factory.add_connections([trafo2_mdl.in_vars[0]], [bus6.rms_model.out_vars[0]])
    grid.var_factory.add_connections([trafo2_mdl.in_vars[1]], [bus6.rms_model.out_vars[1]])

    grid.var_factory.add_connections([trafo2_mdl.in_vars[2]], [bus2.rms_model.out_vars[0]])
    grid.var_factory.add_connections([trafo2_mdl.in_vars[3]], [bus2.rms_model.out_vars[1]])

    grid.var_factory.add_connections([trafo3_mdl.in_vars[0]], [bus11.rms_model.out_vars[0]])
    grid.var_factory.add_connections([trafo3_mdl.in_vars[1]], [bus11.rms_model.out_vars[1]])

    grid.var_factory.add_connections([trafo3_mdl.in_vars[2]], [bus3.rms_model.out_vars[0]])
    grid.var_factory.add_connections([trafo3_mdl.in_vars[3]], [bus3.rms_model.out_vars[1]])

    grid.var_factory.add_connections([trafo4_mdl.in_vars[0]], [bus10.rms_model.out_vars[0]])
    grid.var_factory.add_connections([trafo4_mdl.in_vars[1]], [bus10.rms_model.out_vars[1]])

    grid.var_factory.add_connections([trafo4_mdl.in_vars[2]], [bus4.rms_model.out_vars[0]])
    grid.var_factory.add_connections([trafo4_mdl.in_vars[3]], [bus4.rms_model.out_vars[1]])

    grid.var_factory.add_connections([load1_mdl.in_vars[0]], [bus7.rms_model.out_vars[0]])
    grid.var_factory.add_connections([load1_mdl.in_vars[1]], [bus7.rms_model.out_vars[1]])

    grid.var_factory.add_connections([load2_mdl.in_vars[0]], [bus9.rms_model.out_vars[0]])
    grid.var_factory.add_connections([load2_mdl.in_vars[1]], [bus9.rms_model.out_vars[1]])

    # external mapping

    big_gen1 = Block(children=[genrow_mdl1])
    big_gen2 = Block(children=[genrow_mdl2])
    big_gen3 = Block(children=[genrow_mdl3])
    big_gen4 = Block(children=[genrow_mdl4])

    big_gen1.external_mapping.update({VarPowerFlowReferenceType.P: genrow_mdl1.out_vars[0]})
    big_gen1.external_mapping.update({VarPowerFlowReferenceType.Q: genrow_mdl1.out_vars[1]})

    big_gen2.external_mapping.update({VarPowerFlowReferenceType.P: genrow_mdl2.out_vars[0]})
    big_gen2.external_mapping.update({VarPowerFlowReferenceType.Q: genrow_mdl2.out_vars[1]})

    big_gen3.external_mapping.update({VarPowerFlowReferenceType.P: genrow_mdl3.out_vars[0]})
    big_gen3.external_mapping.update({VarPowerFlowReferenceType.Q: genrow_mdl3.out_vars[1]})

    big_gen4.external_mapping.update({VarPowerFlowReferenceType.P: genrow_mdl4.out_vars[0]})
    big_gen4.external_mapping.update({VarPowerFlowReferenceType.Q: genrow_mdl4.out_vars[1]})

    # add models to opi objects

    gen1.rms_model = big_gen1
    gen2.rms_model = big_gen2
    gen3.rms_model = big_gen3
    gen4.rms_model = big_gen4

    line0.rms_model = line0_mdl
    line1.rms_model = line1_mdl
    line2.rms_model = line2_mdl
    line3.rms_model = line3_mdl
    line4.rms_model = line4_mdl
    line5.rms_model = line5_mdl
    line6.rms_model = line6_mdl
    line7.rms_model = line7_mdl
    line8.rms_model = line8_mdl
    line9.rms_model = line9_mdl
    line10.rms_model = line10_mdl
    line11.rms_model = line11_mdl
    line12.rms_model = line12_mdl
    line13.rms_model = line13_mdl

    trafo_G1.rms_model = trafo1_mdl
    trafo_G2.rms_model = trafo2_mdl
    trafo_G3.rms_model = trafo3_mdl
    trafo_G4.rms_model = trafo4_mdl

    load1.rms_model = load1_mdl
    load2.rms_model = load2_mdl


    grid.add_line(line0)
    grid.add_line(line1)
    grid.add_line(line2)
    grid.add_line(line3)
    grid.add_line(line4)
    grid.add_line(line5)
    grid.add_line(line6)
    grid.add_line(line7)
    grid.add_line(line8)
    grid.add_line(line9)
    grid.add_line(line10)
    grid.add_line(line11)
    grid.add_line(line12)
    grid.add_line(line13)

    grid.add_line(trafo_G1)
    grid.add_line(trafo_G2)
    grid.add_line(trafo_G3)
    grid.add_line(trafo_G4)

    grid.add_load(bus=bus7, api_obj=load1)
    grid.add_load(bus=bus9, api_obj=load2)

    grid.add_generator(bus=bus1, api_obj=gen1)
    grid.add_generator(bus=bus2, api_obj=gen2)
    grid.add_generator(bus=bus3, api_obj=gen3)
    grid.add_generator(bus=bus4, api_obj=gen4)

    os.makedirs(os.path.join("data", "output"), exist_ok=True)
    gce.save_file(grid, os.path.join("data", "output", "kundur.veragrid"))

    t_end_setup = time.perf_counter()

    ###########################################################################################################################
    # Power Flow Execution
    ###########################################################################################################################

    t_start_pf = time.perf_counter()

    pf_options = PowerFlowOptions(
        solver_type=gce.SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1e-6,
        max_iter=25,
        control_q=False,
        control_taps_modules=True,
        control_taps_phase=True,
        control_remote_voltage=True,
        orthogonalize_controls=True,
        apply_temperature_correction=True,
        branch_impedance_tolerance_mode=gce.BranchImpedanceMode.Specified,
        distributed_slack=False,
        ignore_single_node_islands=False,
        trust_radius=1.0,
        backtracking_parameter=0.05,
        use_stored_guess=False,
        initialize_angles=False,
        generate_report=False,
    )
    power_flow = PowerFlowDriver(grid, pf_options)
    power_flow.run()
    res = power_flow.results

    t_end_pf = time.perf_counter()

    ###########################################################################################################################
    # RMS Problem Compilation and SSS Driver Execution
    ###########################################################################################################################

    rms_options = RmsOptions(time_step=0.001,
                             simulation_time=10,
                             tolerance=1e-6,
                             integration_method=DynamicIntegrationMethod.DaeBackEuler,
                             initialization_method=RmsInitializationMethod.Explicit,
                             use_init_values=False,
                             max_iter=1000,
                             verbose=0)

    ss_options = RmsSmallSignalStabilityOptions(ss_assessment_time=0)

    t_start_problem = time.perf_counter()
    t_end_problem = time.perf_counter()

    t_start_sss = time.perf_counter()
    small_signal_driver = SmallSignalStabilityRmsDriver(grid=grid,
                                                        rms_options=rms_options,
                                                        sss_options=ss_options,
                                                        pf_results=power_flow.results)

    assert small_signal_driver.problem.logger is small_signal_driver.logger
    initial_point: np.ndarray = small_signal_driver.problem.get_x0()
    initial_derivatives: np.ndarray = np.zeros_like(initial_point)
    static_state_matrix: sp.csc_matrix = small_signal_driver.problem.get_static_state_matrix(
        x=initial_point,
        dx=initial_derivatives,
    )
    assert sp.isspmatrix_csc(static_state_matrix)

    small_signal_driver.run()
    t_end_sss = time.perf_counter()

    eigenvalues = small_signal_driver.results.eigenvalues
    PFactors = small_signal_driver.results.participation_factors

    print(f"\n--- PROFILING SUMMARY ---")
    print(f"Grid Setup Time:           {t_end_setup - t_start_total:.4f} s")
    print(f"Power Flow Time:           {t_end_pf - t_start_pf:.4f} s")
    print(f"RMS Problem Setup/Compile: {t_end_problem - t_start_problem:.4f} s")
    print(f"SSS Solver Execution:      {t_end_sss - t_start_sss:.4f} s")
    print(f"Total Time:                {t_end_sss - t_start_total:.4f} s")
    print("-------------------------\n")

    return eigenvalues, PFactors


def test_eigenvalues():
    eig_Andes = np.array([-0.3937577370228531 + 7.237668249952536j, -0.3937577370228531 - 7.237668249952536j,
                          -0.39578162845152476 + 7.10610769053952j, -0.39578162845152476 - 7.10610769053952j,
                          -0.393088827518491 + 2.7838009459248343j, -0.393088827518491 - 2.7838009459248343j,
                          -0.7926383508563992 + 0j, 2.8393441106828003e-14 + 0j])

    eig_VeraGrid, pfactors_VeraGrid = stability_kundur_no_shunt()
    eig_VeraGrid_ord = eig_VeraGrid[np.argsort(-np.abs(eig_VeraGrid), kind="stable")]

    equal = False
    if len(eig_Andes) == len(eig_VeraGrid_ord):
        equal = np.allclose(eig_Andes, eig_VeraGrid_ord, atol=1e-3)

    assert equal


def test_participation_factors():
    pfactors_Andes = np.array([[0.1228500000, 0.1228500000, 0.1021600000, 0.1021600000, 0.1731400000, 0.1731400000,
                                0.1942900000, 0.0058800000],
                               [0.1513000000, 0.1513000000, 0.1220100000, 0.1220100000, 0.1164300000, 0.1164300000,
                                0.2107700000, 0.0063900000],
                               [0.1027000000, 0.1027000000, 0.1565200000, 0.1565200000, 0.1016100000, 0.1016100000,
                                0.2798000000, 0.0059200000],
                               [0.1231400000, 0.1231400000, 0.1193200000, 0.1193200000, 0.1072800000, 0.1072800000,
                                0.3021900000, 0.0064000000],
                               [0.1232400000, 0.1232400000, 0.1024900000, 0.1024900000, 0.1738200000, 0.1738200000,
                                0.0000000000, 0.1997800000],
                               [0.1517800000, 0.1517800000, 0.1224000000, 0.1224000000, 0.1168900000, 0.1168900000,
                                0.0000000000, 0.2169300000],
                               [0.1040300000, 0.1040300000, 0.1585600000, 0.1585600000, 0.1028200000, 0.1028200000,
                                0.0000000000, 0.2784500000],
                               [0.1217000000, 0.1217000000, 0.1179300000, 0.1179300000, 0.1059200000, 0.1059200000,
                                0.0000000000, 0.2934000000]])
    eig_VeraGrid, pfactors_VeraGrid = stability_kundur_no_shunt()

    order_rows = [0, 2, 4, 6, 1, 3, 5, 7]
    pfactors_VeraGrid_ord = pfactors_VeraGrid[order_rows, :]

    equal = False
    if pfactors_Andes.shape == pfactors_VeraGrid_ord.shape:
        equal = np.allclose(pfactors_Andes, pfactors_VeraGrid_ord, atol=1e-2)

    assert equal


if __name__ == '__main__':
    test_eigenvalues()
    test_participation_factors()
