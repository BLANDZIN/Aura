"""
platforms/platform_manager.py

Detecta o sistema operacional e expõe a implementação correta de
BasePlatform. Todo o resto do código usa platform_manager — nunca
importa WindowsPlatform/LinuxPlatform diretamente nem checa os.name.

Preparo consciente para controle remoto futuro (não implementado agora,
só a forma): platform_manager é o único ponto de decisão "qual SO
executa isso" — se um dia isso precisar virar "qual MÁQUINA executa
isso" (AURA no Linux controlando um Windows Agent pela rede), a troca
é encapsulada aqui, sem tocar em tools/resolvers.py nem nas ferramentas.
"""
import platform as _stdlib_platform

from platforms.base_platform import BasePlatform
from platforms.linux_platform import LinuxPlatform
from platforms.windows_platform import WindowsPlatform


def _detect() -> BasePlatform:
    system = _stdlib_platform.system()
    if system == "Windows":
        return WindowsPlatform()
    if system == "Linux":
        return LinuxPlatform()
    # macOS e outros: sem implementação dedicada ainda. LinuxPlatform é
    # o fallback menos errado (xdg-open não existe no mac, mas 'open' é
    # próximo o suficiente para não deixar isso travado silenciosamente
    # — registra um aviso em vez de fingir que é Linux de verdade).
    from core.logger import setup_logger
    setup_logger("platforms").warning(
        f"SO '{system}' sem implementação dedicada — usando LinuxPlatform "
        f"como fallback (pode não funcionar corretamente)."
    )
    return LinuxPlatform()


platform_manager: BasePlatform = _detect()
