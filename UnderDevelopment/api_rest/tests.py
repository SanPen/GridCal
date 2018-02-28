
import json
import requests


def get_load_names(url='http://0.0.0.0:5000/loads_list'):
    data = '''{
    }'''
    response = requests.get(url)
    if response.status_code == 200:
        jData = json.loads(response.content)
        print(jData)
    else:
        print('error', response)


def get_grid_name(url='http://0.0.0.0:5000/grid_name'):
    response = requests.get(url)
    if response.status_code == 200:
        jData = json.loads(response.content)
        print(jData)
    else:
        print('error', response)


def set_load_val(idx, P, Q, url='http://0.0.0.0:5000/set_load'):
    data = {'idx': idx, 'P': P, 'Q': Q}
    response = requests.post(url, json=data)
    if response.status_code == 200:
        jData = json.loads(response.content)
        print(jData)
    else:
        print('error', response)


if __name__ == '__main__':

    get_load_names()
    # get_load_names()
    # get_load_names()
    get_grid_name()

    set_load_val(1, 10, 10*1.2)
