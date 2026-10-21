"""Realtime one-time ticket authentication adapter."""

from typing import Optional

from app.core.auth.schemas import AuthenticatedUser
from app.modules.auth.realtime_ticket_service import RealtimeTicketService


class AccessTokenAuthenticationAdapter:
    """Adapt RealtimeTicketService to the websocket authentication port."""

    def __init__(self, ticket_service: Optional[RealtimeTicketService] = None) -> None:
        self._ticket_service = ticket_service or RealtimeTicketService()

    async def authenticate_ticket(self, ticket: str) -> Optional[AuthenticatedUser]:
        return await self._ticket_service.consume_realtime_ticket(ticket)
