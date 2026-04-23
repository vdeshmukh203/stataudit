import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

def test_import():
    import stataudit as sa
    assert hasattr(sa, 'AuditReport')

def test_finding():
    import stataudit as sa
    assert hasattr(sa, 'Finding')

def test_audit_text():
    import stataudit as sa
    assert callable(sa.audit_text)

def test_audit_text_empty():
    import stataudit as sa
    r = sa.audit_text('')
    assert r is not None
