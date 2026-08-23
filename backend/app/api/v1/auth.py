"""
auth.py - Authentication with Google OAuth and 19+ Legal Age Verification
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status
from app.models.schema import UserRegisterRequest, UserResponse
from app.core.security import create_access_token
from app.core.database import db

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=Dict if False else Any)
async def register_user(req: UserRegisterRequest):
    # 1. 19세 이상 법적 인증 필수 검증
    if not req.is_adult_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="청소년 보호법 및 서비스 이용약관에 따라 '19세 이상' 성인 확인에 동의해야 회원가입이 가능합니다."
        )

    user_id = str(uuid.uuid4())
    
    # DB 저장
    if db.pg_pool:
        try:
            async with db.pg_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO users (id, email, oauth_provider, oauth_subject_id, is_adult_verified, adult_verified_at)
                    VALUES ($1, $2, $3, $4, $5, NOW())
                    ON CONFLICT (email) DO UPDATE SET is_adult_verified = EXCLUDED.is_adult_verified
                    """,
                    uuid.UUID(user_id), req.email, req.oauth_provider, req.oauth_token, req.is_adult_verified
                )
                # 크레딧 지갑 초기화 (기본 무료 체험 3,000 KRW 증정)
                await conn.execute(
                    "INSERT INTO credit_wallets (user_id, balance_krw) VALUES ($1, 3000.0) ON CONFLICT DO NOTHING",
                    uuid.UUID(user_id)
                )
        except Exception as e:
            print(f"[DB Auth Error] {e}")

    # Redis 지갑 초기화
    if db.redis:
        await db.redis.set(f"wallet:balance:{user_id}", "3000.0")

    token = create_access_token({"sub": user_id, "email": req.email, "is_adult": True})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user_id,
        "email": req.email,
        "is_adult_verified": req.is_adult_verified,
        "initial_credit_krw": 3000.0
    }
