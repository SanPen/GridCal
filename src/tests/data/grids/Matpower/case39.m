function mpc = case39
%CASE39 Power flow data for 39 bus New England system.
%   Please see CASEFORMAT for details on the case file format.
%
%   Data taken from [1] with the following modifications/additions:
%
%       - renumbered gen buses consecutively (as in [2] and [4])
%       - added Pmin = 0 for all gens
%       - added Qmin, Qmax for gens at 31 & 39 (copied from gen at 35)
%       - added Vg based on V in bus data (missing for bus 39)
%       - added Vg, Pg, Pd, Qd at bus 39 from [2] (same in [4])
%       - added Pmax at bus 39: Pmax = Pg + 100
%       - added line flow limits and area data from [4]
%       - added voltage limits, Vmax = 1.06, Vmin = 0.94
%       - added identical quadratic generator costs
%       - increased Pmax for gen at bus 34 from 308 to 508
%         (assumed typo in [1], makes initial solved case feasible)
%       - re-solved power flow
% 
%   Notes:
%       - Bus 39, its generator and 2 connecting lines were added
%         (by authors of [1]) to represent the interconnection with
%         the rest of the eastern interconnect, and did not include
%         Vg, Pg, Qg, Pd, Qd, Pmin, Pmax, Qmin or Qmax.
%       - As the swing bus, bus 31 did not include and Q limits.
%       - The voltages, etc in [1] appear to be quite close to the
%         power flow solution of the case before adding bus 39 with
%         it's generator and connecting branches, though the solution
%         is not exact.
%       - Explicit voltage setpoints for gen buses are not given, so
%         they are taken from the bus data, however this results in two
%         binding Q limits at buses 34 & 37, so the corresponding
%         voltages have probably deviated from their original setpoints.
%       - The generator locations and types are as follows:
%           1   30      hydro
%           2   31      nuke01
%           3   32      nuke02
%           4   33      fossil02
%           5   34      fossil01
%           6   35      nuke03
%           7   36      fossil04
%           8   37      nuke04
%           9   38      nuke05
%           10  39      interconnection to rest of US/Canada
%
%   This is a solved power flow case, but it includes the following
%   violations:
%       - Pmax violated at bus 31: Pg = 677.87, Pmax = 646
%       - Qmin violated at bus 37: Qg = -1.37,  Qmin = 0
%
%   References:
%   [1] G. W. Bills, et.al., "On-Line Stability Analysis Study"
%       RP90-1 Report for the Edison Electric Institute, October 12, 1970,
%       pp. 1-20 - 1-35.
%       prepared by E. M. Gulachenski - New England Electric System
%                   J. M. Undrill     - General Electric Co.
%       "generally representative of the New England 345 KV system, but is
%        not an exact or complete model of any past, present or projected
%        configuration of the actual New England 345 KV system.
%   [2] M. A. Pai, Energy Function Analysis for Power System Stability,
%       Kluwer Academic Publishers, Boston, 1989.
%       (references [3] as source of data)
%   [3] Athay, T.; Podmore, R.; Virmani, S., "A Practical Method for the
%       Direct Analysis of Transient Stability," IEEE Transactions on Power
%       Apparatus and Systems , vol.PAS-98, no.2, pp.573-584, March 1979.
%       URL: https://doi.org/10.1109/TPAS.1979.319407
%       (references [1] as source of data)
%   [4] Data included with TC Calculator at http://www.pserc.cornell.edu/tcc/
%       for 39-bus system.

%   MATPOWER

%% MATPOWER Case Format : Version 2
mpc.version = '2';

%%-----  Power Flow Data  -----%%
%% system MVA base
mpc.baseMVA = 100;

%% bus data
%	bus_i	type	Pd	Qd	Gs	Bs	area	Vm	Va	baseKV	zone	Vmax	Vmin
mpc.bus = [
	1	1	97.6	44.2	0	0	2	1.0393836	-13.536602	345	1	1.06	0.94;
	2	1	0	0	0	0	2	1.0484941	-9.7852666	345	1	1.06	0.94;
	3	1	322	2.4	0	0	2	1.0307077	-12.276384	345	1	1.06	0.94;
	4	1	500	184	0	0	1	1.00446	-12.626734	345	1	1.06	0.94;
	5	1	0	0	0	0	1	1.0060063	-11.192339	345	1	1.06	0.94;
	6	1	0	0	0	0	1	1.0082256	-10.40833	345	1	1.06	0.94;
	7	1	233.8	84	0	0	1	0.99839728	-12.755626	345	1	1.06	0.94;
	8	1	522	176.6	0	0	1	0.99787232	-13.335844	345	1	1.06	0.94;
	9	1	6.5	-66.6	0	0	1	1.038332	-14.178442	345	1	1.06	0.94;
	10	1	0	0	0	0	1	1.0178431	-8.170875	345	1	1.06	0.94;
	11	1	0	0	0	0	1	1.0133858	-8.9369663	345	1	1.06	0.94;
	12	1	8.53	88	0	0	1	1.000815	-8.9988236	345	1	1.06	0.94;
	13	1	0	0	0	0	1	1.014923	-8.9299272	345	1	1.06	0.94;
	14	1	0	0	0	0	1	1.012319	-10.715295	345	1	1.06	0.94;
	15	1	320	153	0	0	3	1.0161854	-11.345399	345	1	1.06	0.94;
	16	1	329	32.3	0	0	3	1.0325203	-10.033348	345	1	1.06	0.94;
	17	1	0	0	0	0	2	1.0342365	-11.116436	345	1	1.06	0.94;
	18	1	158	30	0	0	2	1.0315726	-11.986168	345	1	1.06	0.94;
	19	1	0	0	0	0	3	1.0501068	-5.4100729	345	1	1.06	0.94;
	20	1	680	103	0	0	3	0.99101054	-6.8211783	345	1	1.06	0.94;
	21	1	274	115	0	0	3	1.0323192	-7.6287461	345	1	1.06	0.94;
	22	1	0	0	0	0	3	1.0501427	-3.1831199	345	1	1.06	0.94;
	23	1	247.5	84.6	0	0	3	1.0451451	-3.3812763	345	1	1.06	0.94;
	24	1	308.6	-92.2	0	0	3	1.038001	-9.9137585	345	1	1.06	0.94;
	25	1	224	47.2	0	0	2	1.0576827	-8.3692354	345	1	1.06	0.94;
	26	1	139	17	0	0	2	1.0525613	-9.4387696	345	1	1.06	0.94;
	27	1	281	75.5	0	0	2	1.0383449	-11.362152	345	1	1.06	0.94;
	28	1	206	27.6	0	0	3	1.0503737	-5.9283592	345	1	1.06	0.94;
	29	1	283.5	26.9	0	0	3	1.0501149	-3.1698741	345	1	1.06	0.94;
	30	2	0	0	0	0	2	1.0499	-7.3704746	345	1	1.06	0.94;
	31	3	9.2	4.6	0	0	1	0.982	0	345	1	1.06	0.94;
	32	2	0	0	0	0	1	0.9841	-0.1884374	345	1	1.06	0.94;
	33	2	0	0	0	0	3	0.9972	-0.19317445	345	1	1.06	0.94;
	34	2	0	0	0	0	3	1.0123	-1.631119	345	1	1.06	0.94;
	35	2	0	0	0	0	3	1.0494	1.7765069	345	1	1.06	0.94;
	36	2	0	0	0	0	3	1.0636	4.4684374	345	1	1.06	0.94;
	37	2	0	0	0	0	2	1.0275	-1.5828988	345	1	1.06	0.94;
	38	2	0	0	0	0	3	1.0265	3.8928177	345	1	1.06	0.94;
	39	2	1104	250	0	0	1	1.03	-14.535256	345	1	1.06	0.94;
];

%% generator data
%	bus	Pg	Qg	Qmax	Qmin	Vg	mBase	status	Pmax	Pmin	Pc1	Pc2	Qc1min	Qc1max	Qc2min	Qc2max	ramp_agc	ramp_10	ramp_30	ramp_q	apf
mpc.gen = [
	30	250	161.762	400	140	1.0499	100	1	1040	0	0	0	0	0	0	0	0	0	0	0	0;
	31	677.871	221.574	300	-100	0.982	100	1	646	0	0	0	0	0	0	0	0	0	0	0	0;
	32	650	206.965	300	150	0.9841	100	1	725	0	0	0	0	0	0	0	0	0	0	0	0;
	33	632	108.293	250	0	0.9972	100	1	652	0	0	0	0	0	0	0	0	0	0	0	0;
	34	508	166.688	167	0	1.0123	100	1	508	0	0	0	0	0	0	0	0	0	0	0	0;
	35	650	210.661	300	-100	1.0494	100	1	687	0	0	0	0	0	0	0	0	0	0	0	0;
	36	560	100.165	240	0	1.0636	100	1	580	0	0	0	0	0	0	0	0	0	0	0	0;
	37	540	-1.36945	250	0	1.0275	100	1	564	0	0	0	0	0	0	0	0	0	0	0	0;
	38	830	21.7327	300	-150	1.0265	100	1	865	0	0	0	0	0	0	0	0	0	0	0	0;
	39	1000	78.4674	300	-100	1.03	100	1	1100	0	0	0	0	0	0	0	0	0	0	0	0;
];

%% branch data
%	fbus	tbus	r	x	b	rateA	rateB	rateC	ratio	angle	status	angmin	angmax
mpc.branch = [
	1	2	0.0035	0.0411	0.6987	600	600	600	0	0	1	-360	360;
	1	39	0.001	0.025	0.75	1000	1000	1000	0	0	1	-360	360;
	2	3	0.0013	0.0151	0.2572	500	500	500	0	0	1	-360	360;
	2	25	0.007	0.0086	0.146	500	500	500	0	0	1	-360	360;
	2	30	0	0.0181	0	900	900	2500	1.025	0	1	-360	360;
	3	4	0.0013	0.0213	0.2214	500	500	500	0	0	1	-360	360;
	3	18	0.0011	0.0133	0.2138	500	500	500	0	0	1	-360	360;
	4	5	0.0008	0.0128	0.1342	600	600	600	0	0	1	-360	360;
	4	14	0.0008	0.0129	0.1382	500	500	500	0	0	1	-360	360;
	5	6	0.0002	0.0026	0.0434	1200	1200	1200	0	0	1	-360	360;
	5	8	0.0008	0.0112	0.1476	900	900	900	0	0	1	-360	360;
	6	7	0.0006	0.0092	0.113	900	900	900	0	0	1	-360	360;
	6	11	0.0007	0.0082	0.1389	480	480	480	0	0	1	-360	360;
	6	31	0	0.025	0	1800	1800	1800	1.07	0	1	-360	360;
	7	8	0.0004	0.0046	0.078	900	900	900	0	0	1	-360	360;
	8	9	0.0023	0.0363	0.3804	900	900	900	0	0	1	-360	360;
	9	39	0.001	0.025	1.2	900	900	900	0	0	1	-360	360;
	10	11	0.0004	0.0043	0.0729	600	600	600	0	0	1	-360	360;
	10	13	0.0004	0.0043	0.0729	600	600	600	0	0	1	-360	360;
	10	32	0	0.02	0	900	900	2500	1.07	0	1	-360	360;
	12	11	0.0016	0.0435	0	500	500	500	1.006	0	1	-360	360;
	12	13	0.0016	0.0435	0	500	500	500	1.006	0	1	-360	360;
	13	14	0.0009	0.0101	0.1723	600	600	600	0	0	1	-360	360;
	14	15	0.0018	0.0217	0.366	600	600	600	0	0	1	-360	360;
	15	16	0.0009	0.0094	0.171	600	600	600	0	0	1	-360	360;
	16	17	0.0007	0.0089	0.1342	600	600	600	0	0	1	-360	360;
	16	19	0.0016	0.0195	0.304	600	600	2500	0	0	1	-360	360;
	16	21	0.0008	0.0135	0.2548	600	600	600	0	0	1	-360	360;
	16	24	0.0003	0.0059	0.068	600	600	600	0	0	1	-360	360;
	17	18	0.0007	0.0082	0.1319	600	600	600	0	0	1	-360	360;
	17	27	0.0013	0.0173	0.3216	600	600	600	0	0	1	-360	360;
	19	20	0.0007	0.0138	0	900	900	2500	1.06	0	1	-360	360;
	19	33	0.0007	0.0142	0	900	900	2500	1.07	0	1	-360	360;
	20	34	0.0009	0.018	0	900	900	2500	1.009	0	1	-360	360;
	21	22	0.0008	0.014	0.2565	900	900	900	0	0	1	-360	360;
	22	23	0.0006	0.0096	0.1846	600	600	600	0	0	1	-360	360;
	22	35	0	0.0143	0	900	900	2500	1.025	0	1	-360	360;
	23	24	0.0022	0.035	0.361	600	600	600	0	0	1	-360	360;
	23	36	0.0005	0.0272	0	900	900	2500	1	0	1	-360	360;
	25	26	0.0032	0.0323	0.531	600	600	600	0	0	1	-360	360;
	25	37	0.0006	0.0232	0	900	900	2500	1.025	0	1	-360	360;
	26	27	0.0014	0.0147	0.2396	600	600	600	0	0	1	-360	360;
	26	28	0.0043	0.0474	0.7802	600	600	600	0	0	1	-360	360;
	26	29	0.0057	0.0625	1.029	600	600	600	0	0	1	-360	360;
	28	29	0.0014	0.0151	0.249	600	600	600	0	0	1	-360	360;
	29	38	0.0008	0.0156	0	1200	1200	2500	1.025	0	1	-360	360;
];

%%-----  OPF Data  -----%%
%% generator cost data
%	1	startup	shutdown	n	x1	y1	...	xn	yn
%	2	startup	shutdown	n	c(n-1)	...	c0
mpc.gencost = [
	2	0	0	3	0.01	0.3	0.2;
	2	0	0	3	0.01	0.3	0.2;
	2	0	0	3	0.01	0.3	0.2;
	2	0	0	3	0.01	0.3	0.2;
	2	0	0	3	0.01	0.3	0.2;
	2	0	0	3	0.01	0.3	0.2;
	2	0	0	3	0.01	0.3	0.2;
	2	0	0	3	0.01	0.3	0.2;
	2	0	0	3	0.01	0.3	0.2;
	2	0	0	3	0.01	0.3	0.2;
];
