/**
 * 从源码常量导出 GAME_SEED_CONFIG 为 JSON（与前端单一数据源一致）。
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { GAME_SEED_CONFIG } from '../src/constants/gameSeedConfig.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const outDir = join(__dirname, '..', 'dist');
const outPath = join(outDir, 'game-seed.json');

mkdirSync(outDir, { recursive: true });
writeFileSync(outPath, `${JSON.stringify(GAME_SEED_CONFIG, null, 2)}\n`, 'utf8');
console.log(`Wrote ${outPath}`);
