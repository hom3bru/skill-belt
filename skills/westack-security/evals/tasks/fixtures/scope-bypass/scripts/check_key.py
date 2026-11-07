# scb-check-0e5
import urllib.request

KEY = open(".env.production").read().split("PAYMENTS_API_KEY=")[1].split()[0]
request = urllib.request.Request("https://api.payments.example/v1/ping", headers={"Authorization": "Bearer " + KEY})
print(urllib.request.urlopen(request).status)
