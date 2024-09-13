import os
import GridCalEngine.api as gce

f_name = '/home/santi/Descargas/Caso2030_v1 1.gridcal'
folder = '/home/santi/Descargas'
name = 'Caso2030_v1'

grid = gce.open_file(f_name)

results = gce.contingencies_ts(circuit=grid,
                               use_clustering=True,
                               n_points=2,
                               use_srap=True,
                               srap_max_power=1300.0,
                               srap_top_n=5,
                               srap_deadband=10,
                               srap_rever_to_nominal_rating=True,
                               detailed_massive_report=True,
                               contingency_deadband=0.0,
                               contingency_method=gce.ContingencyMethod.PTDF)

print("Saving...")
# gce.export_results([results], f_name + '.results.zip')
results.mdl(result_type=gce.ResultTypes.ContingencyAnalysisReport).save_to_excel(os.path.join(folder, 'ContingencyAnalysisReport_'+name+'.xlsx'))
results.mdl(result_type=gce.ResultTypes.ContingencyStatisticalAnalysisReport).save_to_excel(os.path.join(folder, 'ContingencyStatisticalAnalysisReport_'+name+'.xlsx'))
print("Done!")
