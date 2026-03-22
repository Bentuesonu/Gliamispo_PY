"""
Industry-standard export formats — Feature 4.3

Exports schedule data in Movie Magic compatible CSV format.
"""
import csv
import io


def export_movie_magic_csv(db, project_id: int) -> bytes:
    """
    Export schedule data in Movie Magic compatible CSV format.

    Args:
        db: DatabaseManager instance.
        project_id: Project ID to export.

    Returns:
        CSV content as bytes (UTF-8 with BOM for Excel IT compatibility).
    """
    rows = db.execute(
        """
        SELECT s.scene_number, s.day_night, s.int_ext, s.location,
               (s.page_end_whole*8 + s.page_end_eighths
                - s.page_start_whole*8 - s.page_start_eighths) AS eighths,
               GROUP_CONCAT(se.element_name) AS cast_names,
               s.synopsis,
               COALESCE(sds.sort_order, 0) AS shoot_day
        FROM scenes s
        LEFT JOIN scene_elements se
            ON se.scene_id = s.id AND se.category = 'Cast'
        LEFT JOIN shooting_day_scenes sds ON sds.scene_id = s.id
        WHERE s.project_id = ?
        GROUP BY s.id
        ORDER BY shoot_day, s.scene_number
        """,
        (project_id,),
    ).fetchall()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "SceneNum",
            "D/N",
            "I/E",
            "Location",
            "Pages",
            "Cast",
            "Description",
            "ShootDay",
        ]
    )
    for r in rows:
        eighths = r["eighths"] or 0
        pages = f"{eighths // 8} {eighths % 8}/8" if eighths else "1/8"
        w.writerow(
            [
                r["scene_number"],
                r["day_night"],
                r["int_ext"],
                r["location"],
                pages,
                r["cast_names"] or "",
                (r["synopsis"] or "")[:100],
                r["shoot_day"],
            ]
        )
    return buf.getvalue().encode("utf-8-sig")  # BOM for Excel IT
