# -*- coding: utf-8 -*-
"""Unit tests for TranslationCache and GlossaryManager."""

from pathlib import Path
from src.core.cache import TranslationCache
from src.core.glossary import GlossaryManager


def test_cache_set_and_get(tmp_path: Path):
    db_file = tmp_path / "test_cache.db"
    cache = TranslationCache(db_path=db_file)

    assert cache.count() == 0
    cache.set("Attack", "Saldırı", "en", "tr", "google")
    assert cache.count() == 1

    hit = cache.get("Attack", "en", "tr", "google")
    assert hit == "Saldırı"

    miss = cache.get("Defend", "en", "tr", "google")
    assert miss is None

    cache.clear()
    assert cache.count() == 0


def test_glossary_protection(tmp_path: Path):
    glossary_file = tmp_path / "glossary.json"
    glossary = GlossaryManager(glossary_path=glossary_file)

    glossary.add_term("Potion", "İksir")
    glossary.add_term("Gold", "Altın")

    text = "You found a Potion and 50 Gold!"
    result = glossary.apply(text)

    assert result == "You found a İksir and 50 Altın!"

    glossary.remove_term("Potion")
    result2 = glossary.apply(text)
    assert result2 == "You found a Potion and 50 Altın!"


def test_cache_batch_roundtrip_beyond_sql_parameter_limit(tmp_path: Path) -> None:
    cache = TranslationCache(db_path=tmp_path / "batch.db")
    pairs = {f"line {i}": f"satır {i}" for i in range(2500)}
    cache.set_many(pairs, "en", "tr", "google")
    assert cache.count() == 2500

    found = cache.get_many([*pairs, "missing"], "en", "tr", "google")
    assert found == pairs
    assert cache.get_many(pairs, "en", "de", "google") == {}  # keyed by language pair


def test_cache_releases_database_file(tmp_path: Path) -> None:
    db_file = tmp_path / "locked.db"
    cache = TranslationCache(db_path=db_file)
    cache.set("Attack", "Saldırı", "en", "tr", "google")
    db_file.unlink()  # fails on Windows if a connection were left open


def test_glossary_single_pass_literal_replacement(tmp_path: Path) -> None:
    glossary = GlossaryManager(glossary_path=tmp_path / "g.json")
    glossary.add_term("Potion", "Health Potion")  # replacement contains another term
    glossary.add_term("Health Potion", "Can İksiri")
    glossary.add_term("Path", r"C:\Yol\d")  # backslashes are literal text, not regex escapes
    assert glossary.apply("Potion and health potion") == "Health Potion and Can İksiri"
    assert glossary.apply("Path") == r"C:\Yol\d"


class _ProtectingEngine:
    """Behaves like the real engines: protects tokens, translates the rest, restores."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    def translate_batch(self, texts: list[str], sl: str, tl: str) -> list:
        from src.core.syntax_guard import UnitySyntaxGuard
        from src.core.translators.base import TranslationEngine, TranslationResult

        results = []
        for text in texts:
            protected, tags = UnitySyntaxGuard.protect(text)
            self.sent.append(protected)
            translated = protected.replace("Drink a", "Şunu iç:").replace("Health Potion", "Sağlık İksiri")
            results.append(TranslationResult(text, UnitySyntaxGuard.restore(translated, tags), sl, tl,
                                             TranslationEngine.GOOGLE, True))
        return results

    def close(self) -> None:
        pass


def _glossary_manager(tmp_path: Path):  # type: ignore[no-untyped-def]
    from src.core.translators.base import TranslationEngine
    from src.core.translators.manager import TranslationManager
    from src.utils.config import ConfigManager

    glossary = GlossaryManager(glossary_path=tmp_path / "g.json")
    glossary.add_term("Health Potion", "Can İksiri")
    cache = TranslationCache(db_path=tmp_path / "c.db")
    manager = TranslationManager(config=ConfigManager(tmp_path / "c.json"), cache=cache, glossary=glossary)
    engine = _ProtectingEngine()
    manager._translators[TranslationEngine.GOOGLE] = engine  # type: ignore[assignment]
    return manager, engine, cache


def test_glossary_terms_are_hidden_from_engines_and_enforced(tmp_path: Path) -> None:
    from src.core.syntax_guard import UnitySyntaxGuard, set_protected_terms

    manager, engine, _ = _glossary_manager(tmp_path)
    try:
        result = manager.translate_batch(["Drink a Health Potion"], "en", "tr")[0]
        assert "Health Potion" not in engine.sent[0]  # the engine never saw the term
        assert result.translated_text == "Şunu iç: Can İksiri"
        ok, _ = UnitySyntaxGuard.validate_integrity("Drink a Health Potion", result.translated_text)
        assert ok  # the substitution is not mistaken for a dropped token
    finally:
        set_protected_terms([])


def test_stale_cache_entry_is_retranslated_but_manual_fix_is_kept(tmp_path: Path) -> None:
    from src.core.syntax_guard import set_protected_terms

    manager, engine, cache = _glossary_manager(tmp_path)
    try:
        cache.set("Drink a Health Potion", "Bir Sağlık İksiri iç", "en", "tr", "google")  # cached before the term existed
        cache.set("Health Potion sold out", "Can İksiri tükendi", "en", "tr", "google")  # manual review fix
        stale, manual = manager.translate_batch(["Drink a Health Potion", "Health Potion sold out"], "en", "tr")
        assert stale.translated_text == "Şunu iç: Can İksiri" and not stale.metadata.get("from_cache")
        assert manual.translated_text == "Can İksiri tükendi" and manual.metadata.get("from_cache")
        assert len(engine.sent) == 1
    finally:
        set_protected_terms([])
