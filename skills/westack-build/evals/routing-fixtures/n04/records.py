def from_v1(raw):
    return {"id": raw["id"], "title": raw["title"], "owner": raw["owner"]}


def from_v2(raw):
    return {"id": raw["id"], "title": raw["title"], "assignee": raw["assignee"]}
