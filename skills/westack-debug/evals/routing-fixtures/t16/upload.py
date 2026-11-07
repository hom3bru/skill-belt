import urllib.request


def upload(path, url, timeout=2):
    with open(path, "rb") as handle:
        data = handle.read()
    request = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status
