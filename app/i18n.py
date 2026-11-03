"""Arayüz dili.

Şablonlarda metinler {{ _("Türkçe metin") }} biçiminde yazılır. Anahtar
Türkçe metnin kendisidir; seçilen dilde çevirisi yoksa Türkçesi gösterilir.
İngilizceye geçerken metinlerin çevirileri EN sözlüğüne eklenir ve henüz
_() içine alınmamış şablon metinleri sarılır; başka bir şey değişmez.
"""
from fastapi import Request

LANGUAGES = {"tr": "Türkçe", "en": "English"}
DEFAULT_LANG = "tr"
COOKIE = "lang"

# Şimdilik boş: EN seçilse de metinler Türkçe görünür.
CATALOGS: dict[str, dict[str, str]] = {"en": {}}


def get_lang(request: Request) -> str:
    lang = request.cookies.get(COOKIE, DEFAULT_LANG)
    return lang if lang in LANGUAGES else DEFAULT_LANG


def translator(lang: str):
    catalog = CATALOGS.get(lang, {})
    return lambda text: catalog.get(text, text)
