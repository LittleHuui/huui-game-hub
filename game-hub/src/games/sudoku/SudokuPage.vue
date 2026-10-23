<template>
  <div>
    <LightSingleGameLayout class="sudoku-layout"
      :game-title="layoutGameTitle"
      :game-description="layoutGameDescription"
      :game-status-text="layoutGameStatusText"
      :control-fields="controlFields"
      :action-items="actionItems"
      :show-shop="true"
      :show-ranking="true"
      :show-inventory="true"
      board-frame-title="对局区域"
      board-subtitle="点击空格填数 · 可开启草稿模式 · 右键擦除"
      :paused="isPaused"
      @field-change="onControlFieldChange"
      @action="onLayoutAction"
      @resume="resumeGame"
    >
      <template #shop>
        <GameShopPanel :game-code="SUDOKU_CODE" :session-id="matchSessionId" />
      </template>

      <template #ranking>
        <GameRankingPanel
          :game-code="SUDOKU_CODE"
          :mode="SUDOKU_MODE"
          :difficulty-code="difficultyCode"
          value-metric="durationMs"
          :subtitle="`${difficultyLabel} · 全服前十名（按用时排序）`"
        />
      </template>

      <template #match-stats>
        <GameMatchStatsPanel
          :stats="matchStats"
          :summary-keys="['duration','filled','empty']"
          :quotas="matchQuotas"
          :message="matchStatsMessage"
        />
      </template>

      <template #board>
        <SudokuBoard
          ref="boardRef"
          :cells="cells"
          :selected-row="selectedRow"
          :selected-col="selectedCol"
          :draft-mode="draftMode"
          :draft-toggle-disabled="!canInteractBoard"
          :interaction-disabled="!canInteractBoard"
          :popup-visible="popupVisible"
          :popup-position="popupPosition"
          :popup-placement="popupPlacement"
          :available-numbers="popupAvailableNumbers"
          @select-cell="onSelectCell"
          @erase-cell="onEraseCell"
          @pick-number="onPickNumber"
          @update:draft-mode="draftMode = $event"
          @close-popup="closePopup"
        />
        <SudokuNumberPanel class="sudoku-board-number-panel" :remaining="remainingCounts"
          :available-numbers="popupAvailableNumbers" :disabled="!canInteractBoard || selectedRow < 0 || selectedCol < 0 || cells[selectedRow]?.[selectedCol]?.fixed"
          @pick="onPickNumber" />
      </template>

      <template #inventory>
        <GameInventoryPanel
          :game-code="SUDOKU_CODE"
          :usable-props="[SUDOKU_PROP.HINT]"
          :disabled-props="inventoryDisabledProps"
          :use-labels="inventoryUseLabels"
          @use-prop="useHintProp"
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
import { pageComponents, useSudokuPage } from './useSudokuPage.js';

export default {
  name: 'SudokuPage',
  components: pageComponents,
  setup: useSudokuPage
};
</script>
