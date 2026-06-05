"""五子棋托管动作评分器。"""

import random
from typing import Any, Dict, List, Optional, Tuple

from app.modules.room.action_scorer import ActionScore, ManagedActionScorer
from app.modules.strategy_turn.schemas import GameView, LegalAction

_ACTION_PLACE_STONE = "PLACE_STONE"
_ACTION_RESIGN = "RESIGN"
_ACTION_REQUEST_UNDO = "REQUEST_UNDO"
_ACTION_ACCEPT_UNDO = "ACCEPT_UNDO"
_ACTION_REJECT_UNDO = "REJECT_UNDO"
_STONE_BLACK = "BLACK"
_STONE_WHITE = "WHITE"
_DIRECTIONS = ((1, 0), (0, 1), (1, 1), (1, -1))


class GomokuActionScorer(ManagedActionScorer):
    """五子棋托管落子评分。"""

    def score_actions(
        self,
        *,
        game_code: str,
        game_view: GameView,
        legal_actions: List[LegalAction],
        player_id: str,
    ) -> List[ActionScore]:
        """
        对合法动作评分。

        :param game_code: 游戏编码。
        :param game_view: 当前 GameView。
        :param legal_actions: 合法动作列表。
        :param player_id: 行动玩家 ID。
        :return: 评分列表。
        """
        del game_code
        board, board_size, win_length, my_stone = self._build_board_context(
            game_view, player_id
        )
        if board is None or my_stone is None:
            return []
        opponent_stone = _STONE_WHITE if my_stone == _STONE_BLACK else _STONE_BLACK
        results: List[ActionScore] = []
        for action in legal_actions:
            action_type = str(action.actionType or "").strip()
            action_id = str(action.actionId or "").strip()
            if not action_id:
                continue
            if action_type != _ACTION_PLACE_STONE:
                score = self._score_non_place_action(action_type)
                results.append(
                    ActionScore(actionId=action_id, score=score, reason=action_type)
                )
                continue
            row, col = self._parse_cell(action)
            if row is None or col is None:
                continue
            score = self._score_place(
                board,
                board_size,
                win_length,
                row,
                col,
                my_stone,
                opponent_stone,
            )
            results.append(
                ActionScore(actionId=action_id, score=score, reason="place")
            )
        return results

    def _build_board_context(
        self,
        game_view: GameView,
        player_id: str,
    ) -> Tuple[Optional[List[List[Any]]], int, int, Optional[str]]:
        """
        从 GameView 解析棋盘与己方棋子颜色。

        :param game_view: 对局视图。
        :param player_id: 玩家 ID。
        :return: (棋盘, 尺寸, 连子长度, 己方颜色)。
        """
        public_state = game_view.publicState or {}
        game_state = public_state.get("gameState") or {}
        board = game_state.get("board")
        if not isinstance(board, list) or not board:
            return None, 0, 5, None
        board_size = int(game_state.get("boardSize") or len(board))
        win_length = int(game_state.get("winLength") or 5)
        my_stone = None
        for item in public_state.get("players") or []:
            if item.get("playerId") == player_id:
                my_stone = item.get("stone")
                break
        if my_stone not in (_STONE_BLACK, _STONE_WHITE):
            return None, board_size, win_length, None
        copied = [list(row) for row in board]
        return copied, board_size, win_length, my_stone

    def _parse_cell(self, action: LegalAction) -> Tuple[Optional[int], Optional[int]]:
        """
        从合法操作中解析行列。

        :param action: 合法操作。
        :return: (row, col)。
        """
        payload = action.payload or {}
        selection = action.selection or {}
        config = selection.get("config") or {}
        row = payload.get("row", config.get("row"))
        col = payload.get("col", config.get("col"))
        try:
            return int(row), int(col)
        except (TypeError, ValueError):
            return None, None

    def _score_non_place_action(self, action_type: str) -> float:
        """
        非落子动作评分。

        :param action_type: 操作类型。
        :return: 分数。
        """
        if action_type == _ACTION_RESIGN:
            return -1_000_000.0
        if action_type == _ACTION_REJECT_UNDO:
            return 50.0
        if action_type == _ACTION_ACCEPT_UNDO:
            return -10.0
        if action_type == _ACTION_REQUEST_UNDO:
            return -5.0
        return 0.0

    def _score_place(
        self,
        board: List[List[Any]],
        board_size: int,
        win_length: int,
        row: int,
        col: int,
        my_stone: str,
        opponent_stone: str,
    ) -> float:
        """
        评估某一落子点。

        :param board: 棋盘副本。
        :param board_size: 棋盘尺寸。
        :param win_length: 连子长度。
        :param row: 行。
        :param col: 列。
        :param my_stone: 己方颜色。
        :param opponent_stone: 对手颜色。
        :return: 分数。
        """
        if board[row][col] is not None:
            return -1_000_000.0
        score = 0.0
        board[row][col] = my_stone
        if _would_win(board, row, col, my_stone, win_length):
            score += 1_000_000.0
        board[row][col] = None
        board[row][col] = opponent_stone
        if _would_win(board, row, col, opponent_stone, win_length):
            score += 900_000.0
        board[row][col] = None
        board[row][col] = my_stone
        score += _max_line_score(board, row, col, my_stone, win_length) * 1000.0
        board[row][col] = None
        board[row][col] = opponent_stone
        score += _max_line_score(board, row, col, opponent_stone, win_length) * 800.0
        board[row][col] = None
        score += _neighbor_score(board, row, col) * 20.0
        center = (board_size - 1) / 2.0
        distance = abs(row - center) + abs(col - center)
        score += max(0.0, 30.0 - distance * 2.0)
        score += random.uniform(0.0, 3.0)
        return score


def _would_win(
    board: List[List[Any]],
    row: int,
    col: int,
    stone: str,
    win_length: int,
) -> bool:
    """
    判断该点是否已成五。

    :param board: 棋盘。
    :param row: 行。
    :param col: 列。
    :param stone: 棋子颜色。
    :param win_length: 连子长度。
    :return: 成五为 ``True``。
    """
    for delta_row, delta_col in _DIRECTIONS:
        count = 1
        count += _count_line(board, row, col, delta_row, delta_col, stone)
        count += _count_line(board, row, col, -delta_row, -delta_col, stone)
        if count >= win_length:
            return True
    return False


def _count_line(
    board: List[List[Any]],
    row: int,
    col: int,
    delta_row: int,
    delta_col: int,
    stone: str,
) -> int:
    """
    沿方向统计同色连子（不含起点）。

    :param board: 棋盘。
    :param row: 起点行。
    :param col: 起点列。
    :param delta_row: 行增量。
    :param delta_col: 列增量。
    :param stone: 棋子颜色。
    :return: 数量。
    """
    total = 0
    board_size = len(board)
    next_row = row + delta_row
    next_col = col + delta_col
    while (
        0 <= next_row < board_size
        and 0 <= next_col < board_size
        and board[next_row][next_col] == stone
    ):
        total += 1
        next_row += delta_row
        next_col += delta_col
    return total


def _max_line_score(
    board: List[List[Any]],
    row: int,
    col: int,
    stone: str,
    win_length: int,
) -> int:
    """
    估算该点最大连子潜力。

    :param board: 棋盘。
    :param row: 行。
    :param col: 列。
    :param stone: 棋子颜色。
    :param win_length: 连子长度。
    :return: 潜力分。
    """
    best = 0
    for delta_row, delta_col in _DIRECTIONS:
        count = 1
        count += _count_line(board, row, col, delta_row, delta_col, stone)
        count += _count_line(board, row, col, -delta_row, -delta_col, stone)
        best = max(best, count)
    if best >= win_length:
        return 100
    if best >= win_length - 1:
        return 40
    if best >= 3:
        return 15
    if best >= 2:
        return 5
    return 1


def _neighbor_score(board: List[List[Any]], row: int, col: int) -> float:
    """
    邻近已有棋子的加分。

    :param board: 棋盘。
    :param row: 行。
    :param col: 列。
    :return: 分数。
    """
    board_size = len(board)
    score = 0.0
    for delta_row in (-1, 0, 1):
        for delta_col in (-1, 0, 1):
            if delta_row == 0 and delta_col == 0:
                continue
            next_row = row + delta_row
            next_col = col + delta_col
            if (
                0 <= next_row < board_size
                and 0 <= next_col < board_size
                and board[next_row][next_col] is not None
            ):
                score += 1.0
    return score
