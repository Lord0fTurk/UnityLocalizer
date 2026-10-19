# -*- coding: utf-8 -*-
"""Language catalog and per-engine language code mapping.

Canonical codes follow Google Translate (``tr``, ``zh-CN``, ``pt-BR``, ``ceb``)
and are what the app stores in config, the translation cache, the XUnity
``Language=`` setting and the ``BepInEx/Translation/<code>`` folder. Engines
that spell codes differently get them converted at the last moment through
``engine_language_code`` so the rest of the pipeline never sees engine dialects.
"""

from __future__ import annotations

from dataclasses import dataclass

AUTO = "auto"


@dataclass(frozen=True)
class Language:
    """One selectable language: canonical code, English name and native name."""

    code: str
    english: str
    native: str


LANGUAGES: tuple[Language, ...] = tuple(Language(*row) for row in (
    ("af", "Afrikaans", "Afrikaans"), ("sq", "Albanian", "Shqip"), ("am", "Amharic", "አማርኛ"),
    ("ar", "Arabic", "العربية"), ("hy", "Armenian", "Հայերեն"), ("as", "Assamese", "অসমীয়া"),
    ("ay", "Aymara", "Aymar aru"), ("az", "Azerbaijani", "Azərbaycanca"), ("bm", "Bambara", "Bamanankan"),
    ("eu", "Basque", "Euskara"), ("be", "Belarusian", "Беларуская"), ("bn", "Bengali", "বাংলা"),
    ("bho", "Bhojpuri", "भोजपुरी"), ("bs", "Bosnian", "Bosanski"), ("bg", "Bulgarian", "Български"),
    ("ca", "Catalan", "Català"), ("ceb", "Cebuano", "Cebuano"), ("ny", "Chichewa", "Chichewa"),
    ("zh-CN", "Chinese (Simplified)", "简体中文"), ("zh-TW", "Chinese (Traditional)", "繁體中文"),
    ("co", "Corsican", "Corsu"), ("hr", "Croatian", "Hrvatski"), ("cs", "Czech", "Čeština"),
    ("da", "Danish", "Dansk"), ("dv", "Dhivehi", "ދިވެހި"), ("doi", "Dogri", "डोगरी"),
    ("nl", "Dutch", "Nederlands"), ("en", "English", "English"), ("eo", "Esperanto", "Esperanto"),
    ("et", "Estonian", "Eesti"), ("ee", "Ewe", "Eʋegbe"), ("tl", "Filipino", "Filipino"),
    ("fi", "Finnish", "Suomi"), ("fr", "French", "Français"), ("fy", "Frisian", "Frysk"),
    ("gl", "Galician", "Galego"), ("ka", "Georgian", "ქართული"), ("de", "German", "Deutsch"),
    ("el", "Greek", "Ελληνικά"), ("gn", "Guarani", "Avañe'ẽ"), ("gu", "Gujarati", "ગુજરાતી"),
    ("ht", "Haitian Creole", "Kreyòl ayisyen"), ("ha", "Hausa", "Hausa"), ("haw", "Hawaiian", "ʻŌlelo Hawaiʻi"),
    ("he", "Hebrew", "עברית"), ("hi", "Hindi", "हिन्दी"), ("hmn", "Hmong", "Hmoob"),
    ("hu", "Hungarian", "Magyar"), ("is", "Icelandic", "Íslenska"), ("ig", "Igbo", "Igbo"),
    ("ilo", "Ilocano", "Ilokano"), ("id", "Indonesian", "Bahasa Indonesia"), ("ga", "Irish", "Gaeilge"),
    ("it", "Italian", "Italiano"), ("ja", "Japanese", "日本語"), ("jv", "Javanese", "Basa Jawa"),
    ("kn", "Kannada", "ಕನ್ನಡ"), ("kk", "Kazakh", "Қазақ тілі"), ("km", "Khmer", "ខ្មែរ"),
    ("rw", "Kinyarwanda", "Ikinyarwanda"), ("gom", "Konkani", "कोंकणी"), ("ko", "Korean", "한국어"),
    ("kri", "Krio", "Krio"), ("ku", "Kurdish (Kurmanji)", "Kurdî"), ("ckb", "Kurdish (Sorani)", "کوردی"),
    ("ky", "Kyrgyz", "Кыргызча"), ("lo", "Lao", "ລາວ"), ("la", "Latin", "Latina"),
    ("lv", "Latvian", "Latviešu"), ("ln", "Lingala", "Lingála"), ("lt", "Lithuanian", "Lietuvių"),
    ("lg", "Luganda", "Luganda"), ("lb", "Luxembourgish", "Lëtzebuergesch"), ("mk", "Macedonian", "Македонски"),
    ("mai", "Maithili", "मैथिली"), ("mg", "Malagasy", "Malagasy"), ("ms", "Malay", "Bahasa Melayu"),
    ("ml", "Malayalam", "മലയാളം"), ("mt", "Maltese", "Malti"), ("mi", "Maori", "Māori"),
    ("mr", "Marathi", "मराठी"), ("mni-Mtei", "Meiteilon (Manipuri)", "ꯃꯤꯇꯩꯂꯣꯟ"), ("lus", "Mizo", "Mizo ṭawng"),
    ("mn", "Mongolian", "Монгол"), ("my", "Myanmar (Burmese)", "မြန်မာ"), ("ne", "Nepali", "नेपाली"),
    ("no", "Norwegian", "Norsk"), ("or", "Odia", "ଓଡ଼ିଆ"), ("om", "Oromo", "Afaan Oromoo"),
    ("ps", "Pashto", "پښتو"), ("fa", "Persian", "فارسی"), ("pl", "Polish", "Polski"),
    ("pt-BR", "Portuguese (Brazil)", "Português (Brasil)"), ("pt-PT", "Portuguese (Portugal)", "Português (Portugal)"),
    ("pa", "Punjabi", "ਪੰਜਾਬੀ"), ("qu", "Quechua", "Runasimi"), ("ro", "Romanian", "Română"),
    ("ru", "Russian", "Русский"), ("sm", "Samoan", "Gagana Samoa"), ("sa", "Sanskrit", "संस्कृतम्"),
    ("gd", "Scots Gaelic", "Gàidhlig"), ("nso", "Sepedi", "Sesotho sa Leboa"), ("sr", "Serbian", "Српски"),
    ("st", "Sesotho", "Sesotho"), ("sn", "Shona", "chiShona"), ("sd", "Sindhi", "سنڌي"),
    ("si", "Sinhala", "සිංහල"), ("sk", "Slovak", "Slovenčina"), ("sl", "Slovenian", "Slovenščina"),
    ("so", "Somali", "Soomaali"), ("es", "Spanish", "Español"), ("su", "Sundanese", "Basa Sunda"),
    ("sw", "Swahili", "Kiswahili"), ("sv", "Swedish", "Svenska"), ("tg", "Tajik", "Тоҷикӣ"),
    ("ta", "Tamil", "தமிழ்"), ("tt", "Tatar", "Татарча"), ("te", "Telugu", "తెలుగు"),
    ("th", "Thai", "ไทย"), ("ti", "Tigrinya", "ትግርኛ"), ("ts", "Tsonga", "Xitsonga"),
    ("tr", "Turkish", "Türkçe"), ("tk", "Turkmen", "Türkmençe"), ("ak", "Twi (Akan)", "Twi"),
    ("uk", "Ukrainian", "Українська"), ("ur", "Urdu", "اردو"), ("ug", "Uyghur", "ئۇيغۇرچە"),
    ("uz", "Uzbek", "Oʻzbekcha"), ("vi", "Vietnamese", "Tiếng Việt"), ("cy", "Welsh", "Cymraeg"),
    ("xh", "Xhosa", "isiXhosa"), ("yi", "Yiddish", "ייִדיש"), ("yo", "Yoruba", "Yorùbá"),
    ("zu", "Zulu", "isiZulu"),
))

_BY_CODE: dict[str, Language] = {lang.code.lower(): lang for lang in LANGUAGES}

# Engine dialects of canonical codes (only entries that differ are listed).
_GOOGLE_CODES: dict[str, str] = {"pt-BR": "pt"}
_BING_CODES: dict[str, str] = {
    "zh-CN": "zh-Hans", "zh-TW": "zh-Hant", "pt-BR": "pt", "no": "nb", "tl": "fil",
    "sr": "sr-Cyrl", "mn": "mn-Cyrl", "ku": "kmr", "ckb": "ku", "mni-Mtei": "mni",
}
_BING_TO_CANONICAL: dict[str, str] = {v: k for k, v in _BING_CODES.items()}
# DeepL supports a fixed subset; target codes need regional variants for EN/PT/ZH.
_DEEPL_TARGETS: dict[str, str] = {
    "ar": "AR", "bg": "BG", "cs": "CS", "da": "DA", "de": "DE", "el": "EL", "en": "EN-US",
    "es": "ES", "et": "ET", "fi": "FI", "fr": "FR", "hu": "HU", "id": "ID", "it": "IT",
    "ja": "JA", "ko": "KO", "lt": "LT", "lv": "LV", "no": "NB", "nl": "NL", "pl": "PL",
    "pt-BR": "PT-BR", "pt-PT": "PT-PT", "ro": "RO", "ru": "RU", "sk": "SK", "sl": "SL",
    "sv": "SV", "tr": "TR", "uk": "UK", "zh-CN": "ZH-HANS", "zh-TW": "ZH-HANT",
}


def get_language(code: str) -> Language | None:
    """Catalog entry for a canonical code (case-insensitive)."""
    return _BY_CODE.get(code.strip().lower())


def english_name(code: str) -> str:
    """English language name, or the code itself when unknown."""
    language = get_language(code)
    return language.english if language else code


def describe_for_prompt(code: str) -> str:
    """Unambiguous language label for LLM prompts, e.g. 'Cebuano (ceb)'."""
    language = get_language(code)
    return f"{language.english} ({language.code})" if language else code


def engine_supports(engine_id: str, code: str) -> bool:
    """Whether an engine accepts a canonical code ('auto' is accepted everywhere)."""
    if code == AUTO:
        return True
    if engine_id == "deepl":
        return code in _DEEPL_TARGETS
    return get_language(code) is not None or engine_id not in ("google", "bing")


def canonical_from_bing(code: str) -> str:
    """Convert a Bing dialect code back to its canonical code."""
    return _BING_TO_CANONICAL.get(code, code)


def engine_language_code(code: str, engine_id: str, source: bool = False) -> str:
    """Translate a canonical code into the spelling a given engine expects."""
    if code == AUTO:
        return code
    if engine_id == "deepl":
        target = _DEEPL_TARGETS.get(code, code.upper())
        # Source languages are regionless in DeepL (EN, PT, ZH).
        return target.split("-")[0] if source else target
    if engine_id == "bing":
        return _BING_CODES.get(code, code)
    if engine_id == "google":
        return _GOOGLE_CODES.get(code, code)
    return code


def languages_for_engine(engine_id: str) -> list[Language]:
    """Catalog entries an engine can translate to, sorted by English name."""
    return sorted(
        (lang for lang in LANGUAGES if engine_supports(engine_id, lang.code)),
        key=lambda lang: lang.english.lower(),
    )
