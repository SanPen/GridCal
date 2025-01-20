class Line:
    def __init__(self):
        self.node1 = ""  # 0-7: Node 1 code
        self.node2 = ""  # 9-16: Node 2 code
        self.order_code = ""  # 18: Order code
        self.status = 0  # 20: Status
        self.resistance = 0.0  # 22-27: Resistance (Ω)
        self.reactance = 0.0  # 29-34: Reactance (Ω)
        self.susceptance = 0.0  # 36-43: Susceptance (µS)
        self.current_limit = 0  # 45-50: Current limit (A)
        self.name = ""

    def parse(self, line):
        self.node1 = line[0:8].strip()
        self.node2 = line[9:17].strip()
        self.order_code = line[18:19].strip()
        self.status = int(line[20:21].strip())
        self.resistance = float(line[22:28].strip())
        self.reactance = float(line[29:35].strip())
        self.susceptance = float(line[36:44].strip())
        self.current_limit = int(line[45:51].strip())
        self.name = int(line[53:65].strip())