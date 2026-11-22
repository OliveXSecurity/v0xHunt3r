"""
Audio Capture - Captures audio from BlackHole 2ch via sounddevice
"""
import queue
import numpy as np
import sounddevice as sd
from rich.console import Console


console = Console()


class AudioCapture:
    """Captures audio from a specified input device into a thread-safe buffer"""

    def __init__(self, device_index: int, sample_rate: int = None, channels: int = None):
        self.device_index = device_index
        # Use device's native sample rate and channels to avoid issues
        dev_info = sd.query_devices(device_index)
        self.sample_rate = sample_rate or int(dev_info["default_samplerate"])
        self.channels = channels or min(int(dev_info["max_input_channels"]), 2)
        self.audio_queue = queue.Queue()
        self.stream = None
        self.running = False

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback for sounddevice InputStream - pushes audio to queue"""
        if status:
            console.print(f"[yellow]Audio capture status: {status}[/yellow]")
        self.audio_queue.put(indata.copy())

    def start(self):
        """Start capturing audio in background"""
        if self.running:
            return

        self.running = True
        self.stream = sd.InputStream(
            device=self.device_index,
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            blocksize=int(self.sample_rate * 0.03),  # 30ms blocks
            callback=self._audio_callback,
        )
        self.stream.start()
        console.print(f"[dim]Audio capture started (device {self.device_index})[/dim]")

    def stop(self):
        """Stop capturing"""
        self.running = False
        # Unblock any waiting get_audio_chunk calls
        self.audio_queue.put(np.zeros((1, self.channels), dtype="float32"))
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

    def get_audio_chunk(self, duration_ms: int) -> np.ndarray:
        """Get a chunk of audio of specified duration"""
        num_frames = int(self.sample_rate * duration_ms / 1000)
        frames = []
        collected = 0

        while collected < num_frames:
            try:
                chunk = self.audio_queue.get(timeout=duration_ms / 1000 + 1)
                frames.append(chunk)
                collected += len(chunk)
            except queue.Empty:
                break

        if not frames:
            return np.zeros((num_frames, self.channels), dtype="float32")

        audio = np.concatenate(frames, axis=0)
        return audio[:num_frames]

    def get_all_buffered(self) -> np.ndarray:
        """Get all buffered audio and clear the queue"""
        frames = []
        while not self.audio_queue.empty():
            try:
                frames.append(self.audio_queue.get_nowait())
            except queue.Empty:
                break

        if not frames:
            return np.zeros((0, self.channels), dtype="float32")

        return np.concatenate(frames, axis=0)

    def clear_buffer(self):
        """Clear the audio buffer"""
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

    def pause(self):
        """Pause capture (used during TTS playback to avoid feedback)"""
        if self.stream and self.running:
            self.stream.stop()

    def resume(self):
        """Resume capture after pause"""
        if self.stream and self.running:
            self.clear_buffer()
            self.stream.start()
