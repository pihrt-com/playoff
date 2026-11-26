import importlib.util
from pathlib import Path


path = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "check_release_titles.py"
spec = importlib.util.spec_from_file_location("check_release_titles", path)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def test_release_title_must_be_exact_numeric_tag():
    assert checker.validate({"name": "1.0.43", "tag_name": "1.0.43"}) is None
    assert checker.validate({"name": "Playoff 1.0.43", "tag_name": "1.0.43"})
    assert checker.validate({"name": "1.0.42", "tag_name": "1.0.43"})
    assert checker.validate({"name": "v1.0.43", "tag_name": "v1.0.43"})
    assert checker.validate({"name": "", "tag_name": "1.0.43"})
    assert checker.validate({"name": "Opravy chyb, USB status", "tag_name": "1.0.6"}) is None
    assert checker.validate({"name": "Playoff 1.0.6", "tag_name": "1.0.6"})
