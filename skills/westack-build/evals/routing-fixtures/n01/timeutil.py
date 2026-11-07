def format_duration(minutes):
    hours, rest = divmod(minutes, 60)
    if hours:
        return "%dh%02dm" % (hours, rest)
    return "%dm" % rest
