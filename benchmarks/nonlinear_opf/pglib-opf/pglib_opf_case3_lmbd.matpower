%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%                                                                  %%%%%
%%%%    IEEE PES Power Grid Library - Optimal Power Flow - v23.07     %%%%%
%%%%          (https://github.com/power-grid-lib/pglib-opf)           %%%%%
%%%%               Benchmark Group - Typical Operations               %%%%%
%%%%                         23 - July - 2023                         %%%%%
%%%%                                                                  %%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%
%   The semidefinite relaxation of the OPF problem successfully solves 
%   this network with a value of 60 MVA for the line-flow limit on the line from
%   bus 2 to bus 3. The semidefinite relaxation fails to give a physically
%   meaningful solution to this network with a value of 50 MVA for the line-flow
%   limit on this line. See the following publication for further details.
%
%   Lesieutre, B.C. & Molzahn, D.K. & Borden, AR. & Demarco, C.L., 
%   "Examining the Limits of the Application of Semidefinite Programming to Power Flow Problems",
%   49th Annual Allerton Conference on Communication, Control, and Computing (Allerton),  
%   September, 2011, pp. 1492-1499
%
%   opt objective value:  5812.64 $/hr
%
%    Bus      Voltage          Generation             Load          Lambda($/MVA-hr)
%     #   Mag(pu) Ang(deg)   P (MW)   Q (MVAr)   P (MW)   Q (MVAr)     P        Q   
%   ----- ------- --------  --------  --------  --------  --------  -------  -------
%       1  1.100    0.000*   148.07     54.70    110.00     40.00    37.575     -
%       2  0.926    7.259    170.01     -8.79    110.00     40.00    30.101     -
%       3  0.900  -17.267      0.00     -4.84     95.00     50.00    45.537     -
%                           --------  --------  --------  --------
%                  Total:    318.07     41.06    315.00    130.00
%
%   Copyright (c) 2011 by The Institute of Electrical and Electronics Engineers (IEEE)
%   Licensed under the Creative Commons Attribution 4.0
%   International license, http://creativecommons.org/licenses/by/4.0/
%
%   Contact M.E. Brennan (me.brennan@ieee.org) for inquries on further reuse of
%   this dataset.
%
function mpc = pglib_opf_case3_lmbd
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
	1	 3	 0.065	 0.62	 0.45	 9000.0	 9000.0	 9000.0	 0.0	 0.0	 1	 -30.0	 30.0;
	3	 2	 0.025	 0.75	 0.7	 50.0	 50.0	 50.0	 0.0	 0.0	 1	 -30.0	 30.0;
	1	 2	 0.042	 0.9	 0.3	 9000.0	 9000.0	 9000.0	 0.0	 0.0	 1	 -30.0	 30.0;
];

% INFO    : === Translation Options ===
% INFO    : Phase Angle Bound:           30.0 (deg.)
% INFO    : Setting Flat Start
% INFO    : 
% INFO    : === Generator Bounds Update Notes ===
% INFO    : 
% INFO    : === Base KV Replacement Notes ===
% INFO    : 
% INFO    : === Transformer Setting Replacement Notes ===
% INFO    : 
% INFO    : === Line Capacity Monotonicity Notes ===
% INFO    : Updated Thermal Rating: on line 1-3 : Rate B, Rate C - 0.0, 0.0 -> 9000.0, 9000.0
% INFO    : Updated Thermal Rating: on line 3-2 : Rate B, Rate C - 0.0, 0.0 -> 50.0, 50.0
% INFO    : Updated Thermal Rating: on line 1-2 : Rate B, Rate C - 0.0, 0.0 -> 9000.0, 9000.0
% INFO    : 
% INFO    : === Voltage Setpoint Replacement Notes ===
% INFO    : Bus 1	: V=1.0, theta=0.0 -> V=1.0, theta=0.0
% INFO    : Bus 2	: V=1.0, theta=0.0 -> V=1.0, theta=0.0
% INFO    : Bus 3	: V=1.0, theta=0.0 -> V=1.0, theta=0.0
% INFO    : 
% INFO    : === Generator Setpoint Replacement Notes ===
% INFO    : Gen at bus 1	: Pg=0.0, Qg=0.0 -> Pg=1000.0, Qg=0.0
% INFO    : Gen at bus 1	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 2	: Pg=0.0, Qg=0.0 -> Pg=1000.0, Qg=0.0
% INFO    : Gen at bus 2	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 3	: Pg=0.0, Qg=0.0 -> Pg=0.0, Qg=0.0
% INFO    : Gen at bus 3	: Vg=1.0 -> Vg=1.0
% INFO    : 
% INFO    : === Writing Matpower Case File Notes ===
