import json
import numpy as np

class storage:
    def __init__(self, **entries):
        self.__dict__.update(entries)


def get_json_pkl(filename):
    f = open(filename)
    data = json.load(f)
    for x in data.keys():
        if type(data[x]) != list:
            pass
        else:
            try:
                if "j" in data[x][0]:
                    tmp = [complex(y) for y in data[x]]
                    data[x] = np.array(tmp)
                else:
                    tmp = data[x]
                    data[x] = np.array(tmp)
            except Exception as e:
                tmp = data[x]
                data[x] = np.array(tmp)
    pfd = storage(**data)
    return (pfd)