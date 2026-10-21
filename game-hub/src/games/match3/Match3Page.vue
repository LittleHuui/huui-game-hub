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
      @field-change="onControlFieldChange"
      @action="onLayoutAction"
      :show-ranking="true"
      :show-inventory="true"
      :game-code="MATCH3"
      :mode="mode"
      :difficulty-code="difficultyCode"
      board-title="对局信息"
      board-frame-title="对局区域"
      board-subtitle="拖动相邻方块交换以消除"
      :paused="isPaused"
      @resume="resumeGame"
    >
      <template #shop>
        <GameShopPanel :game-code="MATCH3" :session-id="matchSessionId" />
      </template>

      <template #ranking>
        <GameRankingPanel
          :game-code="MATCH3"
          :mode="mode"
          :difficulty-code="difficultyCode"
          value-metric="score"
          :subtitle="rankingSubtitle"
        />
      </template>

      <template #match-stats>
        <GameMatchStatsPanel
          :stats="matchStats"
          :quotas="matchQuotas"
          :message="gameMessage"
          :theme-seed="statThemeSeed"
        />
      </template>

      <template #board>
        <div class="match3-board-wrap">
          <div v-if="chainHint" class="match3-chain-hint">{{ chainHint }}</div>
          <Match3Board
            :board="board"
            :items="gameConfig.items || []"
            :active-tool="activeTool"
            :cell-visuals="cellVisuals"
            :cell-size="clientConfig.cellSize || 44"
            :input-locked="inputLocked"
            :swap-ms="animationConfig.swapMs"
            :remove-ms="animationConfig.removeMs"
            :drop-ms="animationConfig.dropMs"
            @swap-request="handleSwapRequest"
            @cell-click="handleBombCellClick"
          />
        </div>
      </template>

      <template #inventory>
        <GameInventoryPanel
          :game-code="MATCH3"
          :usable-props="[MATCH3_PROP.SHUFFLE, MATCH3_PROP.BOMB]"
          :active-prop="activeTool === 'bomb' ? MATCH3_PROP.BOMB : ''"
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
import { pageComponents, useMatch3Page } from './useMatch3Page.js';

export default {
  name: 'Match3Page',
  components: pageComponents,
  setup: useMatch3Page
};
</script>

<style scoped>
.match3-board-wrap {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
}

.match3-chain-hint {
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  z-index: 2;
  padding: 8px 16px;
  border-radius: 999px;
  color: #fff7ed;
  background: rgba(249, 115, 22, 0.86);
  animation: match3Hint 420ms ease;
  pointer-events: none;
}

@keyframes match3Hint {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(10px) scale(0.9);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0) scale(1);
  }
}
</style>
