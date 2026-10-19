# -*- coding: utf-8 -*-
"""Offline tests for the Google/Bing engines, router, network settings and parallel runner.

No test touches the network: Google gets a fake transport, Bing a fake session.
"""

from typing import Any

import pytest

from src.core.constants import RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD
from src.core.pipeline.translation_runner import BatchTranslationRunner
from src.core.progress import CancelToken, OperationCancelled
from src.core.translators import google as google_module
from src.core.translators.base import TranslationEngine, TranslationResult
from src.core.translators.bing import BingTranslator
from src.core.translators.google import SEPARATOR, GoogleTranslator, split_long_text
from src.core.translators.google_transport import GoogleTransport, RateLimitedError, TransportError
from src.core.translators.network import NetworkSettings, ProxyPool, parse_proxy_list
from src.core.translators.router import EndpointRouter

FAST = NetworkSettings(request_delay=0.0, max_retries=2)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


class FakeTransport:
    """Scriptable stand-in for GoogleTransport; records which family was used."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.primary_fn = lambda text: text.upper()
        self.batch_fn: Any = lambda texts: [t.upper() for t in texts]
        self.clients5_fn = lambda text: f"c5:{text}"
        self.lingva_fn = lambda text: f"lv:{text}"

    def primary(self, endpoint: str, text: str, sl: str, tl: str) -> str:
        self.calls.append("primary")
        return self.primary_fn(text)

    def batchexecute(self, texts: list[str], sl: str, tl: str) -> list[str] | None:
        self.calls.append("batchexecute")
        return self.batch_fn(texts)

    def clients5(self, text: str, sl: str, tl: str) -> str:
        self.calls.append("clients5")
        return self.clients5_fn(text)

    def lingva(self, text: str, sl: str, tl: str) -> str:
        self.calls.append("lingva")
        return self.lingva_fn(text)

    def close(self) -> None:
        pass


def _google(transport: FakeTransport, settings: NetworkSettings = FAST, clock: FakeClock | None = None) -> GoogleTranslator:
    clock = clock or FakeClock()
    router = EndpointRouter(clock=clock, sleep=clock.sleep)
    return GoogleTranslator(settings, router=router, transport=transport)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: Any) -> None:
    monkeypatch.setattr(google_module.time, "sleep", lambda s: None)
    import src.core.translators.bing as bing_module

    monkeypatch.setattr(bing_module.time, "sleep", lambda s: None)


# --- Google: batch routing ---------------------------------------------------------


def test_separator_path_translates_slice_in_one_post() -> None:
    transport = FakeTransport()
    results = _google(transport).translate_batch(["hello", "world", "Gold: {0}"])
    assert [r.translated_text for r in results] == ["HELLO", "WORLD", "GOLD: {0}"]
    assert transport.calls == ["primary"]


def test_separator_mismatch_falls_back_to_batchexecute() -> None:
    transport = FakeTransport()
    transport.primary_fn = lambda text: "merged without separators"
    results = _google(transport).translate_batch(["a b", "c d"])
    assert transport.calls == ["primary", "batchexecute"]
    assert [r.translated_text for r in results] == ["A B", "C D"]


def test_separator_bleeding_is_rejected() -> None:
    transport = FakeTransport()
    transport.primary_fn = lambda text: text.replace("hi", "x" * 200)
    _google(transport).translate_batch(["hi", "yo"])
    assert "batchexecute" in transport.calls


def test_failed_bulk_paths_fall_back_per_item_and_bench_batchexecute() -> None:
    transport = FakeTransport()
    transport.primary_fn = lambda text: (_ for _ in ()).throw(TransportError("HTTP 500"))
    transport.batch_fn = lambda texts: None
    google = _google(transport)
    results = google.translate_batch(["one", "two"])
    assert [r.translated_text for r in results] == ["c5:one", "c5:two"]
    google.translate_batch(["three", "four"])
    assert transport.calls.count("batchexecute") == 2  # benched after 2 consecutive failures
    assert not google.router.is_family_available(EndpointRouter.FAMILY_BATCHEXECUTE)


def test_integrity_failure_from_bulk_is_retried_individually() -> None:
    transport = FakeTransport()
    transport.primary_fn = lambda text: text.replace("⟦ULPH_0⟧", "") if SEPARATOR in text else text
    results = _google(transport).translate_batch(["Gold: {0}", "Hi"])
    assert results[0].translated_text == "Gold: {0}"
    assert transport.calls.count("primary") == 2


def test_aggressive_retry_gives_unchanged_lines_a_second_opinion() -> None:
    transport = FakeTransport()
    transport.primary_fn = lambda text: text  # primary echoes the source ("unchanged")
    transport.clients5_fn = lambda text: "Merhaba"
    settings = NetworkSettings(request_delay=0.0, max_retries=1, aggressive_retry=True)
    results = _google(transport, settings).translate_batch(["Hello", "World"])
    assert [r.translated_text for r in results] == ["Merhaba", "Merhaba"]
    assert transport.calls[0] == "primary" and transport.calls.count("clients5") == 2

    plain = FakeTransport()
    plain.primary_fn = lambda text: text
    unchanged = _google(plain).translate_batch(["Hello", "World"])  # retry disabled by default
    assert [r.translated_text for r in unchanged] == ["Hello", "World"]


# --- Google: single path & limits ---------------------------------------------------


def test_breaker_skips_primary_after_consecutive_429() -> None:
    transport = FakeTransport()
    transport.primary_fn = lambda text: (_ for _ in ()).throw(RateLimitedError("429"))
    clock = FakeClock()
    google = _google(transport, NetworkSettings(request_delay=0.0, max_retries=RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD), clock)
    result = google.translate("Hello")
    assert result.translated_text == "c5:Hello"
    assert google.router.breaker_tripped and google.router.primary_blocked
    transport.calls.clear()
    google.translate("Again")
    assert transport.calls == ["clients5"]  # primary not even attempted while flagged
    assert clock.slept and max(clock.slept) <= 25.0  # shared cooldown is capped per wait


def test_long_text_is_split_and_get_families_avoided() -> None:
    transport = FakeTransport()
    settings = NetworkSettings(request_delay=0.0, max_chars_per_request=500)
    text = ("word " * 400).strip()
    result = _google(transport, settings).translate(text)
    assert result.translated_text == text.upper()
    assert transport.calls.count("primary") >= 4
    assert "clients5" not in transport.calls


def test_lingva_can_be_disabled() -> None:
    transport = FakeTransport()
    for fn in ("primary_fn", "clients5_fn"):
        setattr(transport, fn, lambda text: (_ for _ in ()).throw(TransportError("down")))
    transport.batch_fn = lambda texts: None
    result = _google(transport, NetworkSettings(request_delay=0.0, max_retries=1, lingva_fallback=False)).translate("Hi")
    assert result.success is False and "lingva" not in transport.calls


@pytest.mark.parametrize("limit", [50, 300, 1000])
def test_split_long_text_roundtrips(limit: int) -> None:
    text = "Line one.\nSecond line, with ⟦ULPH_0⟧ token! " * 30 + "x" * 1200
    parts = split_long_text(text, limit)
    assert "".join(parts) == text and all(len(p) <= limit for p in parts)
    assert all(p.count("⟦") == p.count("⟧") for p in parts)


def test_lingva_url_encodes_slashes(monkeypatch: Any) -> None:
    urls: list[str] = []

    class Resp:
        status_code = 200

        def json(self) -> dict[str, str]:
            return {"translation": "ok"}

    transport = GoogleTransport(FAST)
    monkeypatch.setattr(transport.session, "request", lambda method, url, **kw: urls.append(url) or Resp())
    assert transport.lingva("A/B test", "en", "tr") == "ok"
    assert "A%2FB%20test" in urls[0]


# --- Router & network ---------------------------------------------------------------


def test_router_cooldown_escalates_and_probe_slot_is_single() -> None:
    clock = FakeClock()
    router = EndpointRouter(clock=clock, sleep=clock.sleep)
    assert [router.on_rate_limited() for _ in range(3)] == [3.0, 6.0, 12.0]
    for _ in range(RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD - 3):
        router.on_rate_limited()
    assert router.primary_blocked and router.claim_primary_slot() is False
    clock.now += 10_000
    assert router.claim_primary_slot() is True
    assert router.claim_primary_slot() is False  # only one probe per interval
    router.on_primary_success()
    assert router.breaker_tripped is False


def test_router_benches_failing_mirror() -> None:
    router = EndpointRouter(endpoints=["a", "b"])
    for _ in range(5):
        router.mark_mirror_failure("a")
    assert {router.get_endpoint() for _ in range(20)} == {"b"}


def test_proxy_parsing_pool_and_concurrency() -> None:
    proxies = parse_proxy_list("1.2.3.4:8080, socks5://h:1\n# comment\n1.2.3.4:8080")
    assert proxies == ("http://1.2.3.4:8080", "socks5://h:1")
    pool = ProxyPool(proxies)
    for _ in range(3):
        pool.mark_failed("http://1.2.3.4:8080")
    assert {pool.next() for _ in range(4)} == {"socks5://h:1"}
    assert NetworkSettings(concurrency=16).effective_concurrency(32) == 4
    assert NetworkSettings(concurrency=16, proxies=proxies).effective_concurrency(32) == 16
    assert NetworkSettings(concurrency=16, proxies=proxies).effective_concurrency(3) == 3


# --- Bing ---------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, status: int, data: Any = None, text: str = "") -> None:
        self.status_code = status
        self._data = data
        self.text = text

    def json(self) -> Any:
        return self._data


class FakeBingSession:
    def __init__(self, script: list[Any]) -> None:
        self.script = script
        self.payload_sizes: list[int] = []

    def post(self, url: str, data: bytes, **kwargs: Any) -> FakeResponse:
        import json

        payload = json.loads(data.decode("utf-8"))
        self.payload_sizes.append(len(payload))
        step = self.script.pop(0) if self.script else "ok"
        if step == "ok":
            return FakeResponse(200, [{"translations": [{"text": t.upper()}]} for t in payload])
        return step

    def close(self) -> None:
        pass


def _bing(script: list[Any], fallback: Any = None) -> tuple[BingTranslator, FakeBingSession]:
    bing = BingTranslator(NetworkSettings(request_delay=0.0, max_retries=3))
    session = FakeBingSession(script)
    bing.session = session  # type: ignore[assignment]
    bing.set_fallback(fallback)
    return bing, session


def test_bing_chunks_large_batches() -> None:
    bing, session = _bing([])
    results = bing.translate_batch([f"line {i}" for i in range(150)])
    assert session.payload_sizes == [100, 50]
    assert results[149].translated_text == "LINE 149"


def test_bing_retries_429_then_succeeds() -> None:
    bing, session = _bing([FakeResponse(429, text="slow down"), "ok"])
    assert bing.translate_batch(["hi"])[0].translated_text == "HI"
    assert len(session.payload_sizes) == 2


def test_bing_splits_oversized_requests() -> None:
    too_big = FakeResponse(400, text="The maximum allowed translation size was exceeded")
    bing, session = _bing([too_big, "ok", "ok"])
    results = bing.translate_batch(["a", "b", "c", "d"])
    assert session.payload_sizes == [4, 2, 2]
    assert all(r.success for r in results)


class _Fallback:
    def translate_batch(self, texts: list[str], sl: str, tl: str) -> list[TranslationResult]:
        return [TranslationResult(t, f"g:{t}", sl, tl, TranslationEngine.GOOGLE, True) for t in texts]


def test_bing_shape_mismatch_delegates_to_fallback() -> None:
    wrong_shape = FakeResponse(200, [{"translations": [{"text": "only one"}]}])
    bing, _ = _bing([wrong_shape] * 3, fallback=_Fallback())
    results = bing.translate_batch(["x", "y"])
    assert [r.translated_text for r in results] == ["g:x", "g:y"]
    assert all(r.engine == TranslationEngine.BING for r in results)


def test_bing_non_retryable_error_reports_failure_without_fallback() -> None:
    bing, session = _bing([FakeResponse(403, text="blocked")])
    result = bing.translate_batch(["x"])[0]
    assert result.success is False and "403" in (result.error or "")
    assert len(session.payload_sizes) == 1


# --- Parallel runner ----------------------------------------------------------------


class _ParallelManager:
    def __init__(self, workers: int) -> None:
        self.workers = workers
        self.calls = 0

    def concurrency_for(self, engine: TranslationEngine) -> int:
        return self.workers

    def translate_batch(self, texts: list[str], **_: Any) -> list[TranslationResult]:
        self.calls += 1
        return [TranslationResult(t, t + "!", "en", "tr", TranslationEngine.GOOGLE, True) for t in texts]


def test_parallel_runner_translates_everything() -> None:
    manager = _ParallelManager(workers=4)
    runner = BatchTranslationRunner(manager, batch_size=7)  # type: ignore[arg-type]
    report = runner.run([f"s{i}" for i in range(100)], "tr", TranslationEngine.GOOGLE)
    assert len(report.translations) == 100 and manager.calls == 15


def test_parallel_runner_stops_submitting_after_cancel() -> None:
    token = CancelToken()
    manager = _ParallelManager(workers=2)
    original = manager.translate_batch

    def cancelling(texts: list[str], **kw: Any) -> list[TranslationResult]:
        token.cancel()
        return original(texts, **kw)

    manager.translate_batch = cancelling  # type: ignore[method-assign]
    runner = BatchTranslationRunner(manager, batch_size=5)  # type: ignore[arg-type]
    with pytest.raises(OperationCancelled):
        runner.run([f"s{i}" for i in range(200)], "tr", TranslationEngine.GOOGLE, cancel=token)
    assert manager.calls <= 2


def test_runner_auto_repairs_dropped_placeholder() -> None:
    class Manager:
        def translate_batch(self, texts: list[str], **_: Any) -> list[TranslationResult]:
            return [TranslationResult(t, "Altın: jeton", "en", "tr", TranslationEngine.GOOGLE, True) for t in texts]

    report = BatchTranslationRunner(Manager()).run(["Gold: {0} coins"], "tr", TranslationEngine.GOOGLE)  # type: ignore[arg-type]
    assert report.translations == {"Gold: {0} coins": "Altın: {0} jeton"}
    assert report.repaired == {"Gold: {0} coins"}


def test_manager_concurrency_caps(tmp_path: Any) -> None:
    from src.core.translators.manager import TranslationManager
    from src.utils.config import ConfigManager

    config = ConfigManager(tmp_path / "c.json")
    config.set("max_concurrency", 8, auto_save=False)
    manager = TranslationManager(config=config)
    assert manager.concurrency_for(TranslationEngine.GOOGLE) == 4  # no proxies -> single-IP cap
    assert manager.concurrency_for(TranslationEngine.BING) == 3
    assert manager.concurrency_for(TranslationEngine.LOCAL_LLM) == 1
    config.set("proxy_enabled", True, auto_save=False)
    config.set("proxy_list", "1.1.1.1:80", auto_save=False)
    manager.reset_translators()
    assert manager.concurrency_for(TranslationEngine.GOOGLE) == 8


def test_runner_aborts_when_the_engine_keeps_failing() -> None:
    from src.core.pipeline.translation_runner import MAX_CONSECUTIVE_FAILED_BATCHES, TranslationEngineError

    class OfflineManager:
        calls = 0

        def translate_batch(self, texts: list[str], **_: Any) -> list[TranslationResult]:
            OfflineManager.calls += 1
            return [
                TranslationResult(t, t, "en", "tr", TranslationEngine.GOOGLE, False, error="network unreachable")
                for t in texts
            ]

    runner = BatchTranslationRunner(OfflineManager(), batch_size=10)  # type: ignore[arg-type]
    with pytest.raises(TranslationEngineError, match="network unreachable"):
        runner.run([f"s{i}" for i in range(1000)], "tr", TranslationEngine.GOOGLE)
    assert OfflineManager.calls == MAX_CONSECUTIVE_FAILED_BATCHES  # not 100 batches


def test_runner_keeps_going_while_some_lines_succeed() -> None:
    class FlakyManager:
        def translate_batch(self, texts: list[str], **_: Any) -> list[TranslationResult]:
            return [
                TranslationResult(t, t + "!", "en", "tr", TranslationEngine.GOOGLE, i == 0, error=None if i == 0 else "x")
                for i, t in enumerate(texts)
            ]

    report = BatchTranslationRunner(FlakyManager(), batch_size=5).run(  # type: ignore[arg-type]
        [f"s{i}" for i in range(50)], "tr", TranslationEngine.GOOGLE
    )
    assert len(report.translations) == 10 and report.failed == 40
