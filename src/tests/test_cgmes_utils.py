import pytest
from GridCalEngine.IO.cim.cgmes.cgmes_utils import get_windings_number, get_windings
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.power_transformer import PowerTransformer


def test_get_windings_number_no_windings_returns_zero():
    # Create a PowerTransformer instance with no references to PowerTransformerEnd
    power_transformer = PowerTransformer("a","b")
    assert get_windings_number(power_transformer) == 0

def test_get_windings_number_multiple_winding_returns_correct_amount():
    # Create a PowerTransformer instance with one reference to PowerTransformerEnd
    power_transformer = PowerTransformer("a","b")
    power_transformer.references_to_me["PowerTransformerEnd"] = [1,2,3]
    assert get_windings_number(power_transformer) == 3


def test_get_windings_no_windings_returns_no_element():
    # Create a PowerTransformer instance with no references to PowerTransformerEnd
    power_transformer = PowerTransformer("a","b")
    assert len(get_windings(power_transformer)) == 0

def test_get_windings_no_windings_returns_no_element():
    # Create a PowerTransformer instance with no references to PowerTransformerEnd
    power_transformer = PowerTransformer("a","b")
    power_transformer.references_to_me["PowerTransformerEnd"] = [1]
    assert get_windings(power_transformer)[0] == 1