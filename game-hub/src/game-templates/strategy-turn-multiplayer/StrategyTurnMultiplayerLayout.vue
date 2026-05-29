<template>
  <div class="strategy-turn-multiplayer-layout">
    <header class="strategy-turn-multiplayer-layout__top">
      <slot name="topRoomBar" />
    </header>

    <div class="strategy-turn-multiplayer-layout__stage">
      <aside class="strategy-turn-multiplayer-layout__zone strategy-turn-multiplayer-layout__left">
        <slot name="leftPlayers" />
      </aside>

      <main class="strategy-turn-multiplayer-layout__zone strategy-turn-multiplayer-layout__center">
        <slot name="centerStage" />
      </main>

      <aside class="strategy-turn-multiplayer-layout__zone strategy-turn-multiplayer-layout__right">
        <slot name="rightPlayers" />
      </aside>
    </div>

    <footer class="strategy-turn-multiplayer-layout__bottom">
      <slot name="bottomActionArea" />
    </footer>

    <div class="strategy-turn-multiplayer-layout__animation">
      <slot name="animationLayer" />
    </div>
  </div>
</template>

<script setup>
import './strategy-turn-multiplayer.css';
</script>
