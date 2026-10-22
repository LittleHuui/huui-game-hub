<template>
  <div ref="anchor" class="app-menu" :class="`app-menu--${align}`">
    <button ref="trigger" :id="triggerId || undefined" type="button" class="app-menu__trigger" :disabled="disabled" :aria-label="label" :aria-expanded="open" aria-haspopup="menu" @click.stop="toggle" @keydown.down.prevent="show">
      <slot name="trigger"><AppIcon name="more" /></slot>
    </button>
    <Teleport v-if="open" to="body">
      <div v-viewport-backdrop class="app-menu__backdrop" @click="close" />
      <div ref="panel" class="app-menu__panel" :style="positionStyle" role="menu" :aria-label="title || label" @keydown="onKeydown">
        <div class="app-menu__mobile-title"><strong>{{ title || label }}</strong><button type="button" aria-label="关闭菜单" @click="close"><AppIcon name="close" :size="16" /></button></div>
        <div v-if="$slots.header" class="app-menu__header"><slot name="header" /></div>
        <template v-for="item in items" :key="item.id">
          <div v-if="item.type === 'separator'" class="app-menu__separator" role="separator" />
          <button v-else type="button" class="app-menu__item" :class="{ 'is-selected': item.selected, 'is-danger': item.danger }" role="menuitem" :disabled="item.disabled" @click="select(item)">
            <AppIcon v-if="item.icon" :name="item.icon" :size="17" />
            <span>{{ item.label }}</span><AppIcon v-if="item.selected" name="check" :size="16" />
          </button>
        </template>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import AppIcon from './AppIcon.vue';
import vViewportBackdrop from './viewportBackdrop.js';
const props = defineProps({ label: { type: String, default: '更多操作' }, title: { type: String, default: '' }, items: { type: Array, default: () => [] }, align: { type: String, default: 'end' }, disabled: { type: Boolean, default: false }, triggerId: { type: String, default: '' } });
const emit = defineEmits(['select']);
const anchor = ref(null), trigger = ref(null), panel = ref(null), open = ref(false);
const positionStyle = ref({});
function close() { if (!open.value) return; open.value = false; trigger.value?.focus(); }
async function show() {
  if (props.disabled) return;
  open.value = true;
  await nextTick();
  const rect = trigger.value.getBoundingClientRect();
  const menuRect = panel.value.getBoundingClientRect();
  const desiredLeft = props.align === 'start' ? rect.left : rect.right - menuRect.width;
  const left = Math.max(12, Math.min(window.innerWidth - menuRect.width - 12, desiredLeft));
  const top = rect.bottom + menuRect.height + 8 <= window.innerHeight ? rect.bottom + 8 : Math.max(8, rect.top - menuRect.height - 8);
  positionStyle.value = { '--menu-left': `${left}px`, '--menu-top': `${top}px` };
  panel.value?.querySelector('.app-menu__item:not(:disabled)')?.focus();
}
function toggle() { if (open.value) close(); else show(); }
function select(item) { if (item.disabled) return; close(); emit('select', item.id); }
function onOutside(event) { if (open.value && !anchor.value?.contains(event.target) && !panel.value?.contains(event.target)) open.value = false; }
function onScroll(event) { if (open.value && !panel.value?.contains(event.target)) close(); }
function onKeydown(event) {
  if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(); return; }
  if (event.key === 'Tab') {
    event.preventDefault();
    event.stopPropagation();
    const ownerDialog = trigger.value?.closest('[role="dialog"]');
    const scope = ownerDialog || document.body;
    const selector = 'button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href],[tabindex="0"]';
    const controls = [...scope.querySelectorAll(selector)].filter(el => el.getClientRects().length && !panel.value?.contains(el));
    const current = controls.indexOf(trigger.value);
    const step = event.shiftKey ? -1 : 1;
    const desired = current + step;
    const index = ownerDialog ? (desired + controls.length) % controls.length : Math.max(0, Math.min(controls.length - 1, desired));
    const target = controls[index] || trigger.value;
    close();
    nextTick(() => target?.focus());
    return;
  }
  if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
  const items = [...panel.value.querySelectorAll('.app-menu__item:not(:disabled)')];
  if (!items.length) return;
  const current = items.indexOf(document.activeElement);
  const index = event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1 : (current + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
  items[index].focus(); event.preventDefault();
}
onMounted(() => { document.addEventListener('pointerdown', onOutside); window.addEventListener('resize', close); window.addEventListener('scroll', onScroll, true); });
onBeforeUnmount(() => { document.removeEventListener('pointerdown', onOutside); window.removeEventListener('resize', close); window.removeEventListener('scroll', onScroll, true); });
</script>
