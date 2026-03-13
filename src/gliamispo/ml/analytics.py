import time


class MLAnalyticsService:
    def __init__(self, database):
        self._db = database

    def record_prediction(self, scene_id, category, confidence, method):
        self._db.execute(
            "INSERT INTO ml_analytics "
            "(scene_id, category, confidence, method, created_at) "
            "VALUES (?,?,?,?,?)",
            (scene_id, category, confidence, method, int(time.time()))
        )

    def acceptance_rate(self, method=None):
        if method:
            row = self._db.execute(
                "SELECT "
                "  SUM(CASE WHEN action='VERIFY' THEN 1 ELSE 0 END) * 1.0 "
                "  / NULLIF(COUNT(*), 0) "
                "FROM user_corrections uc "
                "JOIN scene_elements se ON se.id = uc.element_id "
                "WHERE se.detection_method = ?",
                (method,)
            ).fetchone()
        else:
            row = self._db.execute(
                "SELECT "
                "  SUM(CASE WHEN action='VERIFY' THEN 1 ELSE 0 END) * 1.0 "
                "  / NULLIF(COUNT(*), 0) "
                "FROM user_corrections "
                "WHERE action IN ('VERIFY','REJECT')"
            ).fetchone()
        return row[0] if row and row[0] is not None else 0.0

    def correction_count(self):
        row = self._db.execute(
            "SELECT COUNT(*) FROM user_corrections WHERE trained_at IS NULL"
        ).fetchone()
        return row[0] if row else 0

    def pending_training_scenes(self):
        rows = self._db.execute(
            "SELECT COUNT(*) FROM training_data WHERE trained_at IS NULL"
        ).fetchone()
        return rows[0] if rows else 0
