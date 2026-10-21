import { createRouter, createWebHistory } from 'vue-router';
import GameHubPage from '../pages/GameHubPage.vue';
import GameUnavailablePage from '../pages/GameUnavailablePage.vue';
import { listGameFrontendModules } from '../games/gameModuleRegistry.js';
import OnlineRoomListPage from '../pages/OnlineRoomListPage.vue';
import OnlineRoomWaitingPage from '../pages/OnlineRoomWaitingPage.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: GameHubPage,
      children: [
        {
          path: '',
          redirect: () => {
            const first = listGameFrontendModules().find((module) => module.route?.name);
            return first
              ? { name: first.route.name }
              : { name: 'game-unavailable', params: { gameCode: 'unknown' } };
          }
        },
        ...listGameFrontendModules().map((module) => ({
          path: module.route.path,
          name: module.route.name,
          component: module.playPageLoader,
          meta: { title: module.route.title }
        })),
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
