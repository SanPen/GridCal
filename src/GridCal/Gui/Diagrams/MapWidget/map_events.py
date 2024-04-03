
from typing import Tuple
from PySide6.QtCore import Signal, QObject


class BaseEvent(QObject):
    """
    Base event class
    """
    signal = Signal(object)

    def __init__(self):
        super(BaseEvent, self).__init__()

    def emit_event(self):
        """
        Emit the class data
        """
        self.signal.emit(self)


class LevelEvent(BaseEvent):

    def __init__(self, level: int):
        super(LevelEvent, self).__init__()

        self.level = level


class PositionEvent(BaseEvent):

    def __init__(self,
                 mposn: Tuple[None, None],
                 vposn: Tuple[int, int]):
        super(PositionEvent, self).__init__()

        self.mposn = mposn
        self.vposn = vposn


class SelectEvent(BaseEvent):

    def __init__(self,
                 mposn: Tuple[None, None],
                 vposn: Tuple[int, int],
                 layer_id,
                 selection,
                 relsel):
        super(SelectEvent, self).__init__()

        self.mposn = mposn
        self.vposn = vposn
        self.layer_id = layer_id
        self.selection = selection
        self.relsel = relsel


class BoxSelectEvent(BaseEvent):

    def __init__(self,
                 mposn: Tuple[None, None],
                 vposn: Tuple[int, int],
                 layer_id,
                 selection,
                 relsel):
        super(BoxSelectEvent, self).__init__()

        self.mposn = mposn
        self.vposn = vposn
        self.layer_id = layer_id
        self.selection = selection
        self.relsel = relsel


class PolySelectEvent(BaseEvent):

    def __init__(self,
                 mposn: Tuple[None, None],
                 vposn: Tuple[int, int],
                 layer_id,
                 selection,
                 relsel):
        super(PolySelectEvent, self).__init__()

        self.mposn = mposn
        self.vposn = vposn
        self.layer_id = layer_id
        self.selection = selection
        self.relsel = relsel


class PolyBoxSelectEvent(BaseEvent):

    def __init__(self,
                 mposn: Tuple[None, None],
                 vposn: Tuple[int, int],
                 layer_id,
                 selection,
                 relsel):
        super(PolyBoxSelectEvent, self).__init__()

        self.mposn = mposn
        self.vposn = vposn
        self.layer_id = layer_id
        self.selection = selection
        self.relsel = relsel
