# -*- coding: utf-8 -*-
"""
Created on Mon Sep 11 12:54:57 2017

@author: Steven

P9 Tested
"""

import os, sys, clr
import json

# load PLEXOS assemblies
sys.path.append('C:\Program Files\Energy Exemplar\PLEXOS 9.0 API')
clr.AddReference('EEUTILITY')
clr.AddReference('EnergyExemplar.PLEXOS.Utility')

# .NET related imports
from EEUTILITY.Enums import *
from EnergyExemplar.PLEXOS.Utility.Enums import *
from System import Enum

def get_enums_dict(cls):

    d = dict()
    for t in clr.GetClrType(cls).Assembly.GetTypes():
        if t.IsEnum:
            attributes = list()
            for en in t.GetEnumNames():
                attributes.append(en)

            if len(attributes):
                d[t.Name] = attributes

    return d


data = {"clases": get_enums_dict(ClassEnum),
        "file_format": get_enums_dict(FlatFileFormatEnum)}


with open('data.json', 'w') as f:
    json.dump(data, f, indent=4)