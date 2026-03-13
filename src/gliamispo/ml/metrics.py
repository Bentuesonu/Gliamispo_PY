import json
import time
from sklearn.metrics import (
    f1_score, precision_score, recall_score,
    classification_report, confusion_matrix,
)
from sklearn.model_selection import train_test_split


def evaluate_model(clf, texts, labels):
    if len(texts) < 10:
        return {"error": "dataset troppo piccolo", "dataset_size": len(texts)}

    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42,
        stratify=labels if len(set(labels)) > 1 else None,
    )

    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)

    f1_weighted = float(f1_score(y_test, y_pred, average="weighted", zero_division=0))
    f1_macro    = float(f1_score(y_test, y_pred, average="macro",    zero_division=0))
    precision   = float(precision_score(y_test, y_pred, average="weighted", zero_division=0))
    recall      = float(recall_score(y_test,    y_pred, average="weighted", zero_division=0))

    report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)

    labels_uniq = sorted(set(y_test) | set(y_pred))
    cm = confusion_matrix(y_test, y_pred, labels=labels_uniq).tolist()

    return {
        "f1_weighted": f1_weighted,
        "f1_macro": f1_macro,
        "precision": precision,
        "recall": recall,
        "category_metrics": report,
        "confusion_matrix": {"labels": labels_uniq, "matrix": cm},
        "test_size": len(y_test),
        "train_size": len(X_train),
        "evaluated_at": int(time.time()),
    }


def save_metrics_to_db(db, model_version, metrics):
    db.execute("""
        UPDATE ml_model_versions SET
            f1_score              = ?,
            precision             = ?,
            recall                = ?,
            category_metrics      = ?,
            confusion_matrix      = ?,
            training_dataset_size = ?
        WHERE version = ?
    """, (
        metrics.get("f1_weighted"),
        metrics.get("precision"),
        metrics.get("recall"),
        json.dumps(metrics.get("category_metrics", {})),
        json.dumps(metrics.get("confusion_matrix", {})),
        metrics.get("train_size", 0) + metrics.get("test_size", 0),
        model_version,
    ))
    db.commit()


def get_metrics_summary(db):
    row = db.execute("""
        SELECT version, f1_score, precision, recall,
               category_metrics, training_dataset_size, trained_on
        FROM ml_model_versions
        WHERE is_active = 1
        ORDER BY trained_on DESC LIMIT 1
    """).fetchone()

    if not row:
        return None

    return {
        "version": row[0],
        "f1_score": row[1],
        "precision": row[2],
        "recall": row[3],
        "category_metrics": json.loads(row[4]) if row[4] else {},
        "dataset_size": row[5],
        "trained_on": row[6],
    }
