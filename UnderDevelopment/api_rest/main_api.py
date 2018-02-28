"""
This is the API-REST server that allows to access the multi circuit object
"""
from uuid import uuid4

from flask import Flask, jsonify, request

from apscheduler.schedulers.background import BackgroundScheduler

from GridCal.Engine.CalculationEngine import *

PORT = 5000


# Instantiate our Node
app = Flask(__name__)

# Generate a globally unique address for this node
node_identifier = str(uuid4()).replace('-', '')

# Instantiate the multi-circuit
grid = MultiCircuit()

fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE_14.xlsx'
# fname = '/Data/Doctorado/spv_phd/GridCal_project/GridCal/IEEE_39Bus(Islands).xls'
grid.load_file(fname)
grid.compile()

options = PowerFlowOptions(SolverType.NR, verbose=False, robust=False, initialize_with_existing_solution=False)
power_flow = PowerFlow(grid, options)


def run_pf():
    print('I am working...')
    power_flow.run()

    # for c in grid.circuits:
    #     print(c.name)
    #     # print(pd.DataFrame(circuit.power_flow_input.Ybus.todense()))
    #     # print('\tV:', c.power_flow_results.voltage)
    #     print('\t|V|:', abs(c.power_flow_results.voltage))
    #     print('\t|Sbranch|:', abs(c.power_flow_results.Sbranch))
    #     print('\t|loading|:', abs(c.power_flow_results.loading) * 100)
    #     print('\terr:', c.power_flow_results.error)
    #     print('\tConv:', c.power_flow_results.converged)

    print('Grid:', grid.name)
    print('\t|V|:', abs(grid.power_flow_results.voltage))
    print('\t|Sbranch|:', abs(grid.power_flow_results.Sbranch))
    print('\t|loading|:', abs(grid.power_flow_results.loading) * 100)
    print('\terr:', grid.power_flow_results.error)
    print('\tConv:', grid.power_flow_results.converged)


if __name__ == '__main__':

    scheduler = BackgroundScheduler()
    job = scheduler.add_job(run_pf, 'interval', seconds=1)
    scheduler.start()

    app.run(host='0.0.0.0', port=PORT)