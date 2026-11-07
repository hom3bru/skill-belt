import json

import redis

client = redis.Redis(host="localhost", port=6379)
TTL = 3600


def save(session_id, data):
    client.setex("sess:" + session_id, TTL, json.dumps(data))


def load(session_id):
    raw = client.get("sess:" + session_id)
    return json.loads(raw) if raw else None


def destroy(session_id):
    client.delete("sess:" + session_id)
