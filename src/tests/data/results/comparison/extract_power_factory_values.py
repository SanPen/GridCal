import sys
import os
POWERFACTORY_PATH = r"C:\Program Files\DIgSILENT\PowerFactory 15.1"
os.environ["PATH"] = POWERFACTORY_PATH + ";" + os.environ["PATH"]
sys.path.append(POWERFACTORY_PATH + "\\python")

# import  PowerFactory  module
import powerfactory

# start PowerFactory  in engine  mode
app = powerfactory.GetApplication()

user = app.GetCurrentUser()

# activate project
project = app.ActivateProject("IEEE30")
prj = app.GetActiveProject()

ldf = app.GetFromStudyCase("ComLdf")

terminals = app.GetCalcRelevantObjects("*.ElmTerm")
lines = app.GetCalcRelevantObjects("*.ElmLne")
tr2 = app.GetCalcRelevantObjects("*.ElmTr2")

# run power flow
ldf.iopt_net = 0
ldf.Execute()

# gather the voltages
app.PrintPlain("Modules")
for term in terminals:
    name = term.GetAttribute('loc_name')
    vm = term.GetAttribute('m:u')
    va = term.GetAttribute('m:phiu')
    app.PrintPlain("{0}|{1}|{2}".format(name, vm, va))

app.PrintPlain("Lines")
for term in lines:
    name = term.GetAttribute('loc_name')
    P = term.GetAttribute('m:P:bus1')
    Q = term.GetAttribute('m:Q:bus1')
    app.PrintPlain("{0}|{1}|{2}".format(name, P, Q))

app.PrintPlain("Transformers2")
for term in tr2:
    name = term.GetAttribute('loc_name')
    P = term.GetAttribute('m:P:bushv')
    Q = term.GetAttribute('m:Q:bushv')
    app.PrintPlain("{0}|{1}|{2}".format(name, P, Q))
