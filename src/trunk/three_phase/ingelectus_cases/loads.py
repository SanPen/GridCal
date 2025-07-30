import pandas as pd
import os
import json

data = []

for i in os.listdir(os.path.join("networks")):
    print(i)
    
    pimp = 0
    pexp = 0
    qimp = 0
    qexp = 0

    with open(os.path.join("networks", i, "imbalance.json"), "r") as f:
        d = json.load(f)
    for n in d:
        for p in d[n]["p"]:
            if p <= 0:
                pimp += abs(p)
            else:
                pexp += abs(p)
        for q in d[n]["q"]:
            if q <= 0:
                qimp += abs(q)
            else:
                qexp += abs(q)

    data.append({
        "ct": i,
        "pimp": round(pimp/1e3,2),
        "pexp": round(pexp/1e3,2),
        "qimp": round(qimp/1e3,2),
        "qexp": round(qexp/1e3,2)
    })
data = pd.DataFrame(data)
data.to_csv("loads.csv", index=False)
    