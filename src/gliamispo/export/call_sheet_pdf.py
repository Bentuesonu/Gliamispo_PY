import os
import sqlite3


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
