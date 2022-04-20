"""Contains endpoint for the API.

Todo:
    * add check for size error in recieve_file
    * add more endpoints
"""

import dataclasses

import fastapi
import httpx

# f# rom app.api.models import UploadReponseNew, UploadResponse
from app.grobid.client import Client, GrobidClientError
from app.grobid.models.form import File, Form
from app.grobid.tei import TEI, GrobidParserError
from fastapi import APIRouter, HTTPException, UploadFile, status
from spacy import load

from app.config import get_settings

router = APIRouter()


@router.on_event("startup")
def load_globals():
    """Load instances once."""
    global model
    model = load("en_core_web_sm")
    global settings
    settings = get_settings()


@router.post("/upload")
async def recieve_file(file: UploadFile = fastapi.File(...)):
    """Parse uploaded file.

    Args:
        file: file which is uploaded
    Returns:
        Article object
    Raises:
        HTTPException: the file cannot be parsed
    """
    if file.content_type != "application/pdf":
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Invalid document type"
        )

    contents = await file.read()
    # TODO: use PyMUPDF to check if document is corrupted
    if not isinstance(contents, bytes):
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Couldn't read document"
        )

    form = Form(
        file=File(
            payload=contents, file_name=file.filename, mime_type=file.content_type
        )
    )

    try:
        client = Client(api_url=settings.grobid_api_url, form=form)
        response = await client.asyncio_request()
    except GrobidClientError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    tei = TEI(response.content, model)

    try:
        article = tei.parse()
    except GrobidParserError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    try:
        return dataclasses.asdict(article)
    except TypeError:
        return HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Couldn't serialise response object",
        )


@router.get("/validate_url/")
async def validate_pdf_url(url: str):
    """Check to see if URL of a PDF is valid.

    Args:
        url: url to be validated
    Returns:
        Status code and detail of request
    Raises:
        HTTPException: URL of a PDF is invalid
    """
    try:
        async with httpx.AsyncClient() as client:
            res = await client.head(url)

        if res.status_code != 200:
            raise HTTPException(
                status_code=res.status_code, detail="Request unsuccessful"
            )
        if res.headers["Content-Type"] != "application/pdf":
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="File has unsupported extension type",
            )
        return {"detail": "PDF URL is valid"}
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while requesting {exc.request.url!r}.",
        )
