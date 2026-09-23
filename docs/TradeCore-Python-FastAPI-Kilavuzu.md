# TradeCore — Python FastAPI & Clean Architecture Kılavuzu

Kaynak PDF: [docs/TradeCore-Python-FastAPI-Kilavuzu.pdf](TradeCore-Python-FastAPI-Kilavuzu.pdf)

Bu kılavuz, TradeCore’u kurumsal .NET mimarisinden yerel-öncelikli (Local-First), sıfır maliyetli Python FastAPI + SQLite mimarisine dönüştürme şartnamesidir.

## 1. Proje Vizyonu ve Mimari İlkeler

- **Hedef:** Kişisel finans yönetimi, BIST hisse/portföy takibi, banka ekstresi (PDF/Excel) ayrıştırma, haber analizi ve Gemini destekli finansal raporlama.
- **Local-First & Sıfır Maliyet:** Veriler yerel `tradecore.db` (SQLite) dosyasında tutulur.
- **Next.js 15 Frontend:** Mevcut App Router + Tailwind/shadcn arayüzü korunur; Python API’ye bağlanır.
- **Telegram Bot:** Mobil cihazdan komutla portföy/özet/analiz sorgusu.

## 2. Cursor Mimari Kuralları

1. **Modüler katman ayrımı**
   - `core/`: Güvenlik, JWT, ayarlar (`config.py`)
   - `models/`: SQLModel entity’leri
   - `services/`: İş mantığı (ekstre, yfinance, Gemini, Telegram)
   - `api/`: FastAPI route’ları
2. **Tip güvenliği:** Pydantic şemaları ve type hint’ler zorunlu.
3. **API uyumluluğu:** `POST /api/auth/login`, `POST /api/auth/register`, `GET /api/auth/me` aynı JSON ve HttpOnly çerez sözleşmesiyle kalır.

## 3. Uygulama Klasör Yapısı (gerçekleşen)

Kılavuzdaki `backend/app/...` taslağı, onaylı planda `server/` köküyle uygulandı:

```text
TradeCore/
├── .cursorrules.ini
├── docs/
│   ├── TradeCore-Python-FastAPI-Kilavuzu.pdf
│   └── TradeCore-Python-FastAPI-Kilavuzu.md
├── frontend/                 # Next.js 15 (değişmeden auth sözleşmesi)
└── server/                   # FastAPI (kılavuzdaki backend/app karşılığı)
    ├── main.py
    ├── requirements.txt
    ├── .env.example
    ├── core/
    │   ├── config.py
    │   ├── database.py
    │   └── security.py
    ├── models/
    │   ├── user.py
    │   └── portfolio.py
    ├── services/
    │   ├── auth_service.py
    │   ├── market_price_service.py
    │   ├── portfolio_service.py
    │   ├── statement_parser.py
    │   ├── gemini_analyst.py
    │   └── telegram_bot.py
    └── api/
        ├── auth.py
        ├── portfolio.py
        ├── market.py
        └── analysis.py
```

## 4. Beş Aşama (durum)

| Aşama | Kılavuz | Durum |
| --- | --- | --- |
| 1 | FastAPI + Auth + SQLite | Tamamlandı (`server/`) |
| 2 | BIST portföy / yfinance | Tamamlandı (holding + kâr/zarar + haber) |
| 3 | PDF ekstre ayrıştırma | Tamamlandı (portföy ekstresi; Excel/kategori motoru sonraki tur) |
| 4 | Gemini analiz | Tamamlandı (`GEMINI_API_KEY` gerekir) |
| 5 | Telegram bot | Tamamlandı (`/portfolio`, `/analiz`, `/haber`) |

### Kılavuzda olup sonraki tura bırakılanlar

- Altın / döviz kursları (`market_service` genişlemesi)
- `Transaction` geçmiş modeli
- Banka harcama ekstresi + kategori kuralları (MIGROS → Market) ve Excel (`openpyxl`)
- `POST /api/parser/upload` ayrı parser route’u (şimdi `POST /api/portfolio/statements/*`)
- Telegram `/harca`, `/durum`, `/hisse` komutları
- Next.js dashboard panellerinin zenginleştirilmesi
- FastAPI + Next.js + SQLite volume `docker-compose` güncellemesi

## 5. Çalıştırma

```powershell
cd TradeCore
$env:PYTHONPATH = (Get-Location).Path
.\server\.venv\Scripts\uvicorn.exe server.main:app --host 127.0.0.1 --port 5080
```

Frontend proxy hedefi: `http://localhost:5080`.
