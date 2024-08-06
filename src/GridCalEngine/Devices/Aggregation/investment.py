from typing import Union

from GridCalEngine.Devices.Parents.editable_device import EditableDevice, DeviceType
from GridCalEngine.Devices.Aggregation.investments_group import InvestmentsGroup


class Investment(EditableDevice):
    """
    Investment
    """

    def __init__(self,
                 idtag: Union[str, None] = None,
                 device_idtag: Union[str, None] = None,
                 name="Investment",
                 code='',
                 CAPEX=0.0,
                 OPEX=0.0,
                 status: bool = True,
                 group: InvestmentsGroup = None,
                 comment: str = ""):
        """
        Investment
        :param idtag: String. Element unique identifier
        :param name: String. Contingency name
        :param code: String. Contingency code name
        :param CAPEX: Float. Capital expenditures
        :param OPEX: Float. Operating expenditures
        :param status: If true the investment activates when applied, otherwise is deactivated
        :param group: ContingencyGroup. Contingency group
        :param comment: Comment
        """

        EditableDevice.__init__(self,
                                idtag=idtag,
                                code=code,
                                name=name,
                                device_type=DeviceType.InvestmentDevice,
                                comment=comment)

        # Contingency type
        self.device_idtag = device_idtag
        self.CAPEX = CAPEX
        self.OPEX = OPEX
        self._group: InvestmentsGroup = group
        self.status: bool = status
        self._template = None

        self.register(key='device_idtag', units='', tpe=str, definition='Unique ID')
        self.register(key='CAPEX', units='Me', tpe=float,
                      definition='Capital expenditures. This is the initial investment.')
        self.register(key='OPEX', units='Me', tpe=float,
                      definition='Operation expenditures. Maintenance costs among other recurrent costs.')
        self.register(key='status', units='', tpe=bool,
                      definition='If true the investment activates when applied, otherwise is deactivated.')
        self.register(key='template', units='', tpe=DeviceType.OverheadLineTypeDevice, definition='', editable=False)
        self.register(key='group', units='', tpe=DeviceType.InvestmentsGroupDevice, definition='Investment group')

    @property
    def group(self) -> InvestmentsGroup:
        """
        Group of investments
        :return:
        """
        return self._group

    @group.setter
    def group(self, val: InvestmentsGroup):
        self._group = val

    @property
    def category(self):
        """
        Display the group category
        :return:
        """
        return self.group.category

    @category.setter
    def category(self, val):
        # The category is set through the group, so no implementation here
        pass

    @property
    def template(self):
        """
        Template of component
        :return:
        """
        return self._template

    @template.setter
    def template(self, val):
        self._template = val
