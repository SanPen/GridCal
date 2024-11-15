function mpc = case4_dist
%CASE4_DIST  Power flow data for 4 bus radial distribution system
%   Please see CASEFORMAT for details on the case file format.

%   MATPOWER

%% MATPOWER Case Format : Version 2
mpc.version = '2';

%%-----  Power Flow Data  -----%%
%% system MVA base
mpc.baseMVA = 1;

%% bus data
%	bus_i	type	Pd	Qd	Gs	Bs	area	Vm	Va	baseKV	zone	Vmax	Vmin
mpc.bus = [
	1	3	0	0	0	0	1	1	0	12.5	1	1.1	0.9;
	2	1	0.4	0.2	0	0	1	1	0	12.5	1	1.1	0.9;
	3	1	0.4	0.2	0	0	1	1	0	12.5	1	1.1	0.9;
	400	2	0.4	0.2	0	0	1	1	0	12.5	1	1.1	0.9;
];

%% generator data
%	bus	Pg	Qg	Qmax	Qmin	Vg	mBase	status	Pmax	Pmin	Pc1	Pc2	Qc1min	Qc1max	Qc2min	Qc2max	ramp_agc	ramp_10	ramp_30	ramp_q	apf
mpc.gen = [
	1	0	0	10	-10	1.05	100	1	10	0	0	0	0	0	0	0	0	0	0	0	0;
	400	0	0	10	-10	1.05	100	1	10	0	0	0	0	0	0	0	0	0	0	0	0;
];

%% branch data
%	fbus	tbus	r	x	b	rateA	rateB	rateC	ratio	angle	status	angmin	angmax
mpc.branch = [
	2	3	0.003	0.006	0	0	0	0	0	0	1	-360	360;
	1	2	0.003	0.006	0	0	0	0	0	0	1	-360	360;
	400	1	0.003	0.006	0	0	0	0	1.025	0	1	-360	360;
];
