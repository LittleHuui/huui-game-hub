import { createRouter, createWebHistory } from 'vue-router';
import GameHubPage from '../pages/GameHubPage.vue';
import GameUnavailablePage from '../pages/GameUnavailablePage.vue';
import MinesweeperPage from '../games/minesweeper/MinesweeperPage.vue';
import Match3Page from '../games/match3/Match3Page.vue';
import Game2048Page from '../games/game2048/Game2048Page.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: GameHubPage,
      children: [
        { path: '', redirect: { name: 'minesweeper' } },
        {
          path: 'minesweeper',
          name: 'minesweeper',
          component: MinesweeperPage,
          meta: { title: '雷区突围' }
        },
        {
          path: 'match3',
          name: 'match3',
          component: Match3Page,
          meta: { title: '幻彩碰撞' }
        },
        {
          path: '2048',
          name: '2048',
          component: Game2048Page,
          meta: { title: '数字方舟' }
        },
        {
          path: ':gameCode',
          name: 'game-unavailable',
          component: GameUnavailablePage,
          meta: { title: '游戏暂未实现' }
        }
      ]
    }
  ]
});

router.afterEach((to) => {
  const title = to.meta?.title;
  document.title = title ? `${title} · Game Hub` : 'Game Hub';
});

export default router;
