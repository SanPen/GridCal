from typing import List
import json


data = json.load(open("data.json"))

print()


def rename(val: str) -> str:

    if val == "None":
        return "None_"
    else:
        return val


def create_class(name: str, attributes: List[str]):

    attributes = "".join([f"\t{rename(a)} = None\n" for a in attributes])

    res = ("@dataclass\n"
           f"class {name}:\n"
           f"{attributes}\n\n")

    return res


with open("code.py", "w") as f:

    f.write("from dataclasses import dataclass\n\n\n")

    for name, attributes in data['clases'].items():

        cls_code = create_class(name=name, attributes=attributes)

        f.write(cls_code)

print()
