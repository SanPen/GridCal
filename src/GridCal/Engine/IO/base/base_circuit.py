

class BaseCircuit:

    def __init__(self):
        pass

    def get_class_properties(self):
        return list()

    def get_objects_list(self, elm_type):
        return getattr(self, elm_type)
