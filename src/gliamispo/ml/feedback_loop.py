import threading
import time
import pickle
import os
from platformdirs import user_data_dir
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from gliamispo.ml.metrics import evaluate_model, save_metrics_to_db


class FeedbackLoopService:
    FLUSH_THRESHOLD = 10
    RETRAIN_THRESHOLD = 50
    MODEL_VERSION_PREFIX = "v1"

    def __init__(self, database, model_dir=None):
        self._db = database
        self._queue = []
        self._lock = threading.Lock()

        self._model_dir = model_dir or user_data_dir("Gliamispo", appauthor=False)
        os.makedirs(self._model_dir, exist_ok=True)

    def track_import(self, scene_id, element_count):
        with self._lock:
            self._queue.append({"scene_id": scene_id, "element_count": element_count})
            if len(self._queue) >= self.FLUSH_THRESHOLD:
                self._flush()

    def _flush(self):
        for entry in self._queue:
            self._db.execute(
                "INSERT INTO training_data (scene_id, scene_text, created_at) "
                "SELECT id, synopsis, strftime('%s','now') FROM scenes "
                "WHERE id = ? AND NOT EXISTS ("
                "  SELECT 1 FROM training_data td WHERE td.scene_id = scenes.id"
                ")",
                (entry["scene_id"],)
            )
        self._queue.clear()

    def record_category_change(self, element_id, scene_id,
                               before_cat, after_cat, confidence):
        self._db.execute(
            "INSERT INTO user_corrections "
            "(element_id, scene_id, action, before_category, "
            "after_category, original_confidence) "
            "VALUES (?,?,'MODIFY_CATEGORY',?,?,?)",
            (element_id, scene_id, before_cat, after_cat, confidence)
        )
        self._check_retrain()

    def track_verification(self, element_id, scene_id, accepted):
        action = "VERIFY" if accepted else "REJECT"
        self._db.execute(
            "INSERT INTO user_corrections "
            "(element_id, scene_id, action) VALUES (?,?,?)",
            (element_id, scene_id, action)
        )
        self._check_retrain()

    def record_deletion(self, element_id, scene_id, element_name, category):
        self._db.execute(
            "INSERT INTO user_corrections "
            "(element_id, scene_id, action, before_category, before_name) "
            "VALUES (?,?,'REJECT',?,?)",
            (element_id, scene_id, category, element_name)
        )
        self._check_retrain()

    def _on_retrain_needed(self):
        pass

    def _check_retrain(self):
        row = self._db.execute(
            "SELECT COUNT(*) FROM user_corrections WHERE trained_at IS NULL"
        ).fetchone()
        if row and row[0] >= self.RETRAIN_THRESHOLD:
            self._on_retrain_needed()
            t = threading.Thread(target=self._retrain_model, daemon=True)
            t.start()

    def _retrain_model(self):
        rows = self._db.execute("""
            SELECT
                se.element_name || ' ' || COALESCE(sc.synopsis, ''),
                uc.after_category
            FROM user_corrections uc
            JOIN scene_elements se ON se.id = uc.element_id
            LEFT JOIN scenes sc ON sc.id = se.scene_id
            WHERE uc.action = 'MODIFY_CATEGORY'
              AND uc.after_category IS NOT NULL
              AND se.element_name IS NOT NULL
        """).fetchall()

        if len(rows) < 10:
            return

        verified_rows = self._db.execute("""
            SELECT
                se.element_name || ' ' || COALESCE(sc.synopsis, ''),
                se.category
            FROM user_corrections uc
            JOIN scene_elements se ON se.id = uc.element_id
            LEFT JOIN scenes sc ON sc.id = se.scene_id
            WHERE uc.action = 'VERIFY'
              AND se.element_name IS NOT NULL
        """).fetchall()

        reject_rows = self._db.execute("""
            SELECT
                uc.before_name || ' ' || COALESCE(sc.synopsis, ''),
                'REJECTED'
            FROM user_corrections uc
            LEFT JOIN scenes sc ON sc.id = uc.scene_id
            WHERE uc.action = 'REJECT'
              AND uc.before_name IS NOT NULL
        """).fetchall()

        all_rows = list(rows) + list(verified_rows) + list(reject_rows)

        texts = [r[0] for r in all_rows]
        labels = [r[1] for r in all_rows]

        if len(set(labels)) < 2:
            return

        try:
            clf = Pipeline([
                ("vec", TfidfVectorizer(
                    ngram_range=(1, 3),
                    min_df=1,
                    analyzer="word",
                    sublinear_tf=True,
                )),
                ("cls", LogisticRegression(
                    max_iter=1000,
                    C=1.0,
                    class_weight="balanced",
                    random_state=42,
                )),
            ])
            clf.fit(texts, labels)
        except Exception as e:
            print(f"[FeedbackLoop] Errore training: {e}")
            return

        version = f"{self.MODEL_VERSION_PREFIX}.{int(time.time())}"
        model_path = os.path.join(self._model_dir, f"model_{version}.pkl")

        f1 = None
        metrics = None
        if len(all_rows) >= 20:
            metrics = evaluate_model(
                Pipeline([
                    ("vec", TfidfVectorizer(
                        ngram_range=(1, 3),
                        min_df=1,
                        analyzer="word",
                        sublinear_tf=True,
                    )),
                    ("cls", LogisticRegression(
                        max_iter=1000,
                        C=1.0,
                        class_weight="balanced",
                        random_state=42,
                    )),
                ]),
                texts, labels,
            )
            f1 = metrics.get("f1_weighted")
            print(f"[FeedbackLoop] F1={f1:.3f} | "
                  f"Precision={metrics['precision']:.3f} | "
                  f"Recall={metrics['recall']:.3f}")

        bundle = {
            "vectorizer": clf.named_steps["vec"],
            "classifier": clf.named_steps["cls"],
            "version": version,
            "trained_at": int(time.time()),
            "dataset_size": len(all_rows),
        }
        with open(model_path, "wb") as f:
            pickle.dump(bundle, f)

        self._db.execute(
            "UPDATE user_corrections SET trained_at = ? WHERE trained_at IS NULL",
            (int(time.time()),)
        )

        self._db.execute("UPDATE ml_model_versions SET is_active = 0")
        self._db.execute("""
            INSERT OR REPLACE INTO ml_model_versions
            (model_name, version, model_path, trained_on,
             training_dataset_size, f1_score, is_active)
            VALUES ('sklearn_tfidf', ?, ?, ?, ?, ?, 1)
        """, (version, model_path, int(time.time()), len(all_rows), f1))
        self._db.commit()

        if metrics is not None:
            save_metrics_to_db(self._db, version, metrics)

        active_link = os.path.join(self._model_dir, "model.pkl")
        if os.path.exists(active_link):
            os.remove(active_link)
        import shutil
        shutil.copy2(model_path, active_link)

        print(f"[FeedbackLoop] Retraining completato → {version}")