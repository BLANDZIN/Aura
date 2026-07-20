"""
voice/voice_engine.py — AURA V11
================================
Motor de Voz leve, cross-platform e otimizado.

TTS (Texto → Fala):
  1. edge-tts     — Microsoft Edge TTS gratuito, vozes neurais PT-BR excelentes (~500KB)
  2. OS nativo     — Windows SAPI, macOS say, Linux espeak/spd-say (fallback)
  3. pyttsx3      — legado, mantido como último recurso

STT (Fala → Texto):
  1. speechrecognition + Google Web Speech — leve, gratuito, ~2MB (~0 deps)
  2. faster-whisper local — opcional para privacidade offline (modelo ~150MB tiny)

Vantagens sobre o voice_manager.py anterior:
  - edge-tts: vozes neurais PT-BR excelentes (Francisca, Antonio) vs espeak robótico
  - Zero dependências de sistema: funciona idêntico em Windows/Linux/macOS
  - ~500KB vs ~15MB do pyttsx3
  - Cancelamento de fala (stop mid-speech)
  - Reload de configurações em runtime
  - Fallback automático em cascata: edge-tts → OS nativo → pyttsx3
"""

import asyncio
import os
import re
import subprocess
import sys
import threading
import queue
import tempfile
import time
from typing import Optional, List

from core.event_bus import bus
from config.settings import settings
from core.logger import setup_logger

logger = setup_logger("voice")


# ═══════════════════════════════════════════════════════════════════════════════
# TTS ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class TTSEngine:
    """
    Text-to-Speech multi-backend com fallback automático.

    Prioridade:
      1. edge-tts (vozes neurais PT-BR, ~500KB, cross-platform)
      2. OS nativo  (Windows SAPI / macOS say / Linux spd-say)
      3. pyttsx3    (legado, pesado)
    """

    # Vozes PT-BR recomendadas do edge-tts
    PT_BR_VOICES = [
        "pt-BR-FranciscaNeural",   # feminina, calorosa — padrão
        "pt-BR-AntonioNeural",     # masculina, clara
        "pt-BR-ThalitaNeural",     # feminina, suave (versão Multilingual)
        "pt-BR-BrendaNeural",      # feminina (versão Multilingual)
    ]

    EN_VOICES = [
        "en-US-JennyNeural",       # feminina
        "en-US-GuyNeural",         # masculina
    ]

    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._current_voice = None
        self._cancel_flag = threading.Event()

        # Backend disponível
        self._backend = None           # "edge_tts" | "native" | "pyttsx3"
        self._pyttsx3_engine = None

        self.reload_settings()

    # ── Configuração ──────────────────────────────────────────────────────────

    def reload_settings(self):
        """Recarrega configurações em runtime (idioma, velocidade, volume)."""
        self._enabled = settings.get("voice", "tts_enabled", default=True)
        self._rate = settings.get("voice", "voice_rate", default=170)
        self._volume = settings.get("voice", "voice_volume", default=0.9)
        self._language = settings.get("voice", "language", default="pt")
        self._auto_speak = settings.get("voice", "auto_speak", default=False)

        # Mapeia rate (pyttsx3: 50-300) → edge-tts (+-50%)
        # 170 (padrão) → +0%, 100 → -30%, 250 → +30%
        self._rate_pct = int((self._rate - 170) / 170 * 50)

    # ── Inicialização ─────────────────────────────────────────────────────────

    def start(self) -> bool:
        """Inicializa o melhor backend disponível."""
        if not self._enabled:
            logger.info("TTS desabilitado nas configurações")
            return False

        # Tenta edge-tts primeiro (melhor qualidade)
        if self._init_edge_tts():
            self._backend = "edge_tts"
            logger.info("TTS: edge-tts (vozes neurais Microsoft)")
        elif self._init_native():
            self._backend = "native"
            logger.info("TTS: OS nativo")
        elif self._init_pyttsx3():
            self._backend = "pyttsx3"
            logger.info("TTS: pyttsx3 (legado)")
        else:
            logger.warning("TTS: nenhum backend disponível")
            return False

        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def _init_edge_tts(self) -> bool:
        """Verifica se edge-tts está disponível."""
        try:
            import edge_tts  # noqa: F401
            # Seleciona voz baseada no idioma
            voices = self.PT_BR_VOICES if self._language.startswith("pt") else self.EN_VOICES
            self._current_voice = voices[0]
            return True
        except ImportError:
            logger.debug("edge-tts não instalado. pip install edge-tts")
            return False

    def _init_native(self) -> bool:
        """Verifica se TTS nativo do OS funciona."""
        system = sys.platform
        if system == "win32":
            # Windows SAPI via PowerShell (disponível em qualquer Windows 10+)
            try:
                r = subprocess.run(
                    ["powershell", "-c", "Add-Type -AssemblyName System.Speech; "
                     "(New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices().Count"],
                    capture_output=True, text=True, timeout=5
                )
                return r.returncode == 0 and int(r.stdout.strip() or "0") > 0
            except Exception:
                return False
        elif system == "darwin":
            return shutil_which("say") is not None
        else:
            # Linux: spd-say (speech-dispatcher) ou espeak
            return (shutil_which("spd-say") or shutil_which("espeak")) is not None

    def _init_pyttsx3(self) -> bool:
        """Fallback legado."""
        try:
            import pyttsx3
            self._pyttsx3_engine = pyttsx3.init()
            self._pyttsx3_engine.setProperty("rate", self._rate)
            self._pyttsx3_engine.setProperty("volume", self._volume)
            return True
        except Exception:
            return False

    # ── API pública ───────────────────────────────────────────────────────────

    def speak(self, text: str) -> None:
        """Enfileira texto para fala (não-bloqueante)."""
        if not self._running:
            return
        clean = self._clean_text(text)
        if clean:
            self._queue.put(clean)

    def stop(self) -> None:
        """Para fala atual e limpa fila."""
        self._cancel_flag.set()
        with self._queue.mutex:
            self._queue.queue.clear()

    def shutdown(self) -> None:
        """Encerra engine."""
        self._running = False
        self.stop()
        self._queue.put(None)  # sentinela

    # ── Loop de fala ──────────────────────────────────────────────────────────

    def _loop(self) -> None:
        while self._running:
            try:
                text = self._queue.get(timeout=0.5)
                if text is None:
                    break
                self._cancel_flag.clear()
                bus.publish("voice.speaking_start", text=text[:100])

                if self._backend == "edge_tts":
                    self._speak_edge_tts(text)
                elif self._backend == "native":
                    self._speak_native(text)
                elif self._backend == "pyttsx3":
                    self._speak_pyttsx3(text)

                if not self._cancel_flag.is_set():
                    bus.publish("voice.speaking_end")
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Erro TTS: {e}")

    def _speak_edge_tts(self, text: str):
        """Fala via edge-tts (async → sync via thread)."""
        try:
            import edge_tts

            voice = self._current_voice or self.PT_BR_VOICES[0]
            rate_str = f"{self._rate_pct:+d}%" if self._rate_pct != 0 else "+0%"
            vol_str = f"{int(self._volume * 100):+d}%"

            communicate = edge_tts.Communicate(
                text, voice,
                rate=rate_str,
                volume=vol_str,
            )

            # Salva em arquivo temporário e toca
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp_path = tmp.name

            async def _run():
                await communicate.save(tmp_path)

            # Executa o async em thread separada
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_run())
            finally:
                loop.close()

            if not self._cancel_flag.is_set():
                self._play_audio(tmp_path)

            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        except Exception as e:
            logger.warning(f"edge-tts falhou: {e} → tentando fallback")
            self._speak_native(text)

    def _speak_native(self, text: str):
        """Fala via TTS nativo do OS."""
        system = sys.platform
        try:
            if system == "win32":
                # Windows SAPI via PowerShell
                ps_script = (
                    f'Add-Type -AssemblyName System.Speech; '
                    f'$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
                    f'$s.Rate = {self._rate_pct // 5}; '
                    f'$s.Volume = {int(self._volume * 100)}; '
                    f'$s.Speak([Console]::In.ReadToEnd())'
                )
                proc = subprocess.Popen(
                    ["powershell", "-c", ps_script],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                proc.communicate(input=text.encode("utf-8"), timeout=30)
            elif system == "darwin":
                rate = max(100, min(300, self._rate))
                subprocess.run(["say", "-r", str(rate), text], timeout=30)
            else:
                # Linux: spd-say preferido, espeak fallback
                if shutil_which("spd-say"):
                    subprocess.run(["spd-say", "-r", str(self._rate), text], timeout=30)
                elif shutil_which("espeak"):
                    rate_wpm = self._rate
                    subprocess.run(
                        ["espeak", "-s", str(rate_wpm), "-v",
                         "pt" if self._language.startswith("pt") else "en", text],
                        timeout=30,
                    )
                else:
                    raise RuntimeError("Nenhum TTS nativo disponível")
        except Exception as e:
            logger.warning(f"TTS nativo falhou: {e}")
            self._speak_pyttsx3(text)

    def _speak_pyttsx3(self, text: str):
        """Fallback legado pyttsx3."""
        if not self._pyttsx3_engine:
            return
        try:
            self._pyttsx3_engine.say(text)
            self._pyttsx3_engine.runAndWait()
        except Exception as e:
            logger.error(f"pyttsx3 falhou: {e}")

    def _play_audio(self, path: str):
        """Toca arquivo de áudio via player nativo."""
        system = sys.platform
        try:
            if system == "win32":
                import winsound
                winsound.PlaySound(path, winsound.SND_FILENAME)
            elif system == "darwin":
                subprocess.run(["afplay", path], timeout=30)
            else:
                # Linux: tenta vários players
                for cmd in (["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
                            ["mpg123", "-q", path],
                            ["aplay", path]):
                    if shutil_which(cmd[0]):
                        subprocess.run(cmd, timeout=30)
                        return
                logger.warning("Nenhum player de áudio encontrado no Linux")
        except Exception as e:
            logger.warning(f"Falha ao tocar áudio: {e}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _clean_text(text: str) -> str:
        """Remove emojis e caracteres problemáticos."""
        cleaned = re.sub(r'[^\w\s\.,!?;:áéíóúàèìòùâêîôûãõçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ\-]', '', text)
        return cleaned.strip()


# ═══════════════════════════════════════════════════════════════════════════════
# STT ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class STTEngine:
    """
    Speech-to-Text multi-backend.

    Prioridade:
      1. speechrecognition + Google Web Speech — leve, gratuito, ~2MB
      2. faster-whisper local — privacidade offline (~150MB modelo tiny)
    """

    def __init__(self):
        self._enabled = settings.get("voice", "stt_enabled", default=False)
        self._model_size = settings.get("voice", "stt_model", default="tiny")
        self._language = settings.get("voice", "language", default="pt")

        # Backends
        self._sr_available = False
        self._whisper_model = None
        self._backend = None

    def init(self) -> bool:
        """Inicializa o melhor backend STT disponível."""
        if not self._enabled:
            return False

        # Tenta speechrecognition primeiro (leve)
        if self._init_speechrecognition():
            self._backend = "speechrecognition"
            logger.info("STT: speechrecognition + Google Web Speech")
            return True

        # Fallback: faster-whisper (pesado, local)
        if self._init_whisper():
            self._backend = "whisper"
            logger.info(f"STT: faster-whisper ({self._model_size})")
            return True

        logger.warning("STT: nenhum backend disponível")
        return False

    def _init_speechrecognition(self) -> bool:
        try:
            import speech_recognition as sr  # noqa: F401
            self._sr_available = True
            return True
        except ImportError:
            logger.debug("speechrecognition não instalado. pip install SpeechRecognition")
            return False

    def _init_whisper(self) -> bool:
        try:
            from faster_whisper import WhisperModel
            logger.info(f"Carregando Whisper '{self._model_size}' (~150MB na 1ª vez)...")
            self._whisper_model = WhisperModel(
                self._model_size, device="cpu", compute_type="int8"
            )
            return True
        except ImportError:
            logger.debug("faster-whisper não instalado")
            return False
        except Exception as e:
            logger.warning(f"Erro ao carregar Whisper: {e}")
            return False

    def listen_once(self, duration: float = 5.0) -> Optional[str]:
        """Grava e transcreve em thread separada."""
        if not self._enabled:
            bus.publish("voice.error", mensagem="STT desabilitado nas configurações")
            return None

        def _record():
            try:
                bus.publish("voice.listening", status=True)

                if self._backend == "speechrecognition":
                    text = self._transcribe_sr(duration)
                elif self._backend == "whisper":
                    text = self._transcribe_whisper(duration)
                else:
                    bus.publish("voice.error", mensagem="STT não disponível")
                    return

                bus.publish("voice.listening", status=False)

                if text:
                    bus.publish("voice.transcribed", text=text)
                else:
                    bus.publish("voice.error", mensagem="Nada detectado")

            except Exception as e:
                bus.publish("voice.listening", status=False)
                bus.publish("voice.error", mensagem=str(e))

        threading.Thread(target=_record, daemon=True).start()

    def _transcribe_sr(self, duration: float) -> Optional[str]:
        """Transcrição via SpeechRecognition + Google."""
        import speech_recognition as sr

        r = sr.Recognizer()
        try:
            with sr.Microphone() as source:
                r.adjust_for_ambient_noise(source, duration=0.5)
                audio = r.listen(source, timeout=duration, phrase_time_limit=duration)

            lang = "pt-BR" if self._language.startswith("pt") else "en-US"
            text = r.recognize_google(audio, language=lang)
            return text.strip()
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            logger.warning(f"Google Speech API indisponível: {e}")
            # Tenta whisper como fallback
            return self._transcribe_whisper(duration)
        except Exception as e:
            logger.error(f"Erro STT (SR): {e}")
            return None

    def _transcribe_whisper(self, duration: float) -> Optional[str]:
        """Transcrição via faster-whisper (offline)."""
        if not self._whisper_model:
            return None

        import sounddevice as sd
        import numpy as np
        import wave

        sample_rate = 16000
        recording = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
        )
        sd.wait()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            with wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes((recording * 32767).astype(np.int16).tobytes())

            segments, _ = self._whisper_model.transcribe(
                tmp_path,
                language=self._language if self._language != "pt" else None,
            )
            text = " ".join(seg.text for seg in segments).strip()
            return text or None
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ═══════════════════════════════════════════════════════════════════════════════
# VOICE MANAGER (fachada unificada)
# ═══════════════════════════════════════════════════════════════════════════════

class VoiceManager:
    """Fachada unificada TTS + STT com EventBus."""

    def __init__(self):
        self.tts = TTSEngine()
        self.stt = STTEngine()
        self._auto_speak = settings.get("voice", "auto_speak", default=False)

    def start(self) -> None:
        """Inicializa TTS e STT, conecta ao EventBus."""
        tts_ok = self.tts.start()
        stt_ok = self.stt.init()

        if tts_ok and self._auto_speak:
            bus.subscribe("ai.response", self._on_ai_response)
            logger.info("Fala automática ativada")

        bus.subscribe("voice.transcribed", self._on_transcribed)

        logger.info(
            f"VoiceManager: TTS={'OK' if tts_ok else 'OFF'} "
            f"| STT={'OK' if stt_ok else 'OFF'}"
        )

    def speak(self, text: str) -> None:
        self.tts.speak(text)

    def listen(self, duration: float = 5.0) -> None:
        self.stt.listen_once(duration)

    def stop(self) -> None:
        self.tts.stop()

    def shutdown(self) -> None:
        self.tts.shutdown()

    def reload_settings(self) -> None:
        """Recarrega configs em runtime (idioma, velocidade)."""
        self.tts.reload_settings()

    def toggle_auto_speak(self) -> bool:
        self._auto_speak = not self._auto_speak
        settings.set("voice", "auto_speak", value=self._auto_speak)
        if self._auto_speak:
            bus.subscribe("ai.response", self._on_ai_response)
        else:
            bus.unsubscribe("ai.response", self._on_ai_response)
        return self._auto_speak

    def _on_ai_response(self, text: str) -> None:
        if len(text) > 5 and not text.startswith(("✅", "❌", "⚙️", "⛔", "💡", "⚠️")):
            self.tts.speak(text)

    def _on_transcribed(self, text: str) -> None:
        from ai.ai_engine import ai_engine
        ai_engine.process(text)


# ── Helpers ───────────────────────────────────────────────────────────────────

def shutil_which(cmd: str) -> Optional[str]:
    """shutil.which compatível com Python 3.7+."""
    import shutil
    return shutil.which(cmd)


# Instância global
voice_manager = VoiceManager()
