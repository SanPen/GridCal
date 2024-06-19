#..................PLOTTING PLATYPUS................................
import matplotlib.pyplot as plt
import matplotlib
import pandas as pd

#===============================PLOT NON DOMINATED SOLUTIONS===============================
matplotlib.use("Qt5Agg")
data_ptp=pd.read_excel(r"C:\Users\cmach\PycharmProjects\GridCal2\src\trunk\investments\nsga_ptp_uf_nd.xlsx")
data_pymoo=pd.read_excel(r"C:\Users\cmach\PycharmProjects\GridCal2\src\trunk\investments\nsga_PYMOO.xlsx")
ptp_plot=plt.scatter(data_ptp[1],data_ptp[0], c='limegreen',edgecolors='g',marker='o') #edgecolors='g',
pymoo_plot=plt.scatter(data_pymoo[1],data_pymoo[0], c='cornflowerblue',edgecolors='b',marker='o') #,edgecolors='b'
plt.legend((ptp_plot,pymoo_plot),('Platypus non-dom results','Pymoo non-dom results'))
plt.show()

#===============================PLOT ALL vs last eval SOLUTIONS===============================
# matplotlib.use("Qt5Agg")
# data_ptp=pd.read_excel(r"C:\Users\cmach\PycharmProjects\GridCal2\src\trunk\investments\nsga_ptp_uf_lastgen.xlsx")
# data_pymoo=pd.read_excel(r"C:\Users\cmach\PycharmProjects\GridCal2\src\trunk\investments\nsga_PYMOO_all.xlsx")
# pymoo_plot=plt.scatter(data_pymoo[0],data_pymoo[1], c='khaki',edgecolors='y',marker='o') #c='cornflowerblue',
# ptp_plot=plt.scatter(data_ptp[1],data_ptp[0],c='r', edgecolors='r',alpha=0.4,marker='o') #edgecolors='g', #c='limegreen'
# plt.legend((ptp_plot,pymoo_plot),('Platypus all results (last generation)','Pymoo all results all evaluations'))
# plt.show()

#===============================PLOT ALL SOLUTIONS===============================
matplotlib.use("Qt5Agg")
data_ptp=pd.read_excel(r"C:\Users\cmach\PycharmProjects\GridCal2\src\trunk\investments\nsga_ptp_uf_all.xlsx")
data_pymoo=pd.read_excel(r"C:\Users\cmach\PycharmProjects\GridCal2\src\trunk\investments\nsga_PYMOO_all.xlsx")
pymoo_plot=plt.scatter(data_pymoo[0],data_pymoo[1], c='khaki',edgecolors='y',marker='o') #c='cornflowerblue',
ptp_plot=plt.scatter(data_ptp[1],data_ptp[0],c='r', edgecolors='r',alpha=0.4,marker='o') #edgecolors='g', #c='limegreen'
plt.legend((ptp_plot,pymoo_plot),('Platypus all results all evaluations','Pymoo all results all evaluations'))
plt.show()




print('hi')