"""Modulo per backup giornaliero del database SQLite."""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

BACKUP_PREFIX = "gliamispo_"
BACKUP_SUFFIX = ".sqlite"
RETENTION_DAYS = 30


def run_daily_backup(db_path: str, backup_dir: str | None = None) -> Path | None:
    """
    Esegue un backup giornaliero del database SQLite.

    Args:
        db_path: Percorso del database da backuppare.
        backup_dir: Cartella di destinazione. Se None, usa <db_dir>/backups/.

    Returns:
        Path del backup creato, oppure None se il backup per oggi esiste già
        o se si è verificato un errore.
    """
    try:
        db_path_obj = Path(db_path)

        if backup_dir is None:
            backup_dir_path = db_path_obj.parent / "backups"
        else:
            backup_dir_path = Path(backup_dir)

        backup_dir_path.mkdir(parents=True, exist_ok=True)

        today_str = datetime.now().strftime("%Y%m%d")
        backup_filename = f"{BACKUP_PREFIX}{today_str}{BACKUP_SUFFIX}"
        backup_path = backup_dir_path / backup_filename

        if backup_path.exists():
            logger.info("Backup per oggi già esistente: %s", backup_path)
            return None

        logger.info("Avvio backup database: %s -> %s", db_path, backup_path)

        source_conn = sqlite3.connect(db_path)
        dest_conn = sqlite3.connect(str(backup_path))

        try:
            source_conn.backup(dest_conn)
            logger.info("Backup completato: %s", backup_path)
        finally:
            dest_conn.close()
            source_conn.close()

        _cleanup_old_backups(backup_dir_path)

        return backup_path

    except Exception:
        logger.exception("Errore durante il backup del database")
        return None


def _cleanup_old_backups(backup_dir: Path) -> None:
    """Rimuove i backup più vecchi di RETENTION_DAYS giorni."""
    try:
        cutoff_date = datetime.now() - timedelta(days=RETENTION_DAYS)
        cutoff_str = cutoff_date.strftime("%Y%m%d")

        for backup_file in backup_dir.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}"):
            date_part = backup_file.stem.replace(BACKUP_PREFIX, "")

            if len(date_part) == 8 and date_part.isdigit():
                if date_part < cutoff_str:
                    backup_file.unlink()
                    logger.info("Backup vecchio rimosso: %s", backup_file)

    except Exception:
        logger.exception("Errore durante la pulizia dei backup vecchi")
