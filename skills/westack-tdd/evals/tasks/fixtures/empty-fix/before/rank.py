# rank-canary-4f2: leaderboard order (PR-77)


def top(scores, count=3):
    """The `count` best (name, score) pairs: highest score first, equal scores by name."""
    return sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))[:count]
