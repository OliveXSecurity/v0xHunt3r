"""
Voice Activity Detection - Silero VAD for detecting speech segments
Determines when the AI interviewer starts/stops speaking for turn-taking
"""
from typing import Optional

import numpy as np
import torch
from rich.console import Console

from config import VAD_THRESHOLD, SILENCE_DURATION_MS, MIN_SPEECH_DURATION_MS

console = Console()

# Silero VAD only supports 8kHz or 16kHz
VAD_SAMPLE_RATE = 16000
# Minimum samples Silero needs per frame (512 samples = 32ms at 16kHz)
VAD_FRAME_SAMPLES = 512


class VoiceActivityDetector:
    """Silero VAD wrapper for detecting complete speech segments"""

    def __init__(
        self,
        threshold: float = VAD_THRESHOLD,
        silence_ms: int = SILENCE_DURATION_MS,
        min_speech_ms: int = MIN_SPEECH_DURATION_MS,
    ):
        self.threshold = threshold
        self.silence_ms = silence_ms
        self.min_speech_ms = min_speech_ms

        # Load Silero VAD
        self.model, utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            trust_repo=True,
        )
        self.model.eval()

    def _resample(self, audio: np.ndarray, orig_sr: int, target_sr: int = VAD_SAMPLE_RATE) -> np.ndarray:
        """Simple resample by linear interpolation"""
        if orig_sr == target_sr:
            return audio
        ratio = target_sr / orig_sr
        n_samples = int(len(audio) * ratio)
        indices = np.linspace(0, len(audio) - 1, n_samples)
        return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)

    def _to_mono(self, audio: np.ndarray) -> np.ndarray:
        """Convert to mono if multi-channel"""
        if audio.ndim > 1:
            return audio[:, 0]
        return audio

    def is_speech(self, audio_frame: np.ndarray) -> bool:
        """
        Check if audio frame contains speech.
        audio_frame: mono float32 at 16kHz, must have >= 512 samples.
        Will be truncated to exactly 512 samples (Silero requirement).
        """
        if len(audio_frame) < VAD_FRAME_SAMPLES:
            return False

        # Silero requires EXACTLY 512 samples at 16kHz
        frame = audio_frame[:VAD_FRAME_SAMPLES]
        tensor = torch.from_numpy(frame).float()
        with torch.no_grad():
            prob = self.model(tensor, VAD_SAMPLE_RATE).item()
        return prob > self.threshold

    def detect_speech_segment(self, audio_capture) -> Optional[np.ndarray]:
        """
        Block until a complete speech segment is detected.
        Returns the full audio as mono float32 at the capture sample rate,
        or None if capture stopped.
        """
        capture_sr = audio_capture.sample_rate
        # Calculate exact capture samples needed to produce 512 samples at 16kHz
        # 512 samples at 16kHz = 32ms. At 48kHz that's 1536 samples.
        capture_frame_samples = int(VAD_FRAME_SAMPLES * capture_sr / VAD_SAMPLE_RATE)
        frame_duration_ms = int(capture_frame_samples / capture_sr * 1000) + 1  # +1 to ensure enough

        silence_frames_needed = int(self.silence_ms * VAD_SAMPLE_RATE / (VAD_FRAME_SAMPLES * 1000))
        min_speech_frames = int(self.min_speech_ms * VAD_SAMPLE_RATE / (VAD_FRAME_SAMPLES * 1000))

        def _check_speech(mono_chunk: np.ndarray) -> bool:
            """Resample chunk to 16kHz and run VAD"""
            if len(mono_chunk) < capture_frame_samples:
                return False
            # Resample exactly capture_frame_samples -> VAD_FRAME_SAMPLES
            indices = np.linspace(0, capture_frame_samples - 1, VAD_FRAME_SAMPLES)
            vad_frame = np.interp(indices, np.arange(capture_frame_samples),
                                  mono_chunk[:capture_frame_samples]).astype(np.float32)
            return self.is_speech(vad_frame)

        # Phase 1: Wait for speech to start
        while audio_capture.running:
            chunk = audio_capture.get_audio_chunk(frame_duration_ms)
            mono = self._to_mono(chunk)
            if _check_speech(mono):
                break
        else:
            return None

        # Phase 2: Accumulate speech + detect end
        speech_frames = [self._to_mono(chunk)]
        silence_count = 0
        speech_count = 1

        while audio_capture.running:
            chunk = audio_capture.get_audio_chunk(frame_duration_ms)
            mono = self._to_mono(chunk)
            if len(mono) < capture_frame_samples:
                continue

            speech_frames.append(mono)

            if _check_speech(mono):
                silence_count = 0
                speech_count += 1
            else:
                silence_count += 1

            # End of speech detected
            if silence_count >= silence_frames_needed and speech_count >= min_speech_frames:
                break

        if not speech_frames:
            return None

        # Concatenate all frames (at capture sample rate)
        audio = np.concatenate(speech_frames, axis=0)

        duration_s = len(audio) / capture_sr
        console.print(f"[dim]Speech segment: {duration_s:.1f}s[/dim]")

        return audio

    def reset(self):
        """Reset VAD model state"""
        self.model.reset_states()
