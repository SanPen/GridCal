import GridCalEngine.api as gce

# fname = '/home/santi/Documentos/Git/GitHub/GridCal/src/tests/data/grids/IEEE39_trafo.gridcal'
fname = '/home/santi/Documentos/Git/GitHub/GridCal/src/tests/data/grids/IEEE39_1W.gridcal'
grid_ = gce.open_file(fname)

iterable = gce.AiIterable(grid=grid_, forced_mttf=10.0, forced_mttr=1.0)
points = [iterable.__next__() for i in range(10)]

a = 0
while a < 100:
    res = iterable.__next__()
    a += 1
    print(res.Sbus)

# for result in iterable:  # inifinte because the iterable has no end
#     print(result.Sbus)
