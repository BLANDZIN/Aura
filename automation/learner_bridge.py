"""automation/learner_bridge.py — Evita import circular entre tool_manager e automation_learner."""
def report_action(acao: str, parametros: dict) -> None:
    try:
        from automation.automation_learner import automation_learner
        automation_learner.register_action(acao, parametros)
    except Exception:
        pass
