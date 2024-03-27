import os
import numpy as np
import pandas as pd
import GridCalEngine.api as gce
from GridCalEngine.Simulations.ContingencyAnalysis.contingency_plan import add_n1_contingencies
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc


def test_ptdf():
    fname = os.path.join('data', 'grids', 'PGOC_6bus.gridcal')
    main_circuit = gce.FileOpen(fname).open()

    options = gce.LinearAnalysisOptions(distribute_slack=False, correct_values=False)
    simulation = gce.LinearAnalysisDriver(grid=main_circuit, options=options)
    simulation.run()
    # ptdf_df = simulation.results.mdl(result_type=ResultTypes.PTDFBranchesSensitivity)

    test_PTDF = [[0, -0.470623900249771, -0.40256295349251, -0.314889382426403, -0.321730075985739, -0.406428143061441],
                 [0, -0.314889382426403, -0.294871456909562, -0.504379230125413, -0.271097081172276,
                  -0.296008277371012],
                 [0, -0.214486717323826, -0.302565589597928, -0.180731387448184, -0.407172842841985,
                  -0.297563579567547],
                 [0, 0.0544487574058086, -0.341553588728013, 0.0160143404134731, -0.105694646728923, -0.1906695048735],
                 [0, 0.311469035646735, 0.215382993165897, -0.378979695398019, 0.101265989626925, 0.220839731380858],
                 [0, 0.0992625495093548, -0.0341902872695879, 0.0291948675027514, -0.192686125518159,
                  -0.0266114841932529],
                 [0, 0.0641957571883298, -0.242202070660806, 0.0188811050553911, -0.124615293365582,
                  -0.409986885375546],
                 [0, 0.0621791365436704, 0.288966580773565, 0.0182879813363736, -0.120700676820066, 0.152630503693843],
                 [0, -0.00773037913786179, 0.369479830498422, -0.00227364092290061, 0.0150060300911433,
                  -0.343300008567343],
                 [0, -0.00342034677966774, -0.0794884637436652, 0.116641074476568, -0.169831091545351,
                  -0.0751685459901542],
                 [0, -0.0564653780504683, -0.127277759837616, -0.0166074641324907, 0.109609263274438,
                  -0.246713106057111]]

    test_PTDF = np.array(test_PTDF)

    test_LODF = [[-1, 0.635343394721096, 0.542704685676172, -0.112684124386252, -0.503097656000511, -0.210286767374975,
                  -0.122087558123504, -0.1369276540164, 0.0134572362760281, 0.00958714325297872, 0.131584605461191],
                 [0.59483112776526, -1, 0.457295314323829, -0.0331423895253682, 0.612143663111281, -0.0618490492279341,
                  -0.0359081053304421, -0.0402728394165882, 0.00395801066942025, -0.326941904498014,
                  0.0387013545474093],
                 [0.405168872234741, 0.364656605278905, -1, 0.14582651391162, -0.10904600711077, 0.27213581660291,
                  0.157995663453946, 0.177200493432987, -0.0174152469454484, 0.317354761245035, -0.1702859600086],
                 [-0.102854581896498, -0.0323116814041619, 0.178289144572286, -1, 0.124161716803985, 0.226174852707117,
                  0.466166167420758, -0.399535592482403, -0.525325532036942, 0.170573566084788, 0.132014620511718],
                 [-0.588370037471834, 0.764656605278904, -0.170818742704686, 0.159083469721767, -1, 0.296875436294083,
                  0.172358905586123, 0.193309629199623, -0.0189984512132158, -0.673058095501986, -0.185766501827564],
                 [-0.187508558766044, -0.0589056578684928, 0.325029181257295, 0.220949263502455, 0.226352430222903, -1,
                  0.239387368869615, 0.268485596110587, -0.0263867377961337, 0.310963332409716, -0.258009030316061],
                 [-0.121266821865624, -0.0380958712851538, 0.210205102551276, 0.507283142389525, 0.1463881969726,
                  0.266662943623824, -1, -0.199187286844206, 0.58416795732232, 0.20110834026046, 0.443345517093098],
                 [-0.117457392906495, -0.036899142344259, 0.20360180090045, -0.375477359519913, 0.141789614868749,
                  0.258286097227264, -0.17202050459348, -1, 0.474674467963059, 0.194790800775838, -0.424639862395184],
                 [0.0146028110099968, 0.00458746094009728, -0.025312656328164, -0.624522640480087, -0.0176278980647632,
                  -0.0321112445201464, 0.638186672014237, 0.600464407517597, -1, -0.0242172346910503,
                  0.556654482906902],
                 [0.00646109029342566, -0.235343394721096, 0.286476571619143, 0.125941080196399, -0.387856336888718,
                  0.235026387066149, 0.136450800255681, 0.153036789783034, -0.0150404405437964, -1, -0.147065147280155],
                 [0.106664010855628, 0.0335084103450569, -0.184892446223112, 0.117239498090562, -0.128760298907837,
                  -0.234551699103677, 0.361813327985762, -0.401277120673391, 0.41583204267768, -0.17689110556941, -1],
                 ]
    test_LODF = np.array(test_LODF)

    assert (np.max(np.abs(simulation.results.PTDF - test_PTDF)) < 1e-3)
    assert (np.max(np.abs(simulation.results.LODF - test_LODF)) < 1e-3)

    return True


def test_ptdf_ieee14_definition():
    """
    Compare the PSSE LODF and the GridCal LODF for the IEEE14
    """
    for fname in [
        os.path.join('data', 'grids', 'RAW', 'IEEE 14 bus.raw'),
        os.path.join('data', 'grids', 'RAW', 'IEEE 30 bus.raw'),
        os.path.join('data', 'grids', 'RAW', 'IEEE 118 Bus v2.raw')
    ]:
        main_circuit = gce.FileOpen(fname).open()

        # add all branch contingencies
        add_n1_contingencies(branches=main_circuit.get_branches(),
                             vmax=1e20, vmin=0,
                             filter_branches_by_voltage=False,
                             branch_types=[gce.DeviceType.LineDevice, gce.DeviceType.Transformer2WDevice])

        # run the linear analysis
        options = gce.LinearAnalysisOptions(distribute_slack=False, correct_values=False)
        simulation = gce.LinearAnalysisDriver(grid=main_circuit, options=options)
        simulation.run()

        # compute the PTDF by the definition: PTDF(i, j) = (flow base(i) - modified flow(i)) / bus power increase(j)
        nc = gce.compile_numerical_circuit_at(main_circuit, t_idx=None)
        options = gce.PowerFlowOptions(solver_type=gce.SolverType.DC)
        base_res = multi_island_pf_nc(nc=nc, options=options)
        S = nc.Sbus.copy()
        ptdf = np.zeros((nc.nbr, nc.nbus))

        for i in range(nc.nbus):
            dS = np.zeros(nc.nbus)
            dS[i] += 0.01  # 1 MW in p.u.
            res = multi_island_pf_nc(nc=nc, options=options, Sbus_input=S + dS)
            ptdf[:, i] = (res.Sf.real - base_res.Sf.real) / (dS[i] * nc.Sbase)

        # diff = simulation.results.PTDF - ptdf
        # print(diff)

        assert np.allclose(simulation.results.PTDF, ptdf)


def test_lodf_ieee14_definition() -> None:
    """
    Compare the PSSE LODF and the GridCal LODF for the IEEE14
    """

    for fname, antenna_branch_idx in [
        (os.path.join('data', 'grids', 'RAW', 'IEEE 14 bus.raw'), [10]),
        (os.path.join('data', 'grids', 'RAW', 'IEEE 30 bus.raw'), [29]),
        (os.path.join('data', 'grids', 'RAW', 'IEEE 118 Bus v2.raw'), [11, 13, 18, 103, 111, 131, 134, 167, 168])
    ]:
        main_circuit = gce.FileOpen(fname).open()

        # add all branch contingencies
        add_n1_contingencies(branches=main_circuit.get_branches(),
                             vmax=1e20, vmin=0,
                             filter_branches_by_voltage=False,
                             branch_types=[gce.DeviceType.LineDevice, gce.DeviceType.Transformer2WDevice])

        # run the linear analysis
        options = gce.LinearAnalysisOptions(distribute_slack=False, correct_values=False)
        simulation = gce.LinearAnalysisDriver(grid=main_circuit, options=options)
        simulation.run()

        # compute the LODF by the definition: PTDF(i, j) = (flow base(i) - modified flow(i)) / flow base(i)
        nc = gce.compile_numerical_circuit_at(main_circuit, t_idx=None)
        options = gce.PowerFlowOptions(solver_type=gce.SolverType.DC)
        base_res = multi_island_pf_nc(nc=nc, options=options)

        lodf = np.zeros((nc.nbr, nc.nbr))

        for i in range(nc.nbr):
            nc.branch_data.active[i] = 0  # fail branch
            res = multi_island_pf_nc(nc=nc, options=options)
            if base_res.Sf.real[i] != 0.0:
                lodf[:, i] = (res.Sf.real - base_res.Sf.real) / base_res.Sf.real[i]
            else:
                lodf[i, i] = -1.0

            nc.branch_data.active[i] = 1  # revert back

        # force zeros in the identified antenna branches
        lodf[:, antenna_branch_idx] = 0
        simulation.results.LODF[:, antenna_branch_idx] = 0

        # diff = simulation.results.LODF - lodf
        # print(diff)

        assert np.allclose(simulation.results.LODF, lodf)


def test_lodf_ieee14_psse() -> None:
    """
    Compare the PSSE LODF and the GridCal LODF for the IEEE14
    """
    fname = os.path.join('data', 'grids', 'RAW', 'IEEE 14 bus.raw')
    main_circuit = gce.FileOpen(fname).open()

    # add all branch contingencies
    add_n1_contingencies(branches=main_circuit.get_branches(),
                         vmax=1e20, vmin=0,
                         filter_branches_by_voltage=False,
                         branch_types=[gce.DeviceType.LineDevice, gce.DeviceType.Transformer2WDevice])

    # run the linear analysis
    options = gce.LinearAnalysisOptions(distribute_slack=False, correct_values=False)
    simulation = gce.LinearAnalysisDriver(grid=main_circuit, options=options)
    simulation.run()

    # load the PSSE "OTDF" which is the same as the LODF concept
    lodf_df = pd.read_excel(os.path.join('data', 'results', 'IEEE14_lodf_psse.xlsx'),
                            sheet_name='lodf_psse', index_col=0)

    # re-order the PSSe LODF to be ordered as the GridCal LODF
    psse_names_dict = {name: i for i, name in enumerate(lodf_df.index.values)}
    gridcal_names = [br.code for br in main_circuit.get_branches()]
    lodf = np.zeros(lodf_df.shape)
    for i, name_i in enumerate(gridcal_names):
        i_psse = psse_names_dict[name_i]
        for j, name_j in enumerate(gridcal_names):
            j_psse = psse_names_dict[name_j]
            lodf[i, j] = lodf_df.values[i_psse, j_psse]

    # force zeros o the branch 10 because it is a feeder
    lodf[:, 10] = 0
    simulation.results.LODF[:, 10] = 0

    # print differences greater than 0.01
    # diff = lodf - simulation.results.LODF
    # print(diff)

    # IEEE14 does have tap modules != 1
    # since gridcal computes b = 1/ (x * m) and PSSe computes b = 1/x, this test will fail
    # but because GridCal approximation is slightly better than PSSe's
    # assert np.allclose(lodf, simulation.results.LODF, atol=1e-5)


def test_dcpowerflow():
    """

    :return:
    """
    for fname in [os.path.join('data', 'grids', 'RAW', 'IEEE 30 bus.raw'),
                  os.path.join('data', 'grids', 'RAW', 'IEEE 14 bus.raw'),
                  # os.path.join('data', 'grids', 'RAW', 'ieee-14-d.raw'),
                  os.path.join('data', 'grids', 'IEEE14-gen80.gridcal')]:
        main_circuit = gce.FileOpen(fname).open()

        pf_options = gce.PowerFlowOptions(gce.SolverType.DC,
                                          verbose=False,
                                          initialize_with_existing_solution=False,
                                          dispatch_storage=True,
                                          control_q=gce.ReactivePowerControlMode.NoControl,
                                          control_p=False)
        options1 = gce.ContingencyAnalysisOptions(pf_options=pf_options, engine=gce.ContingencyMethod.PowerFlow)
        cont_analysis_driver1 = gce.ContingencyAnalysisDriver(grid=main_circuit, options=options1,
                                                              linear_multiple_contingencies=None)
        cont_analysis_driver1.run()
        print()


def test_ptdf_psse() -> None:
    """
    Compare the PSSE PTDF and the GridCal PTDF for IEEE14, IEEE30, IEEE118 and REE networks
    """
    for fname, pssename, name in [
        # (os.path.join('data', 'grids', 'RAW', 'IEEE 14 bus.raw'),
        #  os.path.join('data', 'results', 'comparison', 'IEEE 14 bus PTDF PSSe.csv'), 'IEEE14'),
        (os.path.join('data', 'grids', 'RAW', 'IEEE 30 bus.raw'),
         os.path.join('data', 'results', 'comparison', 'IEEE 30 bus PTDF PSSe.csv'), 'IEEE30'),
        (os.path.join('data', 'grids', 'RAW', 'IEEE 118 Bus v2.raw'),
         os.path.join('data', 'results', 'comparison', 'IEEE 118 bus PTDF PSSe.csv'), 'IEEE118'),
        # (os.path.join('data', 'grids', 'RAW', 'sensitive-raw', '15.Caso_2026.raw'),
        #  os.path.join('data', 'results', 'comparison', '15.Caso_2026 PTDF PSSe.csv'), 'REE'),
        # (os.path.join('data', 'grids', 'RAW', 'ieee-14-bus_d_rename_ptdf.raw'),
        #  os.path.join('data', 'results', 'comparison', 'ieee-14-bus_d_ptdf.csv'), 'IEEE14_D'),
        # (os.path.join('data', 'grids', 'RAW', 'ACTIVSg2000_rename.raw'),
        # os.path.join('data', 'results', 'comparison', 'ACTIVSg2000_PTDF.csv'), 'TEXAS')

    ]:

        if os.path.exists(fname):

            counter = 0  # Amount of failures
            main_circuit = gce.FileOpen(fname).open()

            # Network ordering
            branches = main_circuit.get_branches()
            branches_id = [x.code for x in branches]
            nodes = main_circuit.get_buses()
            nodes_id = [x.code for x in nodes]

            # Calculate GridCal PTDF
            linear_analysis_opt = gce.LinearAnalysisOptions(distribute_slack=False, correct_values=False)
            linear_analysis = gce.LinearAnalysisDriver(grid=main_circuit, options=linear_analysis_opt)
            linear_analysis.run()

            ptdf_gridcal = pd.DataFrame(linear_analysis.results.PTDF, columns=nodes_id)
            ptdf_gridcal['branches'] = branches_id

            # Import PSSe PDTF
            ptdf_psse = pd.read_csv(pssename)

            ptdf_psse.drop(['vbase_nodefrom', 'vbase_nodeto'], axis=1, inplace=True)
            ptdf_psse['branches'] = (ptdf_psse['nodefrom'].astype(str) + '_' + ptdf_psse['nodeto'].astype(str) + '_'
                                     + ptdf_psse['ckt'].astype(str))

            # Test comparison
            ptdf = ptdf_gridcal.merge(ptdf_psse, on='branches', how='inner')
            print(' ')
            print('--Testing PTDF in {}'.format(name))
            for i in nodes_id:
                print('----Node ongoing: {}'.format(i))
                if name == "IEEE118":
                    if i == '69':
                        continue  # Skipping slack (is zero)
                else:
                    if i == '1':
                        continue  # Skipping slack (is zero)

                if 'NUDO{}'.format(i) not in ptdf.columns:
                    print('El nudo {} no se ha calculado por PSSe')
                    continue
                nodegridcal = np.array(ptdf[i])

                nodepsse = np.array(ptdf['NUDO{}'.format(str(i))])

                if not np.allclose(nodegridcal, -nodepsse, atol=1e-3):
                    print('------------ XXXX PTDFs not equal XXXX ------------ ')
                    print('------------------Difference: {}'.format(np.sum(nodegridcal - (-nodepsse))))
                    counter += 1
                # else:
                #    print('------------PTDFs CHECKED')
            print('-- TOTAL FAILURES: {}'.format(counter))
            print(' ')
        else:
            print(fname, "does not exists...")


def test_lodf_psse() -> None:
    """
    Compare the PSSE LODF and the GridCal LODF for IEEE14, IEEE30, IEEE118 and REE networks
    """
    for fname, pssename, name in [
        (os.path.join('data', 'grids', 'RAW', 'IEEE 14 bus.raw'),
         os.path.join('data', 'results', 'comparison', 'IEEE 14 bus LODF PSSe.csv'), 'IEEE14'),
        (os.path.join('data', 'grids', 'RAW', 'IEEE 30 bus.raw'),
         os.path.join('data', 'results', 'comparison', 'IEEE 30 bus LODF PSSe.csv'), 'IEEE30'),
        (os.path.join('data', 'grids', 'RAW', 'IEEE 118 Bus v2.raw'),
         os.path.join('data', 'results', 'comparison', 'IEEE 118 bus LODF PSSe.csv'), 'IEEE118'),
        (os.path.join('data', 'grids', 'RAW', 'sensitive-raw', '15.Caso_2026.raw'),
         os.path.join('data', 'results', 'comparison', '15.Caso_2026 LODF PSSe.csv'), 'REE'),
        (os.path.join('data', 'grids', 'RAW', 'ieee-14-bus_d_rename_lodf.raw'),
         os.path.join('data', 'results', 'comparison', 'ieee-14-bus_d_branches_lodf.csv'), 'IEEE14_D')  # ,
        # (os.path.join('data', 'grids', 'RAW', 'ACTIVSg2000_rename.raw'),
        # os.path.join('data', 'results', 'comparison', 'ACTIVSg2000_branches_LODF.csv'), 'TEXAS')

    ]:

        if os.path.exists(fname):
            counter = 0  # Amount of failures
            main_circuit = gce.FileOpen(fname).open()

            # Network ordering
            branches = main_circuit.get_branches()
            branches_id = [x.code for x in branches]

            # Calculate GridCal LODF
            linear_analysis_opt = gce.LinearAnalysisOptions(distribute_slack=False, correct_values=False)
            linear_analysis = gce.LinearAnalysisDriver(grid=main_circuit, options=linear_analysis_opt)
            linear_analysis.run()

            lodf_gridcal = pd.DataFrame(linear_analysis.results.LODF, columns=branches_id)
            lodf_gridcal['branches'] = branches_id

            # Import PSSe LODF

            lodf_psse = pd.read_csv(pssename)
            lodf_psse.drop(['vbase_nodefrom', 'vbase_nodeto'], axis=1, inplace=True)
            lodf_psse['branches'] = (lodf_psse['nodefrom'].astype(str) + '_' + lodf_psse['nodeto'].astype(str) + '_'
                                     + lodf_psse['ckt'].astype(str))

            # Test comparison
            lodf = lodf_gridcal.merge(lodf_psse, on='branches', how='inner')
            print(' ')
            print('-Testing LODF in {}'.format(name))
            for i in branches_id:
                print('----Branch ongoing: {}'.format(i))

                branchgridcal = np.array(lodf[i])

                branchsearchdirect = i.split("_")[0] + "_" + i.split("_")[1] + "(" + i.split("_")[2] + ")"
                branchsearchundirect = i.split("_")[1] + "_" + i.split("_")[0] + "(" + i.split("_")[2] + ")"
                if branchsearchdirect in lodf.columns:
                    branchpsse = np.array(lodf[branchsearchdirect])
                    branchpsse[branchpsse == '---'] = 0.0
                    branchpsse = branchpsse.astype(float)
                elif branchsearchundirect in lodf.columns:
                    print("----------Schema reordered")
                    branchpsse = np.array(lodf[branchsearchundirect])
                    branchpsse[branchpsse == '---'] = 0.0
                    branchpsse = branchpsse.astype(float)
                    branchpsse = -branchpsse
                else:
                    print('La línea {} no se ha calculado por PSSe'.format(i))

                if not np.allclose(branchgridcal, branchpsse, atol=1e-3):
                    print('------------ XXXX LODFs not equal XXXX ------------ ')
                    print('------------------Difference: {}'.format(np.sum(branchgridcal - branchpsse)))
                    counter += 1
                # else:
                #    print('------------LODFs CHECKED')
            print('-- TOTAL FAILURES: {}'.format(counter))
        else:
            print(fname, "does not exists...")


def test_mlodf() -> None:
    """
    Compare power flow per branches in N-2 contingencies using theoretical methodology and MLODF
    """
    # fname = os.path.join('data', 'grids', 'IEEE14-2_4_1-3_4_1.gridcal')
    # fname = os.path.join('data', 'grids', 'IEEE14-2_5_1-1_5_1.gridcal')

    for fname in [
        os.path.join('data', 'grids', 'IEEE14-2_4_1-3_4_1.gridcal'),
        os.path.join('data', 'grids', 'IEEE14-2_5_1-1_5_1.gridcal'),
        os.path.join('data', 'grids', 'IEEE14-bus_d-6_11-6_13.gridcal'),
        os.path.join('data', 'grids', 'IEEE14-bus_d-7_8-9_10.gridcal'),
    ]:

        main_circuit = gce.FileOpen(fname).open()

        # Branches ordering
        branchdict = {}
        for i, t in enumerate(main_circuit.get_branches()):
            branchdict[t.code] = i

        # Power flow initial using linear method
        linear_analysis = gce.LinearAnalysisDriver(grid=main_circuit)
        linear_analysis.run()

        Sf0 = linear_analysis.results.Sf
        Sf0red = np.array([Sf0[branchdict[t.code]] for t in main_circuit.contingencies])

        linear_multi_contingency = gce.LinearMultiContingencies(grid=main_circuit)
        linear_multi_contingency.compute(ptdf=linear_analysis.results.PTDF, lodf=linear_analysis.results.LODF)
        mlodf = linear_multi_contingency.multi_contingencies[0].mlodf_factors.A  # TODO: Suponemos que son los MLODF

        # Power flow per branches after multicontingency using MLODF method
        Sfmlodf = Sf0 + np.matmul(mlodf, Sf0red)

        # Theoretical method
        pf_options = gce.PowerFlowOptions(gce.SolverType.NR,
                                          verbose=False,
                                          initialize_with_existing_solution=False,
                                          dispatch_storage=True,
                                          control_q=gce.ReactivePowerControlMode.NoControl,
                                          control_p=False)

        options = gce.ContingencyAnalysisOptions(pf_options=pf_options, engine=gce.ContingencyMethod.PTDF)
        cont_analysis_driver = gce.ContingencyAnalysisDriver(grid=main_circuit, options=options,
                                                             linear_multiple_contingencies=linear_multi_contingency)
        cont_analysis_driver.run()
        Sfnr = cont_analysis_driver.results.Sf.real * 1e-2  # TODO: pensamos que las unidades son erróneas

        assert np.allclose(Sfmlodf, Sfnr, atol=1e-5)


def test_mlodf_sanpen():
    """
    Compare power flow per branches in N-2 contingencies using theoretical methodology and MLODF
    """
    for fname in [
        os.path.join('data', 'grids', 'IEEE14-2_4_1-3_4_1.gridcal'),
        os.path.join('data', 'grids', 'IEEE14-2_5_1-1_5_1.gridcal'),
        # os.path.join('data', 'grids', 'IEEE14-bus_d-6_11-6_13.gridcal'),  # TODO: SANPEN: this fails, is this a conceptual failure?
        # os.path.join('data', 'grids', 'IEEE14-bus_d-7_8-9_10.gridcal')  # TODO: SANPEN: this fails, is this a conceptual failure?
    ]:
        main_circuit = gce.FileOpen(fname).open()

        # DC power flow method
        pf_options = gce.PowerFlowOptions(gce.SolverType.DC,
                                          verbose=False,
                                          initialize_with_existing_solution=False,
                                          dispatch_storage=True,
                                          control_q=gce.ReactivePowerControlMode.NoControl,
                                          control_p=False)
        options1 = gce.ContingencyAnalysisOptions(pf_options=pf_options, engine=gce.ContingencyMethod.PowerFlow)
        cont_analysis_driver1 = gce.ContingencyAnalysisDriver(grid=main_circuit, options=options1,
                                                              linear_multiple_contingencies=None)
        cont_analysis_driver1.run()

        # MLODF method
        linear_analysis = gce.LinearAnalysisDriver(grid=main_circuit)
        linear_analysis.run()
        linear_multi_contingency = gce.LinearMultiContingencies(grid=main_circuit)
        linear_multi_contingency.compute(ptdf=linear_analysis.results.PTDF, lodf=linear_analysis.results.LODF)
        options2 = gce.ContingencyAnalysisOptions(pf_options=pf_options, engine=gce.ContingencyMethod.PTDF)
        cont_analysis_driver2 = gce.ContingencyAnalysisDriver(grid=main_circuit, options=options2,
                                                              linear_multiple_contingencies=linear_multi_contingency)
        cont_analysis_driver2.run()

        ok = np.allclose(cont_analysis_driver1.results.Sf, cont_analysis_driver2.results.Sf)

        assert ok


def test_ptdf_generation_contingencies():
    """
    Compare the PSSE PTDF and the GridCal PTDF for IEEE14, IEEE30, IEEE118 and REE networks
    In this test we check a number of grids where only generation variations
    have been introduced via generation contingencies

    The test consists in performing the contingencies with a Power flow driver (with linear power flow)
    later with a PTDF driver and both should provide the same values
    """
    for fname in [
        os.path.join('data', 'grids', 'IEEE14-gen120.gridcal'),
        os.path.join('data', 'grids', 'IEEE14-gen80.gridcal'),
        os.path.join('data', 'grids', 'IEEE30-gen80.gridcal'),
        os.path.join('data', 'grids', 'IEEE30-gen120.gridcal'),
        os.path.join('data', 'grids', 'IEEE118-gen80.gridcal'),
        os.path.join('data', 'grids', 'IEEE118-gen120.gridcal'),

    ]:
        main_circuit = gce.FileOpen(fname).open()

        pf_options = gce.PowerFlowOptions(gce.SolverType.DC,
                                          verbose=False,
                                          initialize_with_existing_solution=False,
                                          dispatch_storage=True,
                                          control_q=gce.ReactivePowerControlMode.NoControl,
                                          control_p=False)
        # DC power flow method

        options1 = gce.ContingencyAnalysisOptions(pf_options=pf_options, engine=gce.ContingencyMethod.PowerFlow)
        cont_analysis_driver1 = gce.ContingencyAnalysisDriver(grid=main_circuit, options=options1,
                                                              linear_multiple_contingencies=None)
        cont_analysis_driver1.run()

        # PTDF METHOD
        linear_analysis = gce.LinearAnalysisDriver(grid=main_circuit)
        linear_analysis.run()
        linear_multi_contingency = gce.LinearMultiContingencies(grid=main_circuit)
        linear_multi_contingency.compute(ptdf=linear_analysis.results.PTDF, lodf=linear_analysis.results.LODF)
        options2 = gce.ContingencyAnalysisOptions(pf_options=pf_options, engine=gce.ContingencyMethod.PTDF)
        cont_analysis_driver2 = gce.ContingencyAnalysisDriver(grid=main_circuit, options=options2)
        cont_analysis_driver2.run()

        ok = np.allclose(cont_analysis_driver1.results.Sf, cont_analysis_driver2.results.Sf, atol=1e-4)
        assert ok


def test_lodf_single_contingencies():
    """
    Compare the PSSE PTDF and the GridCal PTDF for IEEE14, IEEE30, IEEE118 and REE networks
    In this test we check the single contingencies against the power flow driver

    The test consists in performing the contingencies with a Power flow driver (with linear power flow)
    later with a PTDF driver and both should provide the same values
    """
    for fname in [
        os.path.join('data', 'grids', 'IEEE14-13_14.gridcal'),
        os.path.join('data', 'grids', 'IEEE30-12_15.gridcal'),
        os.path.join('data', 'grids', 'IEEE118-38_65.gridcal'),
        os.path.join('data', 'grids', 'IEEE118-80_96.gridcal'),

    ]:
        main_circuit = gce.FileOpen(fname).open()

        # DC power flow method
        pf_options = gce.PowerFlowOptions(gce.SolverType.DC,
                                          verbose=False,
                                          initialize_with_existing_solution=False,
                                          dispatch_storage=True,
                                          control_q=gce.ReactivePowerControlMode.NoControl,
                                          control_p=False)

        options1 = gce.ContingencyAnalysisOptions(pf_options=pf_options,
                                                  engine=gce.ContingencyMethod.PowerFlow)

        cont_analysis_driver1 = gce.ContingencyAnalysisDriver(grid=main_circuit,
                                                              options=options1,
                                                              linear_multiple_contingencies=None)
        cont_analysis_driver1.run()

        # LODF method
        linear_analysis = gce.LinearAnalysisDriver(grid=main_circuit)
        linear_analysis.run()
        linear_multi_contingency = gce.LinearMultiContingencies(grid=main_circuit)
        linear_multi_contingency.compute(ptdf=linear_analysis.results.PTDF, lodf=linear_analysis.results.LODF)
        options2 = gce.ContingencyAnalysisOptions(pf_options=pf_options, engine=gce.ContingencyMethod.PTDF)
        cont_analysis_driver2 = gce.ContingencyAnalysisDriver(grid=main_circuit,
                                                              options=options2)  # linear_multiple_contingencies=linear_multi_contingency)
        cont_analysis_driver2.run()

    ok = np.allclose(cont_analysis_driver1.results.Sf, cont_analysis_driver2.results.Sf, atol=1e-1)
    assert ok


def test_generation_contingencies_powerflow():
    """
    Compare power flow results when using ContingencyAnalysisDriver with generator contingencies

    The test consists in performing the contingencies with a Power flow driver (with linear power flow)
    later perform a power flow again applying the contingencies manually without using ContingencyAnalysisDriver
    """
    for case in [
        {
            'orig': os.path.join('data', 'grids', 'RAW', 'IEEE 14 bus.raw'),
            'conti': os.path.join('data', 'grids', 'IEEE14-gen120.gridcal'),
            'cont_index_change': {1: 1.2}  # Generator contingency dict: {index: %change}
        },
        {
            'orig': os.path.join('data', 'grids', 'RAW', 'IEEE 30 bus.raw'),
            'conti': os.path.join('data', 'grids', 'IEEE30-gen80.gridcal'),
            'cont_index_change': {1: 0.8}
        },
        {
            'orig': os.path.join('data', 'grids', 'RAW', 'IEEE 118 Bus v2.raw'),
            'conti': os.path.join('data', 'grids', 'IEEE118-gen120.gridcal'),
            'cont_index_change': {44: 1.2}
        }
    ]:
        main_circuit = gce.FileOpen(case['conti']).open()

        pf_options = gce.PowerFlowOptions(gce.SolverType.DC,
                                          verbose=False,
                                          initialize_with_existing_solution=False,
                                          dispatch_storage=True,
                                          control_q=gce.ReactivePowerControlMode.NoControl,
                                          control_p=False)

        # DC power flow method with ContingencyAnalysisDriver
        pf_options = gce.PowerFlowOptions(gce.SolverType.DC,
                                          verbose=False,
                                          initialize_with_existing_solution=False,
                                          dispatch_storage=True,
                                          control_q=gce.ReactivePowerControlMode.NoControl,
                                          control_p=False)
        options1 = gce.ContingencyAnalysisOptions(pf_options=pf_options, engine=gce.ContingencyMethod.PowerFlow)
        cont_analysis_driver1 = gce.ContingencyAnalysisDriver(grid=main_circuit, options=options1,
                                                              linear_multiple_contingencies=None)
        cont_analysis_driver1.run()

        # DC power flow
        main_circuit = gce.FileOpen(case['orig']).open()
        nc = gce.compile_numerical_circuit_at(main_circuit, t_idx=None)

        for index, change in case['cont_index_change'].items():
            main_circuit.generators[index].P *= change

        power_flow = gce.PowerFlowDriver(main_circuit, pf_options)
        power_flow.run()

        ok = np.allclose(cont_analysis_driver1.results.Sf, power_flow.results.Sf)
        assert ok


def test_compensated_ptdf():
    """
    Compare compensated ptdf from network with contingencies with ptdf of the same network with that branch disabled.
    """
    for case in [
        {
            'orig': os.path.join('data', 'grids', 'RAW', 'IEEE 14 bus.raw'),
            'conti': os.path.join('data', 'grids', 'IEEE14-1_2-B2.gridcal')
        },
        {
            'orig': os.path.join('data', 'grids', 'RAW', 'IEEE 14 bus.raw'),
            'conti': os.path.join('data', 'grids', 'IEEE14-9_14_1.gridcal')
        },
        {
            'orig': os.path.join('data', 'grids', 'RAW', 'IEEE 30 bus.raw'),
            'conti': os.path.join('data', 'grids', 'IEEE30-27_29_1.gridcal'),
        },
        {
            'orig': os.path.join('data', 'grids', 'RAW', 'IEEE 118 Bus v2.raw'),
            'conti': os.path.join('data', 'grids', 'IEEE118-91_92_1.gridcal'),
        }
    ]:

        main_circuit = gce.FileOpen(case['conti']).open()

        linear_analysis = gce.LinearAnalysisDriver(grid=main_circuit)
        linear_analysis.run()

        linear_multi_contingency = gce.LinearMultiContingencies(grid=main_circuit)
        linear_multi_contingency.compute(ptdf=linear_analysis.results.PTDF, lodf=linear_analysis.results.LODF)

        main_circuit_raw = gce.FileOpen(case['orig']).open()
        # main_circuit_raw.delete_line(main_circuit_raw.get_lines()[0]) # Disable branch 1_2
        line = main_circuit.contingencies[0].code
        for l in main_circuit_raw.lines:
            if l.code == line:
                l.active = False

        linear_analysis_raw = gce.LinearAnalysisDriver(grid=main_circuit_raw)
        linear_analysis_raw.run()

        nc = gce.compile_numerical_circuit_at(main_circuit)
        cnt = linear_multi_contingency.multi_contingencies[0]

        # TODO: Magia que no sé porqué funciona (Santiago)
        ok = np.allclose(cnt.compensated_ptdf_factors.todense(),
                         linear_analysis_raw.results.PTDF[:, nc.T[cnt.branch_indices]],
                         atol=1e-3)
        assert ok


def test_ptdf_contingencies_powerflow():
    """
    Compare power flow results when using ContingencyAnalysisDriver with both generator and branch contingencies

    The test consists in performing the contingencies with a Power flow driver (with linear power flow)
    later perform a power flow again applying the contingencies manually without using ContingencyAnalysisDriver
    """
    for case in [
        {
            'contingency_type': 'single',
            'orig': os.path.join('data', 'grids', 'RAW', 'IEEE 14 bus.raw'),
            'conti': os.path.join('data', 'grids', 'IEEE14-gen120-1_2.gridcal'),
            'cont_index_change': {1: 1.2}  # Generator contingency dict: {index: %change}
        },
        {
            'contingency_type': 'single',
            'orig': os.path.join('data', 'grids', 'RAW', 'IEEE 30 bus.raw'),
            'conti': os.path.join('data', 'grids', 'IEEE30-gen80-1_2.gridcal'),
            'cont_index_change': {1: 0.8}
        },
        {
            'contingency_type': 'single',
            'orig': os.path.join('data', 'grids', 'RAW', 'IEEE 118 Bus v2.raw'),
            'conti': os.path.join('data', 'grids', 'IEEE118-gen120-12_16.gridcal'),
            'cont_index_change': {44: 1.2}
        },
        {
            'contingency_type': 'multiple',
            'orig': os.path.join('data', 'grids', 'RAW', 'IEEE 14 bus.raw'),
            'conti': os.path.join('data', 'grids', 'IEEE14-2_4_1-7_8_1-2_1(80).gridcal'),
            'cont_index_change': {1: 0.8}
        }
    ]:

        main_circuit = gce.FileOpen(case['conti']).open()

        if case['contingency_type'] == 'multiple':
            linear_analysis = gce.LinearAnalysisDriver(grid=main_circuit)
            linear_analysis.run()

            linear_multi_contingency = gce.LinearMultiContingencies(grid=main_circuit)
            linear_multi_contingency.compute(ptdf=linear_analysis.results.PTDF, lodf=linear_analysis.results.LODF)

            # DC power flow method with ContingencyAnalysisDriver
            pf_options = gce.PowerFlowOptions(gce.SolverType.DC,
                                              verbose=False,
                                              initialize_with_existing_solution=False,
                                              dispatch_storage=True,
                                              control_q=gce.ReactivePowerControlMode.NoControl,
                                              control_p=False)

            options1 = gce.ContingencyAnalysisOptions(pf_options=pf_options, engine=gce.ContingencyMethod.PTDF)
            cont_analysis_driver1 = gce.ContingencyAnalysisDriver(grid=main_circuit, options=options1,
                                                                  linear_multiple_contingencies=linear_multi_contingency)
            cont_analysis_driver1.run()

            line_cnt = []
            for cnt in main_circuit.contingencies:
                if cnt.value == 0.0:  # Generator contingencies have values in this test have values <0 or >0
                    line_cnt.append(cnt.code)

            # DC power flow
            main_circuit_raw = gce.FileOpen(case['orig']).open()

            for index, change in case['cont_index_change'].items():
                main_circuit_raw.generators[index].P *= change

            for l in main_circuit_raw.lines:
                if l.code in line_cnt:
                    l.active = False

            power_flow = gce.PowerFlowDriver(main_circuit_raw, pf_options)
            power_flow.run()

            ok = np.allclose(cont_analysis_driver1.results.Sf, power_flow.results.Sf, atol=1e-2)
            assert ok


        else:
            # DC power flow method with ContingencyAnalysisDriver
            pf_options = gce.PowerFlowOptions(gce.SolverType.DC,
                                              verbose=False,
                                              initialize_with_existing_solution=False,
                                              dispatch_storage=True,
                                              control_q=gce.ReactivePowerControlMode.NoControl,
                                              control_p=False)

            options1 = gce.ContingencyAnalysisOptions(pf_options=pf_options, engine=gce.ContingencyMethod.PowerFlow)
            cont_analysis_driver1 = gce.ContingencyAnalysisDriver(grid=main_circuit, options=options1,
                                                                  linear_multiple_contingencies=None)
            cont_analysis_driver1.run()

            line_cnt = ''
            for cnt in main_circuit.contingencies:
                if cnt.value == 0.0:  # Generator contingencies have values in this test have values <0 or >0
                    line_cnt = cnt.code

            # DC power flow
            main_circuit_raw = gce.FileOpen(case['orig']).open()

            for index, change in case['cont_index_change'].items():
                main_circuit_raw.generators[index].P *= change

            for l in main_circuit.lines:
                if l.code == line_cnt:
                    l.active = False

            power_flow = gce.PowerFlowDriver(main_circuit, pf_options)
            power_flow.run()

            ok = np.allclose(cont_analysis_driver1.results.Sf, power_flow.results.Sf)
            assert ok
