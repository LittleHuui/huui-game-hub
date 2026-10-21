import { GAME_SEED_CONFIG } from '../../constants/gameSeedConfig.js';
import { MINESWEEPER_PRESETS, setClientLayoutConfigs } from './minesweeperConfig.js';
import { getEnabledDifficulties, setGameDifficulties } from '../../services/gameDifficultyService.js';
import { getSeedGameConfig } from '../../mappers/gameConfigMapper.js';

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
