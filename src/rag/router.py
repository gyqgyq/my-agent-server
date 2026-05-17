from typing import Annotated

from fastapi import APIRouter, File, UploadFile, status

from src.core.security import CurrentUserIdDep
from src.db.postgres import SessionDep
from src.rag import schemas, service

router = APIRouter(prefix="/works", tags=["作品与知识库"])


@router.post("", response_model=schemas.WorkOut, status_code=status.HTTP_201_CREATED)
async def create_work(
    body: schemas.WorkCreate,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> schemas.WorkOut:
    work = await service.create_work(session, user_id, body.title)
    return schemas.WorkOut.model_validate(work)


@router.get("", response_model=list[schemas.WorkOut])
async def list_works(
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> list[schemas.WorkOut]:
    works = await service.list_works(session, user_id)
    return [schemas.WorkOut.model_validate(w) for w in works]


@router.get("/{work_id}", response_model=schemas.WorkOut)
async def get_work(
    work_id: int,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> schemas.WorkOut:
    work = await service.get_work_for_user(session, work_id, user_id)
    return schemas.WorkOut.model_validate(work)


@router.patch("/{work_id}", response_model=schemas.WorkOut)
async def update_work(
    work_id: int,
    body: schemas.WorkUpdate,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> schemas.WorkOut:
    work = await service.update_work_title(session, work_id, user_id, body.title)
    return schemas.WorkOut.model_validate(work)


@router.delete("/{work_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work(
    work_id: int,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> None:
    await service.delete_work(session, work_id, user_id)


@router.get("/{work_id}/documents", response_model=list[schemas.DocumentOut])
async def list_documents(
    work_id: int,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> list[schemas.DocumentOut]:
    docs = await service.list_documents(session, work_id, user_id)
    return [schemas.DocumentOut.model_validate(d) for d in docs]


@router.post(
    "/{work_id}/documents",
    response_model=schemas.DocumentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    work_id: int,
    user_id: CurrentUserIdDep,
    session: SessionDep,
    file: Annotated[UploadFile, File()],
) -> schemas.DocumentOut:
    doc = await service.upload_document(session, work_id, user_id, file)
    return schemas.DocumentOut.model_validate(doc)


@router.delete(
    "/{work_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    work_id: int,
    document_id: int,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> None:
    await service.delete_document(session, work_id, document_id, user_id)
