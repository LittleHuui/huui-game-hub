<template>
  <section class="game-card game-inventory-panel">
    <p v-if="displayItems.length === 0" class="game-empty">暂无道具</p>
    <div v-else class="game-inventory-list">
      <div
        v-for="item in displayItems"
        :key="item.propCode"
        class="game-inventory-slot"
        :class="{ 'is-exhausted': item.quantity <= 0 }"
      >
        <span v-if="item.icon" class="game-shop-icon game-inventory-icon" :title="item.name">{{ item.icon }}</span>
        <span v-else class="game-shop-icon game-shop-icon--placeholder game-inventory-icon" aria-hidden="true">?</span>
        <span class="game-inventory-name">{{ item.name }}</span>
        <span class="game-inventory-count">×{{ item.quantity }}</span>
        <button
          v-if="canUse(item.propCode)"
          type="button"
          class="game-inventory-use"
          :class="{ 'is-active': activeProp === item.propCode }"
          :disabled="isUseDisabled(item.propCode)"
          @click="$emit('use-prop', item.propCode)"
        >
          {{ useLabel(item.propCode) }}
        </button>
        <slot name="item-extra" :item="item" />
      </div>
    </div>
    <slot name="footer" />
  </section>
</template>

<script setup>
import { computed } from 'vue';
import { useShopStore } from '../../../stores/shopStore.js';
import { useUserStore } from '../../../stores/userStore.js';
import { useInventoryStore } from '../../../stores/inventoryStore.js';
import { quantitiesForUserGame } from '../../../utils/inventoryQuantity.js';

const props = defineProps({
  gameCode: {
    type: String,
    required: true
  },
  usableProps: {
    type: Array,
    default: () => []
  },
  readonly: {
    type: Boolean,
    default: false
  },
  activeProp: {
    type: String,
    default: ''
  },
  disabledProps: {
    type: Object,
    default: () => ({})
  },
  useLabels: {
    type: Object,
    default: () => ({})
  }
});

defineEmits(['use-prop']);

const shopStore = useShopStore();
const userStore = useUserStore();
const inventoryStore = useInventoryStore();

const quantities = computed(() => {
  const uid = userStore.auth.currentUserId;
  return quantitiesForUserGame(
    inventoryStore.listForUser(uid),
    inventoryStore.bagForGame(uid, props.gameCode),
    props.gameCode
  );
});

const displayItems = computed(() => {
  const shopItems = shopStore.itemsForGame(props.gameCode);
  const codes = new Set(shopItems.map((i) => i.propCode));
  for (const code of Object.keys(quantities.value)) {
    codes.add(code);
  }
  return [...codes].map((propCode) => {
    const shop = shopItems.find((i) => i.propCode === propCode);
    return {
      propCode,
      name: shop?.name || propCode,
      icon: shop?.icon || '',
      quantity: quantities.value[propCode] || 0
    };
  });
});

/**
 * 是否显示使用按钮。
 * @param {string} propCode
 * @returns {boolean}
 */
function canUse(propCode) {
  if (props.readonly) {
    return false;
  }
  return props.usableProps.includes(propCode);
}

/**
 * 使用按钮是否禁用。
 * @param {string} propCode
 * @returns {boolean}
 */
function isUseDisabled(propCode) {
  return Boolean(props.disabledProps[propCode]);
}

/**
 * 使用按钮文案。
 * @param {string} propCode
 * @returns {string}
 */
function useLabel(propCode) {
  if (props.useLabels[propCode]) {
    return props.useLabels[propCode];
  }
  return props.activeProp === propCode ? '选格' : '使用';
}
</script>
