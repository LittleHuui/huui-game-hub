"""平台积分结算编排服务。"""


import json
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from app.core.clock import Clock
from app.core.database import new_entity_ids
from app.core.id_utils import generate_server_id
from app.modules.match.entity_service import MatchRecordEntityService
from app.modules.match.repository import MatchRecordRepository
from app.modules.match.schemas import MatchRecordCreate
from app.modules.room.game_settlement_calculator import compute_platform_player_settlements
from app.modules.room.game_settlement_models import GameSettlementPlayerRecord, GameSettlementRecord
from app.modules.room.game_settlement_repository import GameSettlementRepository
from app.modules.room.game_settlement_schemas import GameSettlementResult, PlayerSettlementResult, SettlementPersistenceResult, SettlementPersistenceStatus
from app.modules.strategy_turn.schemas import RuntimeSnapshot, TheoreticalPlayerSettlement
from app.modules.user.entity_service import UserAccountEntityService
from app.modules.user.repository import UserAccountRepository
from app.modules.wallet.entity_service import UserWalletEntityService, WalletLedgerEntityService
from app.modules.wallet.module_service import WalletModuleService
from app.modules.wallet.repository import UserWalletRepository, WalletLedgerRepository
from typing import Callable, ContextManager


_SETTLEMENT_WALLET_REASON = "game_settlement"


class GameSettlementTransaction:
    """单事务完成 settlementId 幂等、钱包与对局记录持久化。"""

    def __init__(self, session_factory: Callable[[], ContextManager[Session]], clock: Clock) -> None:
        """注入事务会话工厂与时钟，事务生命周期由此执行器拥有。"""
        self._session_factory = session_factory
        self._clock = clock

    def execute(
        self,
        settlement_id: str,
        room_id: str,
        game_code: str,
        theoretical_players: List[TheoreticalPlayerSettlement],
        player_ai_map: Dict[str, bool],
        snapshot: RuntimeSnapshot,
    ) -> SettlementPersistenceResult:
        """
        在单数据库事务中完成结算幂等、钱包与对局记录写入。

        :param settlement_id: 结算幂等 ID。
        :param room_id: 房间 ID。
        :param game_code: 游戏编码。
        :param theoretical_players: 理论结算列表。
        :param player_ai_map: AI 玩家映射。
        :param snapshot: 终局运行时快照。
        :return: 数据库结算事务的严格幂等结果。
        """
        with self._session_factory() as session:
            existing = self._load_existing_result(session, settlement_id)
            if existing is not None:
                return SettlementPersistenceResult(
                    status=SettlementPersistenceStatus.ALREADY_COMPLETED,
                    settlementResult=existing,
                )

            wallet_service = self._build_wallet_service(session)
            balance_by_player = self._lock_human_balances(
                session,
                wallet_service,
                theoretical_players,
                player_ai_map,
            )
            player_settlements, system_delta = compute_platform_player_settlements(
                theoretical_players,
                player_ai_map,
                balance_by_player,
            )
            match_id = generate_server_id("match")
            self._apply_wallet_changes(
                wallet_service,
                settlement_id,
                game_code,
                player_settlements,
                player_ai_map,
            )
            self._write_match_records(
                session,
                settlement_id,
                match_id,
                game_code,
                snapshot,
                player_settlements,
                player_ai_map,
            )
            record_server_id, created_at, updated_at = new_entity_ids("game_settlement")
            settlement_record = GameSettlementRecord(
                server_id=record_server_id,
                settlement_id=settlement_id,
                room_id=room_id,
                game_code=game_code,
                match_id=match_id,
                status="COMPLETED",
                system_delta=int(system_delta),
                payload_json=json.dumps(
                    {"roomId": room_id, "gameCode": game_code},
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                created_at=created_at,
                updated_at=updated_at,
                deleted_at=None,
            )
            repo = GameSettlementRepository(session)
            repo.add_record(settlement_record)
            for item in player_settlements:
                player_server_id, player_created_at, player_updated_at = new_entity_ids(
                    "game_settlement_player",
                )
                repo.add_player_record(
                    GameSettlementPlayerRecord(
                        server_id=player_server_id,
                        settlement_id=settlement_id,
                        player_id=item.playerId,
                        expected_delta=int(item.expectedDelta),
                        actual_delta=int(item.actualDelta),
                        balance_before=int(item.balanceBefore),
                        balance_after=int(item.balanceAfter),
                        insufficient_amount=int(item.insufficientAmount),
                        is_ai=bool(item.isAi or player_ai_map.get(item.playerId, False)),
                        created_at=player_created_at,
                        updated_at=player_updated_at,
                        deleted_at=None,
                    ),
                )
            return SettlementPersistenceResult(
                status=SettlementPersistenceStatus.CREATED,
                settlementResult=GameSettlementResult(
                    settlementId=settlement_id,
                    roomId=room_id,
                    gameCode=game_code,
                    matchId=match_id,
                    status="COMPLETED",
                    playerSettlements=player_settlements,
                    systemDelta=int(system_delta),
                ),
            )

    def _load_existing_result(
        self,
        session: Session,
        settlement_id: str,
    ) -> Optional[GameSettlementResult]:
        """
        按 settlementId 读取已完成结算（幂等重放）。

        :param session: 数据库会话。
        :param settlement_id: 结算 ID。
        :return: 已有结果或 ``None``。
        """
        repo = GameSettlementRepository(session)
        main_record = repo.get_by_settlement_id(settlement_id)
        if main_record is None:
            return None
        if str(main_record.status or "").strip() != "COMPLETED":
            return None
        player_rows = repo.list_player_records(settlement_id)
        player_settlements = [
            PlayerSettlementResult(
                playerId=row.player_id,
                expectedDelta=int(row.expected_delta),
                actualDelta=int(row.actual_delta),
                balanceBefore=int(row.balance_before),
                balanceAfter=int(row.balance_after),
                insufficientAmount=int(row.insufficient_amount),
                isAi=bool(row.is_ai),
            )
            for row in player_rows
        ]
        return GameSettlementResult(
            settlementId=settlement_id,
            roomId=main_record.room_id,
            gameCode=main_record.game_code,
            matchId=main_record.match_id,
            status="COMPLETED",
            playerSettlements=player_settlements,
            systemDelta=int(main_record.system_delta),
        )

    def _build_wallet_service(self, session: Session) -> WalletModuleService:
        """
        基于会话构建钱包模块服务。

        :param session: 数据库会话。
        :return: 钱包模块服务。
        """
        return WalletModuleService(
            UserWalletEntityService(UserWalletRepository(session)),
            WalletLedgerEntityService(WalletLedgerRepository(session)),
            UserAccountEntityService(UserAccountRepository(session)),
        )

    def _lock_human_balances(
        self,
        session: Session,
        wallet_service: WalletModuleService,
        theoretical_players: List[TheoreticalPlayerSettlement],
        player_ai_map: Dict[str, bool],
    ) -> Dict[str, int]:
        """
        创建缺失钱包后按稳定顺序加行锁，并读取结算前余额。

        :param session: 当前结算事务会话。
        :param wallet_service: 钱包服务。
        :param theoretical_players: 理论结算列表。
        :param player_ai_map: AI 映射。
        :return: 玩家 ID -> 余额。
        """
        human_player_ids = []
        for item in theoretical_players or []:
            player_id = str(item.playerId or "").strip()
            if not player_id or bool(player_ai_map.get(player_id, False)):
                continue
            wallet_service.get_or_create_wallet(player_id)
            human_player_ids.append(player_id)
        session.flush()
        locked_wallets = UserWalletRepository(session).lock_by_user_ids(human_player_ids)
        return {
            wallet.user_id: max(0, int(wallet.balance))
            for wallet in locked_wallets
        }

    def _apply_wallet_changes(
        self,
        wallet_service: WalletModuleService,
        settlement_id: str,
        game_code: str,
        player_settlements: List[PlayerSettlementResult],
        player_ai_map: Dict[str, bool],
    ) -> None:
        """
        按实际变动写入钱包流水（幂等 clientId）。

        :param wallet_service: 钱包服务。
        :param settlement_id: 结算 ID。
        :param game_code: 游戏编码。
        :param player_settlements: 玩家结算结果。
        :param player_ai_map: AI 映射。
        :return: 无。
        """
        for item in player_settlements:
            if bool(player_ai_map.get(item.playerId, False)):
                continue
            if int(item.actualDelta) == 0:
                continue
            client_id = "{0}:{1}".format(settlement_id, item.playerId)
            payload_json = json.dumps(
                {
                    "settlementId": settlement_id,
                    "playerId": item.playerId,
                    "expectedDelta": int(item.expectedDelta),
                    "actualDelta": int(item.actualDelta),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            if int(item.actualDelta) > 0:
                wallet_service.gain_score(
                    user_id=item.playerId,
                    client_id=client_id,
                    amount=int(item.actualDelta),
                    reason=_SETTLEMENT_WALLET_REASON,
                    game_code=game_code,
                    payload_json=payload_json,
                )
            else:
                wallet_service.cost_score(
                    user_id=item.playerId,
                    client_id=client_id,
                    amount=abs(int(item.actualDelta)),
                    reason=_SETTLEMENT_WALLET_REASON,
                    game_code=game_code,
                    payload_json=payload_json,
                )

    def _write_match_records(
        self,
        session: Session,
        settlement_id: str,
        match_id: str,
        game_code: str,
        snapshot: RuntimeSnapshot,
        player_settlements: List[PlayerSettlementResult],
        player_ai_map: Dict[str, bool],
    ) -> None:
        """
        为真人玩家写入对局历史记录。

        :param session: 数据库会话。
        :param settlement_id: 结算 ID。
        :param match_id: 对局 ID。
        :param game_code: 游戏编码。
        :param snapshot: 终局快照。
        :param player_settlements: 玩家结算。
        :param player_ai_map: AI 映射。
        :return: 无。
        """
        started_at = int(snapshot.startedAt or 0)
        duration_ms = (
            max(0, int(self._clock.now_ms()) - started_at) if started_at > 0 else None
        )
        mode = "online"
        runtime_rule = snapshot.runtimeRule
        if runtime_rule is not None and runtime_rule.mode:
            mode = str(runtime_rule.mode).strip() or mode
        for item in player_settlements:
            if bool(player_ai_map.get(item.playerId, False)):
                continue
            result_label = "draw"
            if int(item.expectedDelta) > 0:
                result_label = "win"
            elif int(item.expectedDelta) < 0:
                result_label = "lose"
            client_id = "{0}:{1}".format(settlement_id, item.playerId)
            payload = {
                "settlementId": settlement_id,
                "matchId": match_id,
                "roomId": str(snapshot.roomId or ""),
                "expectedDelta": int(item.expectedDelta),
                "actualDelta": int(item.actualDelta),
            }
            match_service = MatchRecordEntityService(MatchRecordRepository(session))
            match_service.create_match_record_if_not_exists(
                MatchRecordCreate(
                    clientId=client_id,
                    userId=item.playerId,
                    gameCode=game_code,
                    mode=mode,
                    result=result_label,
                    durationMs=duration_ms,
                    score=int(item.actualDelta),
                    payload=payload,
                ),
            )
