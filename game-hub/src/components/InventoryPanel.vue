<template>
  <div class="backpack-bar">
    <div class="backpack-inline">
      <span class="backpack-inline-label" title="本局道具栏">背包</span>
      <div class="backpack-slot" :class="{ 'is-exhausted': hintExhausted && inBattle }">
        <span class="backpack-ic" title="提示卡">💡</span>
        <span class="backpack-count">×{{ user.props.hintCard }}</span>
        <button
          type="button"
          class="backpack-use-mini"
          :class="{ 'tool-active': activeTool === 'hint' }"
          :disabled="!canUseBattleProps || hintBackpackExhausted"
          @click="$emit('use-hint')"
        >
          {{ activeTool === 'hint' ? '选格' : '用' }}
        </button>
      </div>
      <div class="backpack-slot">
        <span class="backpack-ic" title="复活卡">💊</span>
        <span class="backpack-count">×{{ user.props.reviveCard }}</span>
        <label class="backpack-revive-inline" title="有卡且本局未复活时，踩雷自动消耗一张">
          <input type="checkbox" :checked="!!user.autoRevive" @change="$emit('toggle-auto-revive', $event.target.checked)" />
          <span>自动</span>
        </label>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  user: { type: Object, required: true },
  activeTool: { type: String, default: '' },
  canUseBattleProps: { type: Boolean, default: false },
  hintBackpackExhausted: { type: Boolean, default: false },
  hintExhausted: { type: Boolean, default: false },
  inBattle: { type: Boolean, default: false }
});
defineEmits(['use-hint', 'toggle-auto-revive']);
</script>
