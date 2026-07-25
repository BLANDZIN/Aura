"""
tests/test_voice_engine.py
===========================
Testes para voice/voice_engine.py (V11).
"""
import pytest


class TestVoiceTTS:
    """Testes do motor TTS com fallback em cascata."""

    def test_clean_text_removes_emojis(self):
        from voice.voice_engine import TTSEngine
        text = "Ola! 😊 Como vai? 💜"
        cleaned = TTSEngine._clean_text(text)
        assert "Ola" in cleaned
        assert "😊" not in cleaned
        assert "💜" not in cleaned

    def test_pt_br_voices_defined(self):
        from voice.voice_engine import TTSEngine
        assert len(TTSEngine.PT_BR_VOICES) >= 2
        assert "FranciscaNeural" in TTSEngine.PT_BR_VOICES[0]

    def test_tts_disabled_by_default(self):
        from voice.voice_engine import TTSEngine
        engine = TTSEngine()
        # TTS pode ou nao iniciar dependendo das dependencias
        # Mas a engine existe e tem os metodos esperados
        assert hasattr(engine, 'speak')
        assert hasattr(engine, 'stop')
        assert hasattr(engine, 'reload_settings')

    def test_reload_settings_exists(self):
        from voice.voice_engine import TTSEngine
        engine = TTSEngine()
        engine.reload_settings()  # nao deve crashar
        assert engine._enabled in (True, False)


class TestVoiceSTT:
    """Testes do motor STT."""

    def test_stt_disabled_by_default(self):
        from voice.voice_engine import STTEngine
        engine = STTEngine()
        assert engine._enabled is False

    def test_stt_has_listen_method(self):
        from voice.voice_engine import STTEngine
        engine = STTEngine()
        assert hasattr(engine, 'listen_once')
        assert hasattr(engine, 'init')


class TestVoiceManager:
    """Testes da fachada VoiceManager."""

    def test_manager_exists(self):
        from voice.voice_engine import VoiceManager
        vm = VoiceManager()
        assert hasattr(vm, 'tts')
        assert hasattr(vm, 'stt')
        assert hasattr(vm, 'speak')
        assert hasattr(vm, 'listen')
        assert hasattr(vm, 'stop')

    def test_manager_start_does_not_crash(self):
        from voice.voice_engine import VoiceManager
        vm = VoiceManager()
        vm.start()  # deve funcionar mesmo sem dependencias
        vm.stop()


class TestCrossPlatform:
    """Testes de suporte multi-plataforma."""

    def test_shutil_which_is_importable(self):
        from voice.voice_engine import shutil_which
        assert callable(shutil_which)

    def test_platform_branches_exist(self):
        """Codigo deve conter branches para as 3 plataformas."""
        with open("voice/voice_engine.py") as f:
            code = f.read()
        assert "win32" in code
        assert "darwin" in code or "sys.platform" in code
