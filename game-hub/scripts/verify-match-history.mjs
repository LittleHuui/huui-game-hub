import assert from 'node:assert/strict';
import {
  mapMatchRecord,
  resolveMatchGameCode,
  mapLocalMatchToPayload
} from '../src/mappers/matchMapper.js';

assert.equal(resolveMatchGameCode({ gameCode: 'match3' }), 'match3');
assert.equal(resolveMatchGameCode({ game_code: 'minesweeper' }), 'minesweeper');
assert.equal(resolveMatchGameCode({}), '');

const mapped = mapMatchRecord({ clientId: 'a', game_code: 'match3', score: 10 });
assert.equal(mapped.gameCode, 'match3');

const payload = mapLocalMatchToPayload({ clientId: 'b', game_code: 'minesweeper', result: 'win' });
assert.equal(payload.gameCode, 'minesweeper');

function partition(existing, gameCode) {
  const others = existing.filter((r) => {
    const code = resolveMatchGameCode(r);
    return !code || code !== gameCode;
  });
  const sameGame = existing.filter((r) => resolveMatchGameCode(r) === gameCode);
  return { others, sameGame };
}

const existing = [
  { clientId: '1', gameCode: 'minesweeper' },
  { clientId: '2', gameCode: 'match3' },
  { clientId: '3' }
];
const ms = partition(existing, 'minesweeper');
assert.equal(ms.sameGame.length, 1);
assert.equal(ms.sameGame[0].clientId, '1');
assert.equal(ms.others.length, 2);

console.log('verify-match-history: ok');
