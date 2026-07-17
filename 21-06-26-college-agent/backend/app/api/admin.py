import json
import logging
import os
import shutil
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from app.auth import get_current_admin
from app.config import settings
from app.services.backup import BackupService
from app.services.document_processor import DocumentProcessor

logger = logging.getLogger(__name__)
router = APIRouter()

document_processor = DocumentProcessor(settings.upload_dir)
backup_service = BackupService()


@router.post("/upload")
async def upload_files(
    files: Annotated[list[UploadFile], File(...)],
    current_user: Annotated[str, Depends(get_current_admin)],
    background_tasks: BackgroundTasks = None,
):
    uploaded_files = []
    os.makedirs(settings.upload_dir, exist_ok=True)
    for file in files:
        file_path = os.path.join(settings.upload_dir, file.filename)
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            uploaded_files.append(file.filename)
        except Exception as e:
            logger.error(f"Error saving file {file.filename}: {e}")
    if background_tasks:
        background_tasks.add_task(process_and_index_files, uploaded_files)
    return {"message": f"Successfully uploaded {len(uploaded_files)} files", "files": uploaded_files}


@router.get("/files")
async def list_files(current_user: str = Depends(get_current_admin)):
    try:
        if not os.path.exists(settings.upload_dir):
            return {"files": []}
        files = os.listdir(settings.upload_dir)
        file_list = []
        storage_file = Path(settings.db_dir) / "documents.json"
        processed_sources = set()
        if storage_file.exists():
            try:
                with open(storage_file, encoding="utf-8") as f:
                    all_documents = json.load(f)
                    processed_sources = {doc["source"] for doc in all_documents}
            except Exception as e:
                logger.error(f"Error loading existing documents: {e}")
        for f in files:
            file_path = os.path.join(settings.upload_dir, f)
            file_list.append({
                "filename": f,
                "size": os.path.getsize(file_path),
                "processed": f in processed_sources,
                "uploaded_at": os.path.getmtime(file_path),
            })
        return {"files": file_list}
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


async def process_and_index_files(filenames: list[str]):
    all_documents = []
    storage_file = Path(settings.db_dir) / "documents.json"
    os.makedirs(settings.db_dir, exist_ok=True)
    if storage_file.exists():
        try:
            with open(storage_file, encoding="utf-8") as f:
                all_documents = json.load(f)
        except Exception as e:
            logger.error(f"Error loading existing documents: {e}")
    new_docs = []
    for filename in filenames:
        file_path = os.path.join(settings.upload_dir, filename)
        try:
            docs = await document_processor.process_file(file_path)
            new_docs.extend(docs)
            logger.info(f"Processed {filename}: {len(docs)} chunks")
        except Exception as e:
            logger.error(f"Error processing {filename}: {e}")
    processed_sources = {doc["source"] for doc in new_docs}
    all_documents = [doc for doc in all_documents if doc.get("source") not in processed_sources]
    all_documents.extend(new_docs)
    try:
        with open(storage_file, "w", encoding="utf-8") as f:
            json.dump(all_documents, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(all_documents)} documents to {storage_file}")
    except Exception as e:
        logger.error(f"Error saving documents: {e}")


@router.post("/backup/create")
async def create_backup(current_user: str = Depends(get_current_admin)):
    try:
        result = backup_service.create_backup()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/backups")
async def list_backups(current_user: str = Depends(get_current_admin)):
    try:
        return backup_service.list_backups()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/backup/{filename}")
async def delete_backup(filename: str, current_user: str = Depends(get_current_admin)):
    if backup_service.delete_backup(filename):
        return {"message": "Backup deleted"}
    raise HTTPException(status_code=404, detail="Backup not found")
