import pytest
from GridCalEngine.IO.cim.cgmes.cgmes_utils import get_windings_number, get_windings
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.power_transformer import PowerTransformer

from src.GridCalEngine.IO.cim.cgmes.cgmes_utils import get_pu_values_power_transformer


def test_get_windings_number_no_windings_returns_zero():
    # Create a PowerTransformer instance with no references to PowerTransformerEnd
    power_transformer = PowerTransformer("a", "b")
    assert get_windings_number(power_transformer) == 0


def test_get_windings_number_multiple_winding_returns_correct_amount():
    # Create a PowerTransformer instance with one reference to PowerTransformerEnd
    power_transformer = PowerTransformer("a", "b")
    power_transformer.references_to_me["PowerTransformerEnd"] = [1, 2, 3]
    assert get_windings_number(power_transformer) == 3


def test_get_windings_no_windings_returns_no_element():
    # Create a PowerTransformer instance with no references to PowerTransformerEnd
    power_transformer = PowerTransformer("a", "b")
    assert len(get_windings(power_transformer)) == 0


def test_get_windings_add_windings_returns_correct_element():
    # Create a PowerTransformer instance with no references to PowerTransformerEnd
    power_transformer = PowerTransformer("a", "b")
    power_transformer.references_to_me["PowerTransformerEnd"] = [1]
    assert get_windings(power_transformer)[0] == 1


def test_get_pu_values_power_transformer_no_power_transformer():
    with pytest.raises(AttributeError) as excinfo:
        get_pu_values_power_transformer(None, 100.0)
        assert str(excinfo.value).index('NoneType') != -1
        assert str(excinfo.value).index('references_to_me') != -1


def test_get_pu_values_power_transformer_no_winding():
    power_transformer = PowerTransformer()
    power_transformer.references_to_me["PowerTransformerEnd"] = []
    (R, X, G, B, R0, X0, G0, B0) = get_pu_values_power_transformer(power_transformer, 100.0)
    assert R == 0
    assert X == 0
    assert G == 0
    assert B == 0
    assert R0 == 0
    assert X0 == 0
    assert G0 == 0
    assert B0 == 0
