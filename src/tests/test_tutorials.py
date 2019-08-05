import os
from sys import executable

from Tutorials import defining_a_grid_from_scratch_without_profiles
# from Tutorials import defining_a_grid_from_scratch_with_profiles


def test_define_grid_from_scratch_without_profiles():
    os.system(
        executable + ' ' +
        defining_a_grid_from_scratch_without_profiles.__file__
    )


def _test_define_grid_from_scratch_with_profiles():
    os.system(
        executable + ' ' +
        defining_a_grid_from_scratch_with_profiles.__file__
    )
