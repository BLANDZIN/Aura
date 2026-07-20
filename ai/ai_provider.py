"""
ai/ai_provider.py
Camada de abstração para provedores de IA.
Suporta: Ollama, LM Studio.
Permite troca de provider/modelo sem alterar o restante do sistema.
"""

import json
import time
import requests
from typing import List, Dict, Generator
from abc import ABC, abstractmethod
from config.settings import settings
from core.logger import setup_logger
from core.metrics import timed

logger = setup_logger("ai_provider")

_TIMEOUT_CONNECT = 10    # segundos para estabelecer conexão
_TIMEOUT_READ    = 300   # segundos para ler resposta completa

class AIProvider(ABC):
    """Interface base para todos os provedores de IA."""

    @abstractmethod
    def chat(self, messages: List[Dict], stream: bool = False) -> str:
        """Envia mensagens e retorna resposta."""
        ...

    @abstractmethod
    def chat_stream(self, messages: List[Dict]) -> Generator[str, None, None]:
        """Envia mensagens e retorna resposta em stream."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Verifica se o provider está acessível."""
        ...


# ─────────────────────────────────────────────
# Ollama Provider
# ─────────────────────────────────────────────

class OllamaProvider(AIProvider):
    """
    Provider para Ollama (http://localhost:11434).
    Documentação: https://github.com/ollama/ollama/blob/main/docs/api.md

    settings_namespace permite reaproveitar esta mesma classe com uma
    configuração independente — ex.: a Angela usa OllamaProvider(
    settings_namespace="angela") para ter seu próprio modelo/URL/
    temperatura em config/settings.json, sem tocar no namespace "ai" da
    AURA e sem compartilhar nada além do binário local do Ollama.
    """

    def __init__(self, settings_namespace: str = "ai"):
        ns = settings_namespace
        self.base_url = settings.get(ns, "base_url", default="http://localhost:11434")
        self.model = settings.get(ns, "model", default="qwen2.5:3b")
        self.temperature = settings.get(ns, "temperature", default=0.7)
        self.max_tokens = settings.get(ns, "max_tokens", default=2048)
        # keep_alive=-1: mantém modelo carregado em RAM permanentemente.
        # Evita o custo de reload (~3-8s) a cada chamada. Em máquinas
        # com pouca RAM, configure OLLAMA_KEEP_ALIVE=5m no servidor.
        self.keep_alive = settings.get(ns, "keep_alive", default=-1)

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    @timed("model", name_fn=lambda self: self.model)
    def chat(self, messages: List[Dict], stream: bool = False) -> str:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }
        try:
            r = requests.post(url, json=payload, timeout=(_TIMEOUT_CONNECT, _TIMEOUT_READ))
            r.raise_for_status()
            data = r.json()
            return data["message"]["content"]
        except requests.exceptions.ConnectionError:
            logger.error("Ollama não está rodando. Inicie com: ollama serve")
            return '{"erro": "Ollama não está disponível. Verifique se está rodando."}'
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status is not None and status >= 500:
                # Erro 5xx do próprio Ollama (não da nossa requisição) quase
                # sempre é falha ao CARREGAR o modelo: RAM/VRAM insuficiente,
                # versão do Ollama desatualizada para esse modelo, ou blob
                # corrompido — não é um bug de payload. Diagnóstico direto
                # em vez de só devolver a exceção crua.
                logger.error(f"Ollama respondeu {status} ao carregar '{self.model}': {e}")
                return (
                    f'{{"erro": "Ollama respondeu {status} ao tentar usar o modelo '
                    f'\'{self.model}\'. Isso costuma ser falha ao carregar o modelo '
                    f'(RAM/VRAM insuficiente, Ollama desatualizado ou modelo '
                    f'corrompido) — não é um problema na integração. Rode '
                    f'\\"ollama run {self.model}\\" direto no terminal para ver o erro '
                    f'real, e confira \\"ollama list\\"."}}'
                )
            logger.error(f"Erro HTTP do Ollama: {e}")
            return f'{{"erro": "Erro na comunicação com IA: {str(e)}"}}'
        except Exception as e:
            logger.error(f"Erro na requisição Ollama: {e}")
            return f'{{"erro": "Erro na comunicação com IA: {str(e)}"}}'

    def chat_stream(self, messages: List[Dict]) -> Generator[str, None, None]:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }
        try:
            with requests.post(url, json=payload, stream=True, timeout=(_TIMEOUT_CONNECT, _TIMEOUT_READ)) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]
                        if data.get("done"):
                            break
        except requests.exceptions.ConnectionError:
            yield "[Erro: Ollama não disponível]"
        except Exception as e:
            yield f"[Erro: {e}]"


# ─────────────────────────────────────────────
# LM Studio Provider
# ─────────────────────────────────────────────

class LMStudioProvider(AIProvider):
    """
    Provider para LM Studio (API compatível com OpenAI).
    Porta padrão: 1234.

    ATENÇÃO: LM Studio usa porta diferente do Ollama (1234 vs 11434).
    A base_url em settings.json é usada pelo Ollama. Para o LMStudio,
    configure "lmstudio_url" separado, ou use o default abaixo.
    """

    LMSTUDIO_DEFAULT_URL = "http://localhost:1234"

    def __init__(self):
        # LMStudio tem sua própria URL — não usa a mesma chave do Ollama
        self.base_url = settings.get("ai", "lmstudio_url", default=self.LMSTUDIO_DEFAULT_URL)
        self.model = settings.get("ai", "model", default="local-model")
        self.temperature = settings.get("ai", "temperature", default=0.7)
        self.max_tokens = settings.get("ai", "max_tokens", default=2048)

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/v1/models", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    @timed("model", name_fn=lambda self: self.model)
    def chat(self, messages: List[Dict], stream: bool = False) -> str:
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        try:
            r = requests.post(url, json=payload, timeout=(_TIMEOUT_CONNECT, _TIMEOUT_READ))
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.ConnectionError:
            logger.error("LM Studio não está rodando.")
            return '{"erro": "LM Studio não está disponível."}'
        except Exception as e:
            logger.error(f"Erro na requisição LM Studio: {e}")
            return f'{{"erro": "{str(e)}"}}'

    def chat_stream(self, messages: List[Dict]) -> Generator[str, None, None]:
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
        }
        try:
            with requests.post(url, json=payload, stream=True, timeout=(_TIMEOUT_CONNECT, _TIMEOUT_READ)) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line and line.startswith(b"data: "):
                        data_str = line[6:].decode("utf-8")
                        if data_str == "[DONE]":
                            break
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]
        except Exception as e:
            yield f"[Erro: {e}]"


# ─────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────

def get_provider() -> AIProvider:
    """Retorna o provider configurado nas settings."""
    provider_name = settings.get("ai", "provider", default="ollama")
    providers = {
        "ollama": OllamaProvider,
        "lmstudio": LMStudioProvider,
    }
    cls = providers.get(provider_name, OllamaProvider)
    return cls()
