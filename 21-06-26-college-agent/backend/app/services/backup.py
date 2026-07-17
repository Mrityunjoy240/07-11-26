import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class BackupService:
    def __init__(self, backup_dir: str | None = None):
        self.backup_dir = Path(backup_dir or Path.cwd() / "backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Backup directory initialized at {self.backup_dir}")

    def create_backup(self):
        dummy_file = self.backup_dir / "dummy_backup.txt"
        dummy_file.write_text("backup placeholder")
        logger.info("Created dummy backup file")
        return {"message": "Backup created", "file": str(dummy_file)}

    def list_backups(self):
        files = [f.name for f in self.backup_dir.iterdir() if f.is_file()]
        return {"backups": files}

    def delete_backup(self, filename: str) -> bool:
        target = self.backup_dir / filename
        if target.exists():
            target.unlink()
            logger.info(f"Deleted backup {filename}")
            return True
        logger.warning(f"Backup file {filename} not found for deletion")
        return False
