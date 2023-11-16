import os
from GridCalEngine.api import *

folder = ''
f = os.path.join(folder, 'BASE N.zip')
folder = os.path.dirname(f)

mdl_ = PlexosModel(fname=f)

step = 4
time_indices_ = np.arange(0, 8760, step)

circuit_ = plexos_to_gridcal(mdl=mdl_, plexos_results_folder=folder, time_indices=time_indices_)

fs = FileSave(circuit=circuit_, file_name='spain_plexos(base con restricciones).gridcal', text_func=print)
fs.save()