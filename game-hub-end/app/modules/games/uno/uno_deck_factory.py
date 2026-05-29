"""UNO 牌堆构建工厂（基于在线规则种子）。"""

import random
from typing import List, Optional

from app.common.exceptions import ValidationException
from app.modules.game_seed.schemas import CardDefinition, OnlineGameRuleSeed
from app.modules.games.uno.schemas import UnoCard, UnoRuntimeState


def resolve_deck_set_count(seed: OnlineGameRuleSeed, player_count: int) -> int:
    """
    按玩家人数解析开局牌组套数。

    :param seed: 在线游戏规则种子。
    :param player_count: 玩家人数。
    :return: 牌组套数。
    :raises ValidationException: 无匹配规则时抛出。
    """
    if player_count < 1:
        raise ValidationException("player_count 必须大于 0")
    extension = seed.extensionConfig
    if not isinstance(extension, dict):
        raise ValidationException("UNO 规则种子缺少 initialDeckSetRules")
    raw_rules = extension.get("initialDeckSetRules")
    if not isinstance(raw_rules, list):
        raise ValidationException("UNO 规则种子缺少 initialDeckSetRules")
    for raw_rule in raw_rules:
        if not isinstance(raw_rule, dict):
            continue
        min_count = int(raw_rule.get("minPlayerCount", 0))
        max_count = int(raw_rule.get("maxPlayerCount", 0))
        deck_set_count = int(raw_rule.get("deckSetCount", 0))
        if min_count <= player_count <= max_count and deck_set_count > 0:
            return deck_set_count
    raise ValidationException("未找到适用的 initialDeckSetRules")


def build_deck_set(
    seed: OnlineGameRuleSeed,
    deck_set_index: int,
) -> List[UnoCard]:
    """
    根据种子定义生成单套牌组实例列表。

    :param seed: 在线游戏规则种子。
    :param deck_set_index: 牌组套序号，用于生成唯一实例 ID。
    :return: 单套牌实例列表。
    """
    cards = []
    sequence = 0
    for definition in seed.cardDefinitions:
        for _ in range(definition.countPerDeckSet):
            sequence += 1
            cards.append(_card_from_definition(definition, deck_set_index, sequence))
    return cards


def build_initial_draw_pile(
    seed: OnlineGameRuleSeed,
    player_count: int,
    *,
    shuffle: bool = True,
) -> List[UnoCard]:
    """
    构建开局抽牌堆（按人数决定套数并洗牌）。

    :param seed: 在线游戏规则种子。
    :param player_count: 玩家人数。
    :param shuffle: 是否洗牌。
    :return: 抽牌堆。
    """
    deck_set_count = resolve_deck_set_count(seed, player_count)
    draw_pile = []
    for deck_index in range(deck_set_count):
        draw_pile.extend(build_deck_set(seed, deck_index))
    if shuffle:
        random.shuffle(draw_pile)
    return draw_pile


def append_deck_set_when_empty(
    state: UnoRuntimeState,
    seed: OnlineGameRuleSeed,
    room_config: dict,
) -> bool:
    """
    抽牌堆为空时按房间配置补入牌组。

    :param state: 当前运行时状态。
    :param seed: 在线游戏规则种子。
    :param room_config: 当前房间玩法配置。
    :return: 已补牌为 ``True``，未补为 ``False``。
    """
    if state.drawPile:
        return False
    if not isinstance(room_config, dict):
        return False
    if not bool(room_config.get("appendDeckSetWhenDrawPileEmpty")):
        return False
    try:
        append_count = int(room_config.get("appendDeckSetCount", 0))
    except (TypeError, ValueError):
        append_count = 0
    if append_count < 1:
        return False
    next_deck_index = state.deckSetCount
    appended_cards = []
    for offset in range(append_count):
        appended_cards.extend(build_deck_set(seed, next_deck_index + offset))
    random.shuffle(appended_cards)
    state.drawPile = appended_cards
    state.deckSetCount = state.deckSetCount + append_count
    return True


def draw_cards_from_pile(
    state: UnoRuntimeState,
    seed: OnlineGameRuleSeed,
    count: int,
    room_config: dict,
) -> List[UnoCard]:
    """
    从抽牌堆抽取指定张数，必要时自动补牌组。

    :param state: 当前运行时状态。
    :param seed: 在线游戏规则种子。
    :param count: 抽取张数。
    :param room_config: 当前房间玩法配置。
    :return: 抽到的牌列表。
    """
    if count < 1:
        return []
    drawn = []
    for _ in range(count):
        if not state.drawPile:
            if not append_deck_set_when_empty(state, seed, room_config):
                break
        if not state.drawPile:
            break
        drawn.append(state.drawPile.pop(0))
    return drawn


def _card_from_definition(
    definition: CardDefinition,
    deck_set_index: int,
    sequence: int,
) -> UnoCard:
    """
    由牌型定义生成单张牌实例。

    :param definition: 牌型定义。
    :param deck_set_index: 牌组套序号。
    :param sequence: 套内序号。
    :return: 牌实例。
    """
    instance_id = "{0}_{1}_{2}".format(deck_set_index, definition.cardCode, sequence)
    return UnoCard(
        cardInstanceId=instance_id,
        cardCode=definition.cardCode,
        color=definition.color,
        cardType=definition.cardType,
        numberValue=definition.numberValue,
    )


def pop_starting_discard_card(draw_pile: List[UnoCard]) -> Optional[UnoCard]:
    """
    从抽牌堆取出首张作为开局顶牌（跳过万能牌骨架逻辑）。

    :param draw_pile: 抽牌堆。
    :return: 顶牌；堆为空时为 ``None``。
    """
    if not draw_pile:
        return None
    return draw_pile.pop(0)
