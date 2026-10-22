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
      :game-code="MINESWEEPER_GAME_CODE"
      :mode="MINESWEEPER_MODE"
      :difficulty-code="difficulty"
      board-title="对局信息"
      board-frame-title="对局区域"
      board-subtitle="左键翻开 · 右键标记"
      :paused="isPaused"
      @field-change="handleControlChange"
      @action="handleControlAction"
      @resume="resumeGame"
    >
      <template #game-info-extra>
        <p>积分规则：胜利获得当前难度满积分（初级 100 / 中级 300 / 高级 800）；失败或主动结束时，按正确标记雷数 × 3 结算。</p>
      </template>

      <template #shop>
        <GameShopPanel :game-code="MINESWEEPER_GAME_CODE" :session-id="matchSessionId" />
      </template>

      <template #ranking>
        <GameRankingPanel
          :game-code="MINESWEEPER_GAME_CODE"
          :mode="MINESWEEPER_MODE"
          :difficulty-code="difficulty"
          value-metric="durationMs"
          :subtitle="`${difficultyLabel} · 全服前十名（按用时排序）`"
        />
      </template>

      <template #match-stats>
        <GameMatchStatsPanel
          :stats="matchStats"
          :summary-keys="['remainMines','duration','opened','flagged']"
          :quotas="matchQuotas"
          :message="gameMessage"
          :theme-seed="statThemeSeed"
        />
      </template>

      <template #board>
        <MinesweeperBattlePanel
          :board="board"
          :rows="rows"
          :cols="cols"
          :window-width="windowWidth"
          :neighbor-ring-keys="neighborRingKeys"
          :board-shake="boardShake"
          :game-win="gameWin"
          @cell-click="clickCell"
          @cell-right="rightClick"
          @ring-enter="onNeighborRingCellEnter"
          @ring-leave="onNeighborRingCellLeave"
          @clear-ring="clearNeighborRing"
        />
      </template>

      <template #inventory>
        <GameInventoryPanel
          :game-code="MINESWEEPER_GAME_CODE"
          :usable-props="[MINESWEEPER_PROP.HINT]"
          :active-prop="activeTool === 'hint' ? MINESWEEPER_PROP.HINT : ''"
          :disabled-props="inventoryDisabledProps"
          :use-labels="inventoryUseLabels"
          @use-prop="onInventoryUseProp"
        >
          <template #item-extra="{ item }">
            <button
              v-if="item.propCode === MINESWEEPER_PROP.REVIVE"
              type="button"
              class="game-inventory-use minesweeper-auto-revive-btn"
              :class="{ 'minesweeper-auto-revive-btn--active': user.autoRevive }"
              :disabled="reviveQty <= 0"
              :aria-pressed="user.autoRevive"
              title="有卡且本局未复活时，踩雷自动消耗一张"
              @click="setAutoRevive(!user.autoRevive)"
            >
              自动复活
            </button>
          </template>
        </GameInventoryPanel>
      </template>
    </LightSingleGameLayout>

    <MinesweeperReviveModal
      :visible="reviveOffer.visible"
      :seconds-left="reviveOffer.secondsLeft"
      :revive-disabled="reviveQty <= 0"
      @confirm="confirmReviveOffer"
      @decline="declineReviveOffer"
    />

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
import { pageComponents, useMinesweeperPage } from './useMinesweeperPage.js';

export default {
  name: 'MinesweeperPage',
  components: pageComponents,
  setup: useMinesweeperPage
};
</script>
