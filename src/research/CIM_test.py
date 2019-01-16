import logging
from PyCIM import cimread

logging.basicConfig(level=logging.INFO)
d = cimread('CIMsamples/cim14/ABB40busModified.xml')

pass