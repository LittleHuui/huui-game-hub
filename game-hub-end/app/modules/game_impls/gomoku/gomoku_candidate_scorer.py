"""五子棋托管候选评分器。"""

import random
from typing import Any, Dict, List, Optional, Tuple

from app.modules.strategy_turn.decision.candidate_scorer import CandidateScorer
from app.modules.strategy_turn.schemas import ActionCandidate, ActionDecisionContext, CandidateScore

from app.modules.game_impls.gomoku.gomoku_constants import (
    ACTION_PLACE_STONE, ACTION_RESIGN, ACTION_REQUEST_UNDO,
    ACTION_ACCEPT_UNDO, ACTION_REJECT_UNDO, LINE_DIRECTIONS, WIN_LENGTH,
)
from app.modules.game_impls.gomoku.gomoku_win_rule import count_same, has_five_in_row

_STONE_BLACK = "BLACK"
_STONE_WHITE = "WHITE"


class GomokuCandidateScorer(CandidateScorer):
    """五子棋托管落子候选评分。"""

    def score_candidates(
        self,
        context: ActionDecisionContext,
        candidates: List[ActionCandidate],
    ) -> List[CandidateScore]:
        """
        对候选动作评分。

        :param context: 决策上下文。
        :param candidates: 候选动作列表。
        :return: 评分列表。
        """
        board, board_size, win_length, my_stone = self._build_board_context(context)
        if board is None or my_stone is None:
            return []
        opponent_stone = _STONE_WHITE if my_stone == _STONE_BLACK else _STONE_BLACK
        results: List[CandidateScore] = []
        for candidate in candidates:
            action_type = str(candidate.actionType or "").strip()
            candidate_id = str(candidate.candidateId or "").strip()
            if not candidate_id:
                continue
            if action_type != ACTION_PLACE_STONE:
                score = self._score_non_place_action(action_type)
                results.append(CandidateScore(candidateId=candidate_id, score=score, reason=action_type))
                continue
            row, col = self._parse_cell(candidate)
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
            results.append(CandidateScore(candidateId=candidate_id, score=score, reason="place"))
        return results

    def _build_board_context(
        self,
        context: ActionDecisionContext,
    ) -> Tuple[Optional[List[List[Any]]], int, int, Optional[str]]:
        """
        从决策上下文解析棋盘与己方棋子颜色。

        :param context: 决策上下文。
        :return: (棋盘, 尺寸, 连子长度, 己方颜色)。
        """
        state = context.state if isinstance(context.state, dict) else {}
        board = state.get("board")
        if not isinstance(board, list) or not board:
            return None, 0, WIN_LENGTH, None
        board_size = int(state.get("boardSize") or len(board))
        win_length = int(state.get("winLength") or WIN_LENGTH)
        my_stone = None
        for item in state.get("players") or []:
            if item.get("playerId") == context.playerId:
                my_stone = item.get("stone")
                break
        if my_stone not in (_STONE_BLACK, _STONE_WHITE):
            return None, board_size, win_length, None
        copied = [list(row) for row in board]
        return copied, board_size, win_length, my_stone

    def _parse_cell(self, candidate: ActionCandidate) -> Tuple[Optional[int], Optional[int]]:
        """
        从候选动作中解析行列。

        :param candidate: 候选动作。
        :return: (row, col)。
        """
        payload = candidate.normalizedAction.payload or {}
        selection = candidate.features.get("selection") or {}
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
        if action_type == ACTION_RESIGN:
            return -1_000_000.0
        if action_type == ACTION_REJECT_UNDO:
            return 50.0
        if action_type == ACTION_ACCEPT_UNDO:
            return -10.0
        if action_type == ACTION_REQUEST_UNDO:
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
        if has_five_in_row(board, row, col, my_stone, win_length):
            score += 1_000_000.0
        board[row][col] = None
        board[row][col] = opponent_stone
        if has_five_in_row(board, row, col, opponent_stone, win_length):
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
    for delta_row, delta_col in LINE_DIRECTIONS:
        count = 1
        count += count_same(board, row, col, delta_row, delta_col, stone)
        count += count_same(board, row, col, -delta_row, -delta_col, stone)
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
