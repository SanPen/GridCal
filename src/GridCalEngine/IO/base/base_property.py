
from typing import Dict
from GridCalEngine.IO.base.units import Unit


class BaseProperty:

    def __init__(self, property_name: str,
                 class_type: object,
                 unit: Unit,
                 denominator_unit: Unit = None,
                 description: str = '',
                 max_chars=65000,
                 min_value=-1e20,
                 max_value=1e20):
        """

        :param property_name:
        :param class_type:
        :param unit:
        :param denominator_unit:
        :param description:
        :param max_chars:
        :param min_value:
        :param max_value:
        """
        self.property_name = property_name
        self.class_type = class_type
        self.unit = unit
        self.denominator_unit = denominator_unit
        self.description = description
        self.max_chars = max_chars
        self.min_value = min_value
        self.max_value = max_value

    def get_class_name(self):
        tpe_name = str(self.class_type)
        if '.' in tpe_name:
            chunks = tpe_name.split('.')
            return chunks[-1].replace("'", "") \
                .replace("<", "") \
                .replace(">", "").strip()
        else:
            return tpe_name.replace('class', '') \
                .replace("'", "") \
                .replace("<", "") \
                .replace(">", "").strip()

    def get_unit(self):

        if self.unit is not None:

            if self.unit.has_unit():
                nom = self.unit.get_unit()

                if self.denominator_unit is not None:

                    if self.denominator_unit.has_unit():
                        den = self.denominator_unit.get_unit()

                        return "{0}/{1}".format(nom, den)
                    else:
                        return nom

                else:
                    return nom
            else:
                return ""
        else:
            if self.denominator_unit is not None:
                den = self.denominator_unit.get_unit()

                return "1/{}".format(den)

            else:
                return ""

    def get_dict(self) -> Dict[str, any]:

        return {'property_name': self.property_name,
                'class_type': self.get_class_name(),
                'units': self.get_unit(),
                "descriptions": self.description}