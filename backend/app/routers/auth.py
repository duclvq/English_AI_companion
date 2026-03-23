from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.schemas.auth import RegisterRequest, LoginRequest, RefreshRequest
from app.services import auth_service
from app.models.user import RefreshToken

router = APIRouter()


def _auth_response(access_token: str, refresh_token: str, response: Response) -> dict:
    response.set_cookie(
        "refresh_token", refresh_token,
        httponly=True, secure=False, samesite="lax", max_age=7 * 86400,
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register")
async def register(body: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    try:
        user = await auth_service.register_user(body.email, body.password, db)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    access_token = auth_service.create_access_token(user.id)
    refresh_token = await auth_service.create_refresh_token(user.id, db)
    return _auth_response(access_token, refresh_token, response)


@router.post("/login")
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    try:
        user = await auth_service.authenticate_user(body.email, body.password, db)
    except ValueError:
        raise HTTPException(401, detail="Invalid credentials")
    access_token = auth_service.create_access_token(user.id)
    refresh_token = await auth_service.create_refresh_token(user.id, db)
    return _auth_response(access_token, refresh_token, response)


@router.post("/refresh")
async def refresh(
    request: Request,
    body: RefreshRequest = RefreshRequest(),
    db: AsyncSession = Depends(get_db),
):
    token_str = body.refresh_token or request.cookies.get("refresh_token")
    if not token_str:
        raise HTTPException(401, detail="No refresh token")
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token == token_str, RefreshToken.revoked == False
        )
    )
    rt = result.scalar_one_or_none()
    if not rt:
        raise HTTPException(401, detail="Invalid or expired refresh token")
    return {"access_token": auth_service.create_access_token(rt.user_id)}


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    body: RefreshRequest = RefreshRequest(),
    db: AsyncSession = Depends(get_db),
):
    token_str = body.refresh_token or request.cookies.get("refresh_token")
    if token_str:
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.token == token_str)
        )
        rt = result.scalar_one_or_none()
        if rt:
            rt.revoked = True
            await db.commit()
    response.delete_cookie("refresh_token")
    return {"success": True}
