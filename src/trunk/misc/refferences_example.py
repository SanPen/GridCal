from uuid import uuid4


class Load:

    def __init__(self):
        self.idtag = uuid4().hex
        self.P = 0


class Diagram:

    def __init__(self):
        self.load_dict = dict()

    def add_load(self, elm: Load):
        self.load_dict[elm.idtag] = elm

    def del_load(self, elm: Load):
        del self.load_dict[elm.idtag]


class Circuit:

    def __init__(self):
        self.load_list = list()
        self.diagram_list = list()

    def del_load(self, elm: Load):
        self.load_list.remove(elm)

        for diag in self.diagram_list:
            diag.del_load(elm)


if __name__ == '__main__':
    l1 = Load()

    circuit = Circuit()
    circuit.load_list.append(l1)

    diagram1 = Diagram()
    diagram1.add_load(l1)
    circuit.diagram_list.append(diagram1)

    diagram2 = Diagram()
    diagram2.add_load(l1)
    circuit.diagram_list.append(diagram2)

    circuit.del_load(l1)

    print()
