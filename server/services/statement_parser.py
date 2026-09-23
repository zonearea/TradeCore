from __future__ import annotations

import io
import re
from dataclasses import dataclass

import pdfplumber


class StatementError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


@dataclass
class ParsedHoldingLine:
    symbol: str
    shares_count: int
    average_cost: float
    raw_line: str


SYMBOL_RE = re.compile(r"\b([A-Z]{3,6})\b")
# Turkish money: 1.234,56 or 1234,56 or 1234.56 — do not treat spaces as thousand separators
NUMBER_RE = re.compile(r"(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+,\d+|\d+\.\d+|\d+)")


def _parse_tr_number(raw: str) -> float | None:
    cleaned = raw.strip().replace(" ", "")
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        parts = cleaned.split(",")
        if len(parts[-1]) <= 2:
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


SKIP_WORDS = {
    "TOPLAM",
    "PORTFOY",
    "PORTFÖY",
    "HISSE",
    "ADET",
    "FIYAT",
    "FİYAT",
    "TUTAR",
    "ISLEM",
    "İŞLEM",
    "TARIH",
    "TARİH",
    "SAYFA",
    "TL",
    "TRY",
    "BIST",
}


def extract_text_from_pdf(data: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            parts: list[str] = []
            for page in pdf.pages:
                text = page.extract_text() or ""
                parts.append(text)
            combined = "\n".join(parts).strip()
    except Exception as exc:  # noqa: BLE001
        raise StatementError(400, "The PDF could not be read.") from exc

    if not combined:
        raise StatementError(
            400,
            "No extractable text found. Scanned image PDFs are not supported.",
        )
    return combined


def parse_statement_text(text: str) -> tuple[list[ParsedHoldingLine], list[str]]:
    parsed: list[ParsedHoldingLine] = []
    unparsed: list[str] = []

    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if not line or len(line) < 5:
            continue

        upper = line.upper()
        symbols = [match for match in SYMBOL_RE.findall(upper) if match not in SKIP_WORDS]
        if not symbols:
            if any(char.isdigit() for char in line):
                unparsed.append(line)
            continue

        numbers = [_parse_tr_number(match) for match in NUMBER_RE.findall(line)]
        numbers = [value for value in numbers if value is not None and value > 0]
        if len(numbers) < 2:
            unparsed.append(line)
            continue

        shares = None
        cost = None
        for value in numbers:
            if shares is None and value == int(value) and 1 <= value <= 1_000_000:
                shares = int(value)
                continue
            if shares is not None and value > 0:
                cost = float(value)
                break

        if shares is None or cost is None:
            unparsed.append(line)
            continue

        parsed.append(
            ParsedHoldingLine(
                symbol=symbols[0],
                shares_count=shares,
                average_cost=round(cost, 2),
                raw_line=line,
            )
        )

    return parsed, unparsed


def preview_statement(data: bytes) -> dict:
    text = extract_text_from_pdf(data)
    parsed, unparsed = parse_statement_text(text)
    return {
        "parsed": [
            {
                "symbol": item.symbol,
                "sharesCount": item.shares_count,
                "averageCost": item.average_cost,
                "rawLine": item.raw_line,
            }
            for item in parsed
        ],
        "unparsed": unparsed[:50],
        "lineCount": len(text.splitlines()),
    }
