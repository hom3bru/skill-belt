def total_by_team(rows):
    totals = {}
    for row in rows:
        team = row.get("team") or "unassigned"
        totals[team] = totals.get(team, 0) + (row.get("hours") or 0)
    return totals
