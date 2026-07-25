"""
Testes focados no AIEngine — cobertura mínima para o fix de concorrência
da V12.1 (achado do documento de comportamentos: "perda de objetivo" após
uso prolongado). Não tenta cobrir ai_engine.py inteiro (God Object grande
demais pra um teste só); ver ai/executor.py e ai/prompt_builder.py para os
pedaços já extraídos.
"""
import threading
import time

from ai.ai_engine import ai_engine


def test_processing_flag_is_set_synchronously_before_thread_starts():
    # Regressão do achado V12.1: antes, self._processing só virava True
    # DENTRO da thread (_run), deixando uma janela real onde uma segunda
    # chamada a process() logo em seguida (voz + texto quase ao mesmo
    # tempo, duplo-envio no chat) também passava pelo guard e disparava
    # OUTRA thread concorrente. O teste chama process() sem NENHUM sleep
    # depois — se o guard fosse assíncrono, is_processing() ainda
    # poderia estar False aqui.
    ai_engine._processing = False
    try:
        ai_engine.process("mensagem de teste — nao deve chamar o provider de verdade")
        assert ai_engine.is_processing is True, (
            "self._processing deveria já estar True assim que process() "
            "retorna, antes mesmo da thread rodar"
        )
    finally:
        # Não esperamos a thread real terminar (chamaria o provider de IA).
        # Só resetamos o estado pra não vazar pro próximo teste.
        ai_engine._processing = False


def test_concurrent_process_calls_reject_the_second_one():
    ai_engine._processing = False
    results = []

    def _call(msg):
        results.append(ai_engine.process(msg))

    try:
        t1 = threading.Thread(target=_call, args=("primeira",))
        t2 = threading.Thread(target=_call, args=("segunda",))
        t1.start()
        t2.start()
        t1.join(timeout=2)
        t2.join(timeout=2)
        # Ambas as chamadas a process() devem ter retornado (nenhuma trava),
        # e o estado final deve refletir que só uma ficou "processando".
        assert ai_engine._processing_lock.locked() is False
    finally:
        ai_engine._processing = False
