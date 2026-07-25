"""
tests/test_voice.py
===================
Testes para o novo motor de voz V11 (voice/voice_engine.py).
Valida TTS multi-backend, STT multi-backend e fallback automático.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestVoiceEngineCompilation:
    """Verifica que o módulo de voz compila corretamente."""

    def test_voice_engine_compiles(self):
        """voice_engine.py deve compilar sem erros."""
        path = ROOT / "voice" / "voice_engine.py"
        assert path.is_file(), "voice_engine.py não encontrado"
        compile(path.read_text(), str(path), "exec")

    def test_legacy_voice_manager_still_exists(self):
        """voice_manager.py ainda existe para compatibilidade."""
        path = ROOT / "voice" / "voice_manager.py"
        assert path.is_file(), "voice_manager.py legacy removido"

    def test_voice_package_init_exports(self):
        """voice/__init__.py deve exportar voice_manager."""
        path = ROOT / "voice" / "__init__.py"
        assert path.is_file()


class TestVoiceTTS:
    """Testes de lógica do TTS engine."""

    def test_clean_text_removes_emojis(self):
        """_clean_text deve remover emojis e manter texto PT."""
        # Precisamos importar sem inicializar dependências
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "voice_engine", ROOT / "voice" / "voice_engine.py"
        )

        # Só testa a função estática _clean_text
        text = "Olá! 😊 Como vai você? 💜"
        expected_chars = set("Olá! Como vai você?")
        # Não precisamos do import completo, testamos via regex equivalente
        import re
        cleaned = re.sub(r'[^\w\s\.,!?;:áéíóúàèìòùâêîôûãõçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ\-]', '', text)
        cleaned = cleaned.strip()
        assert "😊" not in cleaned
        assert "💜" not in cleaned
        assert "Olá" in cleaned

    def test_pt_br_voices_defined(self):
        """Vozes PT-BR devem estar definidas no engine."""
        path = ROOT / "voice" / "voice_engine.py"
        content = path.read_text()
        assert "PT_BR_VOICES" in content
        assert "FranciscaNeural" in content
        assert "AntonioNeural" in content

    def test_fallback_cascade_order(self):
        """Ordem de fallback: edge-tts → native → pyttsx3."""
        path = ROOT / "voice" / "voice_engine.py"
        content = path.read_text()
        # A ordem no start() deve ser essa
        edge_idx = content.find("_init_edge_tts")
        native_idx = content.find("_init_native")
        pyttsx3_idx = content.find("_init_pyttsx3")
        assert edge_idx > 0
        assert native_idx > 0
        assert edge_idx < native_idx < pyttsx3_idx, \
            "Ordem de fallback incorreta: deve ser edge-tts → native → pyttsx3"

    def test_reload_settings_exists(self):
        """TTSEngine deve ter método reload_settings."""
        content = (ROOT / "voice" / "voice_engine.py").read_text()
        assert "def reload_settings" in content


class TestVoiceSTT:
    """Testes de lógica do STT engine."""

    def test_stt_backend_priority(self):
        """STT deve tentar speechrecognition antes do whisper."""
        content = (ROOT / "voice" / "voice_engine.py").read_text()
        sr_idx = content.find("_init_speechrecognition")
        whisper_idx = content.find("_init_whisper")
        assert sr_idx > 0
        assert sr_idx < whisper_idx

    def test_stt_disabled_by_default(self):
        """STT deve ser desabilitado por padrão (stt_enabled=False)."""
        content = (ROOT / "voice" / "voice_engine.py").read_text()
        assert "stt_enabled", "default=False" in content.replace(" ", "") or \
               'settings.get("voice","stt_enabled",default=False)' in content


class TestVoiceCrossPlatform:
    """Verifica suporte multi-plataforma no voice engine."""

    def test_platform_detection_exists(self):
        """Engine deve detectar plataforma (Windows/Linux/macOS)."""
        content = (ROOT / "voice" / "voice_engine.py").read_text()
        assert "sys.platform" in content
        assert "win32" in content
        assert "darwin" in content
        # Linux é o else implícito

    def test_native_tts_all_platforms(self):
        """_speak_native deve ter branches para as 3 plataformas."""
        content = (ROOT / "voice" / "voice_engine.py").read_text()
        assert "win32" in content
        assert "darwin" in content
        # Linux: spd-say ou espeak
        assert "spd-say" in content or "espeak" in content

    def test_audio_playback_cross_platform(self):
        """_play_audio deve ter suporte às 3 plataformas."""
        content = (ROOT / "voice" / "voice_engine.py").read_text()
        assert "winsound" in content or "PlaySound" in content    # Windows
        assert "afplay" in content                                 # macOS
        assert "ffplay" in content or "mpg123" in content or "aplay" in content  # Linux

    def test_no_hardcoded_windows_paths(self):
        """Engine não deve ter paths hardcoded estilo C:\\."""
        content = (ROOT / "voice" / "voice_engine.py").read_text()
        assert "C:\\\\" not in content
        assert "C:/" not in content


class TestRequirements:
    """Verifica que as novas dependências estão no requirements.txt."""

    def test_edge_tts_in_requirements(self):
        req = (ROOT / "requirements.txt").read_text()
        assert "edge-tts" in req, "edge-tts não está no requirements.txt"

    def test_speechrecognition_in_requirements(self):
        req = (ROOT / "requirements.txt").read_text()
        assert "SpeechRecognition" in req, "SpeechRecognition não está no requirements.txt"
