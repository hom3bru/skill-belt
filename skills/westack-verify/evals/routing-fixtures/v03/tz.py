from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def to_local(ts, tz_name):
    moment = datetime.fromtimestamp(ts, tz=timezone.utc)
    return moment.astimezone(ZoneInfo(tz_name)).strftime("%Y-%m-%d %H:%M")
