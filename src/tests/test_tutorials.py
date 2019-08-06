from GridCal.Tutorials.defining_a_grid_from_scratch_with_profiles import main \
    as main_with_profiles
from GridCal.Tutorials.defining_a_grid_from_scratch_without_profiles import \
    main as main_without_profiles


def test_define_grid_from_scratch_without_profiles():
    main_without_profiles()


def _test_define_grid_from_scratch_with_profiles():
    main_with_profiles()
