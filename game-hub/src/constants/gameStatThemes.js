/** 统计卡片配色种子数量 */
export const GAME_STAT_THEME_COUNT = 10;

/** @type {Array<{ id: number; name: string; bg: string; border: string; label: string; value: string; accentBg: string; accentBorder: string; accentValue: string; pillBg: string; pillBorder: string; pillValue: string }>} */
export const GAME_STAT_THEMES = [
  {
    id: 0,
    name: 'slate',
    bg: 'rgba(15, 23, 42, 0.5)',
    border: 'rgba(148, 163, 184, 0.28)',
    label: 'rgba(148, 163, 184, 0.95)',
    value: '#f1f5f9',
    accentBg: 'rgba(51, 65, 85, 0.55)',
    accentBorder: 'rgba(148, 163, 184, 0.45)',
    accentValue: '#e2e8f0',
    pillBg: 'rgba(30, 41, 59, 0.65)',
    pillBorder: 'rgba(148, 163, 184, 0.25)',
    pillValue: '#e2e8f0'
  },
  {
    id: 1,
    name: 'blue',
    bg: 'rgba(30, 58, 138, 0.35)',
    border: 'rgba(96, 165, 250, 0.35)',
    label: 'rgba(191, 219, 254, 0.9)',
    value: '#eff6ff',
    accentBg: 'rgba(37, 99, 235, 0.42)',
    accentBorder: 'rgba(147, 197, 253, 0.55)',
    accentValue: '#dbeafe',
    pillBg: 'rgba(30, 64, 175, 0.4)',
    pillBorder: 'rgba(96, 165, 250, 0.35)',
    pillValue: '#bfdbfe'
  },
  {
    id: 2,
    name: 'emerald',
    bg: 'rgba(6, 78, 59, 0.38)',
    border: 'rgba(52, 211, 153, 0.32)',
    label: 'rgba(167, 243, 208, 0.9)',
    value: '#ecfdf5',
    accentBg: 'rgba(5, 150, 105, 0.45)',
    accentBorder: 'rgba(110, 231, 183, 0.5)',
    accentValue: '#d1fae5',
    pillBg: 'rgba(6, 95, 70, 0.42)',
    pillBorder: 'rgba(52, 211, 153, 0.32)',
    pillValue: '#a7f3d0'
  },
  {
    id: 3,
    name: 'amber',
    bg: 'rgba(120, 53, 15, 0.38)',
    border: 'rgba(251, 191, 36, 0.32)',
    label: 'rgba(253, 230, 138, 0.92)',
    value: '#fffbeb',
    accentBg: 'rgba(180, 83, 9, 0.48)',
    accentBorder: 'rgba(252, 211, 77, 0.5)',
    accentValue: '#fef3c7',
    pillBg: 'rgba(146, 64, 14, 0.42)',
    pillBorder: 'rgba(251, 191, 36, 0.32)',
    pillValue: '#fde68a'
  },
  {
    id: 4,
    name: 'rose',
    bg: 'rgba(136, 19, 55, 0.36)',
    border: 'rgba(251, 113, 133, 0.32)',
    label: 'rgba(254, 205, 211, 0.92)',
    value: '#fff1f2',
    accentBg: 'rgba(190, 24, 93, 0.45)',
    accentBorder: 'rgba(253, 164, 175, 0.5)',
    accentValue: '#ffe4e6',
    pillBg: 'rgba(159, 18, 57, 0.4)',
    pillBorder: 'rgba(251, 113, 133, 0.32)',
    pillValue: '#fecdd3'
  },
  {
    id: 5,
    name: 'violet',
    bg: 'rgba(76, 29, 149, 0.38)',
    border: 'rgba(167, 139, 250, 0.32)',
    label: 'rgba(221, 214, 254, 0.92)',
    value: '#f5f3ff',
    accentBg: 'rgba(109, 40, 217, 0.48)',
    accentBorder: 'rgba(196, 181, 253, 0.5)',
    accentValue: '#ede9fe',
    pillBg: 'rgba(91, 33, 182, 0.4)',
    pillBorder: 'rgba(167, 139, 250, 0.32)',
    pillValue: '#ddd6fe'
  },
  {
    id: 6,
    name: 'cyan',
    bg: 'rgba(22, 78, 99, 0.4)',
    border: 'rgba(34, 211, 238, 0.3)',
    label: 'rgba(165, 243, 252, 0.92)',
    value: '#ecfeff',
    accentBg: 'rgba(8, 145, 178, 0.48)',
    accentBorder: 'rgba(103, 232, 249, 0.45)',
    accentValue: '#cffafe',
    pillBg: 'rgba(21, 94, 117, 0.42)',
    pillBorder: 'rgba(34, 211, 238, 0.3)',
    pillValue: '#a5f3fc'
  },
  {
    id: 7,
    name: 'orange',
    bg: 'rgba(124, 45, 18, 0.4)',
    border: 'rgba(251, 146, 60, 0.32)',
    label: 'rgba(254, 215, 170, 0.92)',
    value: '#fff7ed',
    accentBg: 'rgba(194, 65, 12, 0.48)',
    accentBorder: 'rgba(253, 186, 116, 0.5)',
    accentValue: '#ffedd5',
    pillBg: 'rgba(154, 52, 18, 0.42)',
    pillBorder: 'rgba(251, 146, 60, 0.32)',
    pillValue: '#fed7aa'
  },
  {
    id: 8,
    name: 'lime',
    bg: 'rgba(54, 83, 20, 0.42)',
    border: 'rgba(163, 230, 53, 0.3)',
    label: 'rgba(217, 249, 157, 0.92)',
    value: '#f7fee7',
    accentBg: 'rgba(77, 124, 15, 0.5)',
    accentBorder: 'rgba(190, 242, 100, 0.45)',
    accentValue: '#ecfccb',
    pillBg: 'rgba(63, 98, 18, 0.42)',
    pillBorder: 'rgba(163, 230, 53, 0.3)',
    pillValue: '#d9f99d'
  },
  {
    id: 9,
    name: 'fuchsia',
    bg: 'rgba(112, 26, 117, 0.38)',
    border: 'rgba(232, 121, 249, 0.32)',
    label: 'rgba(245, 208, 254, 0.92)',
    value: '#fdf4ff',
    accentBg: 'rgba(162, 28, 175, 0.48)',
    accentBorder: 'rgba(240, 171, 252, 0.5)',
    accentValue: '#fae8ff',
    pillBg: 'rgba(134, 25, 143, 0.4)',
    pillBorder: 'rgba(232, 121, 249, 0.32)',
    pillValue: '#f5d0fe'
  }
];

/**
 * 解析主题：0–9、名称（如 blue）、或 random。
 * @param {number|string|undefined|null} seed
 * @returns {number}
 */
export function resolveGameStatThemeIndex(seed) {
  if (seed === 'random' || seed === undefined || seed === null || seed === '') {
    return Math.floor(Math.random() * GAME_STAT_THEME_COUNT);
  }
  if (typeof seed === 'number' && Number.isFinite(seed)) {
    return ((Math.trunc(seed) % GAME_STAT_THEME_COUNT) + GAME_STAT_THEME_COUNT) % GAME_STAT_THEME_COUNT;
  }
  const text = String(seed).trim().toLowerCase();
  if (text === 'random') {
    return Math.floor(Math.random() * GAME_STAT_THEME_COUNT);
  }
  const byName = GAME_STAT_THEMES.findIndex((t) => t.name === text);
  if (byName >= 0) {
    return byName;
  }
  const asNum = Number(text);
  if (Number.isFinite(asNum)) {
    return ((Math.trunc(asNum) % GAME_STAT_THEME_COUNT) + GAME_STAT_THEME_COUNT) % GAME_STAT_THEME_COUNT;
  }
  return 0;
}

/**
 * @param {number} index
 * @returns {Record<string, string>}
 */
export function gameStatThemeVars(index) {
  const theme = GAME_STAT_THEMES[index] || GAME_STAT_THEMES[0];
  return {
    '--gstat-bg': theme.bg,
    '--gstat-border': theme.border,
    '--gstat-label': theme.label,
    '--gstat-value': theme.value,
    '--gstat-accent-bg': theme.accentBg,
    '--gstat-accent-border': theme.accentBorder,
    '--gstat-accent-value': theme.accentValue,
    '--gstat-pill-bg': theme.pillBg,
    '--gstat-pill-border': theme.pillBorder,
    '--gstat-pill-value': theme.pillValue
  };
}
