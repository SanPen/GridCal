clc;
#define_constants;
mpc = loadcase('case9.m');
mpopt = mpoption('pf.alg', 'FDXB', 'verbose', 2, 'out.all', 1, 'exp.use_legacy_core', 1);
res = runopf(mpc);
