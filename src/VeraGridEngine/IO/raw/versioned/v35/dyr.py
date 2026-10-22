# SPDX-License-Identifier: MPL-2.0
"""POM 35.2 section 16.1.1; ReleaseNotes 35.0 section 7.4 adds USRSWS2 and retains USRSWS. Model aliases are never rewritten."""
from VeraGridEngine.IO.raw.psse_auxiliary import PsseVersion
from VeraGridEngine.IO.raw.versioned.base.dyr import DynamicModelSchema
from VeraGridEngine.IO.raw.versioned.base.auxiliary import FeatureSupport
from VeraGridEngine.IO.raw.versioned.v34.dyr import RawDyrV34


class RawDyrV35(RawDyrV34):
    """PSS/E 35 DYR data; inherit only unchanged grammar."""

    __slots__ = ()

    def __init__(self, source: str = '<dyr>') -> None:
        """Select the documented PSS/E 35 grammar.

        :param source: Diagnostic source label.
        """
        super().__init__(source)
        self.version = PsseVersion.V35
        self.usr_sws2_support = FeatureSupport.YES
        # POM 35.2 section 16.1.1 includes renewable torque calling sequence 108.
        self.torque_model_support = FeatureSupport.YES

    def get_model_schema(self, model: str) -> DynamicModelSchema | None:
        """Select the direct deadband-governor layout documented in this release.

        The earlier supplied library exposes a distinct user-model wrapper.
        That header is not interpreted as this direct built-in assignment.

        :param model: Source model identifier, case insensitive.
        :return: Explicit release schema or an unchanged inherited layout.
        """
        deadband_parents: dict[str,str] = dict(DEGOV1D='DEGOV1', GASTD='GAST', IEESGOD='IEESGO', HYGOVD='HYGOV', HYGOV2D='HYGOV2', PIDGOVD='PIDGOV', TGOV1D='TGOV1')
        parent_name: str | None = deadband_parents.get(model.upper(),None)
        if parent_name is not None:
            parent: DynamicModelSchema | None = super().get_model_schema(parent_name)
            if parent is None:
                return None
            else:
                return DynamicModelSchema(model.upper(),parent.parameters+('DBH','DBL','TRATE'),
                    parent.icon_names,parent.character_icon_names,parent.signed_icon_names)
        elif model.upper() == 'AC7C':
            return DynamicModelSchema('AC7C',('TR','KPR','KIR','KDR','TDR','VRMAX','VRMIN','KPA','KIA','VAMAX','VAMIN','KP','KL','KF1','KF2','KF3','TF3','KC','KD','KE','TE','VFEMAX','VEMIN','E1','SE1','E2','SE2','KI','XL','THETAP','KC1','VBMAX','KR'),('OEL','UEL','SCL','PSS','SW1','SW2'))
        elif model.upper() == 'ST6C':
            return DynamicModelSchema('ST6C',('TR','KPA','KIA','KDA','TDA','VAMAX','VAMIN','KFF','KM','KCI','KLR','ILR','VRMAX','VRMIN','KG','TG','VMMAX','VMMIN','TA','KP','KI','XL','THETAP','KC','VBMAX'),('OEL','UEL','SCL','SW1'))
        elif model.upper() == 'DC4C':
            return DynamicModelSchema('DC4C',('TR','KPR','KJR','KDR','TDR','VRMAX','VRMIN','KA','TA','KE','TE','KF','TF','VEMIN','E1','SE1','E2','SE2','KP','KI','XL','THETAP','KC1','VBMAX'),('OEL','UEL','SCL','SW1'))
        elif model.upper() == 'AC8C':
            return DynamicModelSchema('AC8C',('TR','KPR','KIR','KDR','TDR','VPIDMAX','VPIDMIN','KA','TA','VRMAX','VRMIN','KC','KD','KE','TE','VFEMAX','VEMIN','E1','SE1','E2','SE2','KP','KI','XL','THETAP','KC1','VBMAX'),('OEL','UEL','SCL','PSS','SW1'))
        elif model.upper() == 'ST5C':
            return DynamicModelSchema('ST5C',('TR','TC1','TB1','TC2','TB2','KR','VRMAX','VRMIN','T1','KC','TUC1','TUB1','TUC2','TUB2','TOC1','TOB1','TOC2','TOB2'),('OEL','UEL'))
        elif model.upper() == 'ST4C':
            return DynamicModelSchema('ST4C',('TR','KPR','KIR','VRMAX','VRMIN','KPM','KIM','VMMAX','VMMIN','TA','VAMAX','VAMIN','KG','TG','VGMAX','KP','KI','XL','THETAP','KC','VBMAX'),('PSS','OEL','UEL','SCL','SW1'))
        elif model.upper() == 'ST7C':
            return DynamicModelSchema('ST7C',('TR','TG','TF','VMAX','VMIN','KPA','VRMAX','VRMIN','KH','KL','TC','TB','KIA','TIA','TA'),('OEL','UEL'))
        elif model.upper() == 'ST1C':
            return DynamicModelSchema('ST1C',('TR','VIMAX','VIMIN','TC','TB','TC1','TB1','KA','TA','VAMAX','VAMIN','VRMAX','VRMIN','KC','KF','TF','KLR','ILR'),('UEL','VOS','OEL'))
        elif model.upper() == 'AC5C':
            return DynamicModelSchema('AC5C',('TR','KA','TA','VRMAX','VRMIN','KE','TE','KF','TF1','TF2','TF3','E1','SE1','E2','SE2','KC','KD','VFEMAX','VEMIN'),('OEL','UEL'))
        elif model.upper() == 'AC1C':
            return DynamicModelSchema('AC1C',('TR','TB','TC','KA','TA','VAMAX','VAMIN','TE','KF','TF','KC','KD','KE','E1','SE1','E2','SE2','VRMAX','VRMIN','VFEMAX','VEMIN'),('OEL','UEL'))
        elif model.upper() == 'AC2C':
            return DynamicModelSchema('AC2C',('TR','TB','TC','KA','TA','VAMAX','VAMIN','KB','VRMAX','VRMIN','TE','VFEMAX','KH','KF','TF','KC','KD','KE','E1','SE1','E2','SE2','VEMIN'),('OEL','UEL'))
        elif model.upper() == 'AC4C':
            return DynamicModelSchema('AC4C',('TR','VIMAX','VIMIN','TC','TB','KA','TA','VRMAX','VRMIN','KC'),('OEL','UEL'))
        elif model.upper() in ('DC1C','DC2C'):
            return DynamicModelSchema(model.upper(),('TR','KA','TA','TB','TC','VRMAX','VRMIN','KE','TE','KF','TF','E1','SE1','E2','SE2','VEMAX','VEMIN'),('OEL','UEL'))
        elif model.upper() == 'PSS2C':
            return DynamicModelSchema('PSS2C',('TW1','TW2','T6','TW3','TW4','T7','KS2','KS3','T8','T9','KS1','T1','T2','T3','T4','T10','T11','VS1MAX','VS1MIN','VS2MAX','VS2MIN','VSTMAX','VSTMIN','T12','T13','PSSON','PSSOFF','XCOMP','TCOMP'),('ICS1','REMBUS1','ICS2','REMBUS2','M','N'))
        elif model.upper() == 'BUDCZT':
            # Model Library 35.2 section 6.17 puts TE before TA.
            return DynamicModelSchema('BUDCZT',('KP','KA','KE','TR','TI','TE','TA','URMAX','URMIN','EFDMAX','EFDMIN'))
        elif model.upper() == 'GGOV1D':
            base: DynamicModelSchema | None = super().get_model_schema('GGOV1')
            if base is None:
                return None
            else:
                return DynamicModelSchema('GGOV1D', base.parameters+('DBH', 'DBL'),
                    base.icon_names, base.character_icon_names, base.signed_icon_names)
        elif model.upper() == 'IEEEG1D':
            return DynamicModelSchema('IEEEG1D', ('K', 'T1', 'T2', 'T3', 'UO', 'UC', 'PMAX', 'PMIN',
                'T4', 'K1', 'K2', 'T5', 'K3', 'K4', 'T6', 'K5', 'K6', 'T7', 'K7', 'K8',
                'DBH', 'DBL', 'TRATE'), ('JBUS', 'JD'), ('JD',))
        elif model.upper() == 'IEEEG3D':
            return DynamicModelSchema('IEEEG3D', ('TG', 'TP', 'UO', 'UC', 'PMAX', 'PMIN',
                'SIGMA', 'DELTA', 'TR', 'TW', 'A11', 'A13', 'A21', 'A23', 'DBH', 'DBL', 'TRATE'))
        else:
            return super().get_model_schema(model)
