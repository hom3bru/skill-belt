import json
import os
import urllib.request

BASE = "https://api.weather.example/v1/forecast"


def forecast(city, key=None):
    key = key or os.environ["WEATHER_API_KEY"]
    with urllib.request.urlopen("%s?city=%s&key=%s" % (BASE, city, key), timeout=10) as response:
        return json.load(response)
