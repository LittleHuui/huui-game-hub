<template>
  <div v-if="!leaderboardEnabled && showUnavailableWhenDisabled" class="panel">
    <h2>总排行榜</h2>
    <p class="empty-text" style="margin-bottom: 0">当前游戏暂无排行榜</p>
  </div>
  <div v-else-if="leaderboardEnabled" class="panel">
    <h2>总排行榜</h2>
    <div class="muted-small" style="margin-bottom: 10px">
      {{ difficultyLabel }} · 全服前十名（按成绩排序）
    </div>
    <p
      v-if="platform.networkMode !== 'online' && platform.networkMode !== 'degraded'"
      class="empty-text"
      style="margin-bottom: 0"
    >
      当前为离线模式，排行榜联网后可查看。
    </p>
    <template v-else>
      <div v-if="rows.length === 0" class="empty-text" style="margin-bottom: 0">该难度暂无上榜记录</div>
      <div
        v-for="(item, index) in rows"
        v-else
        :key="item.userId || index"
        class="ranking-item"
        :class="{
          'ranking-item--first': displayRank(item, index) === 1,
          'ranking-item--second': displayRank(item, index) === 2,
          'ranking-item--third': displayRank(item, index) === 3
        }"
      >
        <div class="ranking-item-left">
          <span class="ranking-name-line">
            <span class="ranking-rank-badge">{{ displayRank(item, index) }}</span>
            {{ item.nickname }}
          </span>
          <span v-if="displayAt(item)" class="ranking-date">{{ displayAt(item) }}</span>
        </div>
        <span class="ranking-time">{{ formatDuration(item) }}</span>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { hasGameCapability } from '../constants/gameRegistry.js';
import { useRankingStore } from '../stores/rankingStore.js';
import { usePlatformStore } from '../stores/platformStore.js';
import { formatDisplayTime } from '../utils/formatTime.js';

const props = defineProps({
  gameCode: {
    type: String,
    default: 'minesweeper'
  },
  difficulty: { type: String, required: true },
  difficultyLabel: { type: String, required: true },
  mode: {
    type: String,
    default: 'single'
  },
  showUnavailableWhenDisabled: {
    type: Boolean,
    default: true
  }
});

const ranking = useRankingStore();
const platform = usePlatformStore();

const leaderboardEnabled = computed(() => hasGameCapability(props.gameCode, 'leaderboard'));

const rows = computed(() => {
  if (!leaderboardEnabled.value) {
    return [];
  }
  const raw = ranking.listForDifficulty(props.gameCode, props.difficulty, props.mode);
  return Array.isArray(raw) ? raw.slice(0, 10) : [];
});

function displayRank(item, index) {
  return item.rank != null ? item.rank : index + 1;
}

function displayAt(item) {
  const ts = item.createdAt;
  if (ts != null && Number.isFinite(ts)) {
    return formatDisplayTime(ts);
  }
  return '';
}

function formatDuration(item) {
  if (item.score != null && props.gameCode === 'match3') {
    return `${item.score} 分`;
  }
  if (item.durationMs != null && Number.isFinite(item.durationMs)) {
    return `${(item.durationMs / 1000).toFixed(1)} 秒`;
  }
  if (item.time != null) {
    return `${item.time} 秒`;
  }
  return '—';
}
</script>
