from GridCal.ThirdParty.pymoo.util.ref_dirs.energy import RieszEnergyReferenceDirectionFactory
from GridCal.ThirdParty.pymoo.util.ref_dirs.energy_layer import LayerwiseRieszEnergyReferenceDirectionFactory
from GridCal.ThirdParty.pymoo.util.ref_dirs.reduction import ReductionBasedReferenceDirectionFactory
from GridCal.ThirdParty.pymoo.util.reference_direction import MultiLayerReferenceDirectionFactory


def get_reference_directions(name, *args, **kwargs):
    from GridCal.ThirdParty.pymoo.util.reference_direction import UniformReferenceDirectionFactory

    REF = {
        "uniform": UniformReferenceDirectionFactory,
        "das-dennis": UniformReferenceDirectionFactory,
        "energy": RieszEnergyReferenceDirectionFactory,
        "multi-layer": MultiLayerReferenceDirectionFactory,
        "layer-energy": LayerwiseRieszEnergyReferenceDirectionFactory,
        "reduction": ReductionBasedReferenceDirectionFactory,
    }

    if name not in REF:
        raise Exception("Reference directions factory not found.")

    return REF[name](*args, **kwargs)()
