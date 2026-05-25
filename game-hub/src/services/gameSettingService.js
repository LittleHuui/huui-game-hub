import { GAME_SETTING_DEFINITIONS } from '../constants/gameSettingDefinitions.js';
import { useUserStore } from '../stores/userStore.js';
import * as userService from './userService.js';

/**
 * 构建顶栏设置面板按游戏分组的展示行（读取当前用户已保存值，无则 defaultValue）。
 * @returns {{ gameCode: string; gameName: string; items: { gameCode: string; key: string; label: string; description?: string; value: boolean }[] }[]}
 */
export function buildHubGameSettingGroups() {
  const userStore = useUserStore();
  const uid = userStore.auth.currentUserId;
  const user = userStore.users.find((u) => u.userId === uid);
  const savedByGame = user?.gameSettings && typeof user.gameSettings === 'object' ? user.gameSettings : {};

  return GAME_SETTING_DEFINITIONS.map((group) => ({
    gameCode: group.gameCode,
    gameName: group.gameName,
    items: group.settings
      .filter((def) => def.type === 'switch')
      .map((def) => {
        const row = savedByGame[group.gameCode];
        const raw = row && typeof row === 'object' ? row[def.key] : undefined;
        const value =
          typeof raw === 'boolean' ? raw : userService.readGameSettingBoolean(group.gameCode, def.key, def.defaultValue);
        return {
          gameCode: group.gameCode,
          key: def.key,
          label: def.label,
          description: def.description,
          value
        };
      })
  }));
}

/**
 * 切换顶栏某游戏布尔设置并持久化（按 gameCode + settingKey 隔离）。
 * @param {string} gameCode
 * @param {string} key
 * @param {boolean} value
 * @returns {Promise<void>}
 */
export async function setHubGameSettingSwitch(gameCode, key, value) {
  if (!gameCode || !key) {
    return;
  }
  await userService.updateGameSetting(gameCode, { [key]: !!value });
}
