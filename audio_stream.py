import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib
import numpy as np
import threading

FS = 44100
BLOCKSIZE = 1024

class AudioStream:
    def __init__(self, device=None, callback=None):
        self.name = self.__class__.__name__
        Gst.init(None)
        self.device = device
        if callback:
            self.callback = callback
        self.pipeline = None
        self.appsink = None
        self._lock = threading.Lock()
        self._build_pipeline()

    def _build_pipeline(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)

        device_part = f"device={self.device}" if self.device else ""
        pipeline_desc = (
            f"pulsesrc {device_part} ! "
            f"audio/x-raw,format=S16LE,channels=1,rate={FS} ! "
            f"appsink name=sink emit-signals=true max-buffers=10 drop=true"
        )
        # print(pipeline_desc)
        self.pipeline = Gst.parse_launch(pipeline_desc)
        self.appsink = self.pipeline.get_by_name("sink")
        self.appsink.connect("new-sample", self.on_new_sample)
        self.pipeline.set_state(Gst.State.PLAYING)

    def set_device(self, device):
        with self._lock:
            self.device = device
            self._build_pipeline()

    def audio_callback(self, data: np.ndarray, frames: int, time_info=None, status=None):
        print("received:", data.shape, "frames")

    def on_new_sample(self, sink):
        sample = sink.emit("pull-sample")
        buf = sample.get_buffer()
        success, map_info = buf.map(Gst.MapFlags.READ)
        if success:
            arr = np.frombuffer(map_info.data, dtype=np.int16)
            if arr.size >= BLOCKSIZE:
                arr = arr[:BLOCKSIZE]
            arr = arr.reshape(-1, 1)
            if self.callback:
                self.callback(arr, arr.size)
            else:
                self.audio_callback(arr, arr.size)

            buf.unmap(map_info)
        return Gst.FlowReturn.OK

    def start(self):
        with self._lock:
            if self.pipeline:
                self.pipeline.set_state(Gst.State.PLAYING)

    def stop(self):
        with self._lock:
            if self.pipeline:
                self.pipeline.set_state(Gst.State.NULL)

# ----------Test Part -----------------
if __name__ == "__main__":
    loop = GLib.MainLoop()
    stream = AudioStream(device="")
    stream.start()

    try:
        loop.run()
    except KeyboardInterrupt:
        stream.stop()

