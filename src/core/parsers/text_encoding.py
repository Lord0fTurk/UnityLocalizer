# -*- coding: utf-8 -*-
"""Reads loose game text files in their own encoding and writes them back unchanged.

Games ship ``.json``/``.csv``/``.txt`` files in Shift-JIS, GBK, Big5, EUC-KR, Windows
code pages or UTF-16, not only UTF-8. Decoding those as UTF-8 yields U+FFFD garbage
(which then goes to a paid engine), and writing the patched file back as UTF-8 would
change the file's encoding for a game that reads it with a fixed one.

Detection order: byte-order mark, strict UTF-8, then ``charset-normalizer``. Its answer is
corrected where it is known to be unreliable: single-byte Latin code pages look alike, so
they settle on Windows-1252 unless the source language names another one (Polish, Turkish,
Baltic, ...), and the source language also picks between the CJK and Cyrillic families.
Without a hint, Central European or Turkish files therefore decode as Windows-1252 until the
detected source language is known and the harvest is repeated with it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from charset_normalizer import CharsetMatch, from_bytes

logger = logging.getLogger(__name__)

# (BOM bytes, codec of the body), longest first so UTF-32 LE is not read as UTF-16 LE.
_BOMS: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xef\xbb\xbf", "utf-8"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
)

# Legacy code pages the games of a source language usually use, most likely first.
_HINT_CODECS: dict[str, tuple[str, ...]] = {
    "ja": ("cp932", "euc_jp"),
    "ko": ("cp949", "euc_kr"),
    "zh": ("gb18030", "cp950"),
    "zh-tw": ("cp950", "big5hkscs"),
    "zh-hk": ("cp950", "big5hkscs"),
    "zh-hant": ("cp950", "big5hkscs"),
    "ru": ("cp1251", "koi8_r"),
    "uk": ("cp1251", "koi8_u"),
    "bg": ("cp1251",), "be": ("cp1251",), "sr": ("cp1251",), "mk": ("cp1251",),
    "el": ("cp1253",), "tr": ("cp1254",), "he": ("cp1255",), "ar": ("cp1256",), "fa": ("cp1256",),
    "th": ("cp874",), "vi": ("cp1258",),
    "pl": ("cp1250",), "cs": ("cp1250",), "sk": ("cp1250",), "hu": ("cp1250",),
    "ro": ("cp1250",), "hr": ("cp1250",), "sl": ("cp1250",),
    "lt": ("cp1257",), "lv": ("cp1257",), "et": ("cp1257",),
}

# Single-byte Latin code pages that decode the same bytes without error.
_LATIN_CODECS = frozenset({
    "cp1250", "cp1252", "cp1254", "cp1257", "cp437", "cp775", "cp850", "cp852", "cp858",
    "latin_1", "iso8859_2", "iso8859_4", "iso8859_9", "iso8859_10", "iso8859_13",
    "iso8859_14", "iso8859_15", "iso8859_16", "mac_roman", "mac_latin2", "mac_iceland",
})
_WESTERN_CODEC = "cp1252"
_UNGUESSED_CODECS = frozenset({"utf-8", "utf-16-le", "utf-16-be"})


class UnencodableTextError(ValueError):
    """The text holds characters the file's own encoding cannot represent."""


@dataclass(frozen=True)
class TextEncoding:
    """How a file is encoded: the codec of its body and the byte-order mark to put back."""

    codec: str = "utf-8"
    bom: bytes = b""

    def encode(self, text: str) -> bytes:
        """Bytes of ``text`` in this encoding; raises ``UnencodableTextError`` when it does not fit."""
        try:
            return self.bom + text.encode(self.codec)
        except UnicodeEncodeError as exc:
            raise UnencodableTextError(
                f"{self.codec} cannot represent {text[exc.start:exc.start + 1]!r} (position {exc.start})"
            ) from exc


@dataclass(frozen=True)
class DecodedText:
    """File content as text, with the encoding to write it back in."""

    text: str
    encoding: TextEncoding
    # True when the codec was only the detector's guess (no mark, not UTF-8/UTF-16, not one of the
    # source language's own code pages): short CJK and look-alike single-byte files can be misread.
    guessed: bool = False


def _decode(body: bytes, encoding: TextEncoding) -> DecodedText | None:
    try:
        return DecodedText(body.decode(encoding.codec), encoding)
    except (UnicodeDecodeError, LookupError):
        return None


def _hinted_codecs(language_hint: str) -> tuple[str, ...]:
    """Legacy code pages for a source language ('' when none is known or it uses UTF-8/Latin)."""
    code = language_hint.strip().lower().replace("_", "-")
    if code in _HINT_CODECS:
        return _HINT_CODECS[code]
    return _HINT_CODECS.get(code.split("-")[0], ())


def _best_match(data: bytes, isolation: tuple[str, ...]) -> CharsetMatch | None:
    return from_bytes(data, cp_isolation=list(isolation) if isolation else None).best()


def _settle_latin(match: CharsetMatch, data: bytes) -> str:
    """Windows-1252 for look-alike Latin code pages.

    The detector's language label is no help here (it called Polish "Estonian" and French
    "Czech"), so Central European, Turkish and Baltic files rely on the source language hint.
    """
    codec = match.encoding
    if codec not in _LATIN_CODECS:
        return codec
    try:
        data.decode(_WESTERN_CODEC)
    except UnicodeDecodeError:
        return "latin_1"  # decodes every byte, so patching leaves untouched text byte-for-byte
    return _WESTERN_CODEC


def _utf16_by_zero_bytes(data: bytes) -> str | None:
    """UTF-16 byte order of ASCII-heavy text without a mark: its zero high bytes sit on every second byte."""
    even, odd = data[0::2].count(0), data[1::2].count(0)
    half = max(len(data) // 2, 1)
    if odd >= half * 0.3 and even <= odd * 0.1:
        return "utf-16-le"
    if even >= half * 0.3 and odd <= even * 0.1:
        return "utf-16-be"
    return None


def detect_codec(data: bytes, language_hint: str = "") -> str | None:
    """Codec for BOM-less bytes that are not UTF-8, or None when nothing fits."""
    utf16 = _utf16_by_zero_bytes(data)
    if utf16 is not None:
        return utf16
    hinted = _hinted_codecs(language_hint)
    match = _best_match(data, hinted) if hinted else None
    if match is not None:
        return match.encoding  # restricted to the language's own code pages: trust the order
    match = _best_match(data, ())
    # The detector can give up on the language's own code pages (short text, newer releases); they may still decode it.
    own = next((h for h in hinted if _decode(data, TextEncoding(h)) is not None), None)
    if match is None:
        return own
    codec = _settle_latin(match, data)
    if codec in _LATIN_CODECS and own is not None:
        codec = own
    return "utf-8" if codec == "ascii" else codec


def decode_bytes(data: bytes, language_hint: str = "") -> DecodedText | None:
    """Decode file bytes, remembering the encoding; None when the encoding cannot be determined."""
    for bom, codec in _BOMS:
        if data.startswith(bom):
            return _decode(data[len(bom):], TextEncoding(codec, bom))
    plain = _decode(data, TextEncoding())
    # NUL bytes are valid UTF-8 but never in a text file: that is UTF-16 without a byte-order mark.
    if plain is not None and "\x00" not in plain.text:
        return plain
    codec = detect_codec(data, language_hint)
    decoded = _decode(data, TextEncoding(codec)) if codec else None
    if decoded is None:
        return None
    sure = codec in _UNGUESSED_CODECS or codec in _hinted_codecs(language_hint)
    return DecodedText(decoded.text, decoded.encoding, guessed=not sure)


def decode_file(path: Path | str, language_hint: str = "") -> DecodedText | None:
    """Read a loose text file; None (with a log entry) when it cannot be read or decoded."""
    file_path = Path(path)
    try:
        data = file_path.read_bytes()
    except OSError as exc:
        logger.error("Failed to read %s: %s", file_path, exc)
        return None
    decoded = decode_bytes(data, language_hint)
    if decoded is None:
        logger.warning("Skipped %s: its text encoding could not be determined", file_path.name)
    elif decoded.guessed:
        logger.warning("%s was read as %s, which is only a guess: if its text looks garbled, set the source "
                       "language and scan again", file_path.name, decoded.encoding.codec)
    elif decoded.encoding.codec not in _UNGUESSED_CODECS:
        logger.info("%s is encoded as %s", file_path.name, decoded.encoding.codec)
    return decoded
