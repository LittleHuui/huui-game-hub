<template>
  <div>
    <LightSingleGameLayout
      :game-title="layoutGameTitle"
      :game-subtitle="layoutGameSubtitle"
      :game-description="layoutGameDescription"
      :game-status-text="layoutGameStatusText"
      :control-fields="controlFields"
      :action-items="actionItems"
      :show-shop="true"
      :show-ranking="true"
      :show-inventory="true"
      :game-code="GAME2048_CODE"
      :mode="GAME2048_MODE"
      :difficulty-code="difficultyCode"
      board-title="对局信息"
      board-frame-title="对局区域"
      board-subtitle="方向键 / WASD / 滑动操作"
      :paused="isPaused"
      @action="onLayoutAction"
      @resume="resumeGame"
    >
      <template #shop>
        <GameShopPanel :game-code="GAME2048_CODE" :session-id="matchSessionId" />
      </template>

      <template #ranking>
        <GameRankingPanel
          :game-code="GAME2048_CODE"
          :mode="GAME2048_MODE"
          :difficulty-code="difficultyCode"
          value-metric="score"
          subtitle="经典模式 · 全服前十名（按得分排序）"
        />
      </template>

      <template #match-stats>
        <GameMatchStatsPanel
          :stats="matchStats"
          :quotas="matchQuotas"
          :message="matchStatsMessage"
          theme-seed="2048"
        />
      </template>

      <template #board>
        <div class="game2048-wrap">
          <Game2048Board
            ref="boardComponentRef"
            :tiles="tiles"
            :select-mode="isPropSelecting"
            :move-input-locked="moveInputLocked"
            :board-style="boardAnimationStyle"
            :slide-offsets="slideOffsets"
            :new-tile-ids="newTileIds"
            :merged-tile-ids="mergedTileIds"
            :clearing-tile-id="clearingTileId"
            @move="handleMoveInput"
            @cell-select="handleClearCellSelect"
          />
        </div>
      </template>

      <template #inventory>
        <GameInventoryPanel
          :game-code="GAME2048_CODE"
          :usable-props="[GAME2048_PROP.CLEAR_CELL]"
          :active-prop="activeTool === GAME2048_PROP.CLEAR_CELL ? GAME2048_PROP.CLEAR_CELL : ''"
          :disabled-props="inventoryDisabledProps"
          :use-labels="inventoryUseLabels"
          @use-prop="useProp"
        />
      </template>
    </LightSingleGameLayout>

    <GameResultModal
      :visible="resultModal.visible"
      :title="resultModal.title"
      :subtitle="resultModal.subtitle"
      :result-type="resultModal.resultType"
      :stats="resultModal.stats"
      :rewards="resultModal.rewards"
      :highlights="resultModal.highlights"
      :actions="resultModal.actions"
      @action="onResultModalAction"
      @close="resultModal.visible = false"
    />
  </div>
</template>

<script>
import { pageComponents, useGame2048Page } from './useGame2048Page.js';

export default {
  name: 'Game2048Page',
  components: pageComponents,
  setup: useGame2048Page
};
</script>
