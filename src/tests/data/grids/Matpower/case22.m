function mpc = case22
%CASE22  Power flow data for 22 bus distribution system from Raju, et al
%   Please see CASEFORMAT for details on the case file format.
%
%   Data from ...
%       M. Ramalinga Raju, K.V.S. Ramachandra Murthy, K. Ravindra,
%       Direct search algorithm for capacitive compensation in radial
%       distribution systems, International Journal of Electrical Power &
%       Energy Systems, Volume 42, Issue 1, November 2012, Pages 24-30
%       https://doi.org/10.1016/j.ijepes.2012.03.006
%
%   Represents "a small portion of agricultural distribution of Eastern
%   Power Distribution system in India."
%
%   Modifications:
%     v2 - 2020-09-30 (RDZ, based on contrib by Houssem Bouchekara, et al)
%         - Move branch 4--9 from row 8 to row 5 to match original order.
%         - Added code for explicit conversion of loads from kW to MW and
%           branch parameters from Ohms to p.u.
%         - Bus 1 Vmin = Vmax = 1.0
%         - Gen Qmin, Qmax, Pmax magnitudes set to 10 (instead of 999)
%         - Branch flow limits disabled, i.e. set to 0 (instead of 999)
%         - Add gen cost.
%         - Change baseMVA to 1 MVA.

%% MATPOWER Case Format : Version 2
mpc.version = '2';

%%-----  Power Flow Data  -----%%
%% system MVA base
mpc.baseMVA = 1;

%% bus data
%	bus_i	type	Pd	Qd	Gs	Bs	area	Vm	Va	baseKV	zone	Vmax	Vmin
mpc.bus = [ %% (Pd and Qd are specified in kW & kVAr here, converted to MW & MVAr below)
	1	3	0	0	0	0	1	1	0	11	1	1	1;
	2	1	16.78	20.91	0	0	1	1	0	11	1	1.1	0.9;
	3	1	16.78	20.91	0	0	1	1	0	11	1	1.1	0.9;
	4	1	33.8	37.32	0	0	1	1	0	11	1	1.1	0.9;
	5	1	14.56	12.52	0	0	1	1	0	11	1	1.1	0.9;
	6	1	10.49	14.21	0	0	1	1	0	11	1	1.1	0.9;
	7	1	8.821	11.66	0	0	1	1	0	11	1	1.1	0.9;
	8	1	14.35	18.59	0	0	1	1	0	11	1	1.1	0.9;
	9	1	19.31	25.87	0	0	1	1	0	11	1	1.1	0.9;
	10	1	14.35	18.59	0	0	1	1	0	11	1	1.1	0.9;
	11	1	16.27	19.48	0	0	1	1	0	11	1	1.1	0.9;
	12	1	16.27	19.48	0	0	1	1	0	11	1	1.1	0.9;
	13	1	82.13	71.65	0	0	1	1	0	11	1	1.1	0.9;
	14	1	34.71	30.12	0	0	1	1	0	11	1	1.1	0.9;
	15	1	34.71	30.12	0	0	1	1	0	11	1	1.1	0.9;
	16	1	80.31	70.12	0	0	1	1	0	11	1	1.1	0.9;
	17	1	49.62	47.82	0	0	1	1	0	11	1	1.1	0.9;
	18	1	49.62	47.82	0	0	1	1	0	11	1	1.1	0.9;
	19	1	43.77	38.93	0	0	1	1	0	11	1	1.1	0.9;
	20	1	37.32	35.96	0	0	1	1	0	11	1	1.1	0.9;
	21	1	37.32	35.96	0	0	1	1	0	11	1	1.1	0.9;
	22	1	31.02	29.36	0	0	1	1	0	11	1	1.1	0.9;
];

%% generator data
%	bus	Pg	Qg	Qmax	Qmin	Vg	mBase	status	Pmax	Pmin	Pc1	Pc2	Qc1min	Qc1max	Qc2min	Qc2max	ramp_agc	ramp_10	ramp_30	ramp_q	apf
mpc.gen = [
	1	0	0	10	-10	1	100	1	10	0	0	0	0	0	0	0	0	0	0	0	0;
];

%% branch data
%	fbus	tbus	r	x	b	rateA	rateB	rateC	ratio	angle	status	angmin	angmax
mpc.branch = [  %% (r and x specified in ohms here, converted to p.u. below)
	1	2	0.3664	0.1807	0	0	0	0	0	0	1	-360	360;
	2	3	0.0547	0.0282	0	0	0	0	0	0	1	-360	360;
	2	4	0.5416	0.2789	0	0	0	0	0	0	1	-360	360;
	4	5	0.193	0.099	0	0	0	0	0	0	1	-360	360;
	4	9	0.7431	0.3827	0	0	0	0	0	0	1	-360	360;
	5	6	1.311	0.6752	0	0	0	0	0	0	1	-360	360;
	6	7	0.0598	0.0308	0	0	0	0	0	0	1	-360	360;
	6	8	0.2905	0.1496	0	0	0	0	0	0	1	-360	360;
	9	10	0.0547	0.0282	0	0	0	0	0	0	1	-360	360;
	9	11	0.675	0.3481	0	0	0	0	0	0	1	-360	360;
	11	12	0.0547	0.0282	0	0	0	0	0	0	1	-360	360;
	11	13	0.3942	0.203	0	0	0	0	0	0	1	-360	360;
	13	14	1.046	0.5388	0	0	0	0	0	0	1	-360	360;
	14	15	0.022	0.0116	0	0	0	0	0	0	1	-360	360;
	14	16	0.0547	0.0282	0	0	0	0	0	0	1	-360	360;
	16	17	0.3212	0.1654	0	0	0	0	0	0	1	-360	360;
	17	18	0.0949	0.0488	0	0	0	0	0	0	1	-360	360;
	17	19	0.574	0.2959	0	0	0	0	0	0	1	-360	360;
	19	20	0.1292	0.066	0	0	0	0	0	0	1	-360	360;
	20	21	0.0871	0.045	0	0	0	0	0	0	1	-360	360;
	20	22	0.5329	0.2744	0	0	0	0	0	0	1	-360	360;
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
