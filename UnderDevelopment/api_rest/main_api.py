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
    # print('I am working...')

    grid.compile()
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

    # print('Grid:', grid.name)
    # print('\t|V|:', abs(grid.power_flow_results.voltage))
    # print('\t|Sbranch|:', abs(grid.power_flow_results.Sbranch))
    # print('\t|loading|:', abs(grid.power_flow_results.loading) * 100)
    # print('\terr:', grid.power_flow_results.error)
    # print('\tConv:', grid.power_flow_results.converged)


@app.route('/converged', methods=['GET'])
def converged():
    """

    :return:
    """
    response = {
        'val': grid.power_flow_results.converged,
    }
    return jsonify(response), 200


@app.route('/voltages', methods=['GET'])
def voltages():
    """

    :return:
    """
    response = {
        'val': abs(grid.power_flow_results.voltage).tolist(),
    }
    return jsonify(response), 200


@app.route('/loadings', methods=['GET'])
def loadings():
    """

    :return:
    """
    response = {
        'val': abs(grid.power_flow_results.loading).tolist(),
    }
    return jsonify(response), 200


@app.route('/loads_list', methods=['GET'])
def loads_list():
    """

    :return:
    """
    load_names = [load.name for load in grid.get_loads()]
    response = {
        'loads': load_names,
    }
    return jsonify(response), 200


@app.route('/grid_name', methods=['GET'])
def grid_name():
    """

    :return:
    """
    response = {
        'name': grid.name,
    }
    return jsonify(response), 200


@app.route('/set_load', methods=['POST'])
def set_load():

    data = request.get_json()
    print(data)

    if 'idx' not in data.keys():
        return 1
    if 'P' not in data.keys():
        return 2
    if 'Q' not in data.keys():
        return 3

    idx = int(data['idx'])
    P = float(data['P'])
    Q = float(data['Q'])
    S = P + 1j * Q
    loads = grid.get_loads()
    print('Setting ', S, idx, loads[idx])

    loads[idx].S = S

    # if idx < len(loads):
    #     loads[idx].S = P + 1j*Q
    # else:
    #     return 4
    response = {'message': str(S) + ' set to ' + str(loads[idx])}
    return jsonify(response), 200

if __name__ == '__main__':

    scheduler = BackgroundScheduler()
    job = scheduler.add_job(run_pf, 'interval', seconds=1)
    scheduler.start()

    app.run(host='0.0.0.0', port=PORT)