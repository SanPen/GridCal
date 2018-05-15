
# import genericbus2
import time
import pickle
import shutil
from scipy.sparse import lil_matrix
from scipy import *
from numpy import *
# from DFSvisitar import DFSvisitar
from pylab import *
from scipy.linalg import *
from tkinter import *
# import tkMessageBox
# from tkFileDialog import askopenfilename
# from tkFileDialog import *


def DFSvisitar(Zabct, nodo, padre, estado):
    """
    hallar el vector de precedencias de cada barra de la matriz
    Args:
        Zabct:matriz de impedancia
        nodo: barra de estudio
        padre:vector de precedencia
        estado:vector de nodos visitados

    Returns:

    """
    estado[0, nodo] = 1
    m = len(Zabct)
    n = m
    for i in range(n):
        Zaux = Zabct[nodo, i]
        if Zaux != 0:
            if estado[0, i] == 0:
                padre[0, i] = nodo
                padre = DFSvisitar(Zabct, i, padre, estado)
            estado[0, nodo] = 2

    padreN = padre

    return padreN


def DFS(Zabct):
    """

    Args:
        Zabct: matriz de impedancia

    Returns:

    """
    m = len(Zabct)
    n = m
    padre = zeros((1, n))
    estado = zeros((1, n))
    caminos = zeros((n, n))
    for i in range(n):
        if estado[0, i] == 0:
            padreX = DFSvisitar(Zabct, i, padre, estado)
        for j in range(n):
            inde = n - j - 1
            k = 1
            if padreX[0, inde] != 0:
                caminos[j, k] = inde
                k = k + 1

            while inde > 0 and padreX[0, inde] != 0:
                caminos[j, k] = padreX[0, inde]
                k = k + 1
                inde = padreX[0, inde]

    return caminos


def genericbus2(NN):
    # __author__ ='FranciscoOchoa&JohanRojas'
    # date='$10/10/201104:23:46PM$'
    ##import aciondelibreriasausar
    import random

    # Analisis de Flujo de cargas monofasicos y trifasicos
    # Caso generico de n barras
    # Parametros de control
    econv = 0.010
    itermax = 2000

    ##Basesdelsistema
    Sbase = 100  # Basepotencia
    Vbase = 10  # BaseVoltaje

    # Voltaje
    Voo = 1

    # NumerodeBarras
    NNdes = NN  # Numero de nodos deseados(Incluida laS/E)

    # Parametrosdelasimpedancias(PU)
    rpu = 0.306 / (NNdes - 1)  #Resistencia ensecuencia
    xpu = 0.627 / (NNdes - 1)  # Reactancia ensecuencia
    P = 0.08 / (NNdes - 1)  # Demanda de potencia activa(PU)
    Q = 0.06 / (NNdes - 1)  # Demanda de potencia Reactiva(PU)

    # Generacion de la matriz de dimension nxn
    busaux = [None] * NNdes
    for i in range(NNdes):
        busaux[i] = random.randrange(0, 1e6 * NNdes)
    
    bus = busaux
    bus = sorted(set(bus))
    NN = len(bus)

    branch = [None] * 9
    busbar = [None] * 14
    slack = [None] * 2
    fbus = [None] * (NN-1)
    tbus = [None] * (NN-1)
    br3 = zeros(NN-1)
    br4 = zeros(NN-1)
    br5 = zeros(NN-1)
    br6 = zeros(NN-1)
    br7 = zeros(NN-1)
    br8 = zeros(NN-1)
    br9 = zeros(NN-1)
    bs2 = zeros(NN)
    bs3 = zeros(NN)
    bs4 = zeros(NN)
    bs5 = zeros(NN)
    bs6 = zeros(NN)
    bs7 = zeros(NN)
    bs8 = zeros(NN)
    bs9 = zeros(NN)
    bs10 = zeros(NN)
    bs11 = zeros(NN)
    bs12 = zeros(NN)
    bs13 = zeros(NN)
    bs14 = zeros(NN)

    for n in range(NN-1):
        fbus[n] = bus[n]
        tbus[n] = bus[n+1]
        br3[n] = 0
        br4[n] = rpu
        br5[n] = xpu
        br6[n] = 0
        br7[n] = 0
        br8[n] = 1
        br9[n] = 1

    for n in range(NN):
        bs2[n] = 0
        bs3[n] = 3
        bs4[n] = 0
        bs5[n] = 0
        bs6[n] = P
        bs7[n] = Q
        bs8[n] = 1
        bs9[n] = P
        bs10[n] = Q
        bs11[n] = P
        bs12[n] = Q
        bs13[n] = P
        bs14[n] = Q

    branch[0] = fbus
    branch[1] = tbus
    branch[2] = br3
    branch[3] = br4
    branch[4] = br5
    branch[5] = br6
    branch[6] = br7
    branch[7] = br8
    branch[8] = br9

    busbar[0] = bus
    busbar[1] = bs2
    busbar[2] = bs3
    busbar[3] = bs4
    busbar[4] = bs5
    busbar[5] = bs6
    busbar[6] = bs7
    busbar[7] = bs8
    busbar[8] = bs9
    busbar[9] = bs10
    busbar[10] = bs11
    busbar[11] = bs12
    busbar[12] = bs13
    busbar[13] = bs14

    slack[1] = busbar[1][1]
    out = (busbar, branch)

    return out


#####BasicTRXPowerFlow###########
#####n-busloasFlow########
#####SinglePhase######
print('TRXPOWERFLOW-SINGLEPHASE')
print('*******Desarrolladores*******')
print('FranciscoOchoa&JohanRojas')

#####importaciondemodulodegeneraciondesistema######


######interfaz graficadedatosdeentrada#######
n_bus = 0

##definiciondela funcionprtext####
##Metodoquerecibe 

def prtext():
    global text
    text = entry.get()
    gui.destroy()
    

states=[]
datos=['MatrizT','FDC','NCC']

gui=Tk()
gui.title('Numerodenodosaestudiar')
entry=Entry(gui)
entry.pack()
button=Button(gui,text='agregarnumerodenodos',fg='blue',command=prtext)

button.pack()


gui.mainloop()
n_bus=int(text)


if n_bus < 2:
    print('Elijaunmayornumerodebarras')
    exit()

root = Tk()
root.title('Metododeanalisisdesistemasdedistribucion')
Label(text='Elija los analisisarealizar').pack(side=TOP,padx=10,pady=10)

li=3
if n_bus > 600:
    li=2

for i in range(li):
    var = IntVar()
    chk = Checkbutton(root,text=datos[i],variable=var)
    chk.pack(side=LEFT)
    states.append(var)


Button(text='Siguiente',command=root.quit,fg='blue').pack(side=BOTTOM)

root.mainloop()
# link = map((lambda var: var.get()), states)

link = [x.get() for x in states]

variable_temp = link[0]

##########detenciondelprogramaencasodenoelegirnada#####


if link[1] == 0:
    print('Elija un caso de estudio para el sistema y vuelva a intentarlo')
    exit()
    


##Variabledemediciondetiempo

tinicio=time.time()

##definiciondelafuncionrepmat####
##Metodoquedadaunamarizgeneraunamatrizdeldoblededimension
##repitiendolamatrizinicial.
##Parametros:amatrizaduplicar102
##bnumerode
##cnumerodecolumnasdelamatriz
#Retorna:filas delamatriz lamatrizconeldobledelongitudyelementosduplicados.

def repmat(a, b, c):
    b = b - 1
    c = c - 1
    j = len(a[0])
    for n in range(j):
        k = a[n][:]
        for m in range(b):
            a[n].extend(k)
        k = a[:]
    for n in range(c):
        a.extend(k)
    
    return a

number = 10

###definiciondevaloresdeinteres####
tinicio2=time.time()
trepmat=tinicio2-tinicio
Voo=1
econv=0.010
Sbase=100
Vbase=10

##obtenciondelas variablesdeinteres delgeneradordebarras aleatorio####
busbar_aux = genericbus2(n_bus)
busbar = busbar_aux[0]
branch = busbar_aux[1]
Zr = zeros((len(branch[3]) + 2, len(branch[3]) + 2))
Zx = zeros((len(branch[3]) + 2, len(branch[3]) + 2))

##creaciondelamatrizdeimpedanciaZt####

for i in range(len(branch[3])):
    Zr[i][i+1] = branch[3][i]
    Zx[i][i+1] = branch[4][i]

Zt = Zr + Zx * 1j

##SelecciondelabarraSlack###
slack = busbar[0][0]

####Algoritmodeordenacion##########
fbus = 1*branch[0]  #Vectordenodosdesalida
tbus = 1*branch[1]  #Vectordenodosdellegada
bus = 1*busbar[0]  #Vectordenumeraciondenodos

#####BuscamosnodoS/Eynumerototaldenodos

Nslack=slack
n_bus = len(bus)  # numero de nodos
n_branch = len(fbus)  # numero de ramas

#####Buscamoselnodopadredelabarraslack#####

swapft=[]
if Nslack in fbus:
    f1 = fbus.index(Nslack)
else:
    f1 = []
RdownO = [f1]
NupOc = [tbus[f1]]


if not f1 == []:
    fbus[f1] = repmat([['check']],1,1)
    tbus[f1] = repmat([['check']],1,1)

if Nslack in tbus:
    f1 = tbus.index(Nslack)
    RdownO = RdownO + [f1]
    NupOc = NupOc + tbus[len(f1)]
else:
    f1=[]

if not f1==[]:
    swapft=f1
    fbus[f1]=repmat([['check']],1,1)
    tbus[f1]=repmat([['check']],1,1)

tinicio3 = time.time()
tordenacion = tinicio3 - tinicio2
print('Laordenaciontardo',tordenacion,'segundos')

#####Recorridodelarboldelareddedistribucionparala renumeracion######
#####Arreglosdondesevanaalmacenarlos estratosdenodosyramas#####
ENOD= [0] * n_bus
ERAM= [0] * n_bus

#####Estotraduce losnodosquehayenNupOcaposicionesenel cellbus####
NupO=[]
NNup=len(NupOc)####NumerodenodosconseguidosarribadeRdown

for n in range(NNup):
    NupO = NupO + [bus.index(NupOc[n])]

ENOD[NupO[0]]=1  # Asignamos el valor 1 al primer estrato de nodo
ERAM[RdownO[0]]=1  # asignamos el valor 1 al primer estrato de rama
NENOD = 1  # Contador de estratos de nodos(ya se creo el primero)
NERAM = 1 # Contador de estratos de ramas(ya se creo el primero)

Nupc = NupOc  #Arreglo de nodos arriba de un grupo de ramas Rdown
Rest=RdownO
Rest[0]=Rest[0] + 1
Nestc=NupOc # Vector donde se almacenan concatenados los vectores Nup

Nest=NupO

while not Nupc==[]:
    Nupc=[]
    Rdown=[]
    for n in range(NNup):

        if NupOc[n] in fbus:
            f2=fbus.index(NupOc[n])
            Rdown=Rdown+[f2]
            Nupc=Nupc+[tbus[f2]]

        else:
            f2=[]
        if not f2==[]:
            fbus[f2]=repmat([['check']],1,1)
            tbus[f2]=repmat([['check']],1,1)

        if NupOc[n] in tbus:
            f3=[tbus.index(NupOc[n])]
            Rdown=Rdown+[f3]
            Nupc=Nupc+[fbus[f3]]

        else:
            f3=[]

        if not f3==[]:
            swapft=swapft+[f3]
            fbus[f3]=repmat([['check']],1,1)
            tbus[f3]=repmat([['check']],1,1)

    if not Rdown==[]:
        Rest=Rest+[Rdown[0]+1]

    Nestc=[Nestc]+Nupc
    Nup=[]
    NNup=len(Nupc)

    for n in range(NNup):
        Nup=Nup+[bus.index(Nupc[n])]

    Nest = Nest + Nup
    NENOD = NENOD + 1
    NERAM = NERAM + 1

    if NENOD < n_bus:
        ENOD[Nup[0]]=NENOD
    if NERAM < n_bus:
        ERAM[Rdown[0]]=NERAM

    NupOc=Nupc

if Nslack in bus:
    fs=bus.index(Nslack)
else:
    fs=[]

bus[fs]=[]
ENOD[fs]=[]
Nest=[fs]+Nest
Nestc=[Nslack]+Nestc

if swapft == []:
    aux1=[]
    aux2=[]
else:
    aux1=branch[0][swapft[0]]
    aux2=branch[1][swapft[0]]

if not swapft==[]:
    if aux1==[] or aux2==[]:
        branch[0][swapft[0]]=[]
        branch[1][swapft[0]]=[]
    else:
        branch[0][swapft[0]]=aux2
        branch[1][swapft[0]]=aux1

#####Recordamosque:#######
#####Nest=Indicesviejosenlasbarrasahoraenordentrx######
#####Rest=Indicesviejosdelaslineasahoraenordentrx######
g=len(Nest)
g2=len(Rest)

bdat = [Nest,
        busbar[0][0:g],
        busbar[1][0:g],
        busbar[2][0:g],
        busbar[3][0:g],
        busbar[4][0:g],
        busbar[5][0:g],
        busbar[6][0:g],
        busbar[7][0:g],
        busbar[8][0:g],
        busbar[9][0:g],
        busbar[10][0:g],
        busbar[11][0:g],
        busbar[12][0:g],
        busbar[13][0:g]]

nsend=[]
for n in range(n_branch):
    ii = bdat[1].index(branch[0][n])
    nsend = nsend + [ii]

nrecv = range(1,len(nsend) + 1)
ldat = [Rest,
        nsend[0:g2],
        nrecv[0:g2],
        branch[0][0:g2],
        branch[1][0:g2],
        branch[2][0:g2],
        branch[3][0:g2],
        branch[4][0:g2],
        branch[5][0:g2],
        branch[6][0:g2],
        branch[7][0:g2],
        branch[8][0:g2]]

tinicio4=time.time()
tordenacionC=tinicio4-tinicio3
print('La ordenacion tardo',tordenacionC,'segundos')

######ConstrucciondelamatrizT####
Vox = zeros(n_branch)
Voy = zeros(n_branch)
tinicio5 = time.time()
if variable_temp == 1:
    fbus = ldat[1]
    Tm = lil_matrix((n_branch, n_branch))
    for k in range(n_branch):
        ns = fbus[k]
        if ns == 0:
            B = [0] * n_branch
            B[k] = 1
            for i in range(n_branch):
                Tm[k, i] = B[i]
        else:
            for h in range(n_branch):
                B[h] = Tm[ns-1, h]

            B[k] = 1
            for g in range(n_branch):
                Tm[k, g] = B[g]
    T = Tm.toarray()
    T = transpose(T)
    pickle.dump(T, open('matrizT.pkl', 'wb'))

else:
    T = pickle.load(open('matrizT.pkl', 'rb'))

    tbuildT = tinicio5-tinicio4
    print('lamatrizTtardo', tbuildT, 'segundos')

#####InicializaciondeVoltajes########
for n in range(Voo-1, n_branch):
    Vox[n] = 1
    Voy[n] = 0

#####ConstrucciondelamatrizTRXmonofasicaaproximada######
G = dot(transpose(T), dot(diag(ldat[6]), T))
B = dot(transpose(T), dot(diag(ldat[7]), T))

#####SoloGyBsealmacenanenmemoria############
delta = ones(n_branch)
iter = 0
Iax = zeros(n_branch)
Iay = zeros(n_branch)
Voaux = ones(n_branch)

#####Flujodecarga trifasico######
while max(abs(delta)) > econv:
    iter = iter + 1

    for j in range(n_branch):
        Iax[j]=-((-bdat[6][j+1]+bdat[4][j+1])*Vox[j]-(bdat[7][j+1]-bdat[5][j+1])*Voy[j])/(Vox[j]*Vox[j]+Voy[j]*Voy[j])
        Iay[j]=-((bdat[7][j+1]-bdat[5][j+1])*Vox[j]-(bdat[6][j+1]-bdat[4][j+1])*Voy[j])/(Vox[j]*Vox[j]+Voy[j]*Voy[j])

    Vx2=-dot(G,transpose(Iax))+dot(B,transpose(Iay))+transpose(Voaux)
    Voy=-dot(B,transpose(Iax))-dot(G,transpose(Iay))
    delta=Vox-Vx2
    Vox=Vx2

intertrx=iter
Va=concatenate((Vox,Voy))
tinicio6=time.time()
tflujodecarga=tinicio6-tinicio5
print('elflujodecargatardo',tflujodecarga,'segundos')

##########Flujodecarga trifasico Calculo######
DemandP = sum(bdat[6][:]*Sbase)
DemandQ = sum(bdat[7][:]*Sbase)
DemandS = Sbase * sqrt(DemandP*DemandP+DemandQ*DemandQ)
DemandPF =sum(bdat[6][:]*Sbase)
TOK = zeros((n_branch, n_branch))
Tg = concatenate((concatenate((T,TOK),1),concatenate((TOK,TOK),1)))
Jx = dot(T,transpose(Iax))
Jy = dot(T,transpose(Iay))
J = concatenate((Jx,Jy))
Jline = Jx+sqrt(-1)*Jy
Vnode = Vox+sqrt(-1)*Voy
v = abs(Vnode)
theta = angle(Vnode)
Sij = Vnode*conj(Jline)
absSij=abs(Sij)*Sbase

######Calculosdeperdidas########
Rg=concatenate((concatenate((diag(ldat[6]),TOK),1),concatenate((TOK,diag(ldat[6])),1)))
Xg=concatenate((concatenate((diag(ldat[7]),TOK),1),concatenate((TOK,diag(ldat[7])),1)))
DPR=sum(Rg*(abs(J)*abs(J)))*Sbase
DPX=sum(Xg*(abs(J)*abs(J)))*Sbase
DPZ=sqrt(DPR*DPR+DPX*DPX)

#####Calculosdelafuente#########
SourceP=DemandP+DPR
SourceQ=DemandQ+DPX
SourceS=sqrt(SourceP*SourceP+SourceQ*SourceQ)
SourcePF=SourceP/SourceS
DPRp=DPR*100/SourceP
DPXp=DPX*100/SourceQ
DPZp=DPZ*100/SourceS

######Creaciondelasvariablesdegraficacion#########
Y= [0] * n_branch
vmax= ones(n_branch) * 1.1
vmin= ones(n_branch) * 0.9
v0= [0] * n_branch
Smax= ones(n_branch) * Vbase * 1.73 * .4 * 1.2
Semerg= ones(n_branch) * Vbase * 1.73 * .4
Snormal= ones(n_branch) * Vbase * 1.73 * .4 * .67
for k in range(n_branch):
    Y[k]=k+1
tover=time.time()
t=linspace(0, n_bus, n_bus)
print('elprogramatardo',tover-tinicio,'segundos')
verificacion=0

####Calculodel niveldecorto circuito####
if n_bus < 600:
    verificacion=link[2]

if n_bus < 600 and verificacion==1:
    Zt=abs(Zt)
    B=DFS(Zt)
    m=len(Zt)
    n=m
    Ztt=zeros((len(B),len(B)))
    for i in range(len(B)):
        for j in range(1,len(B)-1):
            Ztt[i,j]=Zt[B[i,j+1],B[i,j]]
    for i in range(len(Ztt)):
        suma=0
        for j in range(len(Ztt)):
            suma = suma + Ztt[i,j]
        if suma==0:
            suma=Zt[0,len(Ztt)-i-1]

        Ztt[i,0] = suma
    Ztotal=[]

    for i in range(len(Ztt)-1):
        Ztotal=Ztotal+[Ztt[len(Ztt)-i-1,0]]

    Vreal = Vox * Vbase
    Ncc = zeros((len(Ztotal)))
    for i in range(len(Ztotal)-1):
        Ncc[i] = (Vbase - Vreal[i]) / Ztotal[i+1] #####ValorenKA

    tover2=time.time()

    print('Ncctardo',tover2-tover,'segundos')

    m=len(Ncc)
    n=m

root.quit()
gui.quit()
link2=[0,0,0]
link2[1]=1
link2[0]=0

####Generaciondegraficasderesultados####

if link2[1]==1 and link2[0]==0:
    figure(1)
    subplot(211)
    plot(Vox,'ro')
    ylabel('Tensionesennodos')
    xlabel('Nodos')
    title('GraficodeResultados')


    if n_bus < 600 and verificacion==1:
        subplot(212)
        plot(Ncc,'go')
        ylabel('Ncc(Ka)')
        xlabel('Nodos')

####Instrucciones para guardar enarchivos los resultados####

try:
    #Python2
    #importTkinterastk
    import tkFileDialog as tkfd

except ImportError:
    #Python3
    #importtkinterastk
    import tkinter.filedialog as tkfd

mask=[('Text files','*.txt'),
      ('Python files','*.py*.pyw'),
      ('All files','*.*')]

filesave='Resultados de estudio'
f=tkfd.asksaveasfile(title='Carpetadondeseguardaranlos',
                     initialdir='C:',
                     initialfile=filesave,
                     defaultextension='.xml',
                     filetypes=mask)

####GeneraciondearchivoODMconlosresultados####
f.write('<xmlversion=\'1.0\'encoding=\'UTF-8\'>\n')
f.write('<pss:PSSStudyCase>\n')
f.write('<pss:id>')
f.write('sistemaprueba')
f.write('<pss:id/>\n')
f.write('<pss:schemaVersion>')
f.write('V1.00')
f.write('</pss:schemaVersion>\n')
f.write('<pss:originalFormat>IEEE-ODM-PSS</pss:originalFormat>\n')
f.write('<pss:analysisCategory>LoadFlow</pss:analysisCategory>\n')
f.write('<pss:networkCategory>Distribution</pss:networkCategory>\n')
f.write('<pss:baseCase>\n')
f.write('<pss:id>Base-Case</pss:id>\n')
f.write('<pss:basePower>')
f.write(str(Sbase))
f.write('<pss:basePower>\n')
f.write('<pss:basePowerUnit>KVA<pss:basePowerUnit>\n')

for i in range(n_bus-1):
    f.write('<pss:bus>\n')
    f.write('<pss:name>')
    f.write('Dis')
    f.write(str(i+1))
    f.write('')
    f.write(str(Vbase*1000))
    f.write('VOLT')
    f.write('</pss:name>\n')
    f.write('<pss:id>')
    f.write(str(i+1))
    f.write('</pss:id>\n')
    f.write('<pss:baseVoltage>')
    f.write(str(Vbase*1000))
    f.write('</pss:baseVoltage>\n')
    f.write('<pss:baseVoltageUnit>Volt</pss:baseVoltageUnit>\n')
    f.write('</pss:bus>\n')
    f.write('<pss:loadflowBusResult>\n')
    f.write('<pss:voltage>')
    f.write(str(Vox[i]))
    f.write('</pss:voltage>\n')
    f.write('<pss:baseVoltageUnit>PU</pss:baseVoltageUnit>\n')
    f.write('</pss:loadflowBusResult>\n')
    if n_bus < 600 and verificacion==1:
        f.write('<pss:NccBusResult>\n')
        f.write('<pss:voltage>')
        f.write(str(Ncc[i]))
        f.write('</pss:voltage>\n')
        f.write('<pss:baseNccUnit>KA</pss:baseNccUnit>\n')
        f.write('</pss:NccBusResult>\n')

f.write('</pss:baseCase>\n')
f.write('</pss:PSSStudyCase>\n')
savefig('simpleplot',format='pdf')
direccion=f.name
slash=[]

for i in range(len(direccion)):
    if direccion[i]=='/':
        slash=slash+[i]

loi=len(slash)-1
direccion=direccion[0:slash[loi]]
direccion=direccion+'/simpleplot'


try:
    #Python2
    #importTkinterastk

    shutil.copyfile(r'simpleplot',direccion)
except shutil.Error:
    print()
f.close()