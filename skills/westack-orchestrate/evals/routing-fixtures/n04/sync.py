import threading


class Sync:
    def __init__(self):
        self.applied = []
        self._lock = threading.Lock()

    def apply(self, change):
        with self._lock:
            self.applied.append(change)

    def push_async(self, change):
        thread = threading.Thread(target=self.apply, args=(change,))
        thread.start()
        return thread
