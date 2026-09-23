from __future__ import annotations

import json
import logging
import re

from server.core.config import Settings
from server.models.portfolio import AiReport, Holding, MarketNews
from server.models.user import utc_now

logger = logging.getLogger(__name__)


class AnalysisError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _extract_json_block(text: str) -> dict:
    fenced = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    raw = fenced.group(1) if fenced else None
    if raw is None:
        braced = re.search(r"\{.*\}", text, re.DOTALL)
        raw = braced.group(0) if braced else None
    if raw is None:
        raise AnalysisError(502, "Gemini returned an unexpected response format.")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AnalysisError(502, "Gemini returned invalid JSON.") from exc


def generate_portfolio_analysis(
    settings: Settings,
    *,
    user_id: str,
    holdings: list[Holding],
    news: list[MarketNews],
) -> AiReport:
    if not settings.gemini_api_key.strip():
        raise AnalysisError(503, "GEMINI_API_KEY is not configured.")
    if not holdings:
        raise AnalysisError(400, "Portfolio is empty. Add holdings before generating a report.")

    try:
        from google import genai
    except ImportError as exc:
        raise AnalysisError(503, "google-genai package is not installed.") from exc

    holdings_payload = [
        {
            "symbol": item.symbol,
            "sharesCount": item.shares_count,
            "averageCost": item.average_cost,
            "currentPrice": item.current_price,
            "currentValue": item.current_value,
            "profitLoss": item.profit_loss,
            "profitLossPercentage": item.profit_loss_percentage,
        }
        for item in holdings
    ]
    news_payload = [
        {
            "symbol": item.symbol,
            "title": item.title,
            "summary": item.summary,
            "sentiment": item.sentiment,
        }
        for item in news[:12]
    ]

    prompt = f"""
Sen bir kişisel portföy analisti asistanısın. Verilen BIST portföyünü ve haberleri incele.
Bu çıktı YATIRIM TAVSİYESİ DEĞİLDİR. Raporun içinde bunu açıkça belirt.

Yalnızca aşağıdaki JSON şemasını döndür:
{{
  "title": "string",
  "executiveSummary": "string",
  "fullReportMarkdown": "markdown string",
  "riskScore": 1-10 integer,
  "recommendations": [{{"symbol":"THYAO","action":"Izle|Azalt|Artir|Tut","note":"string"}}]
}}

Portföy:
{json.dumps(holdings_payload, ensure_ascii=False)}

Haberler:
{json.dumps(news_payload, ensure_ascii=False)}
""".strip()

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
        )
        text = getattr(response, "text", None) or ""
        if not text and getattr(response, "candidates", None):
            parts = []
            for candidate in response.candidates:
                content = getattr(candidate, "content", None)
                for part in getattr(content, "parts", []) or []:
                    parts.append(getattr(part, "text", "") or "")
            text = "\n".join(parts)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini analysis failed")
        raise AnalysisError(502, "Gemini analysis request failed.") from exc

    payload = _extract_json_block(text)
    risk = int(payload.get("riskScore") or 5)
    risk = min(10, max(1, risk))
    recommendations = payload.get("recommendations") or []
    if not isinstance(recommendations, list):
        recommendations = []

    disclaimer = (
        "\n\n> Bu rapor yatırım tavsiyesi değildir. Bilgilendirme amaçlı üretilmiştir.\n"
    )
    markdown = str(payload.get("fullReportMarkdown") or "").strip()
    if "yatırım tavsiyesi değildir" not in markdown.lower() and "yatirim tavsiyesi degildir" not in markdown.lower():
        markdown = f"{markdown}{disclaimer}".strip()

    return AiReport(
        user_id=user_id,
        title=str(payload.get("title") or "Portföy Analiz Raporu")[:250],
        executive_summary=str(payload.get("executiveSummary") or "")[:4000],
        full_report_markdown=markdown,
        risk_score=risk,
        recommendations_json=json.dumps(recommendations, ensure_ascii=False),
        created_at_utc=utc_now(),
    )


def explain_market_news(
    settings: Settings,
    *,
    title: str,
    summary: str,
    symbol: str | None = None,
) -> dict:
    """
    Tek bir piyasa haberini Gemini ile açıklar (Madde: Haber Özeti & Etki Analizi).

    Dönüş alanları (UI akordeonu):
    - summary: 2 cümlelik Türkçe özet
    - impact: Olumlu/Olumsuz/Nötr + gerekçe (hisse veya BIST geneli)
    - verdict: yatırımcı için 1 cümlelik çıkarım
    - warning: anahtar yok / hata durumunda nazik uyarı (opsiyonel)

    Yatırım tavsiyesi değildir; prompt içinde de belirtilir.
    """
    clean_title = (title or "").strip()
    clean_summary = (summary or "").strip() or clean_title
    clean_symbol = (symbol or "").strip().upper() or None

    if not clean_title:
        return {
            "summary": "Haber başlığı boş olduğu için analiz yapılamadı.",
            "impact": "Nötr — yeterli metin yok.",
            "verdict": "Başlıklı bir haber seçip tekrar deneyin.",
            "warning": "Eksik girdi",
        }

    # Anahtar yoksa 503 fırlatmak yerine nazik JSON — UI akordeonu kırılmasın
    if not settings.gemini_api_key.strip():
        return {
            "summary": "Yapay zeka özeti şu an kullanılamıyor.",
            "impact": "Nötr — GEMINI_API_KEY tanımlı değil.",
            "verdict": "server/.env dosyasına GEMINI_API_KEY ekleyerek bu özelliği açabilirsiniz.",
            "warning": "GEMINI_API_KEY eksik",
        }

    try:
        from google import genai
    except ImportError:
        return {
            "summary": "Gemini istemci paketi yüklü değil.",
            "impact": "Nötr — google-genai kurulumu gerekli.",
            "verdict": "pip install google-genai sonrası sunucuyu yeniden başlatın.",
            "warning": "google-genai eksik",
        }

    target = f"hisse {clean_symbol}" if clean_symbol and clean_symbol != "BIST" else "BIST geneli"
    prompt = f"""
Sen bir finans haber okuryazarlığı asistanısın. Bu çıktı YATIRIM TAVSİYESİ DEĞİLDİR.

Haberi {target} açısından analiz et ve YALNIZCA şu JSON'u döndür (Türkçe):
{{
  "summary": "Tam 2 cümlelik sade Türkçe özet",
  "impact": "Olumlu|Olumsuz|Nötr ile başlayan bir cümle: olası etki ve kısa gerekçe",
  "verdict": "Yatırımcı için tek cümlelik temel çıkarım (tavsiye değil, bilgilendirme)"
}}

Başlık: {clean_title}
Metin: {clean_summary}
Sembol: {clean_symbol or "BIST"}
""".strip()

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
        )
        text = getattr(response, "text", None) or ""
        if not text and getattr(response, "candidates", None):
            parts: list[str] = []
            for candidate in response.candidates:
                content = getattr(candidate, "content", None)
                for part in getattr(content, "parts", []) or []:
                    parts.append(getattr(part, "text", "") or "")
            text = "\n".join(parts)
        payload = _extract_json_block(text)
    except AnalysisError:
        return {
            "summary": "Model yanıtı beklenen JSON formatında gelmedi.",
            "impact": "Nötr — analiz tamamlanamadı.",
            "verdict": "Bir süre sonra tekrar deneyebilirsiniz.",
            "warning": "Gemini format hatası",
        }
    except Exception:  # noqa: BLE001
        logger.exception("Gemini news explain failed")
        return {
            "summary": "Haber analizi sırasında bir hata oluştu.",
            "impact": "Nötr — geçici bir sorun olabilir.",
            "verdict": "İnternet bağlantınızı ve API kotanızı kontrol edip yeniden deneyin.",
            "warning": "Gemini istek hatası",
        }

    return {
        "summary": str(payload.get("summary") or "").strip()[:1200] or "Özet üretilemedi.",
        "impact": str(payload.get("impact") or "").strip()[:800] or "Nötr — etki belirtilmedi.",
        "verdict": str(payload.get("verdict") or "").strip()[:500] or "Çıkarım üretilemedi.",
    }
