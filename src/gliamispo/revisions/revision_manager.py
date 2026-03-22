# src/gliamispo/revisions/revision_manager.py

HOLLYWOOD_COLORS = {
    1:  ("white",     "#FFFFFF", "#000000"),
    2:  ("blue",      "#ADD8E6", "#000000"),
    3:  ("pink",      "#FFB6C1", "#000000"),
    4:  ("yellow",    "#FFFF99", "#000000"),
    5:  ("green",     "#90EE90", "#000000"),
    6:  ("goldenrod", "#DAA520", "#FFFFFF"),
    7:  ("buff",      "#F0DC82", "#000000"),
    8:  ("salmon",    "#FA8072", "#FFFFFF"),
    9:  ("cherry",    "#DE3163", "#FFFFFF"),
    10: ("tan",       "#D2B48C", "#000000"),
}


class RevisionManager:
    def __init__(self, db):
        self._db = db

    def import_revision(self, project_id: int, file_path: str, notes: str = "") -> int:
        count = self._db.execute(
            "SELECT COUNT(*) FROM script_revisions WHERE project_id=?",
            (project_id,)
        ).fetchone()[0]
        rev_num = count + 1
        color_name = HOLLYWOOD_COLORS.get(rev_num % 10 or 10, HOLLYWOOD_COLORS[10])[0]

        rev_id = self._db.execute(
            "INSERT INTO script_revisions"
            " (project_id, revision_number, revision_color, notes, file_path, is_current)"
            " VALUES (?,?,?,?,?,1)",
            (project_id, rev_num, color_name, notes, file_path)
        ).lastrowid

        # ✅ CRITICO: entrambi i placeholder '?' presenti (bug delle guide v1/v2 corretto)
        self._db.execute(
            "UPDATE script_revisions SET is_current=0"
            " WHERE project_id=? AND id!=?",
            (project_id, rev_id)
        )
        self._db.commit()
        return rev_id

    def get_color_for_revision(self, rev_num: int) -> tuple:
        return HOLLYWOOD_COLORS.get(rev_num % 10 or 10, HOLLYWOOD_COLORS[1])

    def get_revisions(self, project_id: int) -> list:
        return self._db.execute(
            "SELECT id, revision_number, revision_color, imported_at,"
            " notes, file_path, is_current"
            " FROM script_revisions WHERE project_id=?"
            " ORDER BY revision_number DESC",
            (project_id,)
        ).fetchall()

    def set_current(self, project_id: int, rev_id: int):
        self._db.execute(
            "UPDATE script_revisions SET is_current=0 WHERE project_id=?",
            (project_id,)
        )
        self._db.execute(
            "UPDATE script_revisions SET is_current=1 WHERE id=?",
            (rev_id,)
        )
        self._db.commit()