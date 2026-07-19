"""
core/event_bus.py
Barramento de eventos para comunicacao desacoplada entre modulos.

Quando uma aplicacao Qt esta ativa, eventos publicados por threads de
background sao entregues na thread principal para proteger os widgets.
"""

import threading
import time
from typing import Any, Callable, Dict, List, Optional

from core.logger import setup_logger
from core.metrics import metrics

logger = setup_logger("event_bus")

try:
    from PyQt6.QtCore import QObject, QThread, pyqtSignal
    from PyQt6.QtWidgets import QApplication
except Exception:
    QObject = None
    QThread = None
    pyqtSignal = None
    QApplication = None


if QObject is not None:
    class _QtEventDispatcher(QObject):
        dispatch_signal = pyqtSignal(str, object)
else:
    _QtEventDispatcher = None


class EventBus:
    """
    Barramento central de eventos do AURA.

    Uso:
        bus.subscribe("ai.response", minha_funcao)
        bus.publish("ai.response", text="Ola!")
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()
        self._dispatcher: Optional[_QtEventDispatcher] = None

    def _ensure_dispatcher(self) -> None:
        """Cria o dispatcher Qt somente depois que QApplication existir."""
        if self._dispatcher is not None or QApplication is None:
            return

        app = QApplication.instance()
        if app is None:
            return

        self._dispatcher = _QtEventDispatcher()
        self._dispatcher.dispatch_signal.connect(self._dispatch)

    def _should_queue_to_qt(self) -> bool:
        self._ensure_dispatcher()
        if self._dispatcher is None or QThread is None:
            return False
        return QThread.currentThread() != self._dispatcher.thread()

    def subscribe(self, event: str, callback: Callable) -> None:
        """Registra um callback para um evento."""
        self._ensure_dispatcher()
        with self._lock:
            self._subscribers.setdefault(event, []).append(callback)
        logger.debug(f"Subscrito em '{event}': {callback.__name__}")

    def unsubscribe(self, event: str, callback: Callable) -> None:
        """Remove um callback de um evento."""
        with self._lock:
            if event in self._subscribers:
                self._subscribers[event] = [
                    cb for cb in self._subscribers[event] if cb != callback
                ]

    def publish(self, event: str, **kwargs: Any) -> None:
        """Publica um evento e notifica todos os subscribers."""
        with self._lock:
            if event not in self._subscribers:
                return

        logger.debug(f"Publicando evento '{event}' com {kwargs}")

        if self._should_queue_to_qt():
            self._dispatcher.dispatch_signal.emit(event, kwargs)
            return

        self._dispatch(event, kwargs)

    def _dispatch(self, event: str, kwargs: Dict[str, Any]) -> None:
        with self._lock:
            callbacks = list(self._subscribers.get(event, []))

        start = time.perf_counter()
        for callback in callbacks:
            try:
                callback(**kwargs)
            except Exception as e:
                logger.error(f"Erro no subscriber de '{event}': {e}")
        metrics.record("eventbus", event, (time.perf_counter() - start) * 1000)

    def clear(self, event: str = None) -> None:
        """Limpa subscribers de um evento ou todos."""
        with self._lock:
            if event:
                self._subscribers.pop(event, None)
            else:
                self._subscribers.clear()


bus = EventBus()
