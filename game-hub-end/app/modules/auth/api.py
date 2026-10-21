"""Authentication module HTTP API."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.common.response import ApiResponse, success
from app.core.auth.deps import get_authenticated_user
from app.core.auth.schemas import AuthenticatedUser
from app.core.auth.token_service import issue_access_token
from app.core.database import get_db
from app.modules.auth.deps import get_auth_module_service
from app.modules.auth.module_service import AuthModuleService
from app.modules.auth.realtime_ticket_service import RealtimeTicketService
from app.modules.auth.schemas import LoginRequest, LoginResponse, RealtimeTicketResponse

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post(
    "/login",
    response_model=ApiResponse[LoginResponse],
    summary="Username login",
)
def login(
    request: LoginRequest,
    service: AuthModuleService = Depends(get_auth_module_service),
    db: Session = Depends(get_db),
):
    data = service.login(request)
    db.flush()
    token = issue_access_token(data.user.serverId, request.deviceId)
    db.commit()
    data.accessToken = token.accessToken
    data.expiresAt = token.expiresAt
    return success(data)


@auth_router.post(
    "/realtime-ticket",
    response_model=ApiResponse[RealtimeTicketResponse],
    summary="Issue short-lived realtime ticket",
)
async def issue_realtime_ticket(
    auth_user: AuthenticatedUser = Depends(get_authenticated_user),
):
    ticket, expires_at = await RealtimeTicketService().issue_realtime_ticket(auth_user)
    return success(RealtimeTicketResponse(ticket=ticket, expiresAt=expires_at))
