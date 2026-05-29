<template>
  <div class="turn-action-bar">
    <div class="turn-action-bar__actions">
      <button
        type="button"
        class="game-action-btn turn-action-bar__btn--play game-action-btn--md"
        :disabled="isPlayDisabled"
        :title="managedBlockedHint"
        @click="onBarAction(TURN_ACTION_BAR_KEY.PLAY)"
      >
        出牌
      </button>
      <slot name="middle" />
      <button
        type="button"
        class="game-action-btn turn-action-bar__btn--draw game-action-btn--md"
        :disabled="isDrawDisabled"
        :title="managedBlockedHint"
        @click="onBarAction(TURN_ACTION_BAR_KEY.DRAW)"
      >
        摸牌
      </button>
      <button
        type="button"
        class="game-action-btn turn-action-bar__btn--hint game-action-btn--md"
        :disabled="isHintDisabled"
        :title="managedBlockedHint"
        @click="onBarAction(TURN_ACTION_BAR_KEY.UI_ACTION_HINT)"
      >
        提示
      </button>
      <button
        type="button"
        class="game-action-btn turn-action-bar__btn--end game-action-btn--md"
        :disabled="isEndTurnDisabled"
        :title="managedBlockedHint"
        @click="onBarAction(TURN_ACTION_BAR_KEY.END_TURN)"
      >
        结束回合
      </button>
    </div>
    <div v-if="showCountdown" class="turn-action-bar__countdown">
      <TurnCountdown :seconds="countdownSeconds" :expires-at-ms="countdownExpiresAtMs" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import TurnCountdown from './TurnCountdown.vue';
import {
  filterStrategyTurnActionsByType,
  hasStrategyTurnActionType
} from './turnActionUtils.js';
import { STRATEGY_TURN_ACTION_TYPE, TURN_ACTION_BAR_KEY } from './turnControlEnums.js';
import './turnGame.css';

const props = defineProps({
  /** @type {import('vue').PropType<Array<{ actionType?: string; actionKey?: string; playerId?: string; payload?: object }>>} */
  legalActions: {
    type: Array,
    default: () => []
  },
  disabled: {
    type: Boolean,
    default: false
  },
  busy: {
    type: Boolean,
    default: false
  },
  managedBlocked: {
    type: Boolean,
    default: false
  },
  countdownSeconds: {
    type: Number,
    default: null
  },
  countdownExpiresAtMs: {
    type: Number,
    default: null
  },
  showCountdown: {
    type: Boolean,
    default: true
  },
  playEnabled: {
    type: Boolean,
    default: null
  },
  hintEnabled: {
    type: Boolean,
    default: null
  }
});

const emit = defineEmits(['action']);

const canDraw = computed(() =>
  hasStrategyTurnActionType(props.legalActions, STRATEGY_TURN_ACTION_TYPE.DRAW_CARD)
);
const canPlay = computed(() =>
  hasStrategyTurnActionType(props.legalActions, STRATEGY_TURN_ACTION_TYPE.PLAY_CARD)
);
const canHint = computed(() => props.hintEnabled === true);
const canEndTurn = computed(() =>
  hasStrategyTurnActionType(props.legalActions, STRATEGY_TURN_ACTION_TYPE.PASS_TURN)
);

const interactionBlocked = computed(() => props.disabled || props.busy || props.managedBlocked);

const managedBlockedHint = computed(() =>
  props.managedBlocked ? '请先取消托管' : ''
);

const isDrawDisabled = computed(() => interactionBlocked.value || !canDraw.value);
const isPlayDisabled = computed(() => {
  if (interactionBlocked.value) {
    return true;
  }
  if (props.playEnabled != null) {
    return !props.playEnabled;
  }
  return !canPlay.value;
});
const isHintDisabled = computed(() => interactionBlocked.value || !canHint.value);
const isEndTurnDisabled = computed(() => interactionBlocked.value || !canEndTurn.value);

/**
 * 将操作栏按钮映射为 actionType 并上报匹配到的 legalActions。
 * @param {string} barKey
 */
function onBarAction(barKey) {
  if (interactionBlocked.value) {
    return;
  }
  let actionType = '';
  switch (barKey) {
    case TURN_ACTION_BAR_KEY.DRAW:
      if (!canDraw.value) {
        return;
      }
      actionType = STRATEGY_TURN_ACTION_TYPE.DRAW_CARD;
      break;
    case TURN_ACTION_BAR_KEY.PLAY:
      if (!canPlay.value) {
        return;
      }
      actionType = STRATEGY_TURN_ACTION_TYPE.PLAY_CARD;
      break;
    case TURN_ACTION_BAR_KEY.UI_ACTION_HINT:
      if (!canHint.value) {
        return;
      }
      emit('action', {
        barKey: TURN_ACTION_BAR_KEY.UI_ACTION_HINT,
        actionType: '',
        legalActions: []
      });
      return;
    case TURN_ACTION_BAR_KEY.END_TURN:
      if (!canEndTurn.value) {
        return;
      }
      actionType = STRATEGY_TURN_ACTION_TYPE.PASS_TURN;
      break;
    default:
      return;
  }
  emit('action', {
    barKey,
    actionType,
    legalActions: filterStrategyTurnActionsByType(props.legalActions, actionType)
  });
}
</script>
