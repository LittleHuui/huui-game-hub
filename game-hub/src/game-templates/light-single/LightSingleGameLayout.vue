<template>
  <div class="light-single-layout">
    <aside class="light-single-layout__side">
      <LightSingleGameSidePanel
        :game-title="gameTitle"
        :game-subtitle="gameSubtitle"
        :game-description="gameDescription"
        :game-status-text="gameStatusText"
        :info-stats="infoStats"
        :fields="controlFields"
        :action-items="actionItems"
        @field-change="$emit('field-change', $event)"
        @action="$emit('action', $event)"
      >
        <template v-if="$slots['title-extra']" #title-extra>
          <slot name="title-extra" />
        </template>
        <template v-if="$slots['game-info-extra']" #game-info-extra>
          <slot name="game-info-extra" />
        </template>
      </LightSingleGameSidePanel>

      <slot v-if="showShop" name="shop" />
      <slot v-if="showRanking" name="ranking" />
      <slot name="left-extra" />
    </aside>

    <main class="light-single-layout__main">
      <section v-if="$slots['match-stats']" class="game-card light-single-match-panel">
        <h2 v-if="boardTitle" class="game-card__title">{{ boardTitle }}</h2>
        <div class="game-card__body">
          <slot name="match-stats" />
        </div>
      </section>

      <LightSingleGameBoardFrame
        :title="boardFrameTitle"
        :subtitle="boardSubtitle"
        :paused="paused"
        :pause-title="pauseTitle"
        :pause-description="pauseDescription"
        :pause-action-text="pauseActionText"
        @resume="$emit('resume')"
      >
        <slot name="board" />
      </LightSingleGameBoardFrame>

      <slot v-if="showInventory" name="inventory" />
      <slot name="right-extra" />
    </main>
  </div>
</template>

<script setup>
import './light-single.css';
import LightSingleGameSidePanel from './LightSingleGameSidePanel.vue';
import LightSingleGameBoardFrame from './LightSingleGameBoardFrame.vue';

defineProps({
  gameTitle: {
    type: String,
    default: ''
  },
  gameSubtitle: {
    type: String,
    default: ''
  },
  gameDescription: {
    type: String,
    default: ''
  },
  gameStatusText: {
    type: String,
    default: ''
  },
  infoStats: {
    type: Array,
    default: () => []
  },
  /** 左侧配置项（select / radio / switch），由业务页计算 */
  controlFields: {
    type: Array,
    default: () => []
  },
  actionItems: {
    type: Array,
    default: () => []
  },
  showShop: {
    type: Boolean,
    default: true
  },
  showRanking: {
    type: Boolean,
    default: true
  },
  showInventory: {
    type: Boolean,
    default: true
  },
  gameCode: {
    type: String,
    default: ''
  },
  mode: {
    type: String,
    default: ''
  },
  difficultyCode: {
    type: String,
    default: ''
  },
  /** 右侧对局信息区标题（与棋盘外框标题分离） */
  boardTitle: {
    type: String,
    default: '对局信息'
  },
  /** 棋盘外框标题；为空则不显示外框头部 */
  boardFrameTitle: {
    type: String,
    default: ''
  },
  boardSubtitle: {
    type: String,
    default: ''
  },
  paused: {
    type: Boolean,
    default: false
  },
  pauseTitle: {
    type: String,
    default: ''
  },
  pauseDescription: {
    type: String,
    default: ''
  },
  pauseActionText: {
    type: String,
    default: ''
  }
});

defineEmits(['action', 'field-change', 'resume']);
</script>
