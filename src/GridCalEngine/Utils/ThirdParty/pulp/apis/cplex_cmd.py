# Copyright (c) 2002-2005, Jean-Sebastien Roy
# Modifications Copyright (c) 2007- Stuart Anthony Mitchell
# Modifications Copyright (c) 2014- Santiago Peñate Vera
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
from __future__ import annotations
import os
from typing import List, TYPE_CHECKING
import xml.etree.ElementTree as et

from GridCalEngine.Utils.ThirdParty.pulp.apis.lp_solver_cmd import LpSolver_CMD, subprocess
import GridCalEngine.Utils.ThirdParty.pulp.constants as constants
from GridCalEngine.Utils.ThirdParty.pulp.paths import get_solvers_config

if TYPE_CHECKING:
    from GridCalEngine.Utils.ThirdParty.pulp.model.lp_problem import LpProblem
    from GridCalEngine.Utils.ThirdParty.pulp.model.lp_objects import LpVariable


class CPLEX_CMD(LpSolver_CMD):
    """The CPLEX LP solver"""

    name = "CPLEX_CMD"

    def __init__(self,
                 mip=True,
                 msg=True,
                 timeLimit=None,
                 gapRel=None,
                 gapAbs=None,
                 options=None,
                 warmStart=False,
                 keepFiles=False,
                 path=None,
                 threads=None,
                 logPath=None,
                 maxMemory=None,
                 maxNodes=None):
        """
        :param bool mip: if False, assume LP even if integer variables
        :param bool msg: if False, no log is shown
        :param float timeLimit: maximum time for solver (in seconds)
        :param float gapRel: relative gap tolerance for the solver to stop (in fraction)
        :param float gapAbs: absolute gap tolerance for the solver to stop
        :param int threads: sets the maximum number of threads
        :param list options: list of additional options to pass to solver
        :param bool warmStart: if True, the solver will use the current value of variables as a start
        :param bool keepFiles: if True, files are saved in the current directory and not deleted after solving
        :param str path: path to the solver binary
        :param str logPath: path to the log file
        :param float maxMemory: max memory to use during the solving. Stops the solving when reached.
        :param int maxNodes: max number of nodes during branching. Stops the solving when reached.
        """
        LpSolver_CMD.__init__(
            self,
            gapRel=gapRel,
            mip=mip,
            msg=msg,
            timeLimit=timeLimit,
            options=options,
            maxMemory=maxMemory,
            maxNodes=maxNodes,
            warmStart=warmStart,
            path=path,
            keepFiles=keepFiles,
            threads=threads,
            gapAbs=gapAbs,
            logPath=logPath,
        )

    def defaultPath(self) -> str:
        """

        :return:
        """

        # try to get the executable path from the json config file in the .GridCal folder
        data = get_solvers_config()

        bin_path = data.get('cplex_bin', None)

        if bin_path is None:
            return self.executableExtension("cplex")
        else:
            if os.path.exists(bin_path):
                return bin_path
            else:
                return self.executableExtension("cplex")

    def available(self) -> str:
        """
        True if the solver is available
        :return:
        """
        return self.executable(self.path)

    def actualSolve(self, lp: LpProblem):
        """
        Solve a well formulated lp problem
        :param lp:
        :return:
        """
        """"""
        if not self.executable(self.path):
            raise constants.PulpSolverError("PuLP: cannot execute " + self.path)
        tmpLp, tmpSol, tmpMst = self.create_tmp_files(lp.name, "lp", "sol", "mst")
        vs = lp.writeLP(tmpLp, writeSOS=1)
        try:
            os.remove(tmpSol)
        except:
            pass
        if not self.msg:
            cplex_process = subprocess.Popen(
                self.path,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        else:
            cplex_process = subprocess.Popen(self.path, stdin=subprocess.PIPE)
        cplex_cmds = "read " + tmpLp + "\n"
        if self.optionsDict.get("warmStart", False):
            self.writesol(filename=tmpMst, vs=vs)
            cplex_cmds += "read " + tmpMst + "\n"
            cplex_cmds += "set advance 1\n"

        if self.timeLimit is not None:
            cplex_cmds += "set timelimit " + str(self.timeLimit) + "\n"
        options = self.options + self.getOptions()
        for option in options:
            cplex_cmds += option + "\n"
        if lp.isMIP():
            if self.mip:
                cplex_cmds += "mipopt\n"
                cplex_cmds += "change problem fixed\n"
            else:
                cplex_cmds += "change problem lp\n"
        cplex_cmds += "optimize\n"
        cplex_cmds += "write " + tmpSol + "\n"
        cplex_cmds += "quit\n"
        cplex_cmds = cplex_cmds.encode("UTF-8")
        cplex_process.communicate(cplex_cmds)
        if cplex_process.returncode != 0:
            raise constants.PulpSolverError("PuLP: Error while trying to execute " + self.path)

        if not os.path.exists(tmpSol):
            status = constants.LpStatusInfeasible
            values = reducedCosts = shadowPrices = slacks = solStatus = None

        else:
            (
                status,
                values,
                reducedCosts,
                shadowPrices,
                slacks,
                solStatus,
            ) = self.readsol(tmpSol)
        self.delete_tmp_files(tmpLp, tmpMst, tmpSol)
        if self.optionsDict.get("logPath") != "cplex.log":
            self.delete_tmp_files("cplex.log")
        if status != constants.LpStatusInfeasible:
            lp.assignVarsVals(values)
            lp.assignVarsDj(reducedCosts)
            lp.assignConsPi(shadowPrices)
            lp.assignConsSlack(slacks)
        lp.assignStatus(status, solStatus)
        return status

    def getOptions(self):
        """

        :return:
        """
        # CPLEX parameters: https://www.ibm.com/support/knowledgecenter/en/SSSA5P_12.6.0/ilog.odms.cplex.help/CPLEX/GettingStarted/topics/tutorials/InteractiveOptimizer/settingParams.html
        # CPLEX status: https://www.ibm.com/support/knowledgecenter/en/SSSA5P_12.10.0/ilog.odms.cplex.help/refcallablelibrary/macros/Solution_status_codes.html
        params_eq = dict(
            logPath="set logFile {}",
            gapRel="set mip tolerances mipgap {}",
            gapAbs="set mip tolerances absmipgap {}",
            maxMemory="set mip limits treememory {}",
            threads="set threads {}",
            maxNodes="set mip limits nodes {}",
        )
        return [
            v.format(self.optionsDict[k])
            for k, v in params_eq.items()
            if k in self.optionsDict and self.optionsDict[k] is not None
        ]

    @staticmethod
    def readsol(filename: str):
        """
        Read a CPLEX solution file
        :param filename:
        :return:
        """

        # CPLEX solution codes: http://www-eio.upc.es/lceio/manuals/cplex-11/html/overviewcplex/statuscodes.html
        solutionXML = et.parse(filename).getroot()
        solutionheader = solutionXML.find("header")
        statusString = solutionheader.get("solutionStatusString")
        statusValue = solutionheader.get("solutionStatusValue")
        cplexStatus = {
            "1": constants.LpStatusOptimal,  # optimal
            "3": constants.LpStatusInfeasible,  # infeasible
            "5": constants.LpStatusOptimalWithUnscalesInfeasibilities,
            "101": constants.LpStatusOptimal,  # mip optimal
            "102": constants.LpStatusOptimal,  # mip optimal tolerance
            "104": constants.LpStatusOptimal,  # max solution limit
            "105": constants.LpStatusOptimal,  # node limit feasible
            "107": constants.LpStatusOptimal,  # time lim feasible
            "109": constants.LpStatusOptimal,  # fail but feasible
            "113": constants.LpStatusOptimal,  # abort feasible
        }
        status = cplexStatus.get(statusValue, constants.LpUnknown)

        # we check for integer feasible status to differentiate from optimal in solution status
        cplexSolStatus = {
            "104": constants.LpSolutionIntegerFeasible,  # max solution limit
            "105": constants.LpSolutionIntegerFeasible,  # node limit feasible
            "107": constants.LpSolutionIntegerFeasible,  # time lim feasible
            "109": constants.LpSolutionIntegerFeasible,  # fail but feasible
            "111": constants.LpSolutionIntegerFeasible,  # memory limit feasible
            "113": constants.LpSolutionIntegerFeasible,  # abort feasible
        }
        solStatus = cplexSolStatus.get(statusValue)
        shadowPrices = {}
        slacks = {}
        constraints = solutionXML.find("linearConstraints")
        for constraint in constraints:
            name = constraint.get("name")
            slack = constraint.get("slack")
            shadowPrice = constraint.get("dual")
            try:
                # See issue #508
                shadowPrices[name] = float(shadowPrice)
            except TypeError:
                shadowPrices[name] = None
            slacks[name] = float(slack)

        values = {}
        reducedCosts = {}
        for variable in solutionXML.find("variables"):
            name = variable.get("name")
            value = variable.get("value")
            values[name] = float(value)
            reducedCost = variable.get("reducedCost")
            try:
                # See issue #508
                reducedCosts[name] = float(reducedCost)
            except TypeError:
                reducedCosts[name] = None

        return status, values, reducedCosts, shadowPrices, slacks, solStatus

    @staticmethod
    def writesol(filename: str, vs: List[LpVariable]):
        """
        Writes a CPLEX solution file
        :param filename:
        :param vs:
        :return:
        """

        root = et.Element("CPLEXSolution", version="1.2")
        attrib_head = dict()
        attrib_quality = dict()
        et.SubElement(root, "header", attrib=attrib_head)
        et.SubElement(root, "header", attrib=attrib_quality)
        variables = et.SubElement(root, "variables")

        values = [(v.name, v.value()) for v in vs if v.value() is not None]
        for index, (name, value) in enumerate(values):
            attrib_vars = dict(name=name, value=str(value), index=str(index))
            et.SubElement(variables, "variable", attrib=attrib_vars)

        mst = et.ElementTree(root)
        mst.write(filename, encoding="utf-8", xml_declaration=True)

        return True


CPLEX = CPLEX_CMD
