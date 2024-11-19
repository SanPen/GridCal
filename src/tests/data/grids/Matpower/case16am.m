function mpc = case16am
%CASE16AM  Power flow data for 15 bus distribution system from Das, et al
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
mpc.baseMVA = 10;

%% bus data
%	bus_i	type	Pd	Qd	Gs	Bs	area	Vm	Va	baseKV	zone	Vmax	Vmin
mpc.bus = [ %% (Pd and Qd are specified in kW & kVAr here, converted to MW & MVAr below)
	1	3	0	0	0	0	1	1	0	12.66	1	1	1;
	2	1	0	0	0	0	1	1	0	12.66	1	1.1	0.9;
	3	1	2000	1600	0	0	1	1	0	12.66	1	1.1	0.9;
	4	1	3000	400	0	0	1	1	0	12.66	1	1.1	0.9;
	5	1	2000	-400	0	0	1	1	0	12.66	1	1.1	0.9;
	6	1	1500	1200	0	0	1	1	0	12.66	1	1.1	0.9;
	7	1	4000	2700	0	0	1	1	0	12.66	1	1.1	0.9;
	8	1	5000	1800	0	0	1	1	0	12.66	1	1.1	0.9;
	9	1	1000	900	0	0	1	1	0	12.66	1	1.1	0.9;
	10	1	600	-500	0	0	1	1	0	12.66	1	1.1	0.9;
	11	1	4500	-1700	0	0	1	1	0	12.66	1	1.1	0.9;
	12	1	1000	900	0	0	1	1	0	12.66	1	1.1	0.9;
	13	1	1000	-1100	0	0	1	1	0	12.66	1	1.1	0.9;
	14	1	1000	900	0	0	1	1	0	12.66	1	1.1	0.9;
	15	1	2100	-800	0	0	1	1	0	12.66	1	1.1	0.9;
];

%% generator data
%	bus	Pg	Qg	Qmax	Qmin	Vg	mBase	status	Pmax	Pmin	Pc1	Pc2	Qc1min	Qc1max	Qc2min	Qc2max	ramp_agc	ramp_10	ramp_30	ramp_q	apf
mpc.gen = [
	1	0	0	10	-10	1	100	1	10	0	0	0	0	0	0	0	0	0	0	0	0;
];

%% branch data
%	fbus	tbus	r	x	b	rateA	rateB	rateC	ratio	angle	status	angmin	angmax
mpc.branch = [  %% (r and x specified in ohms here, converted to p.u. below)
	1	2	0	1e-8	0	0	0	0	0	0	1	-360	360;    %% original reactance of 0 set to 1e-8
	2	3	0.1202	0.1603	0	0	0	0	0	0	1	-360	360;
	3	4	0.1282	0.1763	0	0	0	0	0	0	1	-360	360;
	3	5	0.1442	0.2885	0	0	0	0	0	0	1	-360	360;
	5	6	0.0641	0.0641	0	0	0	0	0	0	1	-360	360;
	2	7	0.1763	0.1763	0	0	0	0	0	0	1	-360	360;
	7	8	0.1282	0.1763	0	0	0	0	0	0	1	-360	360;
	7	9	0.1763	0.1763	0	0	0	0	0	0	1	-360	360;
	8	10	0.1763	0.1763	0	0	0	0	0	0	1	-360	360;
	8	11	0.1282	0.1763	0	0	0	0	0	0	1	-360	360;
	2	12	0.1763	0.1763	0	0	0	0	0	0	1	-360	360;
	12	13	0.1442	0.1923	0	0	0	0	0	0	1	-360	360;
	12	14	0.1282	0.1763	0	0	0	0	0	0	1	-360	360;
	14	15	0.0641	0.0641	0	0	0	0	0	0	1	-360	360;
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
