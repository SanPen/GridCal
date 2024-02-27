import os
import json
from typing import List
from GridCalEngine.Devices.Aggregation.contingency import Contingency
from GridCalEngine.Devices.Aggregation.contingency_group import ContingencyGroup
from GridCalEngine.Devices.multi_circuit import MultiCircuit


def parse_contingencies(data):

    contingencies: List[Contingency] = list()

    for key, jentry in data.items():
        group = ContingencyGroup(
            idtag=key,
            name=str(jentry['name']) if 'name' in jentry.keys() else None,
            category=str(jentry['category']) if 'category' in jentry.keys() else None,
        )

        for elem in jentry['elements']:
            cnt = Contingency(
                idtag=elem['key'] if 'name' in elem.keys() else None,
                device_idtag=elem['device_idtag'] if 'device_idtag' in elem.keys() else '',
                name=str(elem['name']) if 'key' in elem.keys() else '',
                code=str(elem['code']) if 'code' in elem.keys() else '',
                prop=str(elem['property']) if 'property' in elem.keys() else '',
                value=str(elem['value']) if 'value' in elem.keys() else 0,
                group=group
            )

            contingencies.append(cnt)

    return contingencies


def import_contingencies_from_json(file_name:str):

    if os.path.exists(file_name):

        # read json file
        data = json.load(open(file_name))

        if data['type'] == 'Contingency Exchange Json File':
            version = float(data['version'])
            if version == 0.0:
                return parse_contingencies(data=data["contingencies"])

    return []


def get_contingencies_dict(circuit: MultiCircuit):
    contingency_groups = dict()

    for contingency in circuit.contingencies:

        element = {
            "key": contingency.idtag,
            "name": contingency.name,
            "code": contingency.code,
            "property": contingency.prop,
            "value": contingency.value,
        }

        if contingency.group.idtag not in contingency_groups.keys():
            contingency_groups[contingency.group.idtag] = {
                "name": contingency.group.name,
                "category": contingency.group.category,
                "elements": [element]
            }

        else:
            contingency_groups[contingency.group.idtag]['elements'].append(element)

    return contingency_groups


def export_contingencies_json_file(circuit: MultiCircuit, file_path):

    version = 0.0

    contingencies = get_contingencies_dict(circuit=circuit)

    data = {
        'file_type': 'Contingency Exchange Json File',
        'version': str(version),
        'contingencies': contingencies,
    }

    data_str = json.dumps(data, indent=True)

    # Save json to a text file
    text_file = open(file_path, "w")
    text_file.write(data_str)
    text_file.close()
