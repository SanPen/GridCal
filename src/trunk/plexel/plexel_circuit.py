from typing import List, Union
from enum import Enum
import pandas as pd
from GridCalEngine.Devices.multi_circuit import MultiCircuit


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
    Nodes = 'Schema'
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


class Object:
    """
    Represents a
    """

    __headers__ = ["class", "GUID", "name", "category", "description"]

    def __init__(self,
                 cls: ClassEnum = ClassEnum.System,
                 guid: str = "0",
                 name: str = "",
                 cat: "Object" = "",
                 desc: str = ""):
        """

        :param cls:
        :param guid:
        :param name:
        :param cat:
        :param desc:
        """
        self.class_: ClassEnum = cls
        self.GUID: str = guid
        self.name: str = name
        self.category: "Object" = cat
        self.description: str = desc

    def get_data(self) -> List[str]:
        """
        Get the properties as a list of strings
        :return: List[str]
        """
        return [self.class_.value,
                self.GUID,
                self.name,
                self.category.name,
                self.description]


class Category:
    """
    Category
    """
    __headers__ = ["class", "category", "rank"]

    def __init__(self,
                 cls: ClassEnum = ClassEnum.System,
                 category_name: str = "",
                 rank: int = 1):
        """

        :param cls: Class of the category
        :param category_name: Name of the category
        :param rank: Rank of the category (must be sequential starting at 1...)
        """
        self.class_: ClassEnum = cls
        self.category: str = category_name
        self.rank: int = rank

    def get_data(self) -> List[str]:
        """
        Get the properties as a list of strings
        :return: List[str]
        """
        return [self.class_.value,
                self.category,
                str(self.rank)]


class Property:
    """
    Represents a property that can evolve (change later, use profiles, etc...)
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

    def __init__(self):
        self.parent_class: str = ""
        self.child_class: str = ""
        self.collection: str = ""
        self.parent_object: str = ""
        self.child_object: str = ""
        self.property_: str = ""
        self.unit: str = ""
        self.band_id: int = 1
        self.value: Union[str, float] = ""
        self.date_from: str = ""
        self.date_to: str = ""
        self.pattern: str = ""
        self.action: str = ""
        self.expression: str = ""
        self.filename: str = ""
        self.scenario: str = ""
        self.memo: str = ""

    def get_data(self) -> List[str]:
        """
        Get the properties as a list of strings
        :return: List[str]
        """
        return [self.parent_class,
                self.child_class,
                self.collection,
                self.parent_object,
                self.child_object,
                self.property_,
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


class Attribute:
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

    def get_data(self) -> List[str]:
        """
        Get the properties as a list of strings
        :return: List[str]
        """
        return [self.name,
                self.class_.value,
                self.attribute,
                str(self.value)]


class Membership:
    """
    Represents the relationships between objects
    """

    __headers__ = ["parent_class", "child_class", "collection", "parent_object", "child_object"]

    def __init__(self, parent_obj: Object, child_obj: Object, collection: CollectionEnum):
        """
        Associate
        :param parent_obj: Object
        :param child_obj: Object
        :param collection: property over which the objects are associated
        :return:
        """
        self.parent_class: ClassEnum = parent_obj.class_
        self.child_class: ClassEnum = child_obj.class_
        self.collection: CollectionEnum = collection
        self.parent_object: str = parent_obj.name
        self.child_object: str = child_obj.name

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


class PlexelList(list):
    """
    List of Plexel object
    """

    def __init__(self, tpe, *args):
        list.__init__(self, *args)
        self.tpe = tpe

    def get_df(self) -> pd.DataFrame:
        """
        Get DataFrame of the table list
        :return:
        """
        hdr = self.tpe.__headers__
        data = list()

        for item in self:
            data.append(item.get_data())

        return pd.DataFrame(data, columns=hdr)


class PlexelBase:

    def __str__(self):
        self.categories = PlexelList(Category)
        self.memberships = PlexelList(Membership)
        self.objects = PlexelList(Object)
        self.attributes = PlexelList(Attribute)
        self.properties = PlexelList(Property)

    def add_category(self, child_class_id, category):
        pass

    def add_membership(self):
        pass

    def add_object(self, child_class_id, child_name, category='', ):
        """
        Add the object if it hasn't been added yet
        :param child_class_id: value from ClassEnum
        :param child_name: name of the object
        :param category: Category name, it it does not exist, it is created
        """

        # create category if it does not exist
        self.add_category(child_class_id, category)

    def add_property(self, collection_id, child_name, enum_id, prop_value,
                     parent_name='System', date_from=None, date_to=None, variable=None,
                     data_file=None, pattern=None, scenario=None, band_id=1, action=0,
                     period=PeriodEnum.Interval):
        pass

    def convert(self, grid: MultiCircuit):
        pass

    def save(self, file_name: str):
        """
        Save the plexel DB to an execl file
        :param file_name: name of the file
        :return: 
        """
        if not file_name.endswith('.xlsx'):
            file_name += '.xlsx'

        ptr = pd.ExcelWriter(file_name, engine='xlsxwriter')
        self.categories.get_df().to_excel(ptr, sheet_name='categories')
        self.memberships.get_df().to_excel(ptr, sheet_name='memberships')
        self.objects.get_df().to_excel(ptr, sheet_name='objects')
        self.attributes.get_df().to_excel(ptr, sheet_name='attributes')
        self.properties.get_df().to_excel(ptr, sheet_name='properties')
        ptr.close()


if __name__ == "__main__":
    import os
    import GridCalEngine.api as gce

    # fname = os.path.join("..", "..", "..", "Grids_and_profiles/grids/hydro_IEEE39_2.gridcal")
    fname = os.path.join("..", "..", "..", "Grids_and_profiles/grids/IEEE 14 bus.raw")

    my_grid = gce.open_file(fname)

    my_plexel_circuit = PlexelBase()

    my_plexel_circuit.convert(my_grid)
