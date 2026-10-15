%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%                                                                  %%%%%
%%%%    IEEE PES Power Grid Library - Optimal Power Flow - v23.07     %%%%%
%%%%          (https://github.com/power-grid-lib/pglib-opf)           %%%%%
%%%%             Benchmark Group - Active Power Increase              %%%%%
%%%%                         23 - July - 2023                         %%%%%
%%%%                                                                  %%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
function mpc = pglib_opf_case3_lmbd__api
mpc.version = '2';
mpc.baseMVA = 100.0;

%% bus data
%	bus_i	type	Pd	Qd	Gs	Bs	area	Vm	Va	baseKV	zone	Vmax	Vmin
mpc.bus = [
	1	 3	 147.08	 40.00	 0.0	 0.0	 1	    1.00000	    0.00000	 240.0	 1	    1.10000	    0.90000;
	2	 2	 147.08	 40.00	 0.0	 0.0	 1	    1.00000	    0.00000	 240.0	 1	    1.10000	    0.90000;
	3	 2	 127.03	 50.00	 0.0	 0.0	 1	    1.00000	    0.00000	 240.0	 1	    1.10000	    0.90000;
];

%% generator data
%	bus	Pg	Qg	Qmax	Qmin	Vg	mBase	status	Pmax	Pmin
mpc.gen = [
	1	 153.5	 0.0	 1000.0	 -1000.0	 1.0	 100.0	 1	 307	 0.0; % PEL
	2	 107.0	 0.0	 1000.0	 -1000.0	 1.0	 100.0	 1	 214	 0.0; % COW
	3	 0.0	 0.0	 1000.0	 -1000.0	 1.0	 100.0	 1	 0	 0.0; % SYNC
];

%% generator cost data
%	2	startup	shutdown	n	c(n-1)	...	c0
mpc.gencost = [
	2	 0.0	 0.0	 3	   0.110000	   5.000000	   0.000000; % PEL
	2	 0.0	 0.0	 3	   0.085000	   1.200000	   0.000000; % COW
	2	 0.0	 0.0	 3	   0.000000	   0.000000	   0.000000; % SYNC
];

%% branch data
%	fbus	tbus	r	x	b	rateA	rateB	rateC	ratio	angle	status	angmin	angmax
mpc.branch = [
	1	 3	 0.065	 0.62	 0.45	 9000.0	 9000.0	 9000.0	 0.0	 0.0	 1	 -30.0	 30.0;
	3	 2	 0.025	 0.75	 0.7	 50.0	 50.0	 50.0	 0.0	 0.0	 1	 -30.0	 30.0;
	1	 2	 0.042	 0.9	 0.3	 9000.0	 9000.0	 9000.0	 0.0	 0.0	 1	 -30.0	 30.0;
];

% INFO    : === Translation Options ===
% INFO    : Load Model:                  from file ./pglib_opf_case3_lmbd.m.api.sol
% INFO    : Gen Active Capacity Model:   stat
% INFO    : Gen Reactive Capacity Model: al50ag
% INFO    : Gen Active Cost Model:       stat
% INFO    : 
% INFO    : === Load Replacement Notes ===
% INFO    : Bus 1	: Pd=110.0, Qd=40.0 -> Pd=147.08, Qd=40.00
% INFO    : Bus 2	: Pd=110.0, Qd=40.0 -> Pd=147.08, Qd=40.00
% INFO    : Bus 3	: Pd=95.0, Qd=50.0 -> Pd=127.03, Qd=50.00
% INFO    : 
% INFO    : === Generator Setpoint Replacement Notes ===
% INFO    : Gen at bus 1	: Pg=1000.0, Qg=0.0 -> Pg=265.0, Qg=41.0
% INFO    : Gen at bus 2	: Pg=1000.0, Qg=0.0 -> Pg=163.0, Qg=-10.0
% INFO    : Gen at bus 3	: Pg=0.0, Qg=0.0 -> Pg=0.0, Qg=15.0
% INFO    : 
% INFO    : === Generator Reactive Capacity Atleast Setpoint Value Notes ===
% INFO    : 
% INFO    : === Generator Classification Notes ===
% INFO    : PEL    1   -    61.92
% INFO    : SYNC   1   -     0.00
% INFO    : COW    1   -    38.08
% INFO    : 
% INFO    : === Generator Active Capacity Stat Model Notes ===
% WARNING : Failed to find a generator capacity within (265.0-1325.0) after 100 samples, using percent increase model
% INFO    : Gen at bus 1 - PEL	: Pg=265.0, Pmax=2000.0 -> Pmax=307   samples: 100
% INFO    : Gen at bus 2 - COW	: Pg=163.0, Pmax=2000.0 -> Pmax=214   samples: 2
% INFO    : Gen at bus 3 - SYNC	: Pg=0.0, Pmax=0.0 -> Pmax=0   samples: 0
% INFO    : 
% INFO    : === Generator Active Capacity LB Model Notes ===
% INFO    : 
% INFO    : === Generator Reactive Capacity Atleast Max 50 Percent Active Model Notes ===
% INFO    : 
% INFO    : === Generator Setpoint Replacement Notes ===
% INFO    : Gen at bus 1	: Pg=265.0, Qg=41.0 -> Pg=153.5, Qg=0.0
% INFO    : Gen at bus 1	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 2	: Pg=163.0, Qg=-10.0 -> Pg=107.0, Qg=0.0
% INFO    : Gen at bus 2	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 3	: Pg=0.0, Qg=15.0 -> Pg=0.0, Qg=0.0
% INFO    : Gen at bus 3	: Vg=1.0 -> Vg=1.0
% INFO    : 
% INFO    : === Writing Matpower Case File Notes ===
