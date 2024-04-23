from GridCal.Gui.Diagrams.MapWidget.Schema.Substations import SubstationGraphicItem
from GridCalEngine.Devices import MultiCircuit

def test_lat_log(diagramEditor, lat, long):
    """
    This function test latitude and longitude conversion to X and Y values in raster image
    It uses adhoc values devX and devY for that purpose
    :param diagramEditor:
    :param lat:
    :param long:
    :return:
    """
    devX = 48.3
    devY = 61.9
    res = diagramEditor.geo_to_view(lat, long)
    posX = long * devX
    posY = -lat * devY