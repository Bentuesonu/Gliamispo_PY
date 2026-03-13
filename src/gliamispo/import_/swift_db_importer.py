import sqlite3

from gliamispo.models.eighths import Eighths


def _get(row, key, default=None):
    try:
        v = row[key]
        return v if v is not None else default
    except (KeyError, IndexError):
        return default


def _has(row, key):
    if isinstance(row, sqlite3.Row):
        return key in row.keys()
    return key in row


class SwiftDbImporter:
    def import_db(self, source_path, target_conn):
        src = sqlite3.connect(source_path)
        src.row_factory = sqlite3.Row
        try:
            schema_type = self._detect_schema(src)
            project_id_map = self._import_projects(src, target_conn)
            scene_id_map = self._import_scenes(
                src, target_conn, schema_type, project_id_map
            )
            elem_count = self._import_elements(src, target_conn, scene_id_map)
            target_conn.commit()
            return {
                "schema_type": schema_type,
                "projects": len(project_id_map),
                "scenes": len(scene_id_map),
                "elements": elem_count,
            }
        finally:
            src.close()

    def _detect_schema(self, conn):
        cols = [c[1] for c in conn.execute("PRAGMA table_info(scenes)").fetchall()]
        if "page_start" in cols:
            return "pre_v6"
        has_backup = (
            conn.execute(
                "SELECT 1 FROM sqlite_master"
                " WHERE type='table' AND name='scenes_backup_v5'"
            ).fetchone()
            is not None
        )
        if has_backup and "estimated_crew_size" not in cols:
            return "post_v6_buggy"
        return "post_v6_clean"

    def _import_projects(self, src, target):
        rows = src.execute("SELECT * FROM projects").fetchall()
        id_map = {}
        for r in rows:
            cur = target.execute(
                "INSERT INTO projects"
                " (title, director, production_company,"
                " created_date, last_modified, language, currency)"
                " VALUES (?,?,?,?,?,?,?)",
                (
                    r["title"],
                    _get(r, "director"),
                    _get(r, "production_company"),
                    _get(r, "created_date"),
                    _get(r, "last_modified"),
                    _get(r, "language"),
                    _get(r, "currency"),
                ),
            )
            id_map[r["id"]] = cur.lastrowid
        return id_map

    def _import_scenes(self, src, target, schema_type, project_id_map):
        id_map = {}
        if schema_type == "pre_v6":
            rows = src.execute("SELECT * FROM scenes").fetchall()
            for r in rows:
                ps = _get(r, "page_start", 1.0) or 1.0
                pe = _get(r, "page_end", 1.0) or 1.0
                start_e = Eighths.from_decimal(ps)
                end_e = Eighths.from_decimal(pe)
                # ensure end >= start
                if end_e.total_eighths < start_e.total_eighths:
                    end_e = start_e
                new_pid = project_id_map.get(r["project_id"], r["project_id"])
                cur = target.execute(
                    "INSERT INTO scenes"
                    " (project_id, scene_number, location,"
                    " int_ext, day_night,"
                    " page_start_whole, page_start_eighths,"
                    " page_end_whole, page_end_eighths,"
                    " synopsis, story_day, requires_intimacy_coordinator,"
                    " estimated_crew_size, special_requirements, created_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        new_pid,
                        _get(r, "scene_number"),
                        _get(r, "location"),
                        r["int_ext"],
                        r["day_night"],
                        start_e.whole,
                        start_e.eighths,
                        end_e.whole,
                        end_e.eighths,
                        _get(r, "synopsis"),
                        _get(r, "story_day", 1),
                        _get(r, "requires_intimacy_coordinator", 0),
                        _get(r, "estimated_crew_size"),
                        _get(r, "special_requirements"),
                        _get(r, "created_at"),
                    ),
                )
                id_map[r["id"]] = cur.lastrowid

        elif schema_type == "post_v6_buggy":
            backup_map = {}
            for br in src.execute("SELECT * FROM scenes_backup_v5").fetchall():
                backup_map[br["id"]] = {
                    "estimated_crew_size": _get(br, "estimated_crew_size"),
                    "special_requirements": _get(br, "special_requirements"),
                }
            rows = src.execute("SELECT * FROM scenes").fetchall()
            for r in rows:
                bk = backup_map.get(r["id"], {})
                new_pid = project_id_map.get(r["project_id"], r["project_id"])
                cur = target.execute(
                    "INSERT INTO scenes"
                    " (project_id, scene_number, location,"
                    " int_ext, day_night,"
                    " page_start_whole, page_start_eighths,"
                    " page_end_whole, page_end_eighths,"
                    " synopsis, story_day, requires_intimacy_coordinator,"
                    " estimated_crew_size, special_requirements, created_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        new_pid,
                        _get(r, "scene_number"),
                        _get(r, "location"),
                        r["int_ext"],
                        r["day_night"],
                        r["page_start_whole"],
                        r["page_start_eighths"],
                        r["page_end_whole"],
                        r["page_end_eighths"],
                        _get(r, "synopsis"),
                        _get(r, "story_day", 1),
                        _get(r, "requires_intimacy_coordinator", 0),
                        bk.get("estimated_crew_size"),
                        bk.get("special_requirements"),
                        _get(r, "created_at"),
                    ),
                )
                id_map[r["id"]] = cur.lastrowid

        else:  # post_v6_clean
            rows = src.execute("SELECT * FROM scenes").fetchall()
            for r in rows:
                new_pid = project_id_map.get(r["project_id"], r["project_id"])
                cur = target.execute(
                    "INSERT INTO scenes"
                    " (project_id, scene_number, location,"
                    " int_ext, day_night,"
                    " page_start_whole, page_start_eighths,"
                    " page_end_whole, page_end_eighths,"
                    " synopsis, story_day, requires_intimacy_coordinator,"
                    " estimated_crew_size, special_requirements, created_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        new_pid,
                        _get(r, "scene_number"),
                        _get(r, "location"),
                        r["int_ext"],
                        r["day_night"],
                        r["page_start_whole"],
                        r["page_start_eighths"],
                        r["page_end_whole"],
                        r["page_end_eighths"],
                        _get(r, "synopsis"),
                        _get(r, "story_day", 1),
                        _get(r, "requires_intimacy_coordinator", 0),
                        _get(r, "estimated_crew_size"),
                        _get(r, "special_requirements"),
                        _get(r, "created_at"),
                    ),
                )
                id_map[r["id"]] = cur.lastrowid

        return id_map

    def _import_elements(self, src, target, scene_id_map):
        # De-duplicazione: per ogni (scene_id, category, element_name) tiene MAX(id)
        # Necessario per DB pre-V6 dove il vincolo UNIQUE non esisteva
        rows = src.execute(
            "SELECT * FROM scene_elements"
            " WHERE id IN ("
            "  SELECT MAX(id) FROM scene_elements"
            "  GROUP BY scene_id, category, element_name"
            " )"
            " ORDER BY id"
        ).fetchall()

        inserted = 0
        for r in rows:
            new_sid = scene_id_map.get(r["scene_id"], r["scene_id"])
            conf = _get(r, "ai_confidence")
            if conf is not None:
                conf = max(0.0, min(1.0, float(conf)))
            qty = _get(r, "quantity", 1) or 1
            if qty < 1:
                qty = 1
            try:
                target.execute(
                    "INSERT OR IGNORE INTO scene_elements"
                    " (scene_id, category, element_name, quantity, notes,"
                    " ai_suggested, ai_confidence, user_verified)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (
                        new_sid,
                        r["category"],
                        r["element_name"],
                        qty,
                        _get(r, "notes"),
                        _get(r, "ai_suggested", 0),
                        conf,
                        _get(r, "user_verified", 0),
                    ),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                pass
        return inserted
