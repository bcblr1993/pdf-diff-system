"""外部 API 鉴权：X-API-Key Header。"""
from __future__ import annotations
from typing import Annotated
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.db.models import ApiKey
from app.services.api_key import verify_key, touch_usage


def require_api_key(
    db: Annotated[Session, Depends(get_db)],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key", description="API Key")] = None,
) -> ApiKey:
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 X-API-Key Header",
            headers={"WWW-Authenticate": 'ApiKey realm="pdf-diff"'},
        )
    rec = verify_key(db, x_api_key)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或已过期的 API Key",
        )
    touch_usage(db, rec)
    db.commit()
    return rec


CurrentApiKey = Annotated[ApiKey, Depends(require_api_key)]
