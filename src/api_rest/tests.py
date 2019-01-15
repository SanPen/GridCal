
import json
import requests
import urllib
import os
# os.environ['no_proxy'] = '127.0.0.1,localhost'

http_proxy = "http://spenate:Hoogstedelaan05@proxy.indra.es:8080/"
https_proxy = "https://spenate:Hoogstedelaan05@proxy.indra.es:8080/"
ftp_proxy = "ftp://spenate:Hoogstedelaan05@proxy.indra.es:8080/"
proxyDict = {"http": http_proxy, 'https': https_proxy, 'ftp': ftp_proxy, 'no': 'pass'}
# proxyDict = {'no': 'pass',}

os.environ['HTTP_PROXY'] = http_proxy


def get_load_names(url='http://0.0.0.0:5000/loads_list'):
    """
    
    :param url: 
    :return: 
    """

    response = requests.get(url)  #, proxies=proxyDict)
    if response.status_code == 200:
        jData = json.loads(response.content)
        print(jData)
    else:
        print('error', response)  #.text)


def get_grid_name(url='http://0.0.0.0:5000/grid_name'):
    """
    
    :param url: 
    :return: 
    """
    response = requests.get(url, proxies=proxyDict)
    if response.status_code == 200:
        jData = json.loads(response.content)
        print(jData)
    else:
        print('error', response)


def set_load_val(idx, P, Q, url='http://0.0.0.0:5000/set_load'):
    """
    
    :param idx: 
    :param P: 
    :param Q: 
    :param url: 
    :return: 
    """
    data = {'idx': idx, 'P': P, 'Q': Q}
    response = requests.post(url, json=data, proxies=proxyDict)
    if response.status_code == 200:
        jData = json.loads(response.content)
        print(jData)
    else:
        print('error', response)


if __name__ == '__main__':

    print('test')
    # url_ = 'http://192.168.197.22:5000'
    # url_ = 'http://127.0.0.1:5000'
    url_ = 'http://192.168.197.22:5000'

    get_load_names(url=url_ + '/loads_list')
    # get_load_names()
    # get_load_names()
    get_grid_name(url=url_ + '/grid_name')

    set_load_val(1, 10, 10*1.2)
