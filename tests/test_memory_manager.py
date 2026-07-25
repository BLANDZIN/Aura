"""
tests/test_memory_manager.py
=============================
Testes para memory/memory_manager.py (V11).
"""
import pytest


class TestClassifyImportance:
    """Testes do classificador de importancia."""

    def test_critical_name_importance(self):
        from memory.memory_manager import classify_importance
        assert classify_importance("meu nome e Joao") == 10

    def test_critical_dream_importance(self):
        from memory.memory_manager import classify_importance
        assert classify_importance("quero passar na EsPCEx esse ano") >= 9

    def test_hobby_importance(self):
        from memory.memory_manager import classify_importance
        assert classify_importance("eu gosto de jogar xadrez") >= 7

    def test_trivial_importance(self):
        from memory.memory_manager import classify_importance
        assert classify_importance("abri o Chrome") <= 3

    def test_meal_importance_low(self):
        from memory.memory_manager import classify_importance
        assert classify_importance("hoje almocEi arroz") <= 3

    def test_default_importance(self):
        from memory.memory_manager import classify_importance
        score = classify_importance("texto qualquer sem regra")
        assert score == 5


class TestShortTermMemory:
    """Testes da memoria de curto prazo."""

    def test_add_and_get(self):
        from memory.memory_manager import ShortTermMemory
        m = ShortTermMemory()
        m.add("user", "ola")
        m.add("assistant", "oi")
        msgs = m.get_messages()
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"

    def test_limit_enforced(self):
        from memory.memory_manager import ShortTermMemory
        m = ShortTermMemory()
        m._limit = 5
        for i in range(10):
            m.add("user", f"msg{i}")
        assert len(m.get_messages()) <= 5

    def test_clear(self):
        from memory.memory_manager import ShortTermMemory
        m = ShortTermMemory()
        m.add("user", "teste")
        m.clear()
        assert m.count() == 0


class TestMemoryManager:
    """Testes do gerenciador unificado."""

    def test_memory_stats(self):
        from memory.memory_manager import memory
        stats = memory.memory_stats()
        assert "short_term" in stats
        assert "permanent" in stats
        assert "procedural" in stats

    def test_build_relevant_context(self):
        from memory.memory_manager import memory
        ctx = memory.build_relevant_context()
        assert isinstance(ctx, str)
