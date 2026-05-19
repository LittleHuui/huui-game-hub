<template>
  <section v-if="leaderboardEnabled" class="game-card game-ranking-panel">
    <h2 class="game-card__title">总排行榜</h2>
    <p v-if="subtitle" class="game-ranking-sub">{{ subtitle }}</p>
    <p
      v-if="platform.networkMode !== 'online' && platform.networkMode !== 'degraded'"
      class="game-empty"
    >
      当前为离线模式，排行榜联网后可查看。
    </p>
    <template v-else>
      <p v-if="rows.length === 0" class="game-empty">该难度暂无上榜记录</p>
      <div
        v-for="(item, index) in rows"
        v-else
        :key="item.userId || `${index}`"
        class="game-ranking-item"
        :class="rankClass(displayRank(item, index))"
      >
        <div class="game-ranking-left">
          <span class="game-ranking-name">
            <span class="game-ranking-badge">{{ displayRank(item, index) }}</span>
            {{ item.nickname }}
          </span>
          <span v-if="displayAt(item)" class="game-ranking-date">{{ displayAt(item) }}</span>
        </div>
        <span class="game-ranking-value">{{ formatValue(item) }}</span>
      </div>
    </template>
  </section>
  <section v-else-if="showUnavailable" class="game-card game-ranking-panel">
    <h2 class="game-card__title">总排行榜</h2>
    <p class="game-empty">当前游戏暂无排行榜</p>
  </section>
</template>

<script setup>
import { computed, watch, onMounted } from 'vue';
import { hasGameCapability } from '../../constants/gameRegistry.js';
import { useRankingStore } from '../../stores/rankingStore.js';
import { usePlatformStore } from '../../stores/platformStore.js';
import * as rankingService from '../../services/rankingService.js';
import { formatDisplayTime } from '../../utils/formatTime.js';

const props = defineProps({
  gameCode: {
    type: String,
    required: true
  },
  mode: {
    type: String,
    default: 'single'
  },
  difficultyCode: {
    type: String,
    required: true
  },
  limit: {
    type: Number,
    default: 10
  },
  subtitle: {
    type: String,
    default: ''
  },
  showUnavailable: {
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
  const raw = ranking.listForDifficulty(props.gameCode, props.difficultyCode, props.mode);
  const list = Array.isArray(raw) ? raw : [];
  return list.slice(0, props.limit);
});

/**
 * 刷新当前难度排行榜。
 * @returns {Promise<void>}
 */
async function refreshCurrent() {
  if (!leaderboardEnabled.value || !props.difficultyCode) {
    return;
  }
  await rankingService.refreshGameLeaderboard(props.gameCode, props.difficultyCode, props.mode);
}

watch(
  () => [props.gameCode, props.mode, props.difficultyCode],
  () => {
    refreshCurrent();
  }
);

onMounted(() => {
  refreshCurrent();
});

/**
 * @param {object} item
 * @param {number} index
 * @returns {number}
 */
function displayRank(item, index) {
  return item.rank != null ? item.rank : index + 1;
}

/**
 * @param {object} item
 * @returns {string}
 */
function displayAt(item) {
  const ts = item.createdAt;
  if (ts != null && Number.isFinite(ts)) {
    return formatDisplayTime(ts);
  }
  return '';
}

/**
 * @param {object} item
 * @returns {string}
 */
function formatValue(item) {
  if (item.score != null && Number.isFinite(Number(item.score))) {
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

/**
 * @param {number} rank
 * @returns {string}
 */
function rankClass(rank) {
  if (rank === 1) {
    return 'game-ranking-item--first';
  }
  if (rank === 2) {
    return 'game-ranking-item--second';
  }
  if (rank === 3) {
    return 'game-ranking-item--third';
  }
  return '';
}
</script>
