"""
Speech-to-Text - Transcribes audio to text using faster-whisper
"""
import io
import numpy as np
import soundfile as sf
from rich.console import Console

from config import STT_ENGINE, WHISPER_MODEL, WHISPER_LANGUAGE, SAMPLE_RATE

console = Console()


class STTEngine:
    """Speech-to-Text engine using faster-whisper (CTranslate2 optimized Whisper)"""

    def __init__(
        self,
        engine: str = STT_ENGINE,
        model: str = WHISPER_MODEL,
        language: str = WHISPER_LANGUAGE,
    ):
        self.engine = engine
        self.language = language

        if engine == "faster-whisper":
            from faster_whisper import WhisperModel
            self.model = WhisperModel(
                model,
                device="cpu",
                compute_type="int8",  # Fast on Apple Silicon
            )
            console.print(f"[dim]STT loaded: faster-whisper ({model})[/dim]")
        else:
            raise ValueError(f"Unsupported STT engine: {engine}")

    def transcribe(self, audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> str:
        """
        Transcribe audio numpy array to text.
        audio: float32 mono array
        Returns: transcribed text string
        """
        if audio is None or len(audio) == 0:
            return ""

        # Ensure mono float32
        if audio.ndim > 1:
            audio = audio[:, 0]
        audio = audio.astype(np.float32)

        if self.engine == "faster-whisper":
            return self._transcribe_whisper(audio, sample_rate)

        return ""

    def _transcribe_whisper(self, audio: np.ndarray, sample_rate: int) -> str:
        """Transcribe using faster-whisper"""
        # Write audio to in-memory WAV buffer
        buffer = io.BytesIO()
        sf.write(buffer, audio, sample_rate, format="WAV", subtype="FLOAT")
        buffer.seek(0)

        # Transcribe
        segments, info = self.model.transcribe(
            buffer,
            language=self.language,
            beam_size=5,
            vad_filter=True,  # Use Silero VAD to filter silence
        )

        # Concatenate all segments
        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())

        text = " ".join(text_parts).strip()

        if text:
            detected_lang = info.language if hasattr(info, "language") else "unknown"
            console.print(f"[dim]STT ({detected_lang}, {info.duration:.1f}s): {text[:80]}{'...' if len(text) > 80 else ''}[/dim]")

        return text

    def detect_language(self, audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> str:
        """Detect language from audio sample"""
        if self.engine != "faster-whisper":
            return "unknown"

        buffer = io.BytesIO()
        sf.write(buffer, audio, sample_rate, format="WAV", subtype="FLOAT")
        buffer.seek(0)

        # Use first 30 seconds for language detection
        _, info = self.model.transcribe(buffer, language=None)
        return info.language
