"""Authenticated XLSX uploads; business writes happen only after confirmation."""
from pathlib import Path
import hashlib
import os
from uuid import UUID, uuid4
from zipfile import BadZipFile, ZipFile
from xml.etree.ElementTree import ParseError
from openpyxl.utils.exceptions import InvalidFileException

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ingest.erp_repository import ERPConflict
from ..erp_import_repository import create_request, get_request, list_requests, public_preview, preview_request, confirm_request
from ..schemas import ERPConfirmInput, ERPPreviewInput
from ..security import Identity, get_current_identity, require_site, require_site_roles

router = APIRouter(prefix='/api/v1', tags=['erp-imports'])
UPLOAD_ROOT = Path(os.getenv('ERP_UPLOAD_ROOT', 'data/raw/uploads'))
MAX_COMPRESSED = 20 * 1024 * 1024
MAX_EXPANDED = 100 * 1024 * 1024


def request_for_identity(import_id, identity):
    request = get_request(import_id)
    if not request:
        raise HTTPException(404, 'import_not_found')
    require_site(identity, request['site_id'])
    return request


@router.post('/sites/{site_id}/erp-imports', status_code=202)
async def upload(site_id: int, file: UploadFile = File(...), identity: Identity = Depends(get_current_identity)):
    require_site_roles(identity, site_id, 'analyst', 'supervisor', 'admin')
    name = Path((file.filename or '').replace('\\', '/')).name
    if not name.lower().endswith('.xlsx'):
        raise HTTPException(415, 'xlsx_required')
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_ROOT / f'{uuid4()}.xlsx'
    digest, size = hashlib.sha256(), 0
    try:
        with path.open('xb') as target:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_COMPRESSED:
                    raise HTTPException(413, 'xlsx_too_large')
                digest.update(chunk)
                target.write(chunk)
        try:
            with ZipFile(path) as archive:
                if sum(info.file_size for info in archive.infolist()) > MAX_EXPANDED:
                    raise HTTPException(413, 'xlsx_expanded_too_large')
                if not {'[Content_Types].xml', 'xl/workbook.xml'} <= set(archive.namelist()):
                    raise HTTPException(415, 'invalid_xlsx')
                if any(info.flag_bits & 1 for info in archive.infolist()):
                    raise HTTPException(415, 'encrypted_xlsx_unsupported')
        except BadZipFile:
            raise HTTPException(415, 'invalid_xlsx') from None
        return create_request(site_id=site_id, creator_id=identity.user_id, raw_path=str(path.resolve()), original_name=name[:255], file_hash=digest.hexdigest())
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


@router.get('/sites/{site_id}/erp-imports')
def journal(site_id: int, identity: Identity = Depends(get_current_identity)):
    require_site(identity, site_id)
    return {'items': list_requests(site_id)}


@router.get('/erp-imports/{import_id}/preview')
def preview(import_id: UUID, refresh: bool = False, identity: Identity = Depends(get_current_identity)):
    request = request_for_identity(import_id, identity)
    if refresh:
        require_site_roles(identity, request['site_id'], 'analyst', 'supervisor', 'admin')
        raise HTTPException(405, 'use_preview_refresh_post')
    return public_preview(request)


@router.post('/erp-imports/{import_id}/preview/refresh')
def refresh_preview(import_id: UUID, identity: Identity = Depends(get_current_identity)):
    request = request_for_identity(import_id, identity)
    require_site_roles(identity, request['site_id'], 'analyst', 'supervisor', 'admin')
    try:
        return preview_request(import_id, refresh=True)
    except ERPConflict as error:
        raise HTTPException(409, str(error)) from None
    except (ValueError, KeyError, BadZipFile, OSError, ParseError, InvalidFileException):
        raise HTTPException(422, 'xlsx_preview_failed') from None


@router.put('/erp-imports/{import_id}/preview')
def configure_preview(import_id: UUID, payload: ERPPreviewInput, identity: Identity = Depends(get_current_identity)):
    request = request_for_identity(import_id, identity)
    require_site_roles(identity, request['site_id'], 'analyst', 'supervisor', 'admin')
    try:
        return preview_request(import_id, refresh=True, choices=payload.model_dump(mode='json'))
    except ERPConflict as error:
        raise HTTPException(409, str(error)) from None
    except (ValueError, KeyError, BadZipFile, OSError, ParseError, InvalidFileException):
        raise HTTPException(422, 'xlsx_preview_failed') from None


@router.post('/erp-imports/{import_id}/confirm', status_code=202)
def confirm(import_id: UUID, payload: ERPConfirmInput, identity: Identity = Depends(get_current_identity)):
    request = request_for_identity(import_id, identity)
    require_site_roles(identity, request['site_id'], 'analyst', 'supervisor', 'admin')
    try:
        return confirm_request(import_id, payload.model_dump(mode='json'))
    except ERPConflict as error:
        raise HTTPException(409, str(error)) from None
