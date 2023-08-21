

def parse_config_df(df, data=None):

    if data is None:
        data = dict()

    if 'baseMVA' in df.index:
        data["baseMVA"] = float(df.at['name', 'Value'])
    else:
        data["baseMVA"] = 100

    if 'version' in df.index:
        data["version"] = float(df.at['version', 'Value'])

    if 'name' in df.index:
        data["name"] = df.at['name', 'Value']
    elif 'Name' in df.index:
        data["name"] = df.at['Name', 'Value']
    else:
        data["name"] = 'Grid'

    if 'Comments' in df.index:
        data["Comments"] = df.at['Comments', 'Value']
    else:
        data["Comments"] = ''

    if 'ModelVersion' in df.index:
        data["ModelVersion"] = df.at['ModelVersion', 'Value']
    else:
        data["ModelVersion"] = 1

    if 'UserName' in df.index:
        data["UserName"] = df.at['UserName', 'Value']
    else:
        pass

    return data
