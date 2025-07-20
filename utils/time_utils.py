import time


class TimeEvents:
    def __init__(self, name="Default"):
        self.name = name
        self.start_time = None
        self.elapsed_time = None
        self.occurrences = 0
        self.frames = 0
        self.end = None

    def restart(self):
        self.start_time = None
        self.elapsed_time = None
        self.occurrences = 0
        self.start()
        return self

    def start(self):
        self.start_time = time.time()
        return self

    def count_frames(self):
        self.frames += 1

    def reset_frames(self):
        self.frames = 0

    def increment(self):
        self.occurrences += 1

    def reset_increment(self):
        self.occurrences = 0

    def elapsed(self):
        if self.start_time is not None:
            self.elapsed_time = time.time() - self.start_time
        return self.elapsed_time

    def cps(self):
        return self.occurrences / self.elapsed_time
