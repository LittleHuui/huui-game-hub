<template>
  <section v-if="shopEnabled" class="game-card game-shop-panel">
    <div class="game-shop-head">
      <h2 class="game-card__title">道具商城</h2>
      <button type="button" class="game-shop-link" @click="openPurchaseRecords">购买记录</button>
    </div>
    <p v-if="scoreLine" class="muted-small game-shop-score">{{ scoreLine }}</p>
    <p v-if="items.length === 0" class="game-empty">暂无在售道具</p>
    <div v-else class="game-shop-list">
      <article v-for="item in items" :key="item.propCode" class="game-shop-item">
        <div class="game-shop-item-head">
          <h3 class="game-shop-item-name">
            <span v-if="item.icon" class="game-shop-icon" aria-hidden="true">{{ item.icon }}</span>
            <span v-else class="game-shop-icon game-shop-icon--fallback" aria-hidden="true">?</span>
            {{ item.name }}
          </h3>
          <span class="game-shop-bag">背包 {{ bagCount(item.propCode) }} 张</span>
        </div>
        <p v-if="item.description" class="game-shop-desc">{{ item.description }}</p>
        <p v-if="item.maxUsePerMatch != null" class="game-shop-meta">每局最多使用 {{ item.maxUsePerMatch }} 次</p>
        <div class="game-shop-actions">
          <span class="game-shop-price">{{ item.price }} 积分 / 张</span>
          <button type="button" class="warning" :disabled="disabled" @click="handleBuy(item.propCode)">购买</button>
        </div>
      </article>
    </div>
  </section>
  <section v-else-if="showUnavailable" class="game-card game-shop-panel">
    <h2 class="game-card__title">道具商城</h2>
    <p class="game-empty">当前游戏暂无商城</p>
  </section>
</template>

<script setup>
import { computed, inject } from 'vue';
import { hasGameCapability } from '../../constants/gameRegistry.js';
import { GH_OPEN_HUB_MODAL } from '../../constants/injectionKeys.js';
import * as purchaseService from '../../services/purchaseService.js';
import { useGamePropQuantities } from '../../composables/useGamePropQuantities.js';
import { useShopStore } from '../../stores/shopStore.js';
import { useUserStore } from '../../stores/userStore.js';

const props = defineProps({
  gameCode: {
    type: String,
    required: true
  },
  disabled: {
    type: Boolean,
    default: false
  },
  sessionId: {
    type: [Object, String, null],
    default: null
  },
  showUnavailable: {
    type: Boolean,
    default: true
  }
});

const emit = defineEmits(['purchased']);

const shopStore = useShopStore();
const userStore = useUserStore();
const openHubModal = inject(GH_OPEN_HUB_MODAL, () => {});
const propQuantities = useGamePropQuantities(() => props.gameCode);

const shopEnabled = computed(() => hasGameCapability(props.gameCode, 'shop'));
const items = computed(() => shopStore.itemsForGame(props.gameCode));

const scoreLine = computed(() => {
  const u = userStore.currentUser;
  if (!u) {
    return '';
  }
  return `当前积分：${u.score || 0} ｜ 总积分：${u.totalScore || 0}`;
});

/**
 * 背包数量（inventory 流水 + 服务端 bag）。
 * @param {string} propCode
 * @returns {number}
 */
function bagCount(propCode) {
  return propQuantities.value[propCode] || 0;
}

/**
 * 打开购买记录弹窗。
 */
function openPurchaseRecords() {
  openHubModal('purchase');
}

/**
 * 购买道具。
 * @param {string} propCode
 */
async function handleBuy(propCode) {
  if (props.disabled) {
    return;
  }
  await purchaseService.buyProp({
    propCode,
    sessionId: props.sessionId,
    gameCode: props.gameCode
  });
  emit('purchased', propCode);
}
</script>
