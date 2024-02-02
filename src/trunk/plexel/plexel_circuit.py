from typing import List, Union
from enum import Enum
import pandas as pd
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
import GridCalEngine.Core.Devices as dev


class ClassEnum(Enum):
    System = 'System'
    Generator = 'Generator'
    Fuel = 'Fuel'
    FuelContract = 'FuelContract'
    Emission = 'Emission'
    Abatement = 'Abatement'
    Storage = 'Storage'
    Waterway = 'Waterway'
    PowerStation = 'PowerStation'
    PhysicalContract = 'PhysicalContract'
    Purchaser = 'Purchaser'
    Reserve = 'Reserve'
    Battery = 'Battery'
    Power2X = 'Power2X'
    Reliability = 'Reliability'
    FinancialContract = 'FinancialContract'
    Cournot = 'Cournot'
    RSI = 'RSI'
    Region = 'Region'
    Pool = 'Pool'
    Zone = 'Zone'
    Node = 'Node'
    Load = 'Load'
    Line = 'Line'
    MLF = 'MLF'
    Transformer = 'Transformer'
    FlowControl = 'FlowControl'
    Interface = 'Interface'
    Contingency = 'Contingency'
    Hub = 'Hub'
    TransmissionRight = 'TransmissionRight'
    HeatPlant = 'HeatPlant'
    HeatNode = 'HeatNode'
    HeatStorage = 'HeatStorage'
    GasField = 'GasField'
    GasPlant = 'GasPlant'
    GasPipeline = 'GasPipeline'
    GasNode = 'GasNode'
    GasStorage = 'GasStorage'
    GasDemand = 'GasDemand'
    GasDSMProgram = 'GasDSMProgram'
    GasBasin = 'GasBasin'
    GasZone = 'GasZone'
    GasContract = 'GasContract'
    GasTransport = 'GasTransport'
    GasCapacityReleaseOffer = 'GasCapacityReleaseOffer'
    WaterPlant = 'WaterPlant'
    WaterPipeline = 'WaterPipeline'
    WaterNode = 'WaterNode'
    WaterStorage = 'WaterStorage'
    WaterDemand = 'WaterDemand'
    WaterZone = 'WaterZone'
    WaterPumpStation = 'WaterPumpStation'
    WaterPump = 'WaterPump'
    Vehicle = 'Vehicle'
    ChargingStation = 'ChargingStation'
    Fleet = 'Fleet'
    Company = 'Company'
    Commodity = 'Commodity'
    Process = 'Process'
    Facility = 'Facility'
    Maintenance = 'Maintenance'
    FlowNetwork = 'FlowNetwork'
    FlowNode = 'FlowNode'
    FlowPath = 'FlowPath'
    FlowStorage = 'FlowStorage'
    Entity = 'Entity'
    Market = 'Market'
    Constraint = 'Constraint'
    Objective = 'Objective'
    DecisionVariable = 'DecisionVariable'
    NonlinearConstraint = 'NonlinearConstraint'
    DataFile = 'DataFile'
    Variable = 'Variable'
    Timeslice = 'Timeslice'
    Global = 'Global'
    Scenario = 'Scenario'
    WeatherStation = 'WeatherStation'
    Model = 'Model'
    Project = 'Project'
    Horizon = 'Horizon'
    Report = 'Report'
    Stochastic = 'Stochastic'
    LTPlan = 'LTPlan'
    PASA = 'PASA'
    MTSchedule = 'MTSchedule'
    STSchedule = 'STSchedule'
    Transmission = 'Transmission'
    Production = 'Production'
    Competition = 'Competition'
    Performance = 'Performance'
    Diagnostic = 'Diagnostic'
    List = 'List'


class CollectionEnum(Enum):
    CapacityGenerationContracts = 'CapacityGenerationContracts'
    CapacityGenerators = 'CapacityGenerators'
    CapacityLoadContracts = 'CapacityLoadContracts'
    CapacityMarkets = 'CapacityMarkets'
    CapacityPurchasers = 'CapacityPurchasers'
    CapacityZones = 'CapacityZones'
    Companies = 'Companies'
    Competition = 'Competition'
    Conditions = 'Conditions'
    Constraints = 'Constraints'
    Contingencies = 'Contingencies'
    Cournots = 'Cournots'
    DataFiles = 'DataFiles'
    Diagnostic = 'Diagnostic'
    Diagnostics = 'Diagnostics'
    Emissions = 'Emissions'
    ExportingCapacityLines = 'ExportingCapacityLines'
    ExportingLines = 'ExportingLines'
    FinancialContracts = 'FinancialContracts'
    Fuel = 'Fuel'
    FuelContracts = 'FuelContracts'
    Fuels = 'Fuels'
    GeneratingCompanies = 'GeneratingCompanies'
    GenerationContracts = 'GenerationContracts'
    GenerationNode = 'GenerationNode'
    GeneratorContingencies = 'GeneratorContingencies'
    Generators = 'Generators'
    HeadStorage = 'HeadStorage'
    HeatInput = 'HeatInput'
    Horizon = 'Horizon'
    Horizons = 'Horizons'
    ImportingCapacityLines = 'ImportingCapacityLines'
    ImportingLines = 'ImportingLines'
    Interfaces = 'Interfaces'
    InterregionalLines = 'InterregionalLines'
    InterzonalLines = 'InterzonalLines'
    IntraregionalLines = 'IntraregionalLines'
    IntrazonalLines = 'IntrazonalLines'
    Line = 'Line'
    LineContingencies = 'LineContingencies'
    Lines = 'Lines'
    LoadContracts = 'LoadContracts'
    LoadNode = 'LoadNode'
    LTPlan = 'LTPlan'
    Markets = 'Markets'
    MLFs = 'MLFs'
    Models = 'Models'
    MTSchedule = 'MTSchedule'
    NestedReserves = 'NestedReserves'
    Node = 'Node'
    NodeFrom = 'NodeFrom'
    NodeTo = 'NodeTo'
    Nodes = 'Nodes'
    PASA = 'PASA'
    Performance = 'Performance'
    FlowControls = 'FlowControls'
    PhysicalContracts = 'PhysicalContracts'
    PowerStation = 'PowerStation'
    PowerStations = 'PowerStations'
    Production = 'Production'
    Projects = 'Projects'
    Purchasers = 'Purchasers'
    PurchasingCompanies = 'PurchasingCompanies'
    ReferenceNode = 'ReferenceNode'
    Region = 'Region'
    Regions = 'Regions'
    Report = 'Report'
    Reports = 'Reports'
    Reserves = 'Reserves'
    RSIs = 'RSIs'
    Scenarios = 'Scenarios'
    STSchedule = 'STSchedule'
    StartFuels = 'StartFuels'
    Stochastic = 'Stochastic'
    StorageFrom = 'StorageFrom'
    StorageTo = 'StorageTo'
    Storages = 'Storages'
    TailStorage = 'TailStorage'
    Timeslices = 'Timeslices'
    Transformers = 'Transformers'
    Transmission = 'Transmission'
    TransmissionRights = 'TransmissionRights'
    Utilities = 'Utilities'
    Variables = 'Variables'
    Waterways = 'Waterways'
    Zone = 'Zone'
    Zones = 'Zones'
    MonitoredLines = 'MonitoredLines'
    MonitoredTransformers = 'MonitoredTransformers'
    MonitoredInterfaces = 'MonitoredInterfaces'
    GeneratorCostAllocation = 'GeneratorCostAllocation'
    GasFields = 'GasFields'
    GasStorages = 'GasStorages'
    GasPipelines = 'GasPipelines'
    GasNodes = 'GasNodes'
    GasDemands = 'GasDemands'
    GasNode = 'GasNode'
    GasNodeFrom = 'GasNodeFrom'
    GasNodeTo = 'GasNodeTo'
    Lists = 'Lists'
    Interleaved = 'Interleaved'
    Template = 'Template'
    Abatements = 'Abatements'
    Consumables = 'Consumables'
    GasZones = 'GasZones'
    ExportingGasPipelines = 'ExportingGasPipelines'
    ImportingGasPipelines = 'ImportingGasPipelines'
    InterzonalGasPipelines = 'InterzonalGasPipelines'
    IntrazonalGasPipelines = 'IntrazonalGasPipelines'
    ExportingCapacityTransformers = 'ExportingCapacityTransformers'
    ImportingCapacityTransformers = 'ImportingCapacityTransformers'
    DecisionVariables = 'DecisionVariables'
    Globals = 'Globals'
    Definition = 'Definition'
    Hubs = 'Hubs'
    ZoneFrom = 'ZoneFrom'
    ZoneTo = 'ZoneTo'
    HubFrom = 'HubFrom'
    HubTo = 'HubTo'
    GasBasins = 'GasBasins'
    Batteries = 'Batteries'
    GasBasin = 'GasBasin'
    Nodes_star_ = 'Nodes_star_'
    Maintenances = 'Maintenances'
    Prerequisites = 'Prerequisites'
    ExportingTransformers = 'ExportingTransformers'
    ImportingTransformers = 'ImportingTransformers'
    InterregionalTransformers = 'InterregionalTransformers'
    InterzonalTransformers = 'InterzonalTransformers'
    IntraregionalTransformers = 'IntraregionalTransformers'
    IntrazonalTransformers = 'IntrazonalTransformers'
    Lines_star_ = 'Lines_star_'
    WaterPlants = 'WaterPlants'
    WaterStorages = 'WaterStorages'
    WaterPipelines = 'WaterPipelines'
    WaterNodes = 'WaterNodes'
    WaterDemands = 'WaterDemands'
    WaterZones = 'WaterZones'
    WaterNode = 'WaterNode'
    WaterNodeFrom = 'WaterNodeFrom'
    WaterNodeTo = 'WaterNodeTo'
    ExportingWaterPipelines = 'ExportingWaterPipelines'
    ImportingWaterPipelines = 'ImportingWaterPipelines'
    InterzonalWaterPipelines = 'InterzonalWaterPipelines'
    IntrazonalWaterPipelines = 'IntrazonalWaterPipelines'
    GasContracts = 'GasContracts'
    InputNode = 'InputNode'
    OutputNode = 'OutputNode'
    GasPlants = 'GasPlants'
    GasTransports = 'GasTransports'
    ExportNode = 'ExportNode'
    ImportNode = 'ImportNode'
    ExportingGasTransports = 'ExportingGasTransports'
    ImportingGasTransports = 'ImportingGasTransports'
    InterzonalGasTransports = 'InterzonalGasTransports'
    IntrazonalGasTransports = 'IntrazonalGasTransports'
    Transition = 'Transition'
    HeatPlants = 'HeatPlants'
    HeatNodes = 'HeatNodes'
    HeatInputNodes = 'HeatInputNodes'
    HeatOutputNodes = 'HeatOutputNodes'
    HeatExportNodes = 'HeatExportNodes'
    CapacityBatteries = 'CapacityBatteries'
    MarktoMarkets = 'MarktoMarkets'
    Pools = 'Pools'
    Pool = 'Pool'
    WeatherStations = 'WeatherStations'
    GasDSMPrograms = 'GasDSMPrograms'
    MasterFilter = 'MasterFilter'
    ObjectFilter = 'ObjectFilter'
    GasCapacityReleaseOffers = 'GasCapacityReleaseOffers'
    Objectives = 'Objectives'
    Vehicles = 'Vehicles'
    ChargingStations = 'ChargingStations'
    Fleets = 'Fleets'
    Power2X = 'Power2X'
    Reliability = 'Reliability'
    NonlinearConstraints = 'NonlinearConstraints'
    DecisionVariableX = 'DecisionVariableX'
    DecisionVariableY = 'DecisionVariableY'
    HeatStorages = 'HeatStorages'
    WaterPumpStations = 'WaterPumpStations'
    WaterPumps = 'WaterPumps'
    WaterPipeline = 'WaterPipeline'
    UpstreamWaterStorage = 'UpstreamWaterStorage'
    DownstreamWaterStorage = 'DownstreamWaterStorage'
    Loads = 'Loads'
    Commodities = 'Commodities'
    Processes = 'Processes'
    PrimaryInput = 'PrimaryInput'
    SecondaryInputs = 'SecondaryInputs'
    PrimaryOutput = 'PrimaryOutput'
    SecondaryOutputs = 'SecondaryOutputs'
    Facilities = 'Facilities'
    PrimaryInputs = 'PrimaryInputs'
    PrimaryOutputs = 'PrimaryOutputs'
    Entities = 'Entities'
    CommoditiesConsumed = 'CommoditiesConsumed'
    CommoditiesProduced = 'CommoditiesProduced'
    PrimaryProcess = 'PrimaryProcess'
    SecondaryProcesses = 'SecondaryProcesses'
    FlowNetworks = 'FlowNetworks'
    FlowNodes = 'FlowNodes'
    FlowPaths = 'FlowPaths'
    FlowNodeFrom = 'FlowNodeFrom'
    FlowNodeTo = 'FlowNodeTo'
    FlowNode = 'FlowNode'
    Company = 'Company'
    HeatMarkets = 'HeatMarkets'
    Commodity = 'Commodity'
    LinkedGasContracts = 'LinkedGasContracts'
    SourceGasFields = 'SourceGasFields'
    SourceGasStorages = 'SourceGasStorages'
    SourceGasContracts = 'SourceGasContracts'
    SourceGasPlants = 'SourceGasPlants'
    SourcePower2X = 'SourcePower2X'
    FlowStorages = 'FlowStorages'
    WarmUpProcess = 'WarmUpProcess'
    BalancingFrom = 'BalancingFrom'
    BalancingTo = 'BalancingTo'


class PropertyEnum(Enum):
    # SystemNodesEnum
    MustReport = 'Must Report'
    IsSlackBus = 'Is Slack Bus'
    AllowDumpEnergy = 'Allow Dump Energy'
    AllowUnservedEnergy = 'Allow Unserved Energy'
    FormulateLoad = 'Formulate Load'
    MaxUnservedEnergy = 'Max Unserved Energy'
    ReferenceLoad = 'Reference Load'
    Voltage = 'Voltage'
    Units = 'Units'
    LoadParticipationFactor = 'Load Participation Factor'
    Load = 'Load'
    FixedLoad = 'Fixed Load'
    FixedGeneration = 'Fixed Generation'
    MaxNetInjection = 'Max Net Injection'
    MaxNetOfftake = 'Max Net Offtake'
    Rating = 'Rating'
    DSPBidQuantity = 'DSP Bid Quantity'
    DSPBidRatio = 'DSP Bid Ratio'
    DSPBidPrice = 'DSP Bid Price'
    Price = 'Price'
    MaxMaintenance = 'Max Maintenance'
    MaintenanceFactor = 'Maintenance Factor'
    MinCapacityReserves = 'Min Capacity Reserves'
    MinCapacityReserveMargin = 'Min Capacity Reserve Margin'
    x = 'x'
    y = 'y'
    z = 'z'


class PlexelObject:
    """
    Represents an independent entity.
    It can be anything within our model!
    The only requirement is that it has to belong to a specific Class from ClassEnum
    """

    __headers__ = ["class", "GUID", "name", "category", "description"]

    def __init__(self,
                 cls: ClassEnum = ClassEnum.System,
                 guid: str = "",
                 name: str = "",
                 cat: "PlexelObject" = None,
                 desc: str = ""):
        """
        Init PlexelObject
        :param cls: Class of the Object
        :param guid:
        :param name: Name of the Object across the model
        :param cat: The Category associated to the object
        :param desc: Description of the Object
        """
        self.class_: ClassEnum = cls
        self.GUID: str = guid
        self.name: str = name
        self.category: "PlexelObject" = cat
        self.description: str = desc

    def get_key(self) -> str:
        return self.class_.value + '_' + self.name

    def get_data(self) -> List[str]:
        """
        Get the properties as a list of strings
        :return: List[str]
        """
        return [self.class_.value,
                self.GUID,
                self.name,
                self.category.name if self.category is not None else '',
                self.description]


class PlexelCategory:
    """
    PlexelCategory serves to rank objects within the same class,
    allowing to customize the order in which they are displayed.
    They are needed if we want to group objects as well.
    For example, if we want to see the generators grouped by technology,
    we need to first create the category and then reference it at the object level.
    """
    __headers__ = ["class", "category", "rank"]

    def __init__(self,
                 cls: ClassEnum = ClassEnum.System,
                 category_name: str = "",
                 rank: int = 1):
        """
        Init PlexelCategory
        :param cls: Class of the category
        :param category_name: Name of the category
        :param rank: Rank of the category (must be sequential starting at 1...)
        """
        self.class_: ClassEnum = cls
        self.category: str = category_name
        self.rank: int = rank

    def get_key(self) -> str:
        return self.category

    def get_data(self) -> List[str]:
        """
        Get the properties as a list of strings
        :return: List[str]
        """
        return [self.class_.value,
                self.category,
                str(self.rank)]


class PlexelProperty:
    """
    Represents a property that can evolve (change later, use profiles, etc...).
    The properties may vary from one Class to another.
    It is crucial to define the Class along with the Collection.
    """

    __headers__ = ['parent_class',
                   'child_class',
                   'collection',
                   'parent_object',
                   'child_object',
                   'property',
                   'unit',
                   'band_id',
                   'value',
                   'date_from',
                   'date_to',
                   'pattern',
                   'action',
                   'expression',
                   'filename',
                   'scenario',
                   'memo']

    def __init__(self,
                 parent_obj: PlexelObject,
                 child_obj: PlexelObject,
                 collection: CollectionEnum,
                 property: PropertyEnum,
                 value: Union[str, float]
                 ):
        self.parent_class: ClassEnum = parent_obj.class_
        self.child_class: ClassEnum = child_obj.class_
        self.collection: CollectionEnum = collection
        self.parent_object: str = parent_obj.name
        self.child_object: str = child_obj.name
        self.property_: PropertyEnum = property
        self.unit: str = ""
        self.band_id: int = 1
        self.value: Union[str, float] = value
        self.date_from: str = ""
        self.date_to: str = ""
        self.pattern: str = ""
        self.action: str = ""
        self.expression: str = ""
        self.filename: str = ""
        self.scenario: str = ""
        self.memo: str = ""

    def get_key(self) -> str:
        return self.child_object + '_' + str(self.property_)

    def get_data(self) -> List[str]:
        """
        Get the properties as a list of strings
        :return: List[str]
        """
        return [self.parent_class.value,
                self.child_class.value,
                self.collection.value,
                self.parent_object,
                self.child_object,
                self.property_.value,
                self.unit,
                self.band_id,
                str(self.value),
                self.date_from,
                self.date_to,
                self.pattern,
                self.action,
                self.expression,
                self.filename,
                self.scenario,
                self.memo]


class PlexelAttribute:
    """
    Represents a property that is filled only one time (akin to the snapshot values)
    """

    __headers__ = ["name", "class", "attribute", "value"]

    def __init__(self,
                 name: str = "",
                 cls: ClassEnum = ClassEnum.System,
                 attribute: str = "",
                 value: Union[str, float] = ""):
        """

        :param name:
        :param cls:
        :param attribute:
        :param value:
        """
        self.name: str = name
        self.class_: ClassEnum = cls
        self.attribute: str = attribute
        self.value: Union[str, float] = value

    def get_key(self) -> str:
        return self.name + '_' + self.attribute

    def get_data(self) -> List[str]:
        """
        Get the properties as a list of strings
        :return: List[str]
        """
        return [self.name,
                self.class_.value,
                self.attribute,
                str(self.value)]


class PlexelMembership:
    """
    Represents the relationships between objects
    """

    __headers__ = ["parent_class", "child_class", "collection", "parent_object", "child_object"]

    def __init__(self, parent_obj: PlexelObject, child_obj: PlexelObject, collection: CollectionEnum):
        """
        Associate a parent object with a child object
        :param parent_obj: PlexelObject
        :param child_obj: PlexelObject
        :param collection: property over which the objects are associated
        :return:
        """
        self.parent_class: ClassEnum = parent_obj.class_
        self.child_class: ClassEnum = child_obj.class_
        self.collection: CollectionEnum = collection
        self.parent_object: str = parent_obj.name
        self.child_object: str = child_obj.name

    def get_key(self) -> str:
        return self.parent_object + '_' + self.child_object + '_' + str(self.collection.value)

    def get_data(self) -> List[str]:
        """
        Get the properties as a list of strings
        :return: List[str]
        """
        return [self.parent_class.value,
                self.child_class.value,
                self.collection.value,
                self.parent_object,
                self.child_object]


class PlexelList:
    """
    List of Plexel object
    """
    def __init__(self, tpe, *args):
        self.tpe = tpe
        self._d = set()
        self._elements = list()

    def get_keys(self):
        return self._d

    def length(self):
        return len(self.get_keys())

    def append(self, __object) -> None:
        self._elements.append(__object)
        self._d.add(__object.get_key())

    def get_df(self) -> pd.DataFrame:
        """
        Get DataFrame of the table list
        :return:
        """
        hdr = self.tpe.__headers__
        data = list()
        for item in self._elements:
            data.append(item.get_data())
        return pd.DataFrame(data, columns=hdr)


class PlexelBase:
    """
    A Plexel object. It serves as a wrapper of the logic.
    This class uses the rest of the classes defined above.
    """

    def __init__(self):
        self.categories: List[PlexelCategory] = list()
        self.memberships = PlexelList(PlexelMembership)
        self.objects = PlexelList(PlexelObject)
        self.attributes: List[PlexelAttribute] = list()
        self.properties = PlexelList(PlexelProperty)

    def add_category(self, child_class_id, category):
        pass

    def add_membership(self, parent_obj, child_obj, collection):
        memb = PlexelMembership(parent_obj=parent_obj, child_obj=child_obj, collection=collection)
        self.memberships.append(memb)

    def add_property(self, collection_id, child_name, enum_id, prop_value,
                     parent_name='System', date_from=None, date_to=None, variable=None,
                     data_file=None, pattern=None, scenario=None, band_id=1, action=0,
                     period=''):
        pass

    def add_object(self, child_class_id, child_name, category=None, description=''):
        """
        Add the object if it hasn't been added yet
        :param child_class_id: value from ClassEnum
        :param child_name: name of the object
        :param category: PlexelCategory name. If it does not exist, it is created
        :param description:
        """
        # TODO: add Object as a Category if not exists
        # create category if it does not exist
        self.add_category(child_class_id, category)

        obj = PlexelObject(cls=child_class_id, name=child_name, desc=description)
        self.objects.append(obj)

    def add_zone(self, zone: dev.Zone):
        # TODO: check if there are any missing fields
        # add the zone as an object
        self.add_object(child_class_id=ClassEnum.Zone, child_name=zone.name, description=zone.name)

    def add_region(self, region: dev.Area):
        # TODO: check if there are any missing fields
        # add the region as an object
        self.add_object(child_class_id=ClassEnum.Region, child_name=region.name, description=region.name)

    def add_node(self, node: dev.Bus, region: dev.Area, zone: dev.Zone):
        # TODO: check if there are any missing fields
        # create name following plexel format
        node_name = node.code + '_' + node.name + '_' + str(int(node.Vnom))

        # add the node as an object
        node_obj = PlexelObject(cls=ClassEnum.Node, name=node_name)
        self.objects.append(node_obj)

        # add membership node <-> region
        region_obj = PlexelObject(cls=ClassEnum.Region, name=node.area.name)
        # is region in objects?
        if self.objects.length() > 0:
            if region_obj.get_key() not in self.objects.get_keys():
                self.add_region(region)

        node_region = PlexelMembership(node_obj, region_obj, CollectionEnum.Region)
        self.memberships.append(node_region)

        # add membership node <-> zone
        zone_obj = PlexelObject(cls=ClassEnum.Zone, name=node.zone.name)
        # is zone in objects?
        if self.objects.length() > 0:
            if zone_obj.get_key() not in self.objects.get_keys():
                self.add_zone(zone)

        node_zone = PlexelMembership(node_obj, zone_obj, CollectionEnum.Zone)
        self.memberships.append(node_zone)

        # add node properties
        node_props_enum = [
            # TODO: convert slack value to Plexel expected format (1/-1)
            [PropertyEnum.IsSlackBus, node.is_slack],
            [PropertyEnum.AllowDumpEnergy, 0],
            [PropertyEnum.Voltage, str(int(node.Vnom))],
            # TODO: get_active_from_bus_profile()
            [PropertyEnum.Units, '?'],
            # TODO: get_load_from_bus()
            [PropertyEnum.FixedLoad, '?'],
        ]

        # init System Object to be used as the Parent Object
        sys_obj = PlexelObject(cls=ClassEnum.System, name='System')
        for p in node_props_enum:
            node_props = PlexelProperty(parent_obj=sys_obj,
                                        child_obj=node_obj,
                                        collection=CollectionEnum.Nodes,
                                        property=p[0],
                                        value=p[1])
            self.properties.append(node_props)

    def save(self, file_name: str):
        """
        Save the Plexel DB to an Excel file
        :param file_name: name of the file
        :return:
        """
        if not file_name.endswith('.xlsx'):
            file_name += '.xlsx'

        with pd.ExcelWriter(file_name) as writer:
            self.objects.get_df().to_excel(writer, index=False, sheet_name='Objects')
            self.memberships.get_df().to_excel(writer, index=False, sheet_name='Memberships')
            self.properties.get_df().to_excel(writer, index=False, sheet_name='Properties')
            # self.categories.get_df().to_excel(ptr, sheet_name='categories')
            # self.attributes.get_df().to_excel(ptr, sheet_name='attributes')


def convert_gridcal_to_plexel(grid: MultiCircuit) -> PlexelBase:
    """
    Convert GridCal MultiCircuit Model to plexel DB
    :param grid: GridCal MultiCircuit object
    :return: a PlexelBase object
    """
    plx = PlexelBase()
    # Add zones
    for z in grid.zones:
        plx.add_zone(z)

    # Add gridcal areas as -> plexel regions
    for a in grid.areas:
        plx.add_region(a)

    # Add gridcal buses as -> plexel nodes
    for b in grid.buses:
        plx.add_node(node=b, region=b.area, zone=b.zone)

    print('Convert done!')
    return plx


if __name__ == "__main__":
    import os
    import GridCalEngine.api as gce

    # fname = os.path.join("..", "..", "..", "Grids_and_profiles/grids/hydro_IEEE39_2.gridcal")
    fname = os.path.join("..", "..", "..", "Grids_and_profiles/grids/IEEE 14 bus.raw")
    out_file = r"plexel_export.xlsx"

    my_grid = gce.open_file(fname)

    my_plexel_circuit = convert_gridcal_to_plexel(my_grid)
    print('Plexel circuit generated!')

    my_plexel_circuit.save(file_name=out_file)
    print('Plexel circuit saved as Excel in {f}'.format(f=out_file))
