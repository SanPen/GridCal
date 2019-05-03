

class Branch:
    """
    Branch class template
    """

    def __init__(self, name, bus_from, bus_to, rating):
        self.name = name

        self.f = bus_from

        self.t = bus_to

        self.rating = rating

    def get_ABCD(self, Sbase):
        pass