from . import sessions


def attach_session(request):
    request["session"] = sessions.load(request["cookies"].get("sid", "")) or {}
    return request
