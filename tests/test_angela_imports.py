def test_angela_audit_import_does_not_load_llm_backend():
    from angela.audit import Auditor

    assert Auditor is not None


def test_angela_public_class_is_lazy_imported():
    from angela import Angela

    assert Angela.__name__ == "Angela"

