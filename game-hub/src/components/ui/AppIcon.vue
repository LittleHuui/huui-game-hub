<template>
  <span class="app-icon" :style="iconStyle" :role="title ? 'img' : undefined" :aria-label="title || undefined" :aria-hidden="title ? undefined : 'true'" />
</template>

<script setup>
import { computed } from 'vue';
const props = defineProps({ name: { type: String, default: 'info' }, size: { type: [Number, String], default: 18 }, title: { type: String, default: '' } });
const files = import.meta.glob('../../assets/icons/*.svg', { eager: true, query: '?url', import: 'default' });
const aliases = { 'squares-four': 'grid-four', 'circles-four': 'circle', 'game-controller': 'grid-four', backpack: 'bag', mine: 'bomb', sparkles: 'sparkle', grid: 'grid-four', spade: 'spade', rotate: 'arrow-counter-clockwise', refresh: 'arrow-clockwise', bag: 'bag', shop: 'storefront', bulb: 'lightbulb', chevron: 'caret-down', close: 'x', erase: 'eraser', settings: 'gear-six', user: 'user-circle', search: 'magnifying-glass', more: 'dots-three', phone: 'device-mobile', warning: 'warning-circle', logout: 'sign-out', sliders: 'sliders-horizontal', edit: 'pencil-simple', help: 'question', shield: 'shield-check', checkCircle: 'check-circle' };
const iconStyle = computed(() => {
  const name = aliases[props.name] || props.name;
  const url = files[`../../assets/icons/${name}.svg`] || files['../../assets/icons/info.svg'];
  const size = typeof props.size === 'number' ? `${props.size}px` : props.size;
  return { width: size, height: size, '--app-icon-url': `url("${url}")` };
});
</script>
