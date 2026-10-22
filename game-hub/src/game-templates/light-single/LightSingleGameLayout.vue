<template>
  <div class="light-single-layout">
    <LightSingleGameSidePanel :game-title="gameTitle" :game-subtitle="gameSubtitle"
      :game-description="gameDescription" :game-status-text="gameStatusText"
      :info-stats="infoStats" :fields="controlFields" :action-items="actionItems"
      @field-change="$emit('field-change', $event)" @action="$emit('action', $event)">
      <template #title-extra><slot name="title-extra" /></template>
      <template #game-info-extra><slot name="game-info-extra" /></template>
    </LightSingleGameSidePanel>
    <main class="light-single-layout__main">
      <div v-if="$slots['match-stats']" class="light-single-match-panel"><slot name="match-stats" /></div>
      <LightSingleGameBoardFrame :title="boardFrameTitle" :subtitle="boardSubtitle"
        :paused="paused" :pause-title="pauseTitle" :pause-description="pauseDescription"
        :pause-action-text="pauseActionText" @resume="$emit('resume')">
        <slot name="board" />
      </LightSingleGameBoardFrame>
      <div v-if="showInventory" class="light-single-layout__inventory"><slot name="inventory" /></div>
      <nav class="light-single-resources" aria-label="游戏资源">
        <button v-if="showShop" type="button" @click="resource = 'shop'"><AppIcon name="shop" />道具商城</button>
        <button v-if="showRanking" type="button" @click="resource = 'ranking'"><AppIcon name="trophy" />排行榜</button>
        <button type="button" @click="resource = 'help'"><AppIcon name="info" />玩法说明</button>
      </nav>
      <slot name="left-extra" /><slot name="right-extra" />
    </main>
    <AppModal :visible="Boolean(resource)" :title="resourceTitle" @close="resource = ''">
      <slot v-if="resource === 'shop'" name="shop" />
      <slot v-else-if="resource === 'ranking'" name="ranking" />
      <div v-else class="light-single-help"><p>{{ gameDescription }}</p><p>{{ boardSubtitle }}</p><slot name="game-info-extra" /></div>
    </AppModal>
  </div>
</template>
<script setup>
import { computed, inject, provide, ref } from 'vue';
import { GH_OPEN_HUB_MODAL } from '../../constants/injectionKeys.js';
import AppModal from '../../components/AppModal.vue';
import AppIcon from '../../components/ui/AppIcon.vue';
import LightSingleGameSidePanel from './LightSingleGameSidePanel.vue';
import LightSingleGameBoardFrame from './LightSingleGameBoardFrame.vue';
defineProps({
  gameTitle: { type: String, default: '' }, gameSubtitle: { type: String, default: '' },
  gameDescription: { type: String, default: '' }, gameStatusText: { type: String, default: '' },
  infoStats: { type: Array, default: () => [] }, controlFields: { type: Array, default: () => [] },
  actionItems: { type: Array, default: () => [] }, showShop: { type: Boolean, default: true },
  showRanking: { type: Boolean, default: true }, showInventory: { type: Boolean, default: true },
  gameCode: { type: String, default: '' }, mode: { type: String, default: '' },
  difficultyCode: { type: String, default: '' }, boardTitle: { type: String, default: '对局信息' },
  boardFrameTitle: { type: String, default: '' }, boardSubtitle: { type: String, default: '' },
  paused: { type: Boolean, default: false }, pauseTitle: { type: String, default: '游戏已暂停' },
  pauseDescription: { type: String, default: '准备好后继续本局' }, pauseActionText: { type: String, default: '继续游戏' }
});
defineEmits(['action', 'field-change', 'resume']);
const resource = ref('');
const openHubModal = inject(GH_OPEN_HUB_MODAL, () => {});
provide(GH_OPEN_HUB_MODAL, (type) => {
  resource.value = '';
  openHubModal(type);
});
const resourceTitle = computed(() => ({ shop: '道具商城', ranking: '排行榜', help: '玩法说明' })[resource.value] || '');
</script>
