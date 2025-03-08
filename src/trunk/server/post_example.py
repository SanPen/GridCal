import requests

url = "http://127.0.0.1:8000/receive-json"

random_json = {
    "name": "Alice",
    "age": 25,
    "address": {
        "street": "456 Elm St",
        "city": "Metropolis"
    },
    "hobbies": ["chess", "coding", "running"],
    "metadata": {"version": 1.2, "active": True}
}

response = requests.post(url, json=random_json)

print("Response Status Code:", response.status_code)
print("Response JSON:", response.json())
