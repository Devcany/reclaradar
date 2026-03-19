#!/usr/bin/env python3
"""
ReclaRadar — Päckchen 2: Claude-Prompt-Pipeline für 8D-Report-Generierung
"""

import json
import os
import sys
from pathlib import Path


def load_from_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"[INPUT] JSON geladen: {filepath}")
    return data


def load_from_pdf(filepath):
    import fitz
    doc = fitz.open(filepath)
    text_parts = []
    for page_num, page in enumerate(doc, 1):
        text_parts.append(f"--- Seite {page_num} ---\n{page.get_text()}")
    full_text = "\n\n".join(text_parts)
    doc.close()
    print(f"[INPUT] PDF extrahiert: {filepath} ({len(full_text)} Zeichen)")
    return full_text


def load_input(filepath):
    ext = Path(filepath).suffix.lower()
    if ext == ".json":
        data = load_from_json(filepath)
        input_text = json.dumps(data, ensure_ascii=False, indent=2)
        return input_text, "json"
    elif ext == ".pdf":
        raw_text = load_from_pdf(filepath)
        return raw_text, "pdf"
    else:
        print(f"[FEHLER] Nicht unterstütztes Format: {ext}")
        sys.exit(1)


SYSTEM_PROMPT = """\
Du bist ein Qualitätsmanagement-Experte mit 15 Jahren Erfahrung in der \
Automotive-Zulieferindustrie. Du erstellst 8D-Reports nach VDA-Standard.

Deine Aufgabe: Analysiere das eingehende Reklamationsdokument und generiere \
einen strukturierten 8D-Report-Skeleton.

REGELN:
- Antworte AUSSCHLIESSLICH mit einem JSON-Objekt. Kein Markdown, kein Fließtext.
- D2, D3, D4, D5, D7 werden von dir inhaltlich generiert basierend auf den \
Reklamationsdaten.
- D1, D6, D8 sind Platzhalter — markiere sie mit "status": "PLATZHALTER" und \
einem hilfreichen Hinweis was dort eingetragen werden muss.
- Verwende Fachsprache der Automotive-Qualitätssicherung (FMEA, Ishikawa, \
Poka-Yoke, SPC, Cpk, etc.) wo angemessen.
- Alle Maßnahmen müssen konkret und umsetzbar sein, nicht generisch.
- Referenziere spezifische Daten aus dem Reklamationsdokument (Sachnummern, \
Chargen, Messwerte, Toleranzen).

AUSGABEFORMAT (exakt dieses JSON-Schema):
{
  "report_meta": {
    "reklamations_nr": "...",
    "erstelldatum": "YYYY-MM-DD",
    "produkt": "...",
    "lieferant": "...",
    "kunde": "..."
  },
  "d1_team": {
    "status": "PLATZHALTER",
    "titel": "Team-Zusammenstellung",
    "inhalt": "...",
    "hinweis": "..."
  },
  "d2_problembeschreibung": {
    "status": "KI_GENERIERT",
    "titel": "Problembeschreibung",
    "ist_zustand": "...",
    "soll_zustand": "...",
    "abweichung": "...",
    "betroffene_menge": "...",
    "auswirkung": "..."
  },
  "d3_sofortmassnahmen": {
    "status": "KI_GENERIERT",
    "titel": "Sofort- und Eindämmungsmaßnahmen",
    "massnahmen": [
      {
        "nr": 1,
        "massnahme": "...",
        "verantwortlich": "... (Rolle/Abteilung)",
        "termin": "...",
        "status_vorschlag": "OFFEN"
      }
    ]
  },
  "d4_grundursache": {
    "status": "KI_GENERIERT",
    "titel": "Grundursachenanalyse",
    "methode": "...",
    "moegliche_ursachen": [
      {
        "kategorie": "...",
        "ursache": "...",
        "bewertung": "..."
      }
    ],
    "wahrscheinlichste_grundursache": "...",
    "begruendung": "..."
  },
  "d5_abstellmassnahmen": {
    "status": "KI_GENERIERT",
    "titel": "Dauerhafte Abstellmaßnahmen",
    "massnahmen": [
      {
        "nr": 1,
        "massnahme": "...",
        "verantwortlich": "... (Rolle/Abteilung)",
        "termin": "...",
        "nachweis": "..."
      }
    ]
  },
  "d6_wirksamkeit": {
    "status": "PLATZHALTER",
    "titel": "Wirksamkeitsnachweis",
    "inhalt": "...",
    "hinweis": "..."
  },
  "d7_vorbeugung": {
    "status": "KI_GENERIERT",
    "titel": "Vorbeugemaßnahmen",
    "massnahmen": [
      {
        "nr": 1,
        "massnahme": "...",
        "bezug": "...",
        "umsetzung": "..."
      }
    ],
    "fmea_update": "...",
    "lessons_learned": "..."
  },
  "d8_abschluss": {
    "status": "PLATZHALTER",
    "titel": "Abschluss und Teamwürdigung",
    "inhalt": "...",
    "hinweis": "..."
  }
}
"""


def build_user_prompt(input_text, input_mode):
    if input_mode == "json":
        return (
            "Hier ist das Reklamationsdokument als strukturiertes JSON. "
            "Analysiere es und erstelle den 8D-Report-Skeleton.\n\n"
            f"```json\n{input_text}\n```"
        )
    else:
        return (
            "Hier ist der extrahierte Text eines Reklamationsdokuments (PDF). "
            "Analysiere den Inhalt und erstelle den 8D-Report-Skeleton.\n\n"
            f"--- DOKUMENTTEXT ---\n{input_text}\n--- ENDE ---"
        )


def call_claude(system_prompt, user_prompt):
    import anthropic
    client = anthropic.Anthropic()
    print("[API] Sende Reklamation an Claude...")
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )
    raw_text = response.content[0].text
    print(f"[API] Antwort erhalten ({len(raw_text)} Zeichen)")

    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        report = json.loads(cleaned)
        print("[OK] 8D-Report JSON erfolgreich geparst")
        return report
    except json.JSONDecodeError as e:
        print(f"[FEHLER] JSON-Parsing fehlgeschlagen: {e}")
        print(f"[DEBUG] Rohantwort (erste 500 Zeichen):\n{raw_text[:500]}")
        return {"_raw_response": raw_text, "_parse_error": str(e)}


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 generate_8d_report.py <reklamation.json|.pdf> [output.json]")
        sys.exit(1)

    input_path = sys.argv[1]
    if not os.path.exists(input_path):
        print(f"[FEHLER] Datei nicht gefunden: {input_path}")
        sys.exit(1)

    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        stem = Path(input_path).stem
        output_path = f"8d_report_{stem}.json"

    input_text, input_mode = load_input(input_path)
    user_prompt = build_user_prompt(input_text, input_mode)
    report = call_claude(SYSTEM_PROMPT, user_prompt)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n[DONE] 8D-Report gespeichert: {output_path}")

    if "_parse_error" not in report:
        generated = [k for k, v in report.items() if isinstance(v, dict) and v.get("status") == "KI_GENERIERT"]
        placeholder = [k for k, v in report.items() if isinstance(v, dict) and v.get("status") == "PLATZHALTER"]
        print(f"  KI-generiert:  {len(generated)} Felder ({', '.join(generated)})")
        print(f"  Platzhalter:   {len(placeholder)} Felder ({', '.join(placeholder)})")


if __name__ == "__main__":
    main()
