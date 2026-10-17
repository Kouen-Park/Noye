"""Application checks for generated presentation, separate from original quotations."""

import re

from app.services import quantity_properties
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
    # "Source language: English" describes the input, even when its field comes
    # after an explicit output directive. Bare/output language fields still apply.
    directives = [
        directive
        for directive in directives
        if not (
            directive.group(3)
            and re.search(
                r"\b(?:sources?|originals?|input)[\s-]*$",
                instruction[: directive.start()],
                re.IGNORECASE,
            )
        )
    ]
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
    # Markdown recognizes LF, CRLF and lone CR as line endings. Normalize only
    # the checked copy, so alternate line endings cannot hide a Setext heading.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if (heading and ("\n" in text or "\r" in text or text.lstrip().startswith("#"))) or (
        not heading
        and re.search(r"(?m)^[ \t]{0,3}#{1,6}\s|^[^\n]+\n[ \t]{0,3}(?:=+|-+)[ \t]*$", text)
    ):
        raise DocumentError(
            "Generated text contains an unplanned Markdown heading. No document was saved."
        )


def check_volume_properties(text, originals):
    try:
        quantity_properties.check_volume_properties(text, originals)
    except quantity_properties.QuantityPropertyError as error:
        raise DocumentError(f"{error} No document was saved.") from None


def check_absence_claim(text, originals):
    # Model batches cannot certify collection-wide missing information. The
    # application owns that coverage report; literal original statements remain.
    if is_absence_heading(text) and not any(text.strip() in original for original in originals):
        raise DocumentError(
            "A generated claim makes an unverified missing-evidence assertion. "
            "Missing material belongs in the coverage report. No document was saved."
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


def has_performance_context(title, originals):
    # A local model approved a combined policy/performance heading from Sunday
    # permissions alone. Require a performance topic or measurement in the
    # originals before asking that model to judge the remaining heading meaning.
    if not re.search(
        r"\b(?:performance|efficiency|throughput|latency|speed|benchmarks?)\b|"
        r"성능|효율|처리량|지연|속도",
        title,
        re.IGNORECASE,
    ):
        return True
    return bool(
        re.search(
            r"\b(?:performance|efficiency|throughput|latency|speed|benchmarks?|runtime|"
            r"memory|elapsed)\b|\brun\s+time\b|"
            r"\b(?:took|finished|completed|finishes|completes|duration|takes)\b"
            r"[^.!?\n]{0,60}\d+(?:\.\d+)?\s*(?:seconds?|minutes?|hours?|s|min|h)\b|"
            r"\d+(?:\.\d+)?\s*(?:ms|µs|ns|milliseconds?|microseconds?|nanoseconds?)\b|"
            r"성능|효율|처리량|지연|속도|메모리|(?:실행|수행|처리|응답)\s*시간|소요",
            originals,
            re.IGNORECASE,
        )
    )


def neutral_title(language, *, section=False):
    if language == "Korean":
        return "원문 정리" if section else "원문 기반 문서"
    return "Source notes" if section else "Source document"
