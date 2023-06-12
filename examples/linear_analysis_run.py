from matplotlib import pyplot as plt
from GridCal.Engine import *

fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/grid_2_islands.xlsx'
# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'
main_circuit = FileOpen(fname).open()

options_ = LinearAnalysisOptions()
ptdf_driver = LinearAnalysisTimeSeries(grid=main_circuit, options=options_)
ptdf_driver.run()

pf_options_ = PowerFlowOptions(solver_type=SolverType.NR)
ts_driver = TimeSeries(grid=main_circuit, options=pf_options_)
ts_driver.run()

fig = plt.figure()
ax1 = fig.add_subplot(221)
ax1.set_title('Newton-Raphson based flow')
ax1.plot(ts_driver.results.Sf.real)

ax2 = fig.add_subplot(222)
ax2.set_title('PTDF based flow')
ax2.plot(ptdf_driver.results.Sf.real)

ax3 = fig.add_subplot(223)
ax3.set_title('Difference')
diff = ts_driver.results.Sf.real - ptdf_driver.results.Sf.real
ax3.plot(diff)

fig2 = plt.figure()
ax1 = fig2.add_subplot(221)
ax1.set_title('Newton-Raphson based voltage')
ax1.plot(np.abs(ts_driver.results.voltage))

ax2 = fig2.add_subplot(222)
ax2.set_title('PTDF based voltage')
ax2.plot(ptdf_driver.results.voltage)

ax3 = fig2.add_subplot(223)
ax3.set_title('Difference')
diff = np.abs(ts_driver.results.voltage) - ptdf_driver.results.voltage
ax3.plot(diff)

plt.show()
