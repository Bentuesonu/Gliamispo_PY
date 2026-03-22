import json
import os
import sqlite3

from fpdf import FPDF


def _sanitize_text(text):
    """Sostituisce caratteri Unicode non supportati da Helvetica."""
    if not text:
        return ''
    replacements = {
        '—': '-', '–': '-',
        ''': "'", ''': "'",
        '"': '"', '"': '"',
        '…': '...',
        '€': 'EUR',
        '°': 'o',
    }
    result = str(text)
    for old, new in replacements.items():
        result = result.replace(old, new)
    return result.encode('latin-1', errors='replace').decode('latin-1')


# ---------------------------------------------------------------------------
# Existing text-based generator (kept for backward compatibility)
# ---------------------------------------------------------------------------

class CallSheetGenerator:
    def generate(self, conn, call_sheet_id, output_path):
        data = self._fetch_data(conn, call_sheet_id)
        if data is None:
            return False
        content = self._build_content(data)
        dirpath = os.path.dirname(output_path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True

    def generate_to_bytes(self, conn, call_sheet_id):
        data = self._fetch_data(conn, call_sheet_id)
        if data is None:
            return b""
        return self._build_content(data).encode("utf-8")

    def _fetch_data(self, conn, call_sheet_id):
        row = conn.execute(
            "SELECT cs.id, cs.crew_call, cs.general_notes, cs.weather_forecast,"
            " sd.day_number, sd.shoot_date, sd.location_primary"
            " FROM call_sheets cs"
            " JOIN shooting_days sd ON sd.id = cs.shooting_day_id"
            " WHERE cs.id = ?",
            (call_sheet_id,),
        ).fetchone()
        if row is None:
            return None

        sheet = self._row_to_dict(row)

        cast_rows = conn.execute(
            "SELECT actor_name, character_name, call_time"
            " FROM call_sheet_cast WHERE call_sheet_id = ? ORDER BY call_time",
            (call_sheet_id,),
        ).fetchall()
        cast = [self._row_to_dict(r) for r in cast_rows]

        crew_rows = conn.execute(
            "SELECT crew_member_name, department, call_time"
            " FROM call_sheet_crew"
            " WHERE call_sheet_id = ? ORDER BY department, call_time",
            (call_sheet_id,),
        ).fetchall()
        crew = [self._row_to_dict(r) for r in crew_rows]

        return {"sheet": sheet, "cast": cast, "crew": crew}

    def _row_to_dict(self, row):
        if isinstance(row, sqlite3.Row):
            return dict(row)
        if isinstance(row, dict):
            return row
        return {str(i): v for i, v in enumerate(row)}

    def _build_content(self, data):
        sheet = data["sheet"]
        cast = data["cast"]
        crew = data["crew"]

        lines = ["=" * 60, "FOGLIO DI LAVORAZIONE", "=" * 60]

        day = sheet.get("day_number", "?")
        date = sheet.get("shoot_date") or "N/D"
        loc = sheet.get("location_primary") or "N/D"
        call = sheet.get("crew_call") or "07:00"

        lines.append(f"Giorno: {day}  Data: {date}")
        lines.append(f"Luogo: {loc}")
        lines.append(f"Chiamata generale: {call}")

        if sheet.get("weather_forecast"):
            lines.append(f"Meteo: {sheet['weather_forecast']}")
        if sheet.get("general_notes"):
            lines.append(f"Note: {sheet['general_notes']}")

        lines += ["", "CAST", "-" * 40]
        if cast:
            for c in cast:
                char = c.get("character_name") or ""
                suffix = f" ({char})" if char else ""
                lines.append(
                    f"  {c.get('actor_name', '')}{suffix}"
                    f" — {c.get('call_time', '')}"
                )
        else:
            lines.append("  Nessun cast")

        lines += ["", "TROUPE", "-" * 40]
        if crew:
            for cr in crew:
                dept = cr.get("department") or ""
                prefix = f"[{dept}] " if dept else ""
                lines.append(
                    f"  {prefix}{cr.get('crew_member_name', '')}"
                    f" — {cr.get('call_time', '')}"
                )
        else:
            lines.append("  Nessuna troupe")

        lines += ["", "=" * 60]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# PDF-based generator (fpdf2)
# ---------------------------------------------------------------------------

class CallSheetPDF(FPDF):
    def __init__(self, production_title, logo_path=None):
        super().__init__(orientation="P", unit="mm", format="A4")
        self._logo = logo_path
        self._title = _sanitize_text(production_title)
        self.set_margins(15, 15, 15)
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        if self._logo and os.path.exists(self._logo):
            self.image(self._logo, 15, 10, 30)
            self.set_xy(50, 12)
        else:
            self.set_xy(15, 12)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(26, 82, 118)
        self.cell(0, 8, self._title.upper(), align="L")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(100, 100, 100)
        self.set_xy(15, 20)
        self.cell(0, 5, "ORDINE DEL GIORNO", align="L")
        self.set_draw_color(200, 148, 10)
        self.set_line_width(0.8)
        self.line(15, 28, 195, 28)
        self.set_y(32)


def _draw_general_info(pdf, cs):
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(26, 82, 118)
    pdf.cell(0, 6, "INFORMAZIONI GENERALI", ln=True)
    pdf.set_draw_color(200, 148, 10)
    pdf.set_line_width(0.4)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(40, 40, 40)

    day = cs["day_number"] if cs["day_number"] is not None else "?"
    date = _sanitize_text(cs["shoot_date"] or "N/D")
    loc = _sanitize_text(cs["location_primary"] or "N/D")
    call = _sanitize_text(cs["crew_call"] or "07:00")
    director = _sanitize_text(cs["director"] or "N/D")

    col_w = 87
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(col_w, 6, f"Giorno: {day}  -  Data: {date}")
    pdf.cell(col_w, 6, f"Regista: {director}", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(col_w, 6, f"Location: {loc}")
    pdf.cell(col_w, 6, f"Chiamata generale: {call}", ln=True)

    if cs["general_notes"]:
        pdf.ln(1)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(80, 80, 80)
        pdf.multi_cell(0, 5, f"Note: {_sanitize_text(cs['general_notes'])}")
    pdf.ln(3)


def _draw_cast_section(pdf, cast):
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(26, 82, 118)
    pdf.cell(0, 6, "CAST", ln=True)
    pdf.set_draw_color(200, 148, 10)
    pdf.set_line_width(0.4)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(2)

    if not cast:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 6, "  Nessun cast", ln=True)
        pdf.ln(2)
        return

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(60, 60, 60)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(70, 6, "Attore", fill=True)
    pdf.cell(70, 6, "Personaggio", fill=True)
    pdf.cell(35, 6, "Chiamata", fill=True, ln=True)

    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(40, 40, 40)
    for i, c in enumerate(cast):
        fill = i % 2 == 0
        pdf.set_fill_color(250, 250, 250) if fill else pdf.set_fill_color(255, 255, 255)
        pdf.cell(70, 5, _sanitize_text(c.get("actor_name") or ""), fill=fill)
        pdf.cell(70, 5, _sanitize_text(c.get("character_name") or ""), fill=fill)
        pdf.cell(35, 5, _sanitize_text(c.get("call_time") or ""), fill=fill, ln=True)
    pdf.ln(3)


def _draw_weather_box(pdf, weather_data):
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(26, 82, 118)
    pdf.cell(0, 6, "METEO", ln=True)
    pdf.set_draw_color(200, 148, 10)
    pdf.set_line_width(0.4)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(40, 40, 40)
    pdf.set_fill_color(232, 244, 253)
    pdf.set_draw_color(180, 220, 250)
    pdf.set_line_width(0.3)

    x = pdf.get_x()
    y = pdf.get_y()
    pdf.rect(x, y, 180, 14, style="FD")

    if isinstance(weather_data, dict):
        desc = weather_data.get("description") or weather_data.get("condition") or str(weather_data)
        temp = weather_data.get("temperature") or ""
        wind = weather_data.get("wind") or ""
        line1 = _sanitize_text(desc)
        line2_parts = []
        if temp:
            line2_parts.append(f"Temp: {_sanitize_text(temp)}")
        if wind:
            line2_parts.append(f"Vento: {_sanitize_text(wind)}")
        line2 = "  |  ".join(line2_parts)
    else:
        line1 = _sanitize_text(str(weather_data))
        line2 = ""

    pdf.set_xy(x + 3, y + 2)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(174, 5, line1)
    if line2:
        pdf.set_xy(x + 3, y + 7)
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(174, 5, line2)
    pdf.set_y(y + 17)
    pdf.ln(1)


def _draw_next_day_preview(pdf, cs):
    preview_raw = cs["next_day_preview"] if cs["next_day_preview"] else None
    if not preview_raw:
        return

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(26, 82, 118)
    pdf.cell(0, 6, "ANTEPRIMA GIORNO SUCCESSIVO", ln=True)
    pdf.set_draw_color(200, 148, 10)
    pdf.set_line_width(0.4)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(80, 80, 80)

    try:
        scenes = json.loads(preview_raw) if isinstance(preview_raw, str) else preview_raw
        if isinstance(scenes, list):
            for s in scenes:
                if isinstance(s, dict):
                    heading = s.get("scene_heading") or s.get("heading") or str(s)
                    pdf.cell(0, 5, _sanitize_text(f"  • {heading}"), ln=True)
                else:
                    pdf.cell(0, 5, _sanitize_text(f"  • {s}"), ln=True)
        else:
            pdf.multi_cell(0, 5, _sanitize_text(str(scenes)))
    except (json.JSONDecodeError, TypeError):
        pdf.multi_cell(0, 5, _sanitize_text(str(preview_raw)))

    pdf.ln(3)


def _draw_signature_field(pdf, cs):
    pdf.ln(4)
    pdf.set_draw_color(150, 150, 150)
    pdf.set_line_width(0.3)
    pdf.line(15, pdf.get_y(), 90, pdf.get_y())
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.set_xy(15, pdf.get_y() + 1)
    pdf.cell(75, 4, "Firma Direttore di Produzione")

    sig_path = cs["director_signature_path"] if cs["director_signature_path"] else None
    if sig_path and os.path.exists(sig_path):
        pdf.image(sig_path, 100, pdf.get_y() - 15, 40)


def generate_call_sheet_pdf(db, call_sheet_id):
    cs = db.execute(
        """
        SELECT cs.*, p.title, p.director,
               cs.production_logo_path
        FROM call_sheets cs
        JOIN shooting_days sd ON sd.id = cs.shooting_day_id
        JOIN shooting_schedules ss ON ss.id = sd.schedule_id
        JOIN projects p ON p.id = ss.project_id
        WHERE cs.id = ?
        """,
        (call_sheet_id,),
    ).fetchone()

    if cs is None:
        return b""

    if isinstance(cs, sqlite3.Row):
        cs = dict(cs)

    logo = cs.get("production_logo_path")
    title = cs.get("title") or "Produzione"

    pdf = CallSheetPDF(title, logo)
    pdf.add_page()

    _draw_general_info(pdf, cs)

    cast = db.execute(
        "SELECT * FROM call_sheet_cast WHERE call_sheet_id = ? ORDER BY call_time",
        (call_sheet_id,),
    ).fetchall()
    cast = [dict(r) if isinstance(r, sqlite3.Row) else r for r in cast]
    _draw_cast_section(pdf, cast)

    if cs.get("weather_forecast"):
        try:
            weather_data = json.loads(cs["weather_forecast"])
        except (json.JSONDecodeError, TypeError):
            weather_data = cs["weather_forecast"]
        _draw_weather_box(pdf, weather_data)

    _draw_next_day_preview(pdf, cs)
    _draw_signature_field(pdf, cs)

    return bytes(pdf.output())
