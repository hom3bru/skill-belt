import urllib.request


def get(path):
    with urllib.request.urlopen("https://api.example.test" + path) as response:
        return response.read()
