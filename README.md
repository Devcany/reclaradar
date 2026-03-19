# ReclaRadar

Reklamationsdokument rein → 8D-Report raus. KI-gestützte Qualitätsmanagement-Pipeline für Automotive-Zulieferer.

## Was es macht

- PDF oder JSON Reklamation hochladen
- Claude analysiert Fehlerbild, klassifiziert, generiert 8D-Report-Skeleton
- D2/D3/D4/D5/D7 KI-generiert (Ishikawa, SPC, Cpk, Poka-Yoke)
- D1/D6/D8 als Platzhalter markiert (benötigen interne Daten)
- Dark-theme Demo-UI mit Drag & Drop

## Stack

- Python / FastAPI / Uvicorn
- Claude API (claude-sonnet-4-20250514)
- PyMuPDF (PDF-Parsing)
- reportlab (Test-PDF-Generierung)
- systemd auf Hetzner

## Quickstart

1. git clone, pip install anthropic fastapi uvicorn PyMuPDF
2. `ANTHROPIC_API_KEY=sk-... python3 generate_8d_report.py reklamation_hoffmann_SG4200.json`
3. Oder: `uvicorn app:app --host 0.0.0.0 --port 8001`

## Demo

Testdaten: `generate_fake_reklamation.py` erzeugt eine realistische Automotive-Reklamation
(Hoffmann Automotive → Müller Präzisionsteile, Steckverbinder-Gehäuse SG-4200)

## Projektkontext

Teil eines B2B Industrial AI Portfolios:
BidRadar (Vertrieb) → Anomaly Narrator (Produktion) → ReclaRadar (Qualität)
