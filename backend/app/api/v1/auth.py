"""
auth.py - Authentication with Google OAuth, 19+ Verification & Admin Auth Gateway
"""
import uuid
import hmac
from datetime import datetime, timedelta
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from app.models.schema import UserRegisterRequest, UserResponse, AdminCreditAdjustRequest
from app.core.security import create_access_token, require_admin_auth, get_master_secret
from app.core.database import db

router = APIRouter(prefix="/auth", tags=["Authentication & User Management"])

class AdminLoginRequest(BaseModel):
    master_secret: str

# In-memory mock store for users
MOCK_USERS: Dict[str, Dict[str, Any]] = {
    "usr-admin-01": {
        "id": "usr-admin-01",
        "email": "admin@domain.com",
        "is_adult_verified": True,
        "status": "ACTIVE",
        "balance_krw": 50000.0,
        "created_at": datetime.utcnow()
    },
    "usr-demo-02": {
        "id": "usr-demo-02",
        "email": "player_steve@gmail.com",
        "is_adult_verified": True,
        "status": "ACTIVE",
        "balance_krw": 3000.0,
        "created_at": datetime.utcnow()
    }
}

# ---------------------------------------------------------------------------
# 1. Admin Login Endpoint (Master Secret Authentication)
# ---------------------------------------------------------------------------
@router.post("/admin/login")
async def admin_login(req: AdminLoginRequest):
    """어드민 관리자 인증 (마스터 시크릿 키 검증 후 어드민 전용 JWT 토큰 발급)"""
    expected = get_master_secret()
    if not hmac.compare_digest(req.master_secret, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="마스터 시크릿 키가 일치하지 않습니다. 올바른 관리자 암호를 입력하십시오."
        )

    admin_token = create_access_token(
        data={"sub": "superadmin", "role": "admin", "is_admin": True},
        expires_delta=timedelta(days=7)
    )

    return {
        "status": "success",
        "access_token": admin_token,
        "token_type": "bearer",
        "role": "admin",
        "message": "어드민 총괄 관리자 인증에 성공하였습니다."
    }

# ---------------------------------------------------------------------------
# 2. General User Registration (19+ Age Verification)
# ---------------------------------------------------------------------------
@router.post("/register")
async def register_user(req: UserRegisterRequest):
    if not req.is_adult_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="청소년 보호법 및 서비스 이용약관에 따라 '19세 이상' 성인 확인에 동의해야 회원가입이 가능합니다."
        )

    user_id = f"usr-{uuid.uuid4().hex[:8]}"
    
    MOCK_USERS[user_id] = {
        "id": user_id,
        "email": req.email,
        "is_adult_verified": req.is_adult_verified,
        "status": "ACTIVE",
        "balance_krw": 3000.0,
        "created_at": datetime.utcnow()
    }

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
                await conn.execute(
                    "INSERT INTO credit_wallets (user_id, balance_krw) VALUES ($1, 3000.0) ON CONFLICT DO NOTHING",
                    uuid.UUID(user_id)
                )
        except Exception as e:
            print(f"[DB Auth Error] {e}")

    if db.redis:
        try:
            await db.redis.set(f"wallet:balance:{user_id}", "3000.0")
        except Exception:
            pass

    token = create_access_token({"sub": user_id, "email": req.email, "is_adult": True, "role": "user"})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user_id,
        "email": req.email,
        "is_adult_verified": req.is_adult_verified,
        "initial_credit_krw": 3000.0
    }

# ---------------------------------------------------------------------------
# 3. Admin User & Credit Management (Protected by require_admin_auth)
# ---------------------------------------------------------------------------
@router.get("/admin/users", response_model=List[UserResponse], dependencies=[Depends(require_admin_auth)])
async def get_all_users_admin():
    """어드민 대시보드: 전체 회원 목록 및 실시간 크레딧 잔액 조회 (인증 필수)"""
    user_list = []
    for uid, u in MOCK_USERS.items():
        bal = u["balance_krw"]
        if db.redis:
            try:
                r_bal = await db.redis.get(f"wallet:balance:{uid}")
                if r_bal:
                    bal = float(r_bal)
            except Exception:
                pass

        user_list.append(UserResponse(
            id=u["id"],
            email=u["email"],
            is_adult_verified=u["is_adult_verified"],
            status=u.get("status", "ACTIVE"),
            balance_krw=bal,
            created_at=u.get("created_at", datetime.utcnow())
        ))
    return user_list

@router.post("/admin/users/adjust-credit", dependencies=[Depends(require_admin_auth)])
async def adjust_user_credit(req: AdminCreditAdjustRequest):
    """어드민 대시보드: 특정 유저에게 크레딧 수동 지급 또는 차감 (인증 필수)"""
    if req.user_id not in MOCK_USERS:
        raise HTTPException(status_code=404, detail="해당 유저를 찾을 수 없습니다.")

    user = MOCK_USERS[req.user_id]
    user["balance_krw"] = max(0.0, user["balance_krw"] + req.amount_krw)

    if db.redis:
        try:
            await db.redis.set(f"wallet:balance:{req.user_id}", str(user["balance_krw"]))
        except Exception:
            pass

    return {
        "status": "success",
        "user_id": req.user_id,
        "adjusted_amount": req.amount_krw,
        "new_balance_krw": user["balance_krw"],
        "reason": req.reason,
        "message": f"[{user['email']}] 계정에 {req.amount_krw:+,.0f} KRW 크레딧이 조정되었습니다."
    }

@router.post("/admin/users/{user_id}/toggle-status", dependencies=[Depends(require_admin_auth)])
async def toggle_user_status(user_id: str):
    """어드민 대시보드: 유저 계정 정지(BANNED) / 활성화(ACTIVE) 토글 (인증 필수)"""
    if user_id not in MOCK_USERS:
        raise HTTPException(status_code=404, detail="해당 유저를 찾을 수 없습니다.")

    user = MOCK_USERS[user_id]
    current = user.get("status", "ACTIVE")
    new_status = "BANNED" if current == "ACTIVE" else "ACTIVE"
    user["status"] = new_status

    return {
        "status": "success",
        "user_id": user_id,
        "new_status": new_status,
        "message": f"[{user['email']}] 상태가 {new_status}로 변경되었습니다."
    }
