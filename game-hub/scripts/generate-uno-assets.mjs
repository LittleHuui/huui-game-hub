/**
 * 生成 UNO 基础 PNG 资源（无第三方图片依赖）。
 * 输出目录：src/assets/games/uno/cards/
 */
import { deflateSync } from 'node:zlib';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT_DIR = join(__dirname, '..', 'src', 'assets', 'games', 'uno', 'cards');

const W = 140;
const H = 200;

const PALETTE = {
  red: [229, 57, 53],
  yellow: [253, 216, 53],
  green: [67, 160, 71],
  blue: [30, 136, 229],
  white: [255, 255, 255],
  ink: [33, 33, 33],
  back: [26, 35, 126],
  backAccent: [57, 73, 171],
  wild: [66, 66, 66]
};

const COLORS = ['red', 'yellow', 'green', 'blue'];
const ACTIONS = [
  { suffix: 'disable', draw: drawDisableSymbol },
  { suffix: 'reverse', draw: drawReverseSymbol },
  { suffix: 'draw_two', draw: drawDrawTwoSymbol }
];

/**
 * @param {number} width
 * @param {number} height
 * @returns {Uint8Array}
 */
function createBuffer(width, height) {
  return new Uint8Array(width * height * 4);
}

/**
 * @param {Uint8Array} buf
 * @param {number} width
 * @param {number} x
 * @param {number} y
 * @param {number[]} rgba
 */
function setPixel(buf, width, x, y, rgba) {
  if (x < 0 || y < 0 || x >= W || y >= H) {
    return;
  }
  const i = (y * width + x) * 4;
  buf[i] = rgba[0];
  buf[i + 1] = rgba[1];
  buf[i + 2] = rgba[2];
  buf[i + 3] = rgba[3] ?? 255;
}

/**
 * @param {Uint8Array} buf
 * @param {number} width
 * @param {number} x0
 * @param {number} y0
 * @param {number} x1
 * @param {number} y1
 * @param {number[]} rgba
 */
function fillRect(buf, width, x0, y0, x1, y1, rgba) {
  for (let y = y0; y <= y1; y += 1) {
    for (let x = x0; x <= x1; x += 1) {
      setPixel(buf, width, x, y, rgba);
    }
  }
}

/**
 * @param {Uint8Array} buf
 * @param {number} width
 * @param {number} cx
 * @param {number} cy
 * @param {number} r
 * @param {number[]} rgba
 */
function fillCircle(buf, width, cx, cy, r, rgba) {
  const r2 = r * r;
  for (let y = cy - r; y <= cy + r; y += 1) {
    for (let x = cx - r; x <= cx + r; x += 1) {
      const dx = x - cx;
      const dy = y - cy;
      if (dx * dx + dy * dy <= r2) {
        setPixel(buf, width, x, y, rgba);
      }
    }
  }
}

/**
 * @param {Uint8Array} buf
 * @param {number} width
 * @param {number} x0
 * @param {number} y0
 * @param {number} x1
 * @param {number} y1
 * @param {number} thickness
 * @param {number[]} rgba
 */
function drawLine(buf, width, x0, y0, x1, y1, thickness, rgba) {
  const steps = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0), 1);
  for (let s = 0; s <= steps; s += 1) {
    const t = s / steps;
    const x = Math.round(x0 + (x1 - x0) * t);
    const y = Math.round(y0 + (y1 - y0) * t);
    for (let oy = -thickness; oy <= thickness; oy += 1) {
      for (let ox = -thickness; ox <= thickness; ox += 1) {
        setPixel(buf, width, x + ox, y + oy, rgba);
      }
    }
  }
}

/**
 * @param {number} deg
 * @returns {number}
 */
function degToRad(deg) {
  return (deg * Math.PI) / 180;
}

/**
 * 绘制圆弧线。
 * @param {Uint8Array} buf
 * @param {number} width
 * @param {number} cx
 * @param {number} cy
 * @param {number} radius
 * @param {number} startDeg
 * @param {number} endDeg
 * @param {number} thickness
 * @param {number[]} rgba
 */
function drawArc(buf, width, cx, cy, radius, startDeg, endDeg, thickness, rgba) {
  const steps = Math.max(24, Math.round(Math.abs(endDeg - startDeg) * radius * 0.12));
  let prevX = null;
  let prevY = null;
  for (let i = 0; i <= steps; i += 1) {
    const t = i / steps;
    const deg = startDeg + (endDeg - startDeg) * t;
    const rad = degToRad(deg);
    const x = Math.round(cx + Math.cos(rad) * radius);
    const y = Math.round(cy + Math.sin(rad) * radius);
    if (prevX !== null && prevY !== null) {
      drawLine(buf, width, prevX, prevY, x, y, thickness, rgba);
    }
    prevX = x;
    prevY = y;
  }
}

/**
 * 绘制箭头。
 * @param {Uint8Array} buf
 * @param {number} width
 * @param {number} tipX
 * @param {number} tipY
 * @param {number} angleDeg
 * @param {number} size
 * @param {number} thickness
 * @param {number[]} rgba
 */
function drawArrowHead(buf, width, tipX, tipY, angleDeg, size, thickness, rgba) {
  const a1 = degToRad(angleDeg + 150);
  const a2 = degToRad(angleDeg - 150);
  const x1 = Math.round(tipX + Math.cos(a1) * size);
  const y1 = Math.round(tipY + Math.sin(a1) * size);
  const x2 = Math.round(tipX + Math.cos(a2) * size);
  const y2 = Math.round(tipY + Math.sin(a2) * size);
  drawLine(buf, width, tipX, tipY, x1, y1, thickness, rgba);
  drawLine(buf, width, tipX, tipY, x2, y2, thickness, rgba);
}

/** 5x7 位图数字 0-9 */
const DIGIT_GLYPHS = {
  0: ['11111', '10001', '10011', '10101', '11001', '10001', '11111'],
  1: ['00100', '01100', '00100', '00100', '00100', '00100', '01110'],
  2: ['11111', '10001', '00001', '00111', '01000', '10000', '11111'],
  3: ['11111', '10001', '00001', '01111', '00001', '10001', '11111'],
  4: ['00010', '00110', '01010', '10010', '11111', '00010', '00010'],
  5: ['11111', '10000', '11111', '00001', '00001', '10001', '11111'],
  6: ['01111', '10000', '11111', '10001', '10001', '10001', '11111'],
  7: ['11111', '00001', '00010', '00100', '01000', '01000', '01000'],
  8: ['11111', '10001', '10001', '11111', '10001', '10001', '11111'],
  9: ['11111', '10001', '10001', '11111', '00001', '00010', '11100']
};

/**
 * @param {Uint8Array} buf
 * @param {number} width
 * @param {number} left
 * @param {number} top
 * @param {number} scale
 * @param {number} digit
 * @param {number[]} rgba
 */
function drawDigit(buf, width, left, top, scale, digit, rgba) {
  const rows = DIGIT_GLYPHS[digit];
  if (!rows) {
    return;
  }
  rows.forEach((row, ry) => {
    [...row].forEach((ch, cx) => {
      if (ch === '1') {
        fillRect(buf, width, left + cx * scale, top + ry * scale, left + (cx + 1) * scale - 1, top + (ry + 1) * scale - 1, rgba);
      }
    });
  });
}

/**
 * @param {Uint8Array} buf
 * @param {number} width
 * @param {number} left
 * @param {number} top
 * @param {number} scale
 * @param {string} text
 * @param {number[]} rgba
 */
function drawText(buf, width, left, top, scale, text, rgba) {
  let x = left;
  for (const ch of text) {
    if (ch >= '0' && ch <= '9') {
      drawDigit(buf, width, x, top, scale, Number(ch), rgba);
      x += 6 * scale + scale;
    } else if (ch === '+') {
      fillRect(buf, width, x + scale, top + 2 * scale, x + 4 * scale, top + 3 * scale, rgba);
      fillRect(buf, width, x, top + scale, x + scale, top + 4 * scale, rgba);
      x += 5 * scale + scale;
    }
  }
}

/**
 * @param {Uint8Array} buf
 * @param {number} width
 * @param {number} cx
 * @param {number} cy
 * @param {number} size
 * @param {number[]} rgba
 */
function drawDisableSymbol(buf, width, cx, cy, size, rgba) {
  const ring = Math.max(3, Math.round(size * 0.2));
  fillCircle(buf, width, cx, cy, size, rgba);
  fillCircle(buf, width, cx, cy, Math.max(3, size - ring), [...PALETTE.white, 255]);
  drawLine(buf, width, cx - size + 6, cy + size - 6, cx + size - 6, cy - size + 6, Math.max(2, Math.round(size * 0.16)), rgba);
  // 中间补一个简化“玩家”图形，增强“跳过/禁止玩家动作”的识别语义。
  const headR = Math.max(2, Math.round(size * 0.17));
  fillCircle(buf, width, cx, cy - Math.round(size * 0.14), headR, [...PALETTE.ink, 255]);
  fillRect(
    buf,
    width,
    cx - Math.max(2, Math.round(size * 0.15)),
    cy + Math.round(size * 0.02),
    cx + Math.max(2, Math.round(size * 0.15)),
    cy + Math.round(size * 0.42),
    [...PALETTE.ink, 255]
  );
}

/**
 * @param {Uint8Array} buf
 * @param {number} width
 * @param {number} cx
 * @param {number} cy
 * @param {number} size
 * @param {number[]} rgba
 */
function drawReverseSymbol(buf, width, cx, cy, size, rgba) {
  const thickness = Math.max(2, Math.round(size * 0.14));
  const outerR = Math.max(10, Math.round(size * 0.72));
  const innerR = Math.max(8, Math.round(size * 0.48));

  drawArc(buf, width, cx, cy, outerR, 200, 20, thickness, rgba);
  const topRightX = Math.round(cx + Math.cos(degToRad(20)) * outerR);
  const topRightY = Math.round(cy + Math.sin(degToRad(20)) * outerR);
  drawArrowHead(
    buf,
    width,
    topRightX,
    topRightY,
    -70,
    Math.max(5, Math.round(size * 0.3)),
    thickness,
    rgba
  );

  drawArc(buf, width, cx, cy, innerR, 20, 200, thickness, rgba);
  const bottomLeftX = Math.round(cx + Math.cos(degToRad(200)) * innerR);
  const bottomLeftY = Math.round(cy + Math.sin(degToRad(200)) * innerR);
  drawArrowHead(
    buf,
    width,
    bottomLeftX,
    bottomLeftY,
    110,
    Math.max(5, Math.round(size * 0.28)),
    thickness,
    rgba
  );
}

/**
 * @param {Uint8Array} buf
 * @param {number} width
 * @param {number} cx
 * @param {number} cy
 * @param {number} scale
 * @param {number[]} rgba
 */
function drawDrawTwoSymbol(buf, width, cx, cy, scale, rgba) {
  const textScale = Math.max(4, Math.round(scale * 0.48));
  drawText(
    buf,
    width,
    cx - Math.round(scale * 1.15),
    cy - Math.round(scale * 1.35),
    textScale,
    '+2',
    rgba
  );

  const cardW = Math.max(12, Math.round(scale * 0.95));
  const cardH = Math.max(18, Math.round(scale * 1.35));
  const baseTop = cy - Math.round(scale * 0.15);
  const card1Left = cx - Math.round(cardW * 1.05);
  const card2Left = card1Left + Math.max(6, Math.round(scale * 0.34));

  fillRect(buf, width, card2Left, baseTop - 4, card2Left + cardW, baseTop - 4 + cardH, rgba);
  fillRect(
    buf,
    width,
    card2Left + 2,
    baseTop - 2,
    card2Left + cardW - 2,
    baseTop - 6 + cardH,
    [...PALETTE.white, 255]
  );

  fillRect(buf, width, card1Left, baseTop, card1Left + cardW, baseTop + cardH, rgba);
  fillRect(
    buf,
    width,
    card1Left + 2,
    baseTop + 2,
    card1Left + cardW - 2,
    baseTop + cardH - 2,
    [...PALETTE.white, 255]
  );
}

/**
 * @param {number[]} borderRgb
 * @param {number} numberValue
 * @returns {Uint8Array}
 */
function renderNumberCard(borderRgb, numberValue) {
  const buf = createBuffer(W, H);
  fillRect(buf, W, 0, 0, W - 1, H - 1, [...borderRgb, 255]);
  fillRect(buf, W, 8, 8, W - 9, H - 9, [...PALETTE.white, 255]);
  drawDigit(buf, W, 52, 78, 6, numberValue, [...borderRgb, 255]);
  drawDigit(buf, W, 18, 18, 3, numberValue, [...borderRgb, 255]);
  drawDigit(buf, W, W - 18 - 15, H - 18 - 21, 3, numberValue, [...borderRgb, 255]);
  return buf;
}

/**
 * @param {number[]} borderRgb
 * @param {(buf: Uint8Array, width: number, cx: number, cy: number, size: number, rgba: number[]) => void} drawSymbol
 * @returns {Uint8Array}
 */
function renderActionCard(borderRgb, drawSymbol) {
  const buf = createBuffer(W, H);
  fillRect(buf, W, 0, 0, W - 1, H - 1, [...borderRgb, 255]);
  fillRect(buf, W, 8, 8, W - 9, H - 9, [...PALETTE.white, 255]);
  const rgba = [...borderRgb, 255];
  drawSymbol(buf, W, 70, 100, 28, rgba);
  drawSymbol(buf, W, 28, 32, 14, rgba);
  drawSymbol(buf, W, W - 28, H - 32, 14, rgba);
  return buf;
}

/**
 * @returns {Uint8Array}
 */
function renderWildCard() {
  const buf = createBuffer(W, H);
  fillRect(buf, W, 0, 0, W - 1, H - 1, [...PALETTE.wild, 255]);
  fillRect(buf, W, 8, 8, W - 9, H - 9, [...PALETTE.ink, 255]);
  const cx = 70;
  const cy = 102;
  const radius = 44;
  const border = 3;

  for (let y = cy - radius; y <= cy + radius; y += 1) {
    for (let x = cx - radius; x <= cx + radius; x += 1) {
      const dx = x - cx;
      const dy = y - cy;
      const diamondDistance = Math.abs(dx) + Math.abs(dy);
      if (diamondDistance > radius) {
        continue;
      }
      if (diamondDistance >= radius - border) {
        setPixel(buf, W, x, y, [...PALETTE.white, 255]);
        continue;
      }
      if (dx <= 0 && dy <= 0) {
        setPixel(buf, W, x, y, [...PALETTE.red, 255]);
      } else if (dx > 0 && dy <= 0) {
        setPixel(buf, W, x, y, [...PALETTE.yellow, 255]);
      } else if (dx <= 0 && dy > 0) {
        setPixel(buf, W, x, y, [...PALETTE.green, 255]);
      } else {
        setPixel(buf, W, x, y, [...PALETTE.blue, 255]);
      }
    }
  }

  // 白色选择指针：强化“可选颜色”语义。
  fillRect(buf, W, cx - 2, cy - 14, cx + 2, cy + 10, [...PALETTE.white, 255]);
  drawLine(buf, W, cx + 2, cy - 14, cx + 14, cy - 24, 2, [...PALETTE.white, 255]);
  drawLine(buf, W, cx + 14, cy - 24, cx + 10, cy - 10, 2, [...PALETTE.white, 255]);
  return buf;
}

/**
 * @returns {Uint8Array}
 */
function renderWildDraw4Card() {
  const buf = createBuffer(W, H);
  fillRect(buf, W, 0, 0, W - 1, H - 1, [...PALETTE.wild, 255]);
  fillRect(buf, W, 8, 8, W - 9, H - 9, [...PALETTE.ink, 255]);

  drawText(buf, W, 40, 34, 6, '+4', [...PALETTE.white, 255]);

  const miniColors = [PALETTE.red, PALETTE.yellow, PALETTE.green, PALETTE.blue];
  const cardW = 20;
  const cardH = 30;
  const baseX = 70;
  const baseY = 118;
  const offsets = [
    [-22, 8],
    [-6, 0],
    [10, 0],
    [26, 8]
  ];
  miniColors.forEach((color, idx) => {
    const left = baseX + offsets[idx][0];
    const top = baseY + offsets[idx][1];
    fillRect(buf, W, left, top, left + cardW, top + cardH, [...color, 255]);
    fillRect(buf, W, left + 2, top + 2, left + cardW - 2, top + cardH - 2, [255, 255, 255, 130]);
  });
  return buf;
}

/**
 * @returns {Uint8Array}
 */
function renderCardBack() {
  const buf = createBuffer(W, H);
  fillRect(buf, W, 0, 0, W - 1, H - 1, [...PALETTE.back, 255]);
  for (let y = 12; y < H - 12; y += 16) {
    for (let x = 12; x < W - 12; x += 16) {
      fillCircle(buf, W, x + 8, y + 8, 5, [...PALETTE.backAccent, 255]);
    }
  }
  fillRect(buf, W, 24, 78, W - 25, 122, [...PALETTE.backAccent, 255]);
  drawText(buf, W, 38, 88, 4, 'UNO', [...PALETTE.white, 255]);
  return buf;
}

/**
 * @param {number} width
 * @param {number} height
 * @param {Uint8Array} rgba
 * @returns {Buffer}
 */
function encodePng(width, height, rgba) {
  const stride = width * 4;
  const raw = Buffer.alloc((stride + 1) * height);
  for (let y = 0; y < height; y += 1) {
    raw[y * (stride + 1)] = 0;
    rgba.slice(y * stride, y * stride + stride).forEach((v, i) => {
      raw[y * (stride + 1) + 1 + i] = v;
    });
  }
  const compressed = deflateSync(raw);

  function chunk(type, data) {
    const typeBuf = Buffer.from(type);
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length, 0);
    const body = Buffer.concat([typeBuf, data]);
    const crcBuf = Buffer.alloc(4);
    crcBuf.writeUInt32BE(crc32(Buffer.concat([typeBuf, data])), 0);
    return Buffer.concat([len, body, crcBuf]);
  }

  const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;
  ihdr[9] = 6;
  ihdr[10] = 0;
  ihdr[11] = 0;
  ihdr[12] = 0;

  return Buffer.concat([
    signature,
    chunk('IHDR', ihdr),
    chunk('IDAT', compressed),
    chunk('IEND', Buffer.alloc(0))
  ]);
}

/**
 * @param {Buffer} buf
 * @returns {number}
 */
function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i += 1) {
    c ^= buf[i];
    for (let k = 0; k < 8; k += 1) {
      c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    }
  }
  return (c ^ 0xffffffff) >>> 0;
}

/**
 * @param {string} name
 * @param {Uint8Array} rgba
 */
function writeCard(name, rgba) {
  const path = join(OUT_DIR, `${name}.png`);
  writeFileSync(path, encodePng(W, H, rgba));
}

mkdirSync(OUT_DIR, { recursive: true });

for (const color of COLORS) {
  const rgb = PALETTE[color];
  for (const action of ACTIONS) {
    writeCard(`${color}_${action.suffix}`, renderActionCard(rgb, action.draw));
  }
}

writeCard('wild', renderWildCard());
writeCard('wild_draw4', renderWildDraw4Card());

console.log(`Generated UNO card PNGs in ${OUT_DIR}`);
