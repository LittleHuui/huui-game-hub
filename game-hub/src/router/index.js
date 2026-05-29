import { createRouter, createWebHistory } from 'vue-router';
import GameHubPage from '../pages/GameHubPage.vue';
import GameUnavailablePage from '../pages/GameUnavailablePage.vue';
import MinesweeperPage from '../games/minesweeper/MinesweeperPage.vue';
import Match3Page from '../games/match3/Match3Page.vue';
import Game2048Page from '../games/game2048/Game2048Page.vue';
import SudokuPage from '../games/sudoku/SudokuPage.vue';
import UnoPlayPage from '../games/uno/UnoPlayPage.vue';
import OnlineRoomListPage from '../pages/OnlineRoomListPage.vue';
import OnlineRoomWaitingPage from '../pages/OnlineRoomWaitingPage.vue';
import OnlineGamePlayEntryPage from '../pages/OnlineGamePlayEntryPage.vue';

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
          path: 'sudoku',
          name: 'sudoku',
          component: SudokuPage,
          meta: { title: '数独' }
        },
        {
          path: 'games/:gameCode/rooms',
          name: 'online-room-list',
          component: OnlineRoomListPage,
          meta: { title: '在线房间' }
        },
        {
          path: 'games/:gameCode/rooms/:roomId',
          name: 'online-room-waiting',
          component: OnlineRoomWaitingPage,
          meta: { title: '在线房间' }
        },
        {
          path: 'games/uno/play/:roomId',
          name: 'uno-play',
          component: UnoPlayPage,
          meta: { title: 'UNO 对战' }
        },
        {
          path: 'games/:gameCode/play/:roomId',
          name: 'online-play-entry',
          component: OnlineGamePlayEntryPage,
          meta: { title: '对战中' }
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
