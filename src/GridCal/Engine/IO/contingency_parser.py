import os
import json
from typing import List
from GridCal.Engine.Devices.contingency import Contingency
from GridCal.Engine.Devices.contingency_group import ContingencyGroup
from GridCal.Engine.Core.multi_circuit import MultiCircuit


def parse_contingencies(data):

    contingencies = List[Contingency]

    for key, jentry in data.items():
        group = ContingencyGroup(
            idtag=key,
            name=str(jentry['name']),
            category=str(jentry['category']),
        )

        for elem in jentry['elements']:
            cnt = Contingency(
                idtag=elem["key"],
                name=str(elem['name']),
                code=str(elem['code']),
                prop=str(elem['property']),
                value=str(elem['value']),
                group=group
            )

            contingencies.append(cnt)

    return contingencies


def import_contingencies_from_json(file_name:str):

    if os.path.exists(file_name):

        # read json file
        data = json.load(open(file_name))

        if data['type'] == 'Contingency Exchange Json File':
            version = data['version']
            if version == 0:
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
