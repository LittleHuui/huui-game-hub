<template>
  <div class="game-layout">
    <aside class="game-layout__side">
      <slot name="config" />
      <slot name="shop" />
      <slot name="ranking" />
    </aside>
    <main class="game-layout__main">
      <slot name="hud" />
      <div class="game-board-area">
        <slot name="board" />
      </div>
      <slot name="inventory" />
    </main>
  </div>
</template>

<script setup>
/**
 * 跨游戏统一左右布局，仅提供 slots，不含业务逻辑。
 */
</script>
