%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%                                                                  %%%%%
%%%%    IEEE PES Power Grid Library - Optimal Power Flow - v23.07     %%%%%
%%%%          (https://github.com/power-grid-lib/pglib-opf)           %%%%%
%%%%             Benchmark Group - Small Angle Difference             %%%%%
%%%%                         23 - July - 2023                         %%%%%
%%%%                                                                  %%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
function mpc = pglib_opf_case3_lmbd__sad
mpc.version = '2';
mpc.baseMVA = 100.0;

%% bus data
%	bus_i	type	Pd	Qd	Gs	Bs	area	Vm	Va	baseKV	zone	Vmax	Vmin
mpc.bus = [
	1	 3	 110.0	 40.0	 0.0	 0.0	 1	    1.00000	    0.00000	 240.0	 1	    1.10000	    0.90000;
	2	 2	 110.0	 40.0	 0.0	 0.0	 1	    1.00000	    0.00000	 240.0	 1	    1.10000	    0.90000;
	3	 2	 95.0	 50.0	 0.0	 0.0	 1	    1.00000	    0.00000	 240.0	 1	    1.10000	    0.90000;
];

%% generator data
%	bus	Pg	Qg	Qmax	Qmin	Vg	mBase	status	Pmax	Pmin
mpc.gen = [
	1	 1000.0	 0.0	 1000.0	 -1000.0	 1.0	 100.0	 1	 2000.0	 0.0;
	2	 1000.0	 0.0	 1000.0	 -1000.0	 1.0	 100.0	 1	 2000.0	 0.0;
	3	 0.0	 0.0	 1000.0	 -1000.0	 1.0	 100.0	 1	 0.0	 0.0;
];

%% generator cost data
%	2	startup	shutdown	n	c(n-1)	...	c0
mpc.gencost = [
	2	 0.0	 0.0	 3	   0.110000	   5.000000	   0.000000;
	2	 0.0	 0.0	 3	   0.085000	   1.200000	   0.000000;
	2	 0.0	 0.0	 3	   0.000000	   0.000000	   0.000000;
];

%% branch data
%	fbus	tbus	r	x	b	rateA	rateB	rateC	ratio	angle	status	angmin	angmax
mpc.branch = [
	1	 3	 0.065	 0.62	 0.45	 9000.0	 9000.0	 9000.0	 0.0	 0.0	 1	 -18.7397099664	 18.7397099664;
	3	 2	 0.025	 0.75	 0.7	 50.0	 50.0	 50.0	 0.0	 0.0	 1	 -18.7397099664	 18.7397099664;
	1	 2	 0.042	 0.9	 0.3	 9000.0	 9000.0	 9000.0	 0.0	 0.0	 1	 -18.7397099664	 18.7397099664;
];

% INFO    : === Translation Options ===
% INFO    : Phase Angle Bound:           18.7397099664 (deg.)
% INFO    : 
% INFO    : === Generator Bounds Update Notes ===
% INFO    : 
% INFO    : === Base KV Replacement Notes ===
% INFO    : 
% INFO    : === Transformer Setting Replacement Notes ===
% INFO    : 
% INFO    : === Line Capacity Monotonicity Notes ===
% INFO    : 
% INFO    : === Writing Matpower Case File Notes ===
