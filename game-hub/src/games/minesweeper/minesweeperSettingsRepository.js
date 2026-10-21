import * as userService from '../../services/userService.js';
import { MINESWEEPER_GAME_CODE } from './minesweeperConfig.js';
import { MINESWEEPER_PAGE_SETTING_HIGHLIGHT_AROUND } from './minesweeperPageSettings.js';

export function isHighlightAroundCellsEnabled() {
  return userService.readGameSettingBoolean(
    MINESWEEPER_GAME_CODE,
    MINESWEEPER_PAGE_SETTING_HIGHLIGHT_AROUND.key,
    true
  );
}

export async function setHighlightAroundCells(value) {
  await userService.updateGameSetting(MINESWEEPER_GAME_CODE, {
    [MINESWEEPER_PAGE_SETTING_HIGHLIGHT_AROUND.key]: !!value
  });
}
