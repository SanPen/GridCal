from GridCal.Engine.IO.file_handler import FileOpen, save_h5, open_h5

# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/1354 Pegase.xlsx'
fname = '/home/santi/Documentos/REE/Debug/Propuesta_2026_v16_con MAR+operabilidad/Propuesta_2026_v16_con MAR+operabilidad.gridcal'

print('First opening...')
circuit = FileOpen(fname).open()

print('Saving...')
save_h5(circuit, file_path='test.gch5')

print('Reopening')
circuit2 = open_h5('test.gch5')