#!/usr/bin/env python3
"""
ReclaRadar — Päckchen 1: Fake-Reklamationsdokument Generator
"""

import json
import os
from datetime import datetime

reklamation = {
    "meta": {
        "reklamations_nr": "RK-2026-00417",
        "datum": "2026-03-12",
        "prioritaet": "Hoch",
        "status": "Offen",
        "typ": "Externe Kundenreklamation"
    },
    "kunde": {
        "firma": "Hoffmann Automotive GmbH",
        "ansprechpartner": "Dipl.-Ing. Stefan Brückner",
        "position": "Leiter Qualitätssicherung",
        "email": "s.brueckner@hoffmann-automotive.de",
        "telefon": "+49 5321 9988-140",
        "adresse": "Industriestraße 22, 38644 Goslar"
    },
    "lieferant": {
        "firma": "Müller Präzisionsteile GmbH",
        "standort": "Werk Detmold",
        "ansprechpartner": "Thomas Krause",
        "position": "Qualitätsmanager",
        "email": "t.krause@mueller-praezision.de",
        "telefon": "+49 5231 7744-200"
    },
    "betroffenes_produkt": {
        "bezeichnung": "Steckverbinder-Gehäuse Typ SG-4200",
        "sachnummer": "MP-SG4200-Rev03",
        "charge": "CH-2026-0088",
        "lieferschein_nr": "LS-2026-03041",
        "lieferdatum": "2026-03-05",
        "bestellmenge": 5000,
        "betroffene_menge": 312,
        "pruefmethode": "Sichtprüfung + Maßprüfung (Koordinatenmessgerät)"
    },
    "fehlerbeschreibung": {
        "kurzbeschreibung": "Maßabweichung an Rastnasen, Gehäuse lässt sich nicht korrekt verriegeln",
        "detailbeschreibung": "Bei der Wareneingangsprüfung der Charge CH-2026-0088 wurde festgestellt, dass bei 312 von 500 geprüften Steckverbinder-Gehäusen Typ SG-4200 die Rastnasen eine Maßabweichung von +0,18 mm bis +0,25 mm aufweisen (Toleranz: ±0,05 mm gemäß Zeichnung MP-SG4200-Rev03-DWG). Die betroffenen Gehäuse lassen sich nicht korrekt mit dem Gegenstück (Buchsenleiste BL-4200) verriegeln. Ein spürbares Spiel bleibt nach dem Einrasten bestehen. Bei Vibrationsbelastung (gemäß LV 124, Profil 3) lösen sich die Verbindungen nach durchschnittlich 4,2 Stunden (Anforderung: min. 72 Stunden).",
        "fehlerart": "Maßabweichung / Fertigungsfehler",
        "fehlerort": "Rastnase links + rechts, Position gemäß Zeichnung Pos. 4a/4b",
        "erstentdeckung": "Wareneingangsprüfung",
        "auswirkung_kunde": "Produktionsstopp Linie 3 (Kabelbaumfertigung) seit 2026-03-10. Tagesausfall ca. 1.200 Kabelsätze. Endkunde (OEM) wurde informiert. Sonderfahrt mit Ersatzlieferung aus Altbestand erforderlich."
    },
    "sofortmassnahmen_kunde": [
        "Sperrung der gesamten Charge CH-2026-0088 im Lager",
        "100%-Prüfung der bereits verbauten Teile aus gleicher Charge (Linie 1 + 2)",
        "Rückstellung von 20 Musterteilen für Lieferanten-Analyse",
        "Umstellung auf Alternativlieferant (Charge AL-2026-0091) ab 2026-03-11",
        "Information an OEM-Qualitätsabteilung (Eskalationsstufe 2)"
    ],
    "forderungen": {
        "8d_report_frist": "2026-03-26 (10 Arbeitstage)",
        "nachlieferung": "4.700 Stück i.O.-Teile bis spätestens 2026-03-19",
        "kostenuebernahme": [
            "Sortierkosten: geschätzt 3.400 EUR",
            "Produktionsausfall Linie 3: geschätzt 18.000 EUR/Tag × 2 Tage = 36.000 EUR",
            "Sonderfahrt Ersatzlieferung: 1.200 EUR",
            "Prüfkosten Koordinatenmessgerät (extern): 850 EUR"
        ],
        "gesamt_schadenssumme_geschaetzt": "41.450 EUR"
    },
    "anlagen": [
        "Prüfbericht WE-2026-03041 (Koordinatenmessgerät, 12 Seiten)",
        "Fotos Rastnasen-Vergleich i.O. vs. n.i.O. (8 Bilder)",
        "Zeichnung MP-SG4200-Rev03-DWG (Auszug Pos. 4a/4b)",
        "Lieferschein LS-2026-03041 (Kopie)",
        "Vibrationstestprotokoll gemäß LV 124 Profil 3"
    ]
}


def generate_json(output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(reklamation, f, ensure_ascii=False, indent=2)
    print(f"[OK] JSON gespeichert: {output_path}")


def generate_pdf(output_path):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=25*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="DocTitle", parent=styles["Title"],
                              fontSize=18, spaceAfter=4*mm,
                              textColor=HexColor("#B22222"), fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle(name="SectionHead", parent=styles["Heading2"],
                              fontSize=12, spaceBefore=6*mm, spaceAfter=2*mm,
                              textColor=HexColor("#1a1a1a"), fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle(name="FieldLabel", parent=styles["Normal"],
                              fontSize=9, fontName="Helvetica-Bold",
                              textColor=HexColor("#555555")))
    styles.add(ParagraphStyle(name="FieldValue", parent=styles["Normal"],
                              fontSize=10, fontName="Helvetica", leading=14))
    styles.add(ParagraphStyle(name="SmallGray", parent=styles["Normal"],
                              fontSize=8, textColor=HexColor("#888888"), alignment=TA_RIGHT))

    story = []
    r = reklamation

    story.append(Paragraph("KUNDENREKLAMATION", styles["DocTitle"]))

    header_data = [
        ["Reklamations-Nr.:", r["meta"]["reklamations_nr"], "Datum:", r["meta"]["datum"]],
        ["Prioritaet:", r["meta"]["prioritaet"], "Status:", r["meta"]["status"]],
        ["Typ:", r["meta"]["typ"], "", ""],
    ]
    header_table = Table(header_data, colWidths=[35*mm, 50*mm, 25*mm, 50*mm])
    header_table.setStyle(TableStyle([
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME", (2,0), (2,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("TEXTCOLOR", (0,0), (0,-1), HexColor("#555555")),
        ("TEXTCOLOR", (2,0), (2,-1), HexColor("#555555")),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 2*mm))
    story.append(HRFlowable(width="100%", color=HexColor("#cccccc")))

    def contact_block(title, data):
        story.append(Paragraph(title, styles["SectionHead"]))
        lines = [
            f"<b>{data['firma']}</b>",
            f"{data['ansprechpartner']} — {data['position']}",
            f"E-Mail: {data['email']} | Tel: {data['telefon']}"
        ]
        if "adresse" in data:
            lines.append(data["adresse"])
        if "standort" in data:
            lines.append(f"Standort: {data['standort']}")
        for line in lines:
            story.append(Paragraph(line, styles["FieldValue"]))

    contact_block("Reklamierender Kunde", r["kunde"])
    contact_block("Betroffener Lieferant", r["lieferant"])

    story.append(Paragraph("Betroffenes Produkt", styles["SectionHead"]))
    p = r["betroffenes_produkt"]
    prod_data = [
        ["Bezeichnung:", p["bezeichnung"], "Sachnummer:", p["sachnummer"]],
        ["Charge:", p["charge"], "Lieferschein:", p["lieferschein_nr"]],
        ["Lieferdatum:", p["lieferdatum"], "Bestellmenge:", str(p["bestellmenge"])],
        ["Betroffene Menge:", str(p["betroffene_menge"]), "Pruefmethode:", p["pruefmethode"]],
    ]
    prod_table = Table(prod_data, colWidths=[32*mm, 50*mm, 30*mm, 50*mm])
    prod_table.setStyle(TableStyle([
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME", (2,0), (2,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("TEXTCOLOR", (0,0), (0,-1), HexColor("#555555")),
        ("TEXTCOLOR", (2,0), (2,-1), HexColor("#555555")),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("BACKGROUND", (0,0), (-1,-1), HexColor("#f8f8f8")),
    ]))
    story.append(prod_table)

    story.append(Paragraph("Fehlerbeschreibung", styles["SectionHead"]))
    fb = r["fehlerbeschreibung"]
    story.append(Paragraph(f"<b>Kurztext:</b> {fb['kurzbeschreibung']}", styles["FieldValue"]))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(fb["detailbeschreibung"], styles["FieldValue"]))
    story.append(Spacer(1, 2*mm))
    detail_data = [
        ["Fehlerart:", fb["fehlerart"]],
        ["Fehlerort:", fb["fehlerort"]],
        ["Erstentdeckung:", fb["erstentdeckung"]]
    ]
    detail_table = Table(detail_data, colWidths=[32*mm, 130*mm])
    detail_table.setStyle(TableStyle([
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("TEXTCOLOR", (0,0), (0,-1), HexColor("#555555")),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ("TOPPADDING", (0,0), (-1,-1), 2),
    ]))
    story.append(detail_table)
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph("<b>Auswirkung beim Kunden:</b>", styles["FieldLabel"]))
    story.append(Paragraph(fb["auswirkung_kunde"], styles["FieldValue"]))

    story.append(Paragraph("Sofortmassnahmen (kundenseitig)", styles["SectionHead"]))
    for i, m in enumerate(r["sofortmassnahmen_kunde"], 1):
        story.append(Paragraph(f"{i}. {m}", styles["FieldValue"]))

    story.append(Paragraph("Forderungen an Lieferant", styles["SectionHead"]))
    ford = r["forderungen"]
    story.append(Paragraph(f"<b>8D-Report Frist:</b> {ford['8d_report_frist']}", styles["FieldValue"]))
    story.append(Paragraph(f"<b>Nachlieferung:</b> {ford['nachlieferung']}", styles["FieldValue"]))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph("<b>Kostenforderungen:</b>", styles["FieldLabel"]))
    for k in ford["kostenuebernahme"]:
        story.append(Paragraph(f" - {k}", styles["FieldValue"]))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(f"<b>Geschaetzte Gesamtschadenssumme: {ford['gesamt_schadenssumme_geschaetzt']}</b>", styles["FieldValue"]))

    story.append(Paragraph("Anlagen", styles["SectionHead"]))
    for i, a in enumerate(r["anlagen"], 1):
        story.append(Paragraph(f"{i}. {a}", styles["FieldValue"]))

    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(width="100%", color=HexColor("#cccccc")))
    story.append(Paragraph(
        f"Erstellt: {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
        "Dieses Dokument ist eine Testreklamation fuer Entwicklungszwecke (ReclaRadar PoC).",
        styles["SmallGray"]
    ))

    doc.build(story)
    print(f"[OK] PDF gespeichert: {output_path}")


if __name__ == "__main__":
    out_dir = os.path.dirname(os.path.abspath(__file__))
    generate_json(os.path.join(out_dir, "reklamation_hoffmann_SG4200.json"))
    generate_pdf(os.path.join(out_dir, "reklamation_hoffmann_SG4200.pdf"))
    print("\n[DONE] Paeckchen 1 abgeschlossen — beide Dateien erzeugt.")
