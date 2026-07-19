"""angela/platforms/__init__.py"""
from angela.platforms.base import EngineeringPlatform, CommandResult, FileEntry
from angela.platforms.local_stub import LocalStubPlatform
from angela.platforms.openclaude import OpenClaudePlatform


def default_platform(project_root: str) -> EngineeringPlatform:
    """
    Escolhe automaticamente a melhor plataforma disponível.
    Prioridade: OpenClaude → LocalStub.
    """
    oc = OpenClaudePlatform(project_root)
    return oc if oc.is_available() else LocalStubPlatform(project_root)


__all__ = [
    "EngineeringPlatform", "CommandResult", "FileEntry",
    "LocalStubPlatform", "OpenClaudePlatform", "default_platform",
]
