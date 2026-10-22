# SPDX-License-Identifier: MPL-2.0
"""POM 33.10 section 15.1.1 defines USRSWS without an equipment ID. Built-in schemas follow the generator model data sheets."""
from VeraGridEngine.IO.raw.psse_auxiliary import PsseVersion
from VeraGridEngine.IO.raw.versioned.base.auxiliary import FeatureSupport
from VeraGridEngine.IO.raw.versioned.base.dyr import (
    RawDyr, DynamicModelSchema, UserDynamicModelSchema, UserModelType)


class RawDyrV33(RawDyr):
    """PSS/E 33 DYR data; inherit only unchanged grammar."""

    __slots__ = ()

    def __init__(self, source: str = '<dyr>') -> None:
        """Select the documented PSS/E 33 grammar.

        :param source: Diagnostic source label.
        """
        super().__init__(source, PsseVersion.V33)
        self.usr_sws2_support = FeatureSupport.NO
        # POM 33.10 section 15.1.1 lists renewable IC codes 101 through 107.
        self.torque_model_support = FeatureSupport.NO

    def get_model_schema(self, model: str) -> DynamicModelSchema | None:
        """Own the release-specific actuator/exciter constant order.

        :param model: Source model identifier, case insensitive.
        :return: Explicit reviewed layout or unchanged common schema.
        """
        if model.upper() == 'BUDCZT':
            # Model Library 33.10 section 6.4 puts TA before TE.
            return DynamicModelSchema('BUDCZT',('KP','KA','KE','TR','TI','TA','TE','URMAX','URMIN','EFDMAX','EFDMIN'))
        else:
            return super().get_model_schema(model)

    def get_user_model_schema(self, name: str) -> UserDynamicModelSchema | None:
        """Select the explicitly reviewed 33.10 governor subroutine contracts.

        :param name: Exact source user-subroutine identifier, case insensitive.
        :return: Reviewed layout/allocation contract or None for unreviewed routines.
        """
        contracts: dict[str,tuple[str,int,int]] = dict(TGOV1DU=('TGOV1',2,2), GASTDU=('GAST',3,2),
            HYGOVDU=('HYGOV',4,3), HYGOV2DU=('HYGOV2',6,2), IEESGODU=('IEESGO',5,2))
        contract: tuple[str,int,int] | None = contracts.get(name.upper(),None)
        if contract is not None:
            parent: DynamicModelSchema | None = self.get_model_schema(contract[0])
            if parent is None:
                return None
            else:
                return UserDynamicModelSchema(DynamicModelSchema(name.upper(),
                    parent.parameters+('DBH','DBL','TRATE')),UserModelType.GOVERNOR,0,contract[1],contract[2])
        elif name.upper() == 'DEGOV1DU':
            engine: DynamicModelSchema | None = self.get_model_schema('DEGOV1')
            if engine is None:
                return None
            else:
                return UserDynamicModelSchema(DynamicModelSchema('DEGOV1DU',
                    engine.parameters+('DBH','DBL','TRATE'),engine.icon_names),UserModelType.GOVERNOR,0,6,15)
        elif name.upper() == 'PIDGOVDU':
            pid: DynamicModelSchema | None = self.get_model_schema('PIDGOV')
            if pid is None:
                return None
            else:
                return UserDynamicModelSchema(DynamicModelSchema('PIDGOVDU',pid.parameters+('DBH','DBL','TRATE'),pid.icon_names),UserModelType.GOVERNOR,0,7,2)
        elif name.upper() == 'GGOV1DU':
            base: DynamicModelSchema | None = self.get_model_schema('GGOV1')
            if base is None:
                return None
            else:
                layout: DynamicModelSchema = DynamicModelSchema('GGOV1DU', base.parameters+('DBH','DBL'),
                    base.icon_names, base.character_icon_names, base.signed_icon_names)
                return UserDynamicModelSchema(layout, UserModelType.GOVERNOR, 0, 10, 22)
        elif name.upper() == 'IEEEG1SDU':
            steam: DynamicModelSchema | None = self.get_model_schema('IEEEG1')
            if steam is None:
                return None
            else:
                return UserDynamicModelSchema(DynamicModelSchema('IEEEG1SDU',
                    steam.parameters+('DBH','DBL','TRATE')), UserModelType.GOVERNOR, 0, 6, 3)
        elif name.upper() == 'IEEEG3DU':
            hydro: DynamicModelSchema | None = self.get_model_schema('IEEEG3')
            if hydro is None:
                return None
            else:
                return UserDynamicModelSchema(DynamicModelSchema('IEEEG3DU',
                    hydro.parameters+('DBH','DBL','TRATE')), UserModelType.GOVERNOR, 0, 4, 2)
        else:
            return None
