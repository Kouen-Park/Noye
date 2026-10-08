"""Application checks for generated presentation, separate from original quotations."""

import re

from app.services.source_documents.local import DocumentError


def language_name(value):
    aliases = {
        "en": "English",
        "en-us": "English",
        "en-gb": "English",
        "english": "English",
        "영어": "English",
        "영문": "English",
        "ko": "Korean",
        "ko-kr": "Korean",
        "korean": "Korean",
        "한국어": "Korean",
        "한글": "Korean",
        "국문": "Korean",
    }
    return aliases.get(value.strip().casefold(), value.strip())


def requested_language(instruction, inferred):
    # Require an output action. A trailing "notes written in English" describes
    # originals and must not override "write/explain in Korean". If the grammar
    # is ambiguous (e.g. "from notes in English"), keep the inferred intent.
    directives = list(
        re.finditer(
            r"\b(?:write|draft|create|generate|produce|compose|prepare|explain|summari[sz]e|"
            r"respond|reply|answer|output|render)\b"
            r"(?:(?![.!?;\n]|\b(?:from|using|written|extracted|based\s+on)\b).){0,120}?"
            r"\bin\s+(English|Korean)\b"
            r"|^\s*(?:please\s+)?in\s+(English|Korean)\b"
            r"|\b(?:output\s+)?language\s*:\s*(English|Korean)\b"
            r"|(한국어|영어|국문|영문)(?:으)?로"
            r"(?!\s*(?:작성된|작성한|작성되어|쓰인|적힌|되어|된))",
            instruction,
            re.IGNORECASE,
        )
    )
    return (
        language_name(next(g for g in directives[-1].groups() if g))
        if directives
        else language_name(inferred)
    )


def check_language(text, language):
    """Conservative script checks, not semantic language identification.

    Exact support quotes, saved originals and literal fallback never pass here.
    Other languages remain explicitly unchecked/partial rather than being certified.
    """
    hangul = re.search(r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7a3]", text)
    if language == "English" and re.search(
        r"[\u1100-\u11ff\u3130-\u318f\u3040-\u30ff\u3400-\u9fff\uac00-\ud7a3]", text
    ):
        raise DocumentError(
            "Generated text does not match requested English. No document was saved."
        )
    letters = sum(character.isalpha() for character in text)
    korean_letters = len(re.findall(r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7a3]", text))
    if language == "Korean" and (not hangul or korean_letters < letters / 4):
        raise DocumentError(
            "Generated text does not match requested Korean. No document was saved."
        )


def check_shape(text, *, heading=False):
    if (heading and ("\n" in text or "\r" in text or text.lstrip().startswith("#"))) or (
        not heading
        and re.search(r"(?m)^[ \t]{0,3}#{1,6}\s|^[^\n]+\n[ \t]{0,3}(?:=+|-+)[ \t]*$", text)
    ):
        raise DocumentError(
            "Generated text contains an unplanned Markdown heading. No document was saved."
        )


def is_comparison(instruction, intent):
    return bool(
        re.search(
            r"\bcompar(?:e|es|ed|ing|ison|isons)\b|비교",
            instruction + " " + intent["document_type"] + " " + intent["purpose"],
            re.IGNORECASE,
        )
    )


def is_absence_heading(title):
    # An isolated source batch cannot establish collection-wide absence. Render
    # missing-material findings only from the application's actual coverage report.
    return bool(
        re.search(
            r"\b(?:no|missing|insufficient|unavailable)\s+(?:information|evidence|data|sources?|material)\b"
            r"|\black\s+of\s+(?:information|evidence|data|sources?|material)\b"
            r"|(?:정보|자료|근거|데이터)(?:가|는|의)?(?:\s+대한\s+정보)?\s*(?:부족|없|누락)",
            title,
            re.IGNORECASE,
        )
    )


def neutral_title(language, *, section=False):
    if language == "Korean":
        return "원문 정리" if section else "원문 기반 문서"
    return "Source notes" if section else "Source document"
