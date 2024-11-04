# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.identified_object import IdentifiedObject, cgmesProfile


class FullModel(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.scenarioTime: str = None
        self.created: str = None
        self.version: str = None
        self.profile: str | list = None
        self.modelingAuthoritySet: str = None
        self.DependentOn: str | list = None
        self.longDependentOnPF: str = None
        self.Supersedes: str = None

        self.register_property(
            name='scenarioTime',
            class_type=str,
            description="scenarioTime.",
            profiles=[cgmesProfile.TP_BD, cgmesProfile.DL, cgmesProfile.SSH, cgmesProfile.EQ,
                      cgmesProfile.DY, cgmesProfile.TP, cgmesProfile.EQ_BD, cgmesProfile.GL,
                      cgmesProfile.SV])

        self.register_property(
            name='created',
            class_type=str,
            description="Creation date.",
            profiles=[cgmesProfile.TP_BD, cgmesProfile.DL, cgmesProfile.SSH, cgmesProfile.EQ,
                      cgmesProfile.DY, cgmesProfile.TP, cgmesProfile.EQ_BD, cgmesProfile.GL,
                      cgmesProfile.SV])

        self.register_property(
            name='version',
            class_type=int,
            description="version.",
            profiles=[cgmesProfile.TP_BD, cgmesProfile.DL, cgmesProfile.SSH, cgmesProfile.EQ,
                      cgmesProfile.DY, cgmesProfile.TP, cgmesProfile.EQ_BD, cgmesProfile.GL,
                      cgmesProfile.SV])

        self.register_property(
            name='profile',
            class_type=str,
            description="profile.",
            profiles=[cgmesProfile.TP_BD, cgmesProfile.DL, cgmesProfile.SSH, cgmesProfile.EQ,
                      cgmesProfile.DY, cgmesProfile.TP, cgmesProfile.EQ_BD, cgmesProfile.GL,
                      cgmesProfile.SV])

        self.register_property(
            name='modelingAuthoritySet',
            class_type=str,
            description="modelingAuthoritySet",
            profiles=[cgmesProfile.TP_BD, cgmesProfile.DL, cgmesProfile.SSH, cgmesProfile.EQ,
                      cgmesProfile.DY, cgmesProfile.TP, cgmesProfile.EQ_BD, cgmesProfile.GL,
                      cgmesProfile.SV])

        self.register_property(
            name='DependentOn',
            class_type=str,
            description="DependentOn.",
            profiles=[cgmesProfile.TP_BD, cgmesProfile.DL, cgmesProfile.SSH, cgmesProfile.EQ,
                      cgmesProfile.DY, cgmesProfile.TP, cgmesProfile.EQ_BD, cgmesProfile.GL,
                      cgmesProfile.SV])

        self.register_property(
            name='longDependentOnPF',
            class_type=str,
            description="longDependentOnPF.",
            profiles=[cgmesProfile.TP_BD, cgmesProfile.DL, cgmesProfile.SSH, cgmesProfile.EQ,
                      cgmesProfile.DY, cgmesProfile.TP, cgmesProfile.EQ_BD, cgmesProfile.GL,
                      cgmesProfile.SV])

        self.register_property(
            name='Supersedes',
            class_type=str,
            description="Supersedes.",
            profiles=[cgmesProfile.TP_BD, cgmesProfile.DL, cgmesProfile.SSH, cgmesProfile.EQ,
                      cgmesProfile.DY, cgmesProfile.TP, cgmesProfile.EQ_BD, cgmesProfile.GL,
                      cgmesProfile.SV])
