# Authored synthetic donor, fixture revision game-v1. Rights: task-authored example.
# Imagine a game's unlocked checkpoint IDs. No fixture imports are executed.
def remember(seen, checkpoint):
    if checkpoint in seen:
        return False
    seen.add(checkpoint)
    return True
