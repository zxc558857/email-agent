import re


BANK_ALIASES = {
    "中國信託": ["中國信託", "中信"],
    "富邦": ["富邦", "台北富邦"],
    "國泰世華": ["國泰", "國泰世華"],
    "LINE Bank": ["line bank", "linebank", "LINE Bank"],
    "合作金庫": ["合作金庫", "合庫"],
    "永豐": ["永豐"],
    "玉山": ["玉山"],
    "元大": ["元大"],
    "台新": ["台新"],
    "兆豐": ["兆豐"],
}


def normalize_query_text(text):
    return re.sub(r"\s+", "", (text or "").strip().lower())


def normalize_bank_name(text):
    normalized_text = normalize_query_text(text)
    for bank_name, aliases in BANK_ALIASES.items():
        for alias in aliases:
            if normalize_query_text(alias) in normalized_text:
                return bank_name
    return None
