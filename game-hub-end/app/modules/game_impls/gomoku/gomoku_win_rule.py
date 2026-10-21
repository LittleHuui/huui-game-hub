"""五子棋胜负判定规则。"""

from typing import Any, List

from app.modules.game_impls.gomoku.gomoku_constants import LINE_DIRECTIONS


def has_five_in_row(
    board: List[List[Any]],
    row: int,
    col: int,
    stone: str,
    win_length: int,
) -> bool:
    """
    判断落子后是否形成五连。

    :param board: 棋盘。
    :param row: 行。
    :param col: 列。
    :param stone: 棋子颜色。
    :param win_length: 连子长度。
    :return: 成五为 ``True``。
    """
    for delta_row, delta_col in LINE_DIRECTIONS:
        count = 1
        count += count_same(board, row, col, delta_row, delta_col, stone)
        count += count_same(board, row, col, -delta_row, -delta_col, stone)
        if count >= win_length:
            return True
    return False


def count_same(
    board: List[List[Any]],
    row: int,
    col: int,
    delta_row: int,
    delta_col: int,
    stone: str,
) -> int:
    """
    沿方向统计同色连续棋子数（不含起点）。

    :param board: 棋盘。
    :param row: 起点行。
    :param col: 起点列。
    :param delta_row: 行增量。
    :param delta_col: 列增量。
    :param stone: 棋子颜色。
    :return: 连续数量。
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
