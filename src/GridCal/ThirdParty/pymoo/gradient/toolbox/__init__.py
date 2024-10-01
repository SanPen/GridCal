import importlib
import sys

from GridCal.ThirdParty.pymoo.gradient import TOOLBOX

sys.modules[__name__] = importlib.import_module(TOOLBOX)
