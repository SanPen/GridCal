%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%                                                                  %%%%%
%%%%    IEEE PES Power Grid Library - Optimal Power Flow - v23.07     %%%%%
%%%%          (https://github.com/power-grid-lib/pglib-opf)           %%%%%
%%%%               Benchmark Group - Typical Operations               %%%%%
%%%%                         23 - July - 2023                         %%%%%
%%%%                                                                  %%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%
%   Power flow data for IEEE 30 bus test case.
%   This data was converted from IEEE Common Data Format
%   (ieee30cdf.txt) on 20-Sep-2004 by cdf2matp, rev. 1.11
%
%   Converted from IEEE CDF file from:
%       http://www.ee.washington.edu/research/pstca/
%
%   Copyright (c) 1999 by Richard D. Christie, University of Washington
%   Electrical Engineering Licensed under the Creative Commons Attribution 4.0
%   International license, http://creativecommons.org/licenses/by/4.0/
%
%   CDF Header:
%   08/20/93 UW ARCHIVE           100.0  1961 W IEEE 30 Bus Test Case
%
function mpc = pglib_opf_case30_ieee
mpc.version = '2';
mpc.baseMVA = 100.0;

%% bus data
%	bus_i	type	Pd	Qd	Gs	Bs	area	Vm	Va	baseKV	zone	Vmax	Vmin
mpc.bus = [
	1	 3	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 132.0	 1	    1.06000	    0.94000;
	2	 2	 21.7	 12.7	 0.0	 0.0	 1	    1.00000	    0.00000	 132.0	 1	    1.06000	    0.94000;
	3	 1	 2.4	 1.2	 0.0	 0.0	 1	    1.00000	    0.00000	 132.0	 1	    1.06000	    0.94000;
	4	 1	 7.6	 1.6	 0.0	 0.0	 1	    1.00000	    0.00000	 132.0	 1	    1.06000	    0.94000;
	5	 2	 94.2	 19.0	 0.0	 0.0	 1	    1.00000	    0.00000	 132.0	 1	    1.06000	    0.94000;
	6	 1	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 132.0	 1	    1.06000	    0.94000;
	7	 1	 22.8	 10.9	 0.0	 0.0	 1	    1.00000	    0.00000	 132.0	 1	    1.06000	    0.94000;
	8	 2	 30.0	 30.0	 0.0	 0.0	 1	    1.00000	    0.00000	 132.0	 1	    1.06000	    0.94000;
	9	 1	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	10	 1	 5.8	 2.0	 0.0	 19.0	 1	    1.00000	    0.00000	 33.0	 1	    1.06000	    0.94000;
	11	 2	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 11.0	 1	    1.06000	    0.94000;
	12	 1	 11.2	 7.5	 0.0	 0.0	 1	    1.00000	    0.00000	 33.0	 1	    1.06000	    0.94000;
	13	 2	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 11.0	 1	    1.06000	    0.94000;
	14	 1	 6.2	 1.6	 0.0	 0.0	 1	    1.00000	    0.00000	 33.0	 1	    1.06000	    0.94000;
	15	 1	 8.2	 2.5	 0.0	 0.0	 1	    1.00000	    0.00000	 33.0	 1	    1.06000	    0.94000;
	16	 1	 3.5	 1.8	 0.0	 0.0	 1	    1.00000	    0.00000	 33.0	 1	    1.06000	    0.94000;
	17	 1	 9.0	 5.8	 0.0	 0.0	 1	    1.00000	    0.00000	 33.0	 1	    1.06000	    0.94000;
	18	 1	 3.2	 0.9	 0.0	 0.0	 1	    1.00000	    0.00000	 33.0	 1	    1.06000	    0.94000;
	19	 1	 9.5	 3.4	 0.0	 0.0	 1	    1.00000	    0.00000	 33.0	 1	    1.06000	    0.94000;
	20	 1	 2.2	 0.7	 0.0	 0.0	 1	    1.00000	    0.00000	 33.0	 1	    1.06000	    0.94000;
	21	 1	 17.5	 11.2	 0.0	 0.0	 1	    1.00000	    0.00000	 33.0	 1	    1.06000	    0.94000;
	22	 1	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 33.0	 1	    1.06000	    0.94000;
	23	 1	 3.2	 1.6	 0.0	 0.0	 1	    1.00000	    0.00000	 33.0	 1	    1.06000	    0.94000;
	24	 1	 8.7	 6.7	 0.0	 4.3	 1	    1.00000	    0.00000	 33.0	 1	    1.06000	    0.94000;
	25	 1	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 33.0	 1	    1.06000	    0.94000;
	26	 1	 3.5	 2.3	 0.0	 0.0	 1	    1.00000	    0.00000	 33.0	 1	    1.06000	    0.94000;
	27	 1	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 33.0	 1	    1.06000	    0.94000;
	28	 1	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 132.0	 1	    1.06000	    0.94000;
	29	 1	 2.4	 0.9	 0.0	 0.0	 1	    1.00000	    0.00000	 33.0	 1	    1.06000	    0.94000;
	30	 1	 10.6	 1.9	 0.0	 0.0	 1	    1.00000	    0.00000	 33.0	 1	    1.06000	    0.94000;
];

%% generator data
%	bus	Pg	Qg	Qmax	Qmin	Vg	mBase	status	Pmax	Pmin
mpc.gen = [
	1	 135.5	 5.0	 10.0	 0.0	 1.0	 100.0	 1	 271	 0.0; % NG
	2	 46.0	 3.0	 46.0	 -40.0	 1.0	 100.0	 1	 92	 0.0; % NG
	5	 0.0	 0.0	 40.0	 -40.0	 1.0	 100.0	 1	 0	 0.0; % SYNC
	8	 0.0	 15.0	 40.0	 -10.0	 1.0	 100.0	 1	 0	 0.0; % SYNC
	11	 0.0	 9.0	 24.0	 -6.0	 1.0	 100.0	 1	 0	 0.0; % SYNC
	13	 0.0	 9.0	 24.0	 -6.0	 1.0	 100.0	 1	 0	 0.0; % SYNC
];

%% generator cost data
%	2	startup	shutdown	n	c(n-1)	...	c0
mpc.gencost = [
	2	 0.0	 0.0	 3	   0.000000	  18.421528	   0.000000; % NG
	2	 0.0	 0.0	 3	   0.000000	  52.182254	   0.000000; % NG
	2	 0.0	 0.0	 3	   0.000000	   0.000000	   0.000000; % SYNC
	2	 0.0	 0.0	 3	   0.000000	   0.000000	   0.000000; % SYNC
	2	 0.0	 0.0	 3	   0.000000	   0.000000	   0.000000; % SYNC
	2	 0.0	 0.0	 3	   0.000000	   0.000000	   0.000000; % SYNC
];

%% branch data
%	fbus	tbus	r	x	b	rateA	rateB	rateC	ratio	angle	status	angmin	angmax
mpc.branch = [
	1	 2	 0.0192	 0.0575	 0.0528	 138	 138	 138	 0.0	 0.0	 1	 -30.0	 30.0;
	1	 3	 0.0452	 0.1652	 0.0408	 152	 152	 152	 0.0	 0.0	 1	 -30.0	 30.0;
	2	 4	 0.057	 0.1737	 0.0368	 139	 139	 139	 0.0	 0.0	 1	 -30.0	 30.0;
	3	 4	 0.0132	 0.0379	 0.0084	 135	 135	 135	 0.0	 0.0	 1	 -30.0	 30.0;
	2	 5	 0.0472	 0.1983	 0.0418	 144	 144	 144	 0.0	 0.0	 1	 -30.0	 30.0;
	2	 6	 0.0581	 0.1763	 0.0374	 139	 139	 139	 0.0	 0.0	 1	 -30.0	 30.0;
	4	 6	 0.0119	 0.0414	 0.009	 148	 148	 148	 0.0	 0.0	 1	 -30.0	 30.0;
	5	 7	 0.046	 0.116	 0.0204	 127	 127	 127	 0.0	 0.0	 1	 -30.0	 30.0;
	6	 7	 0.0267	 0.082	 0.017	 140	 140	 140	 0.0	 0.0	 1	 -30.0	 30.0;
	6	 8	 0.012	 0.042	 0.009	 148	 148	 148	 0.0	 0.0	 1	 -30.0	 30.0;
	6	 9	 0.0	 0.208	 0.0	 142	 142	 142	 0.978	 0.0	 1	 -30.0	 30.0;
	6	 10	 0.0	 0.556	 0.0	 53	 53	 53	 0.969	 0.0	 1	 -30.0	 30.0;
	9	 11	 0.0	 0.208	 0.0	 142	 142	 142	 1.0	 0.0	 1	 -30.0	 30.0;
	9	 10	 0.0	 0.11	 0.0	 267	 267	 267	 1.0	 0.0	 1	 -30.0	 30.0;
	4	 12	 0.0	 0.256	 0.0	 115	 115	 115	 0.932	 0.0	 1	 -30.0	 30.0;
	12	 13	 0.0	 0.14	 0.0	 210	 210	 210	 1.0	 0.0	 1	 -30.0	 30.0;
	12	 14	 0.1231	 0.2559	 0.0	 29	 29	 29	 0.0	 0.0	 1	 -30.0	 30.0;
	12	 15	 0.0662	 0.1304	 0.0	 29	 29	 29	 0.0	 0.0	 1	 -30.0	 30.0;
	12	 16	 0.0945	 0.1987	 0.0	 30	 30	 30	 0.0	 0.0	 1	 -30.0	 30.0;
	14	 15	 0.221	 0.1997	 0.0	 20	 20	 20	 0.0	 0.0	 1	 -30.0	 30.0;
	16	 17	 0.0524	 0.1923	 0.0	 38	 38	 38	 0.0	 0.0	 1	 -30.0	 30.0;
	15	 18	 0.1073	 0.2185	 0.0	 29	 29	 29	 0.0	 0.0	 1	 -30.0	 30.0;
	18	 19	 0.0639	 0.1292	 0.0	 29	 29	 29	 0.0	 0.0	 1	 -30.0	 30.0;
	19	 20	 0.034	 0.068	 0.0	 29	 29	 29	 0.0	 0.0	 1	 -30.0	 30.0;
	10	 20	 0.0936	 0.209	 0.0	 30	 30	 30	 0.0	 0.0	 1	 -30.0	 30.0;
	10	 17	 0.0324	 0.0845	 0.0	 33	 33	 33	 0.0	 0.0	 1	 -30.0	 30.0;
	10	 21	 0.0348	 0.0749	 0.0	 30	 30	 30	 0.0	 0.0	 1	 -30.0	 30.0;
	10	 22	 0.0727	 0.1499	 0.0	 29	 29	 29	 0.0	 0.0	 1	 -30.0	 30.0;
	21	 22	 0.0116	 0.0236	 0.0	 29	 29	 29	 0.0	 0.0	 1	 -30.0	 30.0;
	15	 23	 0.1	 0.202	 0.0	 29	 29	 29	 0.0	 0.0	 1	 -30.0	 30.0;
	22	 24	 0.115	 0.179	 0.0	 26	 26	 26	 0.0	 0.0	 1	 -30.0	 30.0;
	23	 24	 0.132	 0.27	 0.0	 29	 29	 29	 0.0	 0.0	 1	 -30.0	 30.0;
	24	 25	 0.1885	 0.3292	 0.0	 27	 27	 27	 0.0	 0.0	 1	 -30.0	 30.0;
	25	 26	 0.2544	 0.38	 0.0	 25	 25	 25	 0.0	 0.0	 1	 -30.0	 30.0;
	25	 27	 0.1093	 0.2087	 0.0	 28	 28	 28	 0.0	 0.0	 1	 -30.0	 30.0;
	28	 27	 0.0	 0.396	 0.0	 75	 75	 75	 0.968	 0.0	 1	 -30.0	 30.0;
	27	 29	 0.2198	 0.4153	 0.0	 28	 28	 28	 0.0	 0.0	 1	 -30.0	 30.0;
	27	 30	 0.3202	 0.6027	 0.0	 28	 28	 28	 0.0	 0.0	 1	 -30.0	 30.0;
	29	 30	 0.2399	 0.4533	 0.0	 28	 28	 28	 0.0	 0.0	 1	 -30.0	 30.0;
	8	 28	 0.0636	 0.2	 0.0428	 140	 140	 140	 0.0	 0.0	 1	 -30.0	 30.0;
	6	 28	 0.0169	 0.0599	 0.013	 149	 149	 149	 0.0	 0.0	 1	 -30.0	 30.0;
];

% INFO    : === Translation Options ===
% INFO    : Phase Angle Bound:           30.0 (deg.)
% INFO    : Line Capacity Model:         stat
% INFO    : Gen Active Capacity Model:   stat
% INFO    : Gen Reactive Capacity Model: am50ag
% INFO    : Gen Active Cost Model:       stat
% INFO    : Setting Flat Start
% INFO    : Line Capacity PAB:           15.0 (deg.)
% INFO    : 
% INFO    : === Generator Classification Notes ===
% INFO    : SYNC   4   -     0.00
% INFO    : NG     2   -   100.00
% INFO    : 
% INFO    : === Generator Active Capacity Stat Model Notes ===
% INFO    : Gen at bus 1 - NG	: Pg=260.2, Pmax=360.2 -> Pmax=271   samples: 15
% INFO    : Gen at bus 2 - NG	: Pg=40.0, Pmax=140.0 -> Pmax=92   samples: 4
% INFO    : Gen at bus 5 - SYNC	: Pg=0.0, Pmax=100.0 -> Pmax=0   samples: 0
% INFO    : Gen at bus 8 - SYNC	: Pg=0.0, Pmax=100.0 -> Pmax=0   samples: 0
% INFO    : Gen at bus 11 - SYNC	: Pg=0.0, Pmax=100.0 -> Pmax=0   samples: 0
% INFO    : Gen at bus 13 - SYNC	: Pg=0.0, Pmax=100.0 -> Pmax=0   samples: 0
% INFO    : 
% INFO    : === Generator Reactive Capacity Atmost Max 50 Percent Active Model Notes ===
% INFO    : Gen at bus 2 - NG	: Pmax 92.0, Qmin -40.0, Qmax 50.0 -> Qmin -40.0, Qmax 46.0
% INFO    : 
% INFO    : === Generator Active Cost Stat Model Notes ===
% INFO    : Updated Generator Cost: NG - 0.0 20.0 0.038432 -> 0 18.4215281069 0
% INFO    : Updated Generator Cost: NG - 0.0 20.0 0.25 -> 0 52.182254017 0
% INFO    : Updated Generator Cost: SYNC - 0.0 40.0 0.01 -> 0 0.0 0
% INFO    : Updated Generator Cost: SYNC - 0.0 40.0 0.01 -> 0 0.0 0
% INFO    : Updated Generator Cost: SYNC - 0.0 40.0 0.01 -> 0 0.0 0
% INFO    : Updated Generator Cost: SYNC - 0.0 40.0 0.01 -> 0 0.0 0
% INFO    : 
% INFO    : === Generator Bounds Update Notes ===
% INFO    : 
% INFO    : === Base KV Replacement Notes ===
% INFO    : 
% INFO    : === Transformer Setting Replacement Notes ===
% WARNING : Branch 9-11 connects two different voltage levels (1.0, 11.0), changing tap ratio 0.0 => 1.0
% WARNING : Branch 9-10 connects two different voltage levels (1.0, 33.0), changing tap ratio 0.0 => 1.0
% WARNING : Branch 12-13 connects two different voltage levels (33.0, 11.0), changing tap ratio 0.0 => 1.0
% INFO    : 
% INFO    : === Line Capacity Stat Model Notes ===
% INFO    : Updated Thermal Rating: on line 1-2 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 138
% INFO    : Updated Thermal Rating: on line 1-3 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 152
% INFO    : Updated Thermal Rating: on line 2-4 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 139
% INFO    : Updated Thermal Rating: on line 3-4 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 135
% WARNING : Updated Thermal Rating Stat Model was larger than UB Model: on 2-5 : 161 , 143
% INFO    : Updated Thermal Rating: on line 2-5 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 144
% INFO    : Updated Thermal Rating: on line 2-6 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 139
% INFO    : Updated Thermal Rating: on line 4-6 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 148
% INFO    : Updated Thermal Rating: on line 5-7 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 127
% INFO    : Updated Thermal Rating: on line 6-7 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 140
% INFO    : Updated Thermal Rating: on line 6-8 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 148
% WARNING : Missing data for branch flow stat model on line 6-9 using max current model : from_basekv=132.0 to_basekv=1.0 r=0.0 x=0.208
% INFO    : Updated Thermal Rating: on transformer 6-9 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 142
% WARNING : Missing data for branch flow stat model on line 6-10 using max current model : from_basekv=132.0 to_basekv=33.0 r=0.0 x=0.556
% INFO    : Updated Thermal Rating: on transformer 6-10 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 53
% WARNING : Missing data for branch flow stat model on line 9-11 using max current model : from_basekv=1.0 to_basekv=11.0 r=0.0 x=0.208
% INFO    : Updated Thermal Rating: on transformer 9-11 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 142
% WARNING : Missing data for branch flow stat model on line 9-10 using max current model : from_basekv=1.0 to_basekv=33.0 r=0.0 x=0.11
% INFO    : Updated Thermal Rating: on transformer 9-10 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 267
% WARNING : Missing data for branch flow stat model on line 4-12 using max current model : from_basekv=132.0 to_basekv=33.0 r=0.0 x=0.256
% INFO    : Updated Thermal Rating: on transformer 4-12 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 115
% WARNING : Missing data for branch flow stat model on line 12-13 using max current model : from_basekv=33.0 to_basekv=11.0 r=0.0 x=0.14
% INFO    : Updated Thermal Rating: on transformer 12-13 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 210
% INFO    : Updated Thermal Rating: on line 12-14 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 29
% INFO    : Updated Thermal Rating: on line 12-15 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 29
% INFO    : Updated Thermal Rating: on line 12-16 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 30
% INFO    : Updated Thermal Rating: on line 14-15 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 20
% INFO    : Updated Thermal Rating: on line 16-17 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 38
% INFO    : Updated Thermal Rating: on line 15-18 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 29
% INFO    : Updated Thermal Rating: on line 18-19 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 29
% INFO    : Updated Thermal Rating: on line 19-20 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 29
% INFO    : Updated Thermal Rating: on line 10-20 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 30
% INFO    : Updated Thermal Rating: on line 10-17 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 33
% INFO    : Updated Thermal Rating: on line 10-21 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 30
% INFO    : Updated Thermal Rating: on line 10-22 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 29
% INFO    : Updated Thermal Rating: on line 21-22 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 29
% INFO    : Updated Thermal Rating: on line 15-23 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 29
% INFO    : Updated Thermal Rating: on line 22-24 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 26
% INFO    : Updated Thermal Rating: on line 23-24 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 29
% INFO    : Updated Thermal Rating: on line 24-25 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 27
% INFO    : Updated Thermal Rating: on line 25-26 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 25
% INFO    : Updated Thermal Rating: on line 25-27 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 28
% WARNING : Missing data for branch flow stat model on line 28-27 using max current model : from_basekv=132.0 to_basekv=33.0 r=0.0 x=0.396
% INFO    : Updated Thermal Rating: on transformer 28-27 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 75
% INFO    : Updated Thermal Rating: on line 27-29 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 28
% INFO    : Updated Thermal Rating: on line 27-30 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 28
% INFO    : Updated Thermal Rating: on line 29-30 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 28
% WARNING : Updated Thermal Rating Stat Model was larger than UB Model: on 8-28 : 140 , 139
% INFO    : Updated Thermal Rating: on line 8-28 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 140
% INFO    : Updated Thermal Rating: on line 6-28 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 149
% INFO    : 
% INFO    : === Line Capacity Monotonicity Notes ===
% INFO    : 
% INFO    : === Voltage Setpoint Replacement Notes ===
% INFO    : Bus 1	: V=1.06, theta=0.0 -> V=1.0, theta=0.0
% INFO    : Bus 2	: V=1.043, theta=-5.48 -> V=1.0, theta=0.0
% INFO    : Bus 3	: V=1.021, theta=-7.96 -> V=1.0, theta=0.0
% INFO    : Bus 4	: V=1.012, theta=-9.62 -> V=1.0, theta=0.0
% INFO    : Bus 5	: V=1.01, theta=-14.37 -> V=1.0, theta=0.0
% INFO    : Bus 6	: V=1.01, theta=-11.34 -> V=1.0, theta=0.0
% INFO    : Bus 7	: V=1.002, theta=-13.12 -> V=1.0, theta=0.0
% INFO    : Bus 8	: V=1.01, theta=-12.1 -> V=1.0, theta=0.0
% INFO    : Bus 9	: V=1.051, theta=-14.38 -> V=1.0, theta=0.0
% INFO    : Bus 10	: V=1.045, theta=-15.97 -> V=1.0, theta=0.0
% INFO    : Bus 11	: V=1.082, theta=-14.39 -> V=1.0, theta=0.0
% INFO    : Bus 12	: V=1.057, theta=-15.24 -> V=1.0, theta=0.0
% INFO    : Bus 13	: V=1.071, theta=-15.24 -> V=1.0, theta=0.0
% INFO    : Bus 14	: V=1.042, theta=-16.13 -> V=1.0, theta=0.0
% INFO    : Bus 15	: V=1.038, theta=-16.22 -> V=1.0, theta=0.0
% INFO    : Bus 16	: V=1.045, theta=-15.83 -> V=1.0, theta=0.0
% INFO    : Bus 17	: V=1.04, theta=-16.14 -> V=1.0, theta=0.0
% INFO    : Bus 18	: V=1.028, theta=-16.82 -> V=1.0, theta=0.0
% INFO    : Bus 19	: V=1.026, theta=-17.0 -> V=1.0, theta=0.0
% INFO    : Bus 20	: V=1.03, theta=-16.8 -> V=1.0, theta=0.0
% INFO    : Bus 21	: V=1.033, theta=-16.42 -> V=1.0, theta=0.0
% INFO    : Bus 22	: V=1.033, theta=-16.41 -> V=1.0, theta=0.0
% INFO    : Bus 23	: V=1.027, theta=-16.61 -> V=1.0, theta=0.0
% INFO    : Bus 24	: V=1.021, theta=-16.78 -> V=1.0, theta=0.0
% INFO    : Bus 25	: V=1.017, theta=-16.35 -> V=1.0, theta=0.0
% INFO    : Bus 26	: V=1.0, theta=-16.77 -> V=1.0, theta=0.0
% INFO    : Bus 27	: V=1.023, theta=-15.82 -> V=1.0, theta=0.0
% INFO    : Bus 28	: V=1.007, theta=-11.97 -> V=1.0, theta=0.0
% INFO    : Bus 29	: V=1.003, theta=-17.06 -> V=1.0, theta=0.0
% INFO    : Bus 30	: V=0.992, theta=-17.94 -> V=1.0, theta=0.0
% INFO    : 
% INFO    : === Generator Setpoint Replacement Notes ===
% INFO    : Gen at bus 1	: Pg=260.2, Qg=-16.1 -> Pg=135.5, Qg=5.0
% INFO    : Gen at bus 1	: Vg=1.06 -> Vg=1.0
% INFO    : Gen at bus 2	: Pg=40.0, Qg=50.0 -> Pg=46.0, Qg=3.0
% INFO    : Gen at bus 2	: Vg=1.045 -> Vg=1.0
% INFO    : Gen at bus 5	: Pg=0.0, Qg=37.0 -> Pg=0.0, Qg=0.0
% INFO    : Gen at bus 5	: Vg=1.01 -> Vg=1.0
% INFO    : Gen at bus 8	: Pg=0.0, Qg=37.3 -> Pg=0.0, Qg=15.0
% INFO    : Gen at bus 8	: Vg=1.01 -> Vg=1.0
% INFO    : Gen at bus 11	: Pg=0.0, Qg=16.2 -> Pg=0.0, Qg=9.0
% INFO    : Gen at bus 11	: Vg=1.082 -> Vg=1.0
% INFO    : Gen at bus 13	: Pg=0.0, Qg=10.6 -> Pg=0.0, Qg=9.0
% INFO    : Gen at bus 13	: Vg=1.071 -> Vg=1.0
% INFO    : 
% INFO    : === Writing Matpower Case File Notes ===
