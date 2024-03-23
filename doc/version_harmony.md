## Files affected by the modification.

### src\GridCalEngine\IO\cim\cgmes
- cgmes_to_gridcal.py
- cgmes_circuit.py
- cgmes_utils.py
- cgmes_writer.py
- gridcal_to_cgmes.py

### src\tests
- test_cgmes_to_gridcal_ac_lines.py
- test_cgmes_to_gridcal_ac_transformers.py
- test_cgmes_to_gridcal_generators.py
- test_cgmes_utils.py

## Method 1 - Duplication of methods and CgmesCircuit class.
Main advantages are:

- Fast initial creation: copy-pasting files into versioned directories and replacing version numbers.
- Code for different versions is separated, making it easy to read, debug and apply version based modifications.
- Simplified code: no branching in the code.
- Faster execution: no need for property checks.

Disadvantage:
- Most of the code will be duplicated (multiplied).
- If you have to modify same logic for all versions 


## Method 2 - Usage of Protocol
Advantage:
- Dont need to import all versions or duplicate code
- Probably no need for branching in the code.
- Probably no need for property checks.

Disadvantage:
- You need to create classes implementing "Protocol" (with shared class members used in methods).

src\GridCalEngine\IO\cim\cgmes\base\devices
```python
from typing import Protocol, runtime_checkable
from typing import Dict, List
from GridCalEngine.data_logger import DataLogger


@runtime_checkable
class ConductingEquipment(Protocol):
    uuid: str    
    

class Terminal(Protocol):
    ConductingEquipment: ConductingEquipment
    rdfid: str
    tpe: str
    

class CgmesCircuit(Protocol):
    Terminal_list: List[Terminal]
    

class CgmesCircuit_3_0(CgmesCircuit):
    NewField: List[Terminal]

    
class Builder(Protocol):
    def create_connectivity_node(self) -> ConnectivityNode:
        pass
        


def get_gcdev_device_to_terminal_dict(cgmes_model: CgmesCircuit,
                                      builder: Builder,
                                      logger: DataLogger) -> Dict[str, List[Terminal]]:
    """
    Dictionary relating the conducting equipment to the terminal object(s)
    """
    # dictionary relating the conducting equipment to the terminal object
    device_to_terminal_dict: Dict[str, List[Terminal]] = dict()

    a = cgmes_model.NewField
    
    if isinstance(cgmes_model, CgmesCircuit_3_0):
        b = cgmes_model.NewField
        
    
    for e in cgmes_model.Terminal_list:
        if isinstance(e.ConductingEquipment, ConductingEquipment):
            lst = device_to_terminal_dict.get(e.ConductingEquipment.uuid, None)
            if lst is None:
                device_to_terminal_dict[e.ConductingEquipment.uuid] = [e]
            else:
                lst.append(e)
        else:
            logger.add_error(msg='The object is not a ConductingEquipment',
                             device=e.rdfid,
                             device_class=e.tpe,
                             device_property="ConductingEquipment",
                             value=e.ConductingEquipment,
                             expected_value='object')
    return device_to_terminal_dict


```


## Method 3 - Extension of methods, usage of type union
Main advantages are:
- The different versions of the logics will be managed in one place. (you can change the same logic to apply it for each version)
- No unnecessary code duplication.

Disadvantage:
- No real IDE assistance (IntelliSense for only one version).
- Harder to read and debug.

### cgmes_to_gridcal.py

```python
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from GridCalEngine.data_logger import DataLogger
from typing import Dict, List

from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.terminal import Terminal as Terminal_2_4_15
from GridCalEngine.IO.cim.cgmes.cgmes_v2_4_15.devices.conducting_equipment import ConductingEquipment as ConductingEquipment_2_4_15

from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.terminal import Terminal as Terminal_3_0_0
from GridCalEngine.IO.cim.cgmes.cgmes_v3_0_0.devices.conducting_equipment import ConductingEquipment as ConductingEquipment_3_0_0


def get_gcdev_device_to_terminal_dict(cgmes_model: CgmesCircuit,
                                      logger: DataLogger) -> Dict[str, List[Terminal_2_4_15 | Terminal_3_0_0]]:
    """
    Dictionary relating the conducting equipment to the terminal object(s)
    """
    # dictionary relating the conducting equipment to the terminal object
    device_to_terminal_dict: Dict[str, List[Terminal_2_4_15 | Terminal_3_0_0]] = dict()

    for e in cgmes_model.Terminal_list:
        # todo: code duplication for check the version in sublevel
        if isinstance(e.ConductingEquipment, ConductingEquipment_2_4_15) or isinstance(e.ConductingEquipment,
                                                                                       ConductingEquipment_3_0_0):
            # todo 1: in some cases, the same attribute may not exist in every version
            # if it exists, the original iodine can remain.
            lst = device_to_terminal_dict.get(e.ConductingEquipment.uuid, None)  

            # todo 2: or if it doesn't exist, an if-else branch need to be created 
            if isinstance(e.ConductingEquipment, ConductingEquipment_2_4_15):
                lst = device_to_terminal_dict.get(e.ConductingEquipment.uuid, None)
            elif isinstance(e.ConductingEquipment, ConductingEquipment_3_0_0):
                lst = device_to_terminal_dict.get(e.ConductingEquipment.uuid, None) # read the uuid from somewhere else 
            
            # todo 3: or you can use a custom attr reader (it returns with None if the attr doesn't exist):
            ce_uuid = get_attr(e, 'ConductingEquipment.uuid')
            lst = device_to_terminal_dict.get(ce_uuid, None)

            if lst is None:
                device_to_terminal_dict[e.ConductingEquipment.uuid] = [e]
            else:
                lst.append(e)
        else:
            logger.add_error(msg='The object is not a ConductingEquipment',
                             device=e.rdfid,
                             device_class=e.tpe,
                             device_property="ConductingEquipment",
                             value=e.ConductingEquipment,
                             expected_value='object')
    return device_to_terminal_dict


def get_attr(obj, attr):
    for name in attr.split("."):
        obj = getattr(obj, name, None)
    return obj
```

