import { GAME_SEED_CONFIG } from '../constants/gameSeedConfig.js';
import { MINESWEEPER_PRESETS, setClientLayoutConfigs } from '../games/minesweeper/minesweeperConfig.js';
import { getEnabledDifficulties, setGameDifficulties } from '../services/gameDifficultyService.js';
import { mapGamePropRuleToShopItem } from './propMapper.js';

/**
 * 按 gameCode 查找种子中的游戏配置。
 * @param {string} gameCode
 * @param {typeof GAME_SEED_CONFIG} [seedConfig]
 * @returns {object|null}
 */
export function getSeedGameConfig(gameCode, seedConfig = GAME_SEED_CONFIG) {
  const games = Array.isArray(seedConfig?.games) ? seedConfig.games : [];
  return games.find((g) => g && g.gameCode === gameCode) || null;
}

/**
 * 合并平台道具定义与游戏规则，生成商城商品列表。
 * @param {typeof GAME_SEED_CONFIG} seedConfig
 * @param {string} gameCode
 * @returns {import('../stores/shopStore.js').ShopItem[]}
 */
export function mergeGameProps(seedConfig, gameCode) {
  const game = getSeedGameConfig(gameCode, seedConfig);
  if (!game) {
    return [];
  }
  const propMap = {};
  for (const def of Array.isArray(seedConfig?.props) ? seedConfig.props : []) {
    if (def?.propCode) {
      propMap[def.propCode] = def;
    }
  }
  const items = [];
  for (const rule of Array.isArray(game.propRules) ? game.propRules : []) {
    if (!rule?.propCode || rule.enabled === false) {
      continue;
    }
    const definition = propMap[rule.propCode];
    if (!definition || definition.enabled === false) {
      continue;
    }
    const price =
      rule.price != null ? Number(rule.price) : definition.basePrice != null ? Number(definition.basePrice) : 0;
    items.push(
      mapGamePropRuleToShopItem(
        {
          ...rule,
          propName: definition.propName,
          price
        },
        definition
      )
    );
  }
  return items;
}

/**
 * 将种子配置转为扫雷服务端配置结构（供 applyMinesweeperServerConfig 消费）。
 * @param {typeof GAME_SEED_CONFIG} [seedConfig]
 * @returns {{ difficulties: object[]; clientConfigs: object[] }}
 */
export function mapGameSeedToMinesweeperConfig(seedConfig = GAME_SEED_CONFIG) {
  const game = getSeedGameConfig('minesweeper', seedConfig);
  if (!game) {
    return { difficulties: [], clientConfigs: [] };
  }
  const difficulties = (Array.isArray(game.difficulties) ? game.difficulties : []).map((d) => ({
    difficultyCode: d.difficultyCode,
    difficultyName: d.difficultyName,
    enabled: d.enabled === true,
    sortNo: d.sortNo != null ? Number(d.sortNo) : 999,
    config: d.config || d
  }));
  return {
    difficulties,
    clientConfigs: Array.isArray(game.clientConfigs) ? game.clientConfigs : []
  };
}

/**
 * 将服务端扫雷配置应用到本地常量（不改变玩法规则结构）。
 * @param {object} data GameConfigResponse
 */
export function applyMinesweeperServerConfig(data) {
  if (!data || typeof data !== 'object') {
    return;
  }
  const rawList = Array.isArray(data.difficulties) ? data.difficulties : [];
  setGameDifficulties('minesweeper', rawList);
  for (const d of getEnabledDifficulties('minesweeper')) {
    const code = d.difficultyCode;
    if (!code || !MINESWEEPER_PRESETS[code]) {
      continue;
    }
    const cfg = d.config || {};
    const prev = MINESWEEPER_PRESETS[code];
    MINESWEEPER_PRESETS[code] = {
      rows: cfg.rows ?? prev.rows,
      cols: cfg.cols ?? prev.cols,
      mines: cfg.mines ?? prev.mines,
      label: d.difficultyName || prev.label,
      scoreWin: cfg.winReward ?? prev.scoreWin,
      failRewardPerFlag: cfg.failRewardPerCorrectFlag ?? 3
    };
    if (code === 'hard') {
      MINESWEEPER_PRESETS[code].rows = cfg.rows ?? 16;
      MINESWEEPER_PRESETS[code].cols = cfg.cols ?? 30;
      MINESWEEPER_PRESETS[code].mines = cfg.mines ?? 100;
    }
  }
  setClientLayoutConfigs(data.clientConfigs);
}
