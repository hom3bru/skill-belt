import threading
import time


class Scheduler:
    def __init__(self):
        self.results = []
        self._threads = []

    def run_after(self, delay, name):
        def job():
            time.sleep(delay)
            self.results.append(name)

        thread = threading.Thread(target=job)
        thread.start()
        self._threads.append(thread)

    def wait(self):
        for thread in self._threads:
            thread.join()
