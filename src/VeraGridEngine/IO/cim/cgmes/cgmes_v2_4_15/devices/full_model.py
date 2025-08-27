# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from typing import List
from VeraGridEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.identified_object import IdentifiedObject, CgmesProfileType


class FullModel(IdentifiedObject):

    def __init__(self, rdfid, tpe):
        IdentifiedObject.__init__(self, rdfid, tpe)

        self.scenarioTime: str | None = None
        self.created: str | None = None
        self.version: str | None = None
        self.profile: str | List[str] | None = None  # TODO: Crazy polymorphism
        self.modelingAuthoritySet: str | List[str] | None = None  # TODO: Crazy polymorphism
        self.DependentOn: str | list | None = None  # TODO: Crazy polymorphism
        self.longDependentOnPF: str | None = None
        self.Supersedes: str | None = None

        self.register_property(
            name='scenarioTime',
            class_type=str,
            description="scenarioTime.",
            profiles=[CgmesProfileType.TP_BD, CgmesProfileType.DL, CgmesProfileType.SSH, CgmesProfileType.EQ,
                      CgmesProfileType.DY, CgmesProfileType.TP, CgmesProfileType.EQ_BD, CgmesProfileType.GL,
                      CgmesProfileType.SV])

        self.register_property(
            name='created',
            class_type=str,
            description="Creation date.",
            profiles=[CgmesProfileType.TP_BD, CgmesProfileType.DL, CgmesProfileType.SSH, CgmesProfileType.EQ,
                      CgmesProfileType.DY, CgmesProfileType.TP, CgmesProfileType.EQ_BD, CgmesProfileType.GL,
                      CgmesProfileType.SV])

        self.register_property(
            name='version',
            class_type=int,
            description="version.",
            profiles=[CgmesProfileType.TP_BD, CgmesProfileType.DL, CgmesProfileType.SSH, CgmesProfileType.EQ,
                      CgmesProfileType.DY, CgmesProfileType.TP, CgmesProfileType.EQ_BD, CgmesProfileType.GL,
                      CgmesProfileType.SV])

        self.register_property(
            name='profile',
            class_type=str,
            description="profile.",
            profiles=[CgmesProfileType.TP_BD, CgmesProfileType.DL, CgmesProfileType.SSH, CgmesProfileType.EQ,
                      CgmesProfileType.DY, CgmesProfileType.TP, CgmesProfileType.EQ_BD, CgmesProfileType.GL,
                      CgmesProfileType.SV])

        self.register_property(
            name='modelingAuthoritySet',
            class_type=str,
            description="modelingAuthoritySet",
            profiles=[CgmesProfileType.TP_BD, CgmesProfileType.DL, CgmesProfileType.SSH, CgmesProfileType.EQ,
                      CgmesProfileType.DY, CgmesProfileType.TP, CgmesProfileType.EQ_BD, CgmesProfileType.GL,
                      CgmesProfileType.SV])

        self.register_property(
            name='DependentOn',
            class_type=str,
            description="DependentOn.",
            profiles=[CgmesProfileType.TP_BD, CgmesProfileType.DL, CgmesProfileType.SSH, CgmesProfileType.EQ,
                      CgmesProfileType.DY, CgmesProfileType.TP, CgmesProfileType.EQ_BD, CgmesProfileType.GL,
                      CgmesProfileType.SV])

        self.register_property(
            name='longDependentOnPF',
            class_type=str,
            description="longDependentOnPF.",
            profiles=[CgmesProfileType.TP_BD, CgmesProfileType.DL, CgmesProfileType.SSH, CgmesProfileType.EQ,
                      CgmesProfileType.DY, CgmesProfileType.TP, CgmesProfileType.EQ_BD, CgmesProfileType.GL,
                      CgmesProfileType.SV])

        self.register_property(
            name='Supersedes',
            class_type=str,
            description="Supersedes.",
            profiles=[CgmesProfileType.TP_BD, CgmesProfileType.DL, CgmesProfileType.SSH, CgmesProfileType.EQ,
                      CgmesProfileType.DY, CgmesProfileType.TP, CgmesProfileType.EQ_BD, CgmesProfileType.GL,
                      CgmesProfileType.SV])
