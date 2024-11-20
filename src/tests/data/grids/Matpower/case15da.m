function mpc = case15da
%CASE15DA  Power flow data for 15 bus distribution system from Das, et al
%   Please see CASEFORMAT for details on the case file format.
%
%   Data from ...
%       Das D, Kothari DP, Kalam A (1995) Simple and efficient method for load
%       flow solution of radial distribution networks. Int J Electr Power
%       Energy Syst 17:335-346. doi: 10.1016/0142-0615(95)00050-0
%       URL: https://doi.org/10.1016/0142-0615(95)00050-0

%% MATPOWER Case Format : Version 2
mpc.version = '2';

%%-----  Power Flow Data  -----%%
%% system MVA base
mpc.baseMVA = 1;

%% bus data
%	bus_i	type	Pd	Qd	Gs	Bs	area	Vm	Va	baseKV	zone	Vmax	Vmin
mpc.bus = [ %% (Pd and Qd are specified in kW & kVAr here, converted to MW & MVAr below)
	1	3	0	0	0	0	1	1	0	11	1	1	1;
	2	1	44.1	44.991	0	0	1	1	0	11	1	1.1	0.9;
	3	1	70	71.4143	0	0	1	1	0	11	1	1.1	0.9;
	4	1	140	142.8286	0	0	1	1	0	11	1	1.1	0.9;
	5	1	44.1	44.991	0	0	1	1	0	11	1	1.1	0.9;
	6	1	140	142.8286	0	0	1	1	0	11	1	1.1	0.9;
	7	1	140	142.8286	0	0	1	1	0	11	1	1.1	0.9;
	8	1	70	71.4143	0	0	1	1	0	11	1	1.1	0.9;
	9	1	70	71.4143	0	0	1	1	0	11	1	1.1	0.9;
	10	1	44.1	44.991	0	0	1	1	0	11	1	1.1	0.9;
	11	1	140	142.8286	0	0	1	1	0	11	1	1.1	0.9;
	12	1	70	71.4143	0	0	1	1	0	11	1	1.1	0.9;
	13	1	44.1	44.991	0	0	1	1	0	11	1	1.1	0.9;
	14	1	70	71.4143	0	0	1	1	0	11	1	1.1	0.9;
	15	1	140	142.8286	0	0	1	1	0	11	1	1.1	0.9;
];

%% generator data
%	bus	Pg	Qg	Qmax	Qmin	Vg	mBase	status	Pmax	Pmin	Pc1	Pc2	Qc1min	Qc1max	Qc2min	Qc2max	ramp_agc	ramp_10	ramp_30	ramp_q	apf
mpc.gen = [
	1	0	0	10	-10	1	100	1	10	0	0	0	0	0	0	0	0	0	0	0	0;
];

%% branch data
%	fbus	tbus	r	x	b	rateA	rateB	rateC	ratio	angle	status	angmin	angmax
mpc.branch = [  %% (r and x specified in ohms here, converted to p.u. below)
	1	2	1.35309	1.32349	0	0	0	0	0	0	1	-360	360;
	2	3	1.17024	1.14464	0	0	0	0	0	0	1	-360	360;
	3	4	0.84111	0.82271	0	0	0	0	0	0	1	-360	360;
	4	5	1.52348	1.0276	0	0	0	0	0	0	1	-360	360;
	2	9	2.01317	1.3579	0	0	0	0	0	0	1	-360	360;
	9	10	1.68671	1.1377	0	0	0	0	0	0	1	-360	360;
	2	6	2.55727	1.7249	0	0	0	0	0	0	1	-360	360;
	6	7	1.0882	0.734	0	0	0	0	0	0	1	-360	360;
	6	8	1.25143	0.8441	0	0	0	0	0	0	1	-360	360;
	3	11	1.79553	1.2111	0	0	0	0	0	0	1	-360	360;
	11	12	2.44845	1.6515	0	0	0	0	0	0	1	-360	360;
	12	13	2.01317	1.3579	0	0	0	0	0	0	1	-360	360;
	4	14	2.23081	1.5047	0	0	0	0	0	0	1	-360	360;
	4	15	1.19702	0.8074	0	0	0	0	0	0	1	-360	360;
];

%%-----  OPF Data  -----%%
%% generator cost data
%	1	startup	shutdown	n	x1	y1	...	xn	yn
%	2	startup	shutdown	n	c(n-1)	...	c0
mpc.gencost = [
	2	0	0	3	0	20	0;
];


%% convert branch impedances from Ohms to p.u.
[PQ, PV, REF, NONE, BUS_I, BUS_TYPE, PD, QD, GS, BS, BUS_AREA, VM, ...
    VA, BASE_KV, ZONE, VMAX, VMIN, LAM_P, LAM_Q, MU_VMAX, MU_VMIN] = idx_bus;
[F_BUS, T_BUS, BR_R, BR_X, BR_B, RATE_A, RATE_B, RATE_C, ...
    TAP, SHIFT, BR_STATUS, PF, QF, PT, QT, MU_SF, MU_ST, ...
    ANGMIN, ANGMAX, MU_ANGMIN, MU_ANGMAX] = idx_brch;
Vbase = mpc.bus(1, BASE_KV) * 1e3;      %% in Volts
Sbase = mpc.baseMVA * 1e6;              %% in VA
mpc.branch(:, [BR_R BR_X]) = mpc.branch(:, [BR_R BR_X]) / (Vbase^2 / Sbase);

%% convert loads from kW to MW
mpc.bus(:, [PD, QD]) = mpc.bus(:, [PD, QD]) / 1e3;
