from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness, plus whether the demo auth bypass is on.

    The frontend reads `demo_auth` to show a banner on the sign in screen.
    A bypass the person demoing cannot see is one they will forget to turn
    off.
    """
    return {"status": "ok", "demo_auth": get_settings().demo_auth}
