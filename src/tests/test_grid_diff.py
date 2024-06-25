import os
import GridCalEngine.api as gce


def test_add_stuff_roundtrip() -> None:
    """

    :return:
    """
    original = gce.open_file(filename=os.path.join("data", "grids", "IEEE57.gridcal"))  # we use this for diff
    grid1 = gce.open_file(filename=os.path.join("data", "grids", "IEEE57.gridcal"))  # we modify this one in place

    # add stuff
    lynn_original = gce.open_file(filename=os.path.join("data", "grids", "lynn5node.gridcal"))
    lynn_original.delete_profiles()

    # add elements one by one
    for elm in lynn_original.items():
        grid1.add_element(obj=elm)
        # TODO: adding elements makes null the preeisting bus!

    # calculate the difference of the modified grid with the original
    ok_diff, diff_logger, diff = grid1.differentiate_circuits(base_grid=original)

    diff.clean()

    # the calculated difference should be equal to the grid we added
    ok_compare, comp_logger = diff.compare_circuits(grid2=lynn_original)

    if not ok_compare:
        comp_logger.print()

    assert ok_compare
