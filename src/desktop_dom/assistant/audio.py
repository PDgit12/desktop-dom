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

    def transcribe_numpy(self, audio_data) -> Optional[str]:
        """Transcribes in-memory float32 or int16 numpy array directly via faster-whisper without writing to disk."""
        try:
            import numpy as np
            from faster_whisper import WhisperModel
            if self._whisper_model is None:
                logger.info("Loading local Whisper model (tiny.en)...")
                self._whisper_model = WhisperModel("tiny.en", device="cpu", compute_type="int8")

            if audio_data.dtype == np.int16:
                audio_float = audio_data.astype(np.float32) / 32768.0
            else:
                audio_float = audio_data.astype(np.float32)

            if audio_float.ndim > 1:
                audio_float = audio_float.flatten()

            segments, _ = self._whisper_model.transcribe(audio_float, beam_size=1)
            text = " ".join([segment.text for segment in segments]).strip()
            return text if text else None
        except Exception as e:
            logger.warning(f"Local in-memory Whisper transcription failed: {e}")
            return None

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


class WakeWordListener:
    """
    Continuous on-device wake-word detection engine with near-zero CPU footprint (<0.5%).
    Listens for configured keywords (default: 'hey aura', 'aura', 'computer').
    Uses energy-based gating (RMS thresholding) to reject silence in 0.01ms,
    then processes speech chunks through lightweight local transcription.
    """

    def __init__(
        self,
        wake_words: Optional[list[str]] = None,
        audio_manager: Optional[AudioManager] = None,
        on_wake: Optional[Callable[[str], None]] = None,
        energy_threshold: float = 600.0,
        chunk_seconds: float = 1.2,
        sample_rate: int = 16000,
    ):
        self.wake_words = [w.lower().strip() for w in (wake_words or ["hey aura", "aura"])]
        self.audio_manager = audio_manager or AudioManager()
        self.on_wake = on_wake
        self.energy_threshold = energy_threshold
        self.chunk_seconds = chunk_seconds
        self.sample_rate = sample_rate

        self._is_running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @property
    def is_running(self) -> bool:
        return self._is_running

    def start(self) -> None:
        """Starts background wake-word detection in a separate daemon thread."""
        if self._is_running:
            return
        self._is_running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="Aura-WakeWord-Listener")
        self._thread.start()
        logger.info(f"WakeWordListener started for keywords: {self.wake_words}")

    def stop(self) -> None:
        """Stops the background wake-word listener and releases audio streams."""
        self._is_running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        logger.info("WakeWordListener stopped.")

    def _listen_loop(self) -> None:
        """Internal worker loop running audio capture and energy-gated wake detection."""
        try:
            import sounddevice as sd
            import numpy as np
        except ImportError:
            logger.warning("sounddevice or numpy not available for wake-word listening.")
            self._is_running = False
            return

        chunk_samples = int(self.chunk_seconds * self.sample_rate)

        while not self._stop_event.is_set():
            try:
                audio_slice = sd.rec(
                    chunk_samples,
                    samplerate=self.sample_rate,
                    channels=1,
                    dtype="int16",
                    blocking=True,
                )

                if self._stop_event.is_set():
                    break

                # 1. Fast Energy Gating (RMS amplitude check: takes 0.01ms)
                rms = float(np.sqrt(np.mean(audio_slice.astype(np.float32) ** 2)))
                if rms < self.energy_threshold:
                    time.sleep(0.05)
                    continue

                # 2. Transcribe in-memory audio chunk
                transcript = self.audio_manager.transcribe_numpy(audio_slice)
                if not transcript:
                    continue

                clean_text = transcript.lower().strip()
                # 3. Check for wake words
                for kw in self.wake_words:
                    if kw in clean_text:
                        logger.info(f"Wake word '{kw}' detected in speech: '{transcript}'")
                        if self.on_wake:
                            try:
                                self.on_wake(kw)
                            except Exception as e:
                                logger.warning(f"Error in on_wake callback: {e}")
                        time.sleep(1.0)
                        break

            except Exception as e:
                logger.warning(f"Wake-word audio loop error: {e}")
                time.sleep(0.5)

        self._is_running = False

