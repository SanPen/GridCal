from PySide6.QtWidgets import QSizePolicy, QWidget, QMessageBox
from GridCal.Gui.MapWidget.map_widget import MapWidget


class GridMapWidget(MapWidget):

    def __init__(self, parent: QWidget, tile_src, start_level: int, name: str):
        MapWidget.__init__(self, parent=parent, tile_src=tile_src, start_level=start_level)

        self.name = name

        # add empty polylines layer
        self.polyline_layer_id = self.AddPolylineLayer(data=[],
                                                       map_rel=True,
                                                       visible=True,
                                                       show_levels=list(range(20)),
                                                       selectable=True,
                                                       # levels at which to show the polylines
                                                       name='<polyline_layer>')

    def setBranchData(self, data):
        self.setLayerData(self.polyline_layer_id, data)
        self.update()