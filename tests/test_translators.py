# -*- coding: utf-8 -*-
"""Tests for translation engines (Google, Bing, Mock AI, Batching)."""

from unittest.mock import MagicMock, patch
from src.core.translators.base import TranslationEngine, TranslationResult
from src.core.translators.services import PseudoTranslator
from src.core.translators.manager import TranslationManager


def test_pseudo_translator_batch():
    translator = PseudoTranslator()
    texts = ["Game Over", "Start Adventure", "Exit Game"]
    results = translator.translate_batch(texts, target_lang="tr")
    assert len(results) == 3
    assert all(r.success for r in results)
    assert "[TR~" in results[0].translated_text


def test_translation_manager_batch_and_cache(tmp_path):
    from src.core.cache import TranslationCache
    fresh_cache = TranslationCache(db_path=tmp_path / "test_cache.db")
    tm = TranslationManager(cache=fresh_cache)
    with patch.object(tm, "get_translator") as mock_get:
        mock_tr = MagicMock()
        mock_tr.translate_batch.return_value = [
            TranslationResult(
                original_text="Save",
                translated_text="Kaydet",
                source_lang="auto",
                target_lang="tr",
                engine=TranslationEngine.GOOGLE,
                success=True,
            )
        ]
        mock_get.return_value = mock_tr

        # 1. Translate via engine
        results1 = tm.translate_batch(["Save"], target_lang="tr")
        assert results1[0].translated_text == "Kaydet"
        assert mock_tr.translate_batch.call_count == 1

        # 2. Second translate should hit cache
        results2 = tm.translate_batch(["Save"], target_lang="tr")
        assert results2[0].translated_text == "Kaydet"
        assert results2[0].metadata.get("from_cache") is True
        # Engine should NOT be called again
        assert mock_tr.translate_batch.call_count == 1
