"""
Text-to-Speech - Converts attack payloads to spoken audio
Primary: OpenAI TTS API, Fallback: edge-tts (free)
"""
from typing import Tuple

import io
import asyncio
import threading
import numpy as np
import soundfile as sf
from rich.console import Console

from config import (
    TTS_ENGINE, OPENAI_TTS_MODEL, OPENAI_TTS_VOICE,
    EDGE_TTS_VOICE, TTS_SPEED, PLAYBACK_SAMPLE_RATE,
    EDGE_TTS_VOICES, OPENAI_TTS_VOICES,
)

console = Console()


class TTSEngine:
    """Text-to-Speech engine with OpenAI and edge-tts backends"""

    def __init__(self, engine: str = TTS_ENGINE, voice: str = None, language: str = "en"):
        self.engine = engine
        self.language = language

        if engine == "openai":
            import openai
            self.client = openai.OpenAI()
            self.voice = voice or OPENAI_TTS_VOICES.get(language, OPENAI_TTS_VOICE)
            self.model = OPENAI_TTS_MODEL
            console.print(f"[dim]TTS loaded: OpenAI ({self.model}, {self.voice})[/dim]")
        elif engine == "edge-tts":
            self.voice = voice or EDGE_TTS_VOICES.get(language, EDGE_TTS_VOICE)
            console.print(f"[dim]TTS loaded: edge-tts ({self.voice})[/dim]")
        else:
            raise ValueError(f"Unsupported TTS engine: {engine}")

    def set_language(self, language: str):
        """Change TTS language/voice mid-session"""
        self.language = language
        if self.engine == "openai":
            self.voice = OPENAI_TTS_VOICES.get(language, OPENAI_TTS_VOICE)
        elif self.engine == "edge-tts":
            self.voice = EDGE_TTS_VOICES.get(language, EDGE_TTS_VOICE)
        console.print(f"[dim]TTS language changed to {language} (voice: {self.voice})[/dim]")

    def synthesize(self, text: str) -> Tuple[np.ndarray, int]:
        """
        Convert text to audio numpy array.
        Returns: (audio_array, sample_rate)
        """
        if not text:
            return np.zeros(0, dtype="float32"), PLAYBACK_SAMPLE_RATE

        if self.engine == "openai":
            return self._synthesize_openai(text)
        elif self.engine == "edge-tts":
            return self._synthesize_edge(text)

        return np.zeros(0, dtype="float32"), PLAYBACK_SAMPLE_RATE

    def _synthesize_openai(self, text: str) -> Tuple[np.ndarray, int]:
        """Synthesize using OpenAI TTS API - returns PCM audio"""
        response = self.client.audio.speech.create(
            model=self.model,
            voice=self.voice,
            input=text,
            speed=TTS_SPEED,
            response_format="wav",
        )

        # Read WAV bytes into numpy array
        audio_bytes = io.BytesIO(response.content)
        audio, sample_rate = sf.read(audio_bytes, dtype="float32")

        # Ensure mono
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        console.print(f"[dim]TTS generated: {len(audio)/sample_rate:.1f}s[/dim]")
        return audio, sample_rate

    def _synthesize_edge(self, text: str) -> Tuple[np.ndarray, int]:
        """Synthesize using edge-tts (free Microsoft voices)"""
        import av

        # edge-tts is async - run in a separate thread to avoid nested loop issues
        audio_data = None
        exc = None

        def _run():
            nonlocal audio_data, exc
            loop = asyncio.new_event_loop()
            try:
                audio_data = loop.run_until_complete(self._edge_tts_generate(text))
            except Exception as e:
                exc = e
            finally:
                loop.close()

        t = threading.Thread(target=_run)
        t.start()
        t.join()
        if exc:
            raise exc

        if not audio_data:
            return np.zeros(0, dtype="float32"), PLAYBACK_SAMPLE_RATE

        # Decode MP3 using av (PyAV) - no ffmpeg CLI needed
        mp3_buffer = io.BytesIO(audio_data)
        container = av.open(mp3_buffer, format="mp3")
        frames = []
        sample_rate = PLAYBACK_SAMPLE_RATE

        for frame in container.decode(audio=0):
            sample_rate = frame.sample_rate
            arr = frame.to_ndarray().astype(np.float32)
            # Normalize if int format
            if frame.format.name in ("s16", "s16p"):
                arr = arr / 32768.0
            elif frame.format.name in ("s32", "s32p"):
                arr = arr / 2147483648.0
            # to_ndarray returns (channels, samples) for planar, take first channel
            if arr.ndim > 1:
                arr = arr[0]
            frames.append(arr)

        container.close()

        if not frames:
            return np.zeros(0, dtype="float32"), PLAYBACK_SAMPLE_RATE

        samples = np.concatenate(frames)
        console.print(f"[dim]TTS generated: {len(samples)/sample_rate:.1f}s[/dim]")
        return samples, sample_rate

    async def _edge_tts_generate(self, text: str) -> bytes:
        """Generate audio bytes from edge-tts"""
        import edge_tts

        communicate = edge_tts.Communicate(text, self.voice)
        audio_chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        return b"".join(audio_chunks) if audio_chunks else b""

    def synthesize_to_file(self, text: str, path: str):
        """Save TTS output to a WAV file (for evidence/logging)"""
        audio, sample_rate = self.synthesize(text)
        if len(audio) > 0:
            sf.write(path, audio, sample_rate)
