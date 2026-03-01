import requests

url = "http://localhost:8000/db/sync"
data = {
    "email": "arnaucosta95@gmail.com",
    "password": "3jJDblpR.1", 
    "start_date": "2025-01-01",
    "end_date": "2025-10-09",
    "sync_details": True  # Cambiar a True si quieres detalles completos
}

response = requests.post(url, json=data)
print(response.json())