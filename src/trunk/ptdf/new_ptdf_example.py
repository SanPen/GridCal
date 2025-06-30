import os
import numpy as np
import GridCalEngine.api as gce

fname = os.path.join('..', '..', 'tests', 'data', 'grids', 'PGOC_6bus.gridcal')
grid = gce.FileOpen(fname).open()

options = gce.LinearAnalysisOptions(distribute_slack=False, correct_values=False)
simulation = gce.LinearAnalysisDriver(grid=grid, options=options)
simulation.run()
# ptdf_df = simulation.results.mdl(result_type=ResultTypes.PTDFBranchesSensitivity)

test_PTDF = [[0, -0.470623900249771, -0.40256295349251, -0.314889382426403, -0.321730075985739, -0.406428143061441],
             [0, -0.314889382426403, -0.294871456909562, -0.504379230125413, -0.271097081172276, -0.296008277371012],
             [0, -0.214486717323826, -0.302565589597928, -0.180731387448184, -0.407172842841985, -0.297563579567547],
             [0, 0.0544487574058086, -0.341553588728013, 0.0160143404134731, -0.105694646728923, -0.1906695048735],
             [0, 0.311469035646735, 0.215382993165897, -0.378979695398019, 0.101265989626925, 0.220839731380858],
             [0, 0.0992625495093548, -0.0341902872695879, 0.0291948675027514, -0.192686125518159, -0.0266114841932529],
             [0, 0.0641957571883298, -0.242202070660806, 0.0188811050553911, -0.124615293365582, -0.409986885375546],
             [0, 0.0621791365436704, 0.288966580773565, 0.0182879813363736, -0.120700676820066, 0.152630503693843],
             [0, -0.00773037913786179, 0.369479830498422, -0.00227364092290061, 0.0150060300911433, -0.343300008567343],
             [0, -0.00342034677966774, -0.0794884637436652, 0.116641074476568, -0.169831091545351, -0.0751685459901542],
             [0, -0.0564653780504683, -0.127277759837616, -0.0166074641324907, 0.109609263274438, -0.246713106057111]]

test_PTDF = np.array(test_PTDF)

# ----------------------------------------------------------------------------------------------------------------------

nc = gce.compile_numerical_circuit_at(grid)
S0 = nc.get_power_injections_pu()
ind = nc.get_simulation_indices(Sbus=S0)
lin_adm = nc.get_linear_admittance_matrices(indices=ind)
res = gce.power_flow(grid=grid, options=gce.PowerFlowOptions(solver_type=gce.SolverType.DC))

Va = np.angle(res.voltage)

n = nc.nbus
m = nc.nbr
PTDF = np.zeros((m, n))

Vref = Va[ind.vd][0]
for k in range(m):
    for i in ind.no_slack:
        f = nc.passive_branch_data.F[k]
        t = nc.passive_branch_data.T[k]
        x = nc.passive_branch_data.X[k]
        PTDF[k, i] = (Va[f] - Va[i]) / x

print("new PTDF:\n", PTDF)
