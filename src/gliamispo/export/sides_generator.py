"""
Script Sides Generator — Feature 4.2

Generates PDF sides for actors, containing only the scenes they appear in.
"""
from fpdf import FPDF


def generate_sides_for_actor(
    db, project_id: int, actor_name: str, call_sheet_id: int
) -> bytes:
    """
    Generate a PDF with sides for a specific actor.

    Args:
        db: DatabaseManager instance.
        project_id: Project ID.
        actor_name: Name of the actor.
        call_sheet_id: Call sheet ID to generate sides for.

    Returns:
        PDF content as bytes.
    """
    # JOIN via shooting_days (NOT sds.call_sheet_id — column does not exist)
    scenes = db.execute(
        """
        SELECT s.scene_number, s.location, s.int_ext,
               s.day_night, s.synopsis, s.raw_blocks
        FROM call_sheets cs
        JOIN shooting_days sd ON sd.id = cs.shooting_day_id
        JOIN shooting_day_scenes sds ON sds.shooting_day_id = sd.id
        JOIN scenes s ON s.id = sds.scene_id
        JOIN scene_elements se ON se.scene_id = s.id
        WHERE cs.id = ? AND se.category = 'Cast' AND se.element_name = ?
        ORDER BY sds.sort_order
        """,
        (call_sheet_id, actor_name),
    ).fetchall()

    # crew_call (not general_call), sd.day_number (not cs.day_number)
    cs = db.execute(
        """
        SELECT cs.*, sd.day_number
        FROM call_sheets cs
        JOIN shooting_days sd ON sd.id = cs.shooting_day_id
        WHERE cs.id = ?
        """,
        (call_sheet_id,),
    ).fetchone()

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(20, 20, 20)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"SIDES - {actor_name.upper()}", align="C")
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 10)
    crew_call = cs["crew_call"] if cs else ""
    day_num = cs["day_number"] if cs else ""
    pdf.cell(0, 6, f"Chiamata: {crew_call} - Shoot Day #{day_num}", align="C")
    pdf.ln(10)

    for sc in scenes:
        pdf.set_font("Courier", "B", 12)
        heading = (
            f"SCENA {sc['scene_number']} - {sc['location']}"
            f" {sc['int_ext']} {sc['day_night']}"
        )
        pdf.cell(0, 8, heading)
        pdf.ln(8)
        if sc["synopsis"]:
            pdf.set_font("Courier", "", 11)
            pdf.multi_cell(0, 6, sc["synopsis"])
            pdf.ln(4)

    return bytes(pdf.output())


def generate_all_sides_batch(db, project_id: int, call_sheet_id: int) -> dict:
    """
    Generate sides for all actors appearing in the given call sheet.

    Args:
        db: DatabaseManager instance.
        project_id: Project ID.
        call_sheet_id: Call sheet ID.

    Returns:
        Dictionary mapping actor names to PDF bytes.
    """
    actors = db.execute(
        """
        SELECT DISTINCT se.element_name
        FROM call_sheet_cast csc
        JOIN scene_elements se ON se.element_name = csc.actor_name
        WHERE csc.call_sheet_id = ? AND se.category = 'Cast'
        """,
        (call_sheet_id,),
    ).fetchall()

    return {
        a[0]: generate_sides_for_actor(db, project_id, a[0], call_sheet_id)
        for a in actors
    }
