from GridCalEngine.IO.file_handler import FileOpen, FileSave
import os

file_path = os.path.join(
    'C:/Users/some1/Desktop/GridCal_SCOPF/Grids_and_profiles/grids/IEEE 30 Bus.gridcal')
grid = FileOpen(file_path).open()

output_dir = 'contingency_grids'
os.makedirs(output_dir, exist_ok=True)

contingency_count = 0

for line in grid.lines:
    endpoints = [line.bus_from, line.bus_to]
    critical = False

    for bus in endpoints:
        connected_lines = [
            l for l in grid.lines if l is not line and (l.bus_from == bus or l.bus_to == bus)]
        if not connected_lines:
            critical = True
            break

    if not critical:
        continue

    print(f'Critical line detected: {line.name} (idtag={line.idtag})')

    # Remove the line from the cloned grid
    line_to_remove = next((l for l in grid.lines if l.idtag == line.idtag), None)
    if line_to_remove:
        line_to_remove.active = False
        print(f'  -> Removed line {line_to_remove.name}')

    # Save the new grid with contingency applied
    file_name = os.path.join(output_dir, f'contingency_{contingency_count}.gridcal')
    FileSave(grid, file_name).save()
    print(f'  -> Saved as: {file_name}')
    contingency_count += 1

if contingency_count == 0:
    FileSave(grid, os.path.join(output_dir, 'base_case.gridcal')).save()
    print('No contingencies found.')
