import json


def export_json(notes):
    return json.dumps([{"id": n["id"], "title": n["title"], "body": n["body"]} for n in notes])
