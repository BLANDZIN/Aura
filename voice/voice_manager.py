"""
voice/voice_manager.py — AURA v3.1
TTS (texto → fala) e STT (fala → texto) offline.

TTS: pyttsx3 (sem internet, funciona no Windows imediato)
STT: faster-whisper via microfone (requer: pip install faster-whisper sounddevice)

Design: não trava a UI — tudo em threads daemon.
A UI conecta ao EventBus:
  Publica: voice.speaking_start, voice.speaking_end, voice.transcribed, voice.error
  Escuta:  ai.response (para falar automaticamente)
"""

import threading
import queue
import time
from typing import Optional
from core.event_bus import bus
from config.settings import settings
from core.logger import setup_logger

logger = setup_logger("voice")


class TTSEngine:
    """
    Text-to-Speech offline via pyttsx3.
    Fala em thread separada para não travar a UI.
    """

    def __init__(self):
        self._engine   = None
        self._queue:   queue.Queue = queue.Queue()
        self._running  = False
        self._thread:  Optional[threading.Thread] = None
        self._enabled  = settings.get("voice","tts_enabled", default=True)
        self._rate     = settings.get("voice","voice_rate",  default=170)
        self._volume   = settings.get("voice","voice_volume",default=0.9)

    def start(self) -> bool:
        """Inicializa pyttsx3 e começa thread de fala."""
        if not self._enabled:
            return False
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate",   self._rate)
            self._engine.setProperty("volume", self._volume)

            # Configura voz em português se disponível
            voices = self._engine.getProperty("voices")
            for v in voices:
                if "pt" in v.id.lower() or "brazil" in v.name.lower() or "portuguesa" in v.name.lower():
                    self._engine.setProperty("voice", v.id)
                    logger.info(f"Voz PT selecionada: {v.name}")
                    break

            self._running = True
            self._thread  = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
            logger.info("TTS iniciado (pyttsx3)")
            return True
        except ImportError:
            logger.warning("pyttsx3 não instalado — TTS desabilitado. Execute: pip install pyttsx3")
            return False
        except Exception as e:
            logger.error(f"Erro ao iniciar TTS: {e}")
            return False

    def speak(self, text: str) -> None:
        """Adiciona texto à fila de fala (não-bloqueante)."""
        if not self._running or not self._engine:
            return
        # Remove emojis e caracteres especiais que confundem o TTS
        import re
        clean = re.sub(r'[^\w\s\.,!?;:áéíóúàèìòùâêîôûãõç\-]', '', text)
        clean = clean.strip()
        if clean:
            self._queue.put(clean)

    def stop(self) -> None:
        self._running = False
        with self._queue.mutex:
            self._queue.queue.clear()

    def _loop(self) -> None:
        while self._running:
            try:
                text = self._queue.get(timeout=0.5)
                bus.publish("voice.speaking_start", text=text)
                self._engine.say(text)
                self._engine.runAndWait()
                bus.publish("voice.speaking_end")
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Erro TTS: {e}")


class STTEngine:
    """
    Speech-to-Text via faster-whisper + sounddevice.
    Grava do microfone quando ativado e transcreve.
    """

    def __init__(self):
        self._model    = None
        self._enabled  = settings.get("voice","stt_enabled", default=False)
        self._model_sz = settings.get("voice","stt_model",   default="tiny")
        self._lang     = settings.get("voice","language",    default="pt")
        self._recording = False
        self._available = False

    def init(self) -> bool:
        """Carrega o modelo Whisper (pode demorar na primeira vez)."""
        if not self._enabled:
            return False
        try:
            from faster_whisper import WhisperModel
            logger.info(f"Carregando Whisper '{self._model_sz}'...")
            self._model    = WhisperModel(self._model_sz, device="cpu", compute_type="int8")
            self._available = True
            logger.info("STT iniciado (faster-whisper)")
            return True
        except ImportError:
            logger.warning("faster-whisper não instalado — STT desabilitado.\nExecute: pip install faster-whisper sounddevice")
            return False
        except Exception as e:
            logger.error(f"Erro ao carregar Whisper: {e}")
            return False

    def listen_once(self, duration: float = 5.0) -> Optional[str]:
        """
        Grava N segundos do microfone e retorna transcrição.
        Chamado quando usuário pressiona o botão de microfone.
        """
        if not self._available or not self._model:
            bus.publish("voice.error", mensagem="STT não disponível. Instale faster-whisper.")
            return None

        def _record_and_transcribe():
            try:
                import sounddevice as sd
                import numpy as np
                import tempfile, wave

                logger.info(f"Gravando {duration}s...")
                bus.publish("voice.listening", status=True)

                sample_rate = 16000
                recording   = sd.rec(
                    int(duration * sample_rate),
                    samplerate=sample_rate,
                    channels=1,
                    dtype="float32"
                )
                sd.wait()
                bus.publish("voice.listening", status=False)

                # Salva em WAV temporário
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp_path = tmp.name
                with wave.open(tmp_path, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes((recording * 32767).astype(np.int16).tobytes())

                # Transcreve
                segments, _ = self._model.transcribe(tmp_path, language=self._lang)
                text = " ".join(seg.text for seg in segments).strip()

                import os; os.unlink(tmp_path)

                if text:
                    logger.info(f"Transcrito: '{text}'")
                    bus.publish("voice.transcribed", text=text)
                else:
                    bus.publish("voice.error", mensagem="Nada detectado. Tente falar mais alto.")

            except Exception as e:
                logger.error(f"Erro STT: {e}")
                bus.publish("voice.listening", status=False)
                bus.publish("voice.error", mensagem=f"Erro no microfone: {e}")

        threading.Thread(target=_record_and_transcribe, daemon=True).start()


class VoiceManager:
    """
    Fachada unificada para TTS e STT.
    Conecta automaticamente ao EventBus para falar as respostas da IA.
    """

    def __init__(self):
        self.tts = TTSEngine()
        self.stt = STTEngine()
        self._auto_speak = settings.get("voice","auto_speak", default=False)

    def start(self) -> None:
        """Inicializa TTS e conecta ao EventBus."""
        tts_ok = self.tts.start()
        stt_ok = self.stt.init()

        if tts_ok and self._auto_speak:
            # Fala automaticamente as respostas da IA
            bus.subscribe("ai.response", self._on_ai_response)
            logger.info("Fala automática ativada")

        # Transcrição → envia para IA automaticamente
        bus.subscribe("voice.transcribed", self._on_transcribed)

        logger.info(f"VoiceManager: TTS={'OK' if tts_ok else 'OFF'} | STT={'OK' if stt_ok else 'OFF'}")

    def speak(self, text: str) -> None:
        """Fala um texto manualmente."""
        self.tts.speak(text)

    def listen(self, duration: float = 5.0) -> None:
        """Inicia gravação do microfone."""
        self.stt.listen_once(duration)

    def toggle_auto_speak(self) -> bool:
        """Liga/desliga fala automática das respostas."""
        self._auto_speak = not self._auto_speak
        settings.set("voice","auto_speak", value=self._auto_speak)
        if self._auto_speak:
            bus.subscribe("ai.response", self._on_ai_response)
        else:
            bus.unsubscribe("ai.response", self._on_ai_response)
        return self._auto_speak

    def _on_ai_response(self, text: str) -> None:
        """Fala resposta da IA automaticamente."""
        # Não fala mensagens de sistema curtas como "✅ Concluído"
        if len(text) > 5 and not text.startswith(("✅","❌","⚙️","⛔","💡","⚠️")):
            self.tts.speak(text)

    def _on_transcribed(self, text: str) -> None:
        """Envia transcrição para o motor de IA."""
        from ai.ai_engine import ai_engine
        ai_engine.process(text)

    def stop(self) -> None:
        self.tts.stop()


# Instância global
voice_manager = VoiceManager()
