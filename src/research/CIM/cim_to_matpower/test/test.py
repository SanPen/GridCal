
import CIM2Matpower

# from scipy.io import savemat

cim_to_matpower_filename = 'CIM_to_Matpower_import'

cimfiles = ['./UCTE10_20090319_modified_EQ.xml',
            './UCTE10_20090319_modified_TP.xml',
            './UCTE10_20090319_modified_SV.xml']

boundary_profiles = []

mpc = CIM2Matpower.cim_to_mpc(cimfiles, boundary_profiles)  #, 'imported_CIM.log')

# savemat(cim_to_matpower_filename+'.mat', mpc)
