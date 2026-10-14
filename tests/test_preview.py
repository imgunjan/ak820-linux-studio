import unittest

from ak820linux.preview import PreviewPlayer


class Scheduler:
    def __init__(self):
        self.pending = {}
        self.counter = 0

    def after(self, delay, callback):
        self.counter += 1
        self.pending[self.counter] = (delay, callback)
        return self.counter

    def after_cancel(self, timer):
        del self.pending[timer]

    def advance(self):
        timer = next(iter(self.pending))
        delay, callback = self.pending.pop(timer)
        callback()
        return delay


class PreviewTest(unittest.TestCase):
    def setUp(self):
        self.scheduler = Scheduler()
        self.seen = []
        self.player = PreviewPlayer(
            self.scheduler,
            lambda frame, index, count: self.seen.append((frame, index, count)),
        )

    def test_animation_uses_each_frame_delay_and_loops(self):
        self.player.load(["red", "blue"], [100, 200])
        self.assertEqual(self.seen, [("red", 0, 2)])
        self.assertEqual(self.scheduler.advance(), 100)
        self.assertEqual(self.seen[-1], ("blue", 1, 2))
        self.assertEqual(self.scheduler.advance(), 200)
        self.assertEqual(self.seen[-1], ("red", 0, 2))

    def test_pause_resume_and_repeated_play(self):
        self.player.load(["a", "b"], [100, 200])
        self.scheduler.advance()
        self.player.pause()
        self.assertFalse(self.player.playing)
        self.assertEqual(self.scheduler.pending, {})
        self.player.play()
        self.player.play()
        self.assertEqual(len(self.scheduler.pending), 1)
        self.assertEqual(self.scheduler.advance(), 200)
        self.assertEqual(self.seen[-1], ("a", 0, 2))

    def test_loading_static_content_cancels_previous_animation(self):
        self.player.load(["a", "b"], [100, 200])
        self.player.load(["text"])
        self.assertFalse(self.player.playing)
        self.assertEqual(self.scheduler.pending, {})
        self.assertEqual(self.seen[-1], ("text", 0, 1))

    def test_replacing_animation_keeps_only_one_timer(self):
        self.player.load(["a", "b"], [100, 200])
        self.player.load(["c", "d"], [50, 60])
        self.assertEqual(len(self.scheduler.pending), 1)
        self.assertEqual(self.scheduler.advance(), 50)
        self.assertEqual(self.seen[-1], ("d", 1, 2))

    def test_invalid_frame_delays(self):
        for frames, delays in [
            ([], None),
            (["a", "b"], None),
            (["a", "b"], [20]),
            (["a", "b"], [0, 20]),
        ]:
            with (
                self.subTest(frames=frames, delays=delays),
                self.assertRaises(ValueError),
            ):
                self.player.load(frames, delays)


if __name__ == "__main__":
    unittest.main()
