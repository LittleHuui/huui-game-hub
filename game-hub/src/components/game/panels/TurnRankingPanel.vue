<template>
  <section class="turn-ranking-panel game-card">
    <h2 v-if="title" class="turn-ranking-panel__title">{{ title }}</h2>
    <p v-if="!sortedItems.length" class="empty-text">{{ emptyText }}</p>
    <ul v-else class="turn-ranking-panel__list">
      <li
        v-for="item in sortedItems"
        :key="item.playerId"
        class="turn-ranking-panel__item"
        :class="{ 'turn-ranking-panel__item--viewer': item.isViewer }"
      >
        <span class="turn-ranking-panel__rank">{{ formatRank(item.rank) }}</span>
        <div class="turn-ranking-panel__avatar" :title="item.nickname">
          <img v-if="item.avatarUrl" :src="item.avatarUrl" :alt="item.nickname" />
          <span v-else aria-hidden="true">{{ item.avatarInitial }}</span>
        </div>
        <div class="turn-ranking-panel__info">
          <p class="turn-ranking-panel__name">{{ item.nickname }}</p>
          <p v-if="item.label" class="turn-ranking-panel__label">{{ item.label }}</p>
        </div>
      </li>
    </ul>
  </section>
</template>

<script setup>
import { computed } from 'vue';
import '../controls/turnGame.css';

const props = defineProps({
  title: {
    type: String,
    default: '排名'
  },
  emptyText: {
    type: String,
    default: '暂无排名'
  },
  /** @type {import('vue').PropType<Array<{ playerId: string; rank?: number; nickname?: string; avatar?: string; label?: string; isViewer?: boolean }>>} */
  rankings: {
    type: Array,
    default: () => []
  }
});

/**
 * @param {number|null|undefined} rank
 * @returns {string}
 */
function formatRank(rank) {
  if (rank == null || !Number.isFinite(Number(rank))) {
    return '—';
  }
  return `#${Number(rank)}`;
}

/**
 * 归一化并排序排名项。
 */
const sortedItems = computed(() => {
  const list = (props.rankings || [])
    .map((raw) => {
      const playerId = String(raw?.playerId || '').trim();
      if (!playerId) {
        return null;
      }
      const nickname = String(raw?.nickname || '').trim() || playerId;
      const avatarUrl = String(raw?.avatar || '').trim();
      return {
        playerId,
        rank: raw?.rank != null && Number.isFinite(Number(raw.rank)) ? Number(raw.rank) : null,
        nickname,
        avatarUrl,
        avatarInitial: nickname.charAt(0) || '?',
        label: String(raw?.label || '').trim(),
        isViewer: Boolean(raw?.isViewer)
      };
    })
    .filter(Boolean);

  return list.sort((a, b) => {
    if (a.rank == null && b.rank == null) {
      return a.nickname.localeCompare(b.nickname);
    }
    if (a.rank == null) {
      return 1;
    }
    if (b.rank == null) {
      return -1;
    }
    return a.rank - b.rank;
  });
});
</script>
