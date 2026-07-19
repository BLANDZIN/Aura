"""
angela/communication.py
Canal AURA ↔ Angela.

Não há chamada direta. Toda troca acontece por eventos publicados no
`core.event_bus`, seguindo estritamente estes tópicos:

    aura.needs_angela        AURA pede investigação (autoengenharia ou usuário)
    angela.request           Usuário pediu direto pelo painel da Angela
    angela.acknowledged      Angela recebeu e vai investigar
    angela.step              Progresso do workflow (uma por etapa)
    angela.report            Relatório final (InvestigationReport)
    angela.failed            Investigação abortou por erro
    aura.speak_for_angela    AURA fala em nome da Angela ao usuário

Este módulo isola os nomes dos tópicos para nunca haver typo silencioso.
"""


class Topics:
    NEEDS_ANGELA        = "aura.needs_angela"
    REQUEST             = "angela.request"
    ACKNOWLEDGED        = "angela.acknowledged"
    STEP                = "angela.step"
    REPORT              = "angela.report"
    FAILED              = "angela.failed"
    AURA_SPEAKS         = "aura.speak_for_angela"


TOPIC_HELP = {
    Topics.NEEDS_ANGELA: "AURA solicita análise da Angela",
    Topics.REQUEST:      "Usuário fala diretamente com Angela",
    Topics.ACKNOWLEDGED: "Angela confirmou recebimento",
    Topics.STEP:         "Progresso do workflow obrigatório",
    Topics.REPORT:       "InvestigationReport finalizado",
    Topics.FAILED:       "Investigação abortada",
    Topics.AURA_SPEAKS:  "AURA repassa síntese ao usuário",
}
