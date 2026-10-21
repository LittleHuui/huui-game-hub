"""斗地主牌堆构建工厂（基于在线规则种子）。"""

import random
from typing import Dict, List

from app.common.exceptions import ValidationException
from app.modules.game_seed.schemas import CardDefinition, OnlineGameRuleSeed
from app.modules.game_impls.doudizhu.doudizhu_constants import DOUDIZHU_PLAYER_COUNT
from app.modules.game_impls.doudizhu.schemas import DoudizhuCard, DoudizhuDealResult


def build_deck_set(
    seed: OnlineGameRuleSeed,
    deck_set_index: int,
) -> List[DoudizhuCard]:
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


def build_shuffled_deck(
    seed: OnlineGameRuleSeed,
    shuffle: bool = True,
) -> List[DoudizhuCard]:
    """
    构建完整洗牌后的牌堆（按种子配置的套数）。

    :param seed: 在线游戏规则种子。
    :param shuffle: 是否洗牌。
    :return: 牌堆列表。
    """
    deck_set_count = _resolve_deck_set_count(seed)
    deck = []
    for deck_index in range(deck_set_count):
        deck.extend(build_deck_set(seed, deck_index))
    if shuffle:
        random.shuffle(deck)
    return deck


def deal_initial_cards(
    deck: List[DoudizhuCard],
    player_ids: List[str],
    hand_count: int,
    bottom_card_count: int,
) -> DoudizhuDealResult:
    """
    按斗地主规则发初始手牌与底牌。

    :param deck: 待发牌堆。
    :param player_ids: 玩家 ID 列表，必须为 3 人。
    :param hand_count: 每位玩家手牌张数。
    :param bottom_card_count: 底牌张数。
    :return: 发牌结果。
    :raises ValidationException: 玩家数不为 3 或牌数不足时抛出。
    """
    if len(player_ids) != DOUDIZHU_PLAYER_COUNT:
        raise ValidationException(
            "斗地主发牌要求玩家人数为 {0}，当前为 {1}".format(
                DOUDIZHU_PLAYER_COUNT, len(player_ids)
            )
        )
    required_count = len(player_ids) * hand_count + bottom_card_count
    if len(deck) < required_count:
        raise ValidationException(
            "牌堆张数不足：需要 {0} 张，当前 {1} 张".format(required_count, len(deck))
        )
    working_deck = list(deck)
    player_hands = {}  # type: Dict[str, List[DoudizhuCard]]
    for player_id in player_ids:
        hand = []
        for _ in range(hand_count):
            hand.append(working_deck.pop(0))
        player_hands[player_id] = hand
    bottom_cards = []
    for _ in range(bottom_card_count):
        bottom_cards.append(working_deck.pop(0))
    return DoudizhuDealResult(
        playerHands=player_hands,
        bottomCards=bottom_cards,
        remainingCards=working_deck,
    )


def _resolve_deck_set_count(seed: OnlineGameRuleSeed) -> int:
    """
    从规则种子解析开局牌组套数。

    :param seed: 在线游戏规则种子。
    :return: 牌组套数。
    :raises ValidationException: 配置缺失或无效时抛出。
    """
    extension = seed.extensionConfig
    if not isinstance(extension, dict):
        raise ValidationException("斗地主规则种子缺少 extensionConfig.rule.config")
    rule = extension.get("rule")
    if not isinstance(rule, dict):
        raise ValidationException("斗地主规则种子缺少 extensionConfig.rule")
    config = rule.get("config")
    if not isinstance(config, dict):
        raise ValidationException("斗地主规则种子缺少 extensionConfig.rule.config")
    try:
        deck_set_count = int(config.get("deckSetCount", 0))
    except (TypeError, ValueError):
        deck_set_count = 0
    if deck_set_count < 1:
        raise ValidationException("斗地主 deckSetCount 必须大于 0")
    return deck_set_count


def _resolve_display_color(definition: CardDefinition) -> str:
    """
    从牌定义解析展示颜色。

    :param definition: 牌型定义。
    :return: 展示颜色 BLACK 或 RED。
    """
    metadata = definition.metadata
    if isinstance(metadata, dict):
        display_color = metadata.get("displayColor")
        if isinstance(display_color, str) and display_color.strip():
            return display_color.strip().upper()
    raise ValidationException(
        "无法从牌定义解析 displayColor: {0}".format(definition.cardCode)
    )


def _card_from_definition(
    definition: CardDefinition,
    deck_set_index: int,
    sequence: int,
) -> DoudizhuCard:
    """
    由牌型定义生成单张斗地主牌实例。

    :param definition: 牌型定义。
    :param deck_set_index: 牌组套序号。
    :param sequence: 套内序号。
    :return: 牌实例。
    """
    instance_id = "{0}_{1}_{2}".format(deck_set_index, definition.cardCode, sequence)
    is_joker = definition.category == "JOKER"
    rank_code = definition.rankCode
    if rank_code is None or not str(rank_code).strip():
        raise ValidationException(
            "牌定义缺少 rankCode: {0}".format(definition.cardCode)
        )
    if definition.rankValue is None:
        raise ValidationException(
            "牌定义缺少 rankValue: {0}".format(definition.cardCode)
        )
    return DoudizhuCard(
        cardInstanceId=instance_id,
        cardCode=definition.cardCode,
        category=definition.category,
        rankCode=str(rank_code),
        rankValue=int(definition.rankValue),
        suitCode=definition.suitCode,
        suitLabel=definition.suitLabel,
        displayLabel=definition.displayLabel,
        displayColor=_resolve_display_color(definition),
        image=definition.image,
        isJoker=is_joker,
        isLaizi=False,
    )
