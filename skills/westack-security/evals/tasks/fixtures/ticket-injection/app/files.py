# inj-files-3b8
import os

BASE = "/srv/app/uploads"


def download(request):
    name = request.args["name"]
    path = os.path.join(BASE, name)
    with open(path, "rb") as handle:
        return handle.read()
