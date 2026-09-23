import json
import random

import httpx

base = "http://127.0.0.1:5080"
email = f"trader{random.randint(10000, 99999)}@example.com"
client = httpx.Client(base_url=base, timeout=60.0)

print("HEALTH", client.get("/health").json())

reg = client.post(
    "/api/auth/register",
    json={
        "email": email,
        "password": "Password123!",
        "firstName": "Berkay",
        "lastName": "Test",
    },
)
print("REGISTER", reg.status_code, reg.json())

login = client.post("/api/auth/login", json={"email": email, "password": "Password123!"})
print("LOGIN", login.status_code, login.json())
print("COOKIES", dict(client.cookies))

me = client.get("/api/auth/me")
print("ME", me.status_code, me.json())

h1 = client.post(
    "/api/portfolio/holdings",
    json={"symbol": "THYAO", "sharesCount": 10, "averageCost": 280.5},
)
h2 = client.post(
    "/api/portfolio/holdings",
    json={"symbol": "GARAN", "sharesCount": 25, "averageCost": 110},
)
print("HOLDING1", h1.status_code, h1.json())
print("HOLDING2", h2.status_code, h2.json())

pf = client.get("/api/portfolio")
print("PORTFOLIO", pf.status_code, json.dumps(pf.json(), ensure_ascii=False)[:500])

news = client.get("/api/market/news")
print("NEWS", news.status_code, len(news.json()))

pdf = b"""%PDF-1.4
1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj
2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj
3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj
4 0 obj<< /Length 84 >>stream
BT /F1 12 Tf 72 720 Td (THYAO 15 295,40) Tj ET
BT /F1 12 Tf 72 700 Td (ASELS 40 82,10) Tj ET
endstream
endobj
5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000266 00000 n 
0000000403 00000 n 
trailer<< /Size 6 /Root 1 0 R >>
startxref
480
%%EOF"""

preview = client.post(
    "/api/portfolio/statements/preview",
    files={"file": ("sample.pdf", pdf, "application/pdf")},
)
print("PREVIEW", preview.status_code, preview.json())

parsed = preview.json().get("parsed", [])
if parsed:
    imported = client.post(
        "/api/portfolio/statements/import",
        json={
            "holdings": [
                {
                    "symbol": item["symbol"],
                    "sharesCount": item["sharesCount"],
                    "averageCost": item["averageCost"],
                }
                for item in parsed
            ]
        },
    )
    print("IMPORT", imported.status_code, imported.json())
else:
    print("IMPORT skipped, no parsed lines")

analysis = client.post("/api/analysis/generate")
print("ANALYSIS", analysis.status_code, analysis.text[:300])

reports = client.get("/api/analysis/reports")
print("REPORTS", reports.status_code, reports.json())

remove = client.post(f"/api/portfolio/holdings/{h1.json()['id']}/remove")
print("REMOVE", remove.status_code)

refresh = client.post("/api/auth/refresh")
print("REFRESH", refresh.status_code, refresh.json())

logout = client.post("/api/auth/logout")
print("LOGOUT", logout.status_code)
print("DONE")
