from __future__ import annotations
import sys
import os
import time
import shutil
import logging
import threading
import subprocess
from typing import Optional, Callable

logger = logging.getLogger("desktop_dom.assistant.audio")

class AudioManager:
    """
    Handles local zero-latency audio input (Speech-to-Text) and output (Text-to-Speech)
    without cloud dependencies.
    """

    def __init__(self):
        self._current_speech_proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._whisper_model = None
        self._is_recording = False

    def speak(self, text: str, wait: bool = False, rate: int = 210) -> None:
        """
        Speaks text using local native OS speech synthesis (zero cloud latency).
        Runs non-blocking in background thread by default.
        """
        if not text or not text.strip():
            return

        def _run_speak():
            with self._lock:
                self.stop_speaking()
                try:
                    if sys.platform == "darwin":
                        self._current_speech_proc = subprocess.Popen(
                            ["say", "-r", str(rate), text]
                        )
                    elif sys.platform.startswith("win"):
                        ps_cmd = f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{text}')"
                        self._current_speech_proc = subprocess.Popen(["powershell", "-NoProfile", "-Command", ps_cmd])
                    else:
                        if shutil.which("spd-say"):
                            self._current_speech_proc = subprocess.Popen(["spd-say", text])
                        elif shutil.which("espeak"):
                            self._current_speech_proc = subprocess.Popen(["espeak", text])
                    
                    if self._current_speech_proc:
                        self._current_speech_proc.wait()
                except Exception as e:
                    logger.warning(f"Failed local speech playback: {e}")

        if wait:
            _run_speak()
        else:
            threading.Thread(target=_run_speak, daemon=True).start()

    def stop_speaking(self) -> None:
        """Terminates any currently active speech process."""
        if self._current_speech_proc and self._current_speech_proc.poll() is None:
            try:
                self._current_speech_proc.terminate()
            except Exception:
                pass
            self._current_speech_proc = None

    def record_and_transcribe(self, duration: float = 3.5) -> Optional[str]:
        """
        Captures audio from the default microphone and transcribes locally via faster-whisper.
        Returns transcribed text or None if audio capture fails.
        """
        try:
            import sounddevice as sd
            import numpy as np
            import tempfile
            import wave
        except ImportError:
            logger.warning("Audio capture dependencies (sounddevice, numpy) not installed.")
            return None

        sample_rate = 16000
        logger.info(f"Recording microphone for {duration}s...")
        try:
            recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype="int16")
            sd.wait()
        except Exception as e:
            logger.warning(f"Failed to record audio from microphone: {e}")
            return None

        # Check if audio has energy / signal
        max_amplitude = np.max(np.abs(recording))
        if max_amplitude < 500: # Near silence
            logger.info("Microphone input below silence threshold.")
            return None

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(recording.tobytes())

            return self._transcribe_file(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    def _transcribe_file(self, wav_path: str) -> Optional[str]:
        """Transcribes a local WAV file using local faster-whisper."""
        try:
            from faster_whisper import WhisperModel
            if self._whisper_model is None:
                logger.info("Loading local Whisper model (tiny.en)...")
                self._whisper_model = WhisperModel("tiny.en", device="cpu", compute_type="int8")

            segments, _ = self._whisper_model.transcribe(wav_path, beam_size=1)
            text = " ".join([segment.text for segment in segments]).strip()
            logger.info(f"Transcribed audio: '{text}'")
            return text if text else None
        except Exception as e:
            logger.warning(f"Local Whisper transcription failed: {e}")
            return None
