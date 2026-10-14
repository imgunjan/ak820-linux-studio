"""Animation playback using the GUI's scheduler, without a worker thread."""


class PreviewPlayer:
    def __init__(self, scheduler, on_frame):
        self.scheduler = scheduler
        self.on_frame = on_frame
        self.frames = []
        self.delays = []
        self.index = 0
        self.playing = False
        self.timer = None

    def load(self, frames, delays=None):
        if not frames:
            raise ValueError("Preview needs at least one frame")
        if len(frames) > 1 and (
            delays is None or len(delays) != len(frames) or any(d <= 0 for d in delays)
        ):
            raise ValueError("Animated preview needs one positive delay per frame")
        self.pause()
        self.frames = list(frames)
        self.delays = list(delays) if delays is not None else []
        self.index = 0
        self.on_frame(self.frames[0], 0, len(self.frames))
        self.play()

    def play(self):
        if self.playing or len(self.frames) < 2:
            return
        self.playing = True
        self._schedule()

    def pause(self):
        self.playing = False
        if self.timer is not None:
            self.scheduler.after_cancel(self.timer)
            self.timer = None

    def _schedule(self):
        self.timer = self.scheduler.after(self.delays[self.index], self._advance)

    def _advance(self):
        self.timer = None
        if not self.playing:
            return
        self.index = (self.index + 1) % len(self.frames)
        self.on_frame(self.frames[self.index], self.index, len(self.frames))
        self._schedule()
