import GridCalEngine.api as gce

my_grid = gce.open_file("src/trunk/three_phase/Saved_Line.gridcal")
for line in my_grid.lines:
    print(line)