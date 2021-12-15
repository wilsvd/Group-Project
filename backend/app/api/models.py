"""Contains response models for the routes module.

Todo:
    * Add model for /validate_url
"""
from pydantic import BaseModel


class UploadResponse(BaseModel):
    """Object used as a response model for /upload endpoint.

    Models public properties in Parser

    Todo:
        * Add new properties to model
    """

    title: str
    metadata: dict[str, str]
    toc: list
    summary: list[str]
    common_words: list[tuple[str, int]]