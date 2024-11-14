function mpc = case16ci
%CASE16CI  Power flow data for 16 bus distribution system from Civanlar, et al
%   Please see CASEFORMAT for details on the case file format.
%
%   Data from ...
%       Civanlar S, Grainger JJ, Yin H, Lee SSH (1988) Distribution Feeder
%       Reconfiguration for Loss Reduction. IEEE Trans Power Deliv
%       3:1217-1223. doi: 10.1109/61.193906
%       URL: https://doi.org/10.1109/61.193906
%   and
%       Zhu JZ (2002) Optimal reconfiguration of electrical distribution
%       network using the refined genetic algorithm, Electr Power Syst Res
%       62:37-42. doi: 10.1016/S0378-7796(02)00041-X
%       URL: https://doi.org/10.1016/S0378-7796(02)00041-X

%% MATPOWER Case Format : Version 2
mpc.version = '2';

%%-----  Power Flow Data  -----%%
%% system MVA base
mpc.baseMVA = 10;

%% bus data
%	bus_i	type	Pd	Qd	Gs	Bs	area	Vm	Va	baseKV	zone	Vmax	Vmin
mpc.bus = [ %% (Pd and Qd are specified in kW & kVAr here, converted to MW & MVAr below)
	1	3	0	0	0	0	1	1	0	12.66	1	1	1;
	2	3	0	0	0	0	1	1	0	12.66	1	1	1;
	3	3	0	0	0	0	1	1	0	12.66	1	1	1;
	4	1	2000	1600	0	0	1	1	0	12.66	1	1	1;
	5	1	3000	400	0	0	1	1	0	12.66	1	1.1	0.9;
	6	1	2000	-400	0	0	1	1	0	12.66	1	1.1	0.9;
	7	1	1500	1200	0	0	1	1	0	12.66	1	1.1	0.9;
	8	1	4000	2700	0	0	1	1	0	12.66	1	1.1	0.9;
	9	1	5000	1800	0	0	1	1	0	12.66	1	1.1	0.9;
	10	1	1000	900	0	0	1	1	0	12.66	1	1.1	0.9;
	11	1	600	-500	0	0	1	1	0	12.66	1	1.1	0.9;
	12	1	4500	-1700	0	0	1	1	0	12.66	1	1.1	0.9;
	13	1	1000	900	0	0	1	1	0	12.66	1	1.1	0.9;
	14	1	1000	-1100	0	0	1	1	0	12.66	1	1.1	0.9;
	15	1	1000	900	0	0	1	1	0	12.66	1	1.1	0.9;
	16	1	2100	-800	0	0	1	1	0	12.66	1	1.1	0.9;
];

%% generator data
%	bus	Pg	Qg	Qmax	Qmin	Vg	mBase	status	Pmax	Pmin	Pc1	Pc2	Qc1min	Qc1max	Qc2min	Qc2max	ramp_agc	ramp_10	ramp_30	ramp_q	apf
mpc.gen = [
	1	0	0	10	-10	1	100	1	10	0	0	0	0	0	0	0	0	0	0	0	0;
	2	0	0	10	-10	1	100	1	10	0	0	0	0	0	0	0	0	0	0	0	0;
	3	0	0	10	-10	1	100	1	10	0	0	0	0	0	0	0	0	0	0	0	0;
];

%% branch data
%	fbus	tbus	r	x	b	rateA	rateB	rateC	ratio	angle	status	angmin	angmax
mpc.branch = [  %% (r and x specified in ohms here, converted to p.u. below)
	1	4	0.075	0.1	0	0	0	0	0	0	1	-360	360;
	4	5	0.08	0.11	0	0	0	0	0	0	1	-360	360;
	4	6	0.09	0.18	0	0	0	0	0	0	1	-360	360;
	6	7	0.04	0.04	0	0	0	0	0	0	1	-360	360;
	2	8	0.11	0.11	0	0	0	0	0	0	1	-360	360;
	8	9	0.08	0.11	0	0	0	0	0	0	1	-360	360;
	8	10	0.11	0.11	0	0	0	0	0	0	1	-360	360;
	9	11	0.11	0.11	0	0	0	0	0	0	1	-360	360;
	9	12	0.08	0.11	0	0	0	0	0	0	1	-360	360;
	3	13	0.11	0.11	0	0	0	0	0	0	1	-360	360;
	13	14	0.09	0.12	0	0	0	0	0	0	1	-360	360;
	13	15	0.08	0.11	0	0	0	0	0	0	1	-360	360;
	15	16	0.04	0.04	0	0	0	0	0	0	1	-360	360;
	5	11	0.04	0.04	0	0	0	0	0	0	0	-360	360;
	10	14	0.04	0.04	0	0	0	0	0	0	0	-360	360;
	7	16	0.09	0.12	0	0	0	0	0	0	0	-360	360;
];

%%-----  OPF Data  -----%%
%% generator cost data
%	1	startup	shutdown	n	x1	y1	...	xn	yn
%	2	startup	shutdown	n	c(n-1)	...	c0
mpc.gencost = [
	2	0	0	3	0	20	0;
	2	0	0	3	0	20	0;
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
