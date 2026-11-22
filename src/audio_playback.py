"""
Audio Playback - Plays TTS audio through BlackHole 16ch virtual mic
"""
import numpy as np
import sounddevice as sd
import soundfile as sf
from rich.console import Console

from config import PLAYBACK_SAMPLE_RATE

console = Console()


class AudioPlayback:
    """Plays audio through a specified output device (BlackHole 16ch as virtual mic)"""

    def __init__(self, device_index: int, sample_rate: int = PLAYBACK_SAMPLE_RATE):
        self.device_index = device_index
        self.default_sample_rate = sample_rate

    def play(self, audio: np.ndarray, sample_rate: int = None, blocking: bool = True):
        """
        Play audio array through the virtual mic device.
        audio: float32 mono/stereo numpy array
        sample_rate: sample rate of the audio
        blocking: if True, wait until playback completes
        """
        if audio is None or len(audio) == 0:
            return

        sr = sample_rate or self.default_sample_rate

        # Ensure float32
        audio = audio.astype(np.float32)

        # Ensure proper shape for sounddevice
        if audio.ndim == 1:
            audio = audio.reshape(-1, 1)

        sd.play(audio, samplerate=sr, device=self.device_index, blocking=blocking)

    def play_file(self, path: str, blocking: bool = True):
        """Play a WAV file through the virtual mic"""
        audio, sr = sf.read(path, dtype="float32")
        self.play(audio, sample_rate=sr, blocking=blocking)

    def stop(self):
        """Stop any active playback"""
        sd.stop()
