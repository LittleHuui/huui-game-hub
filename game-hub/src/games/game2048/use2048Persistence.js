/**
 * Creates local persistence helpers for 2048 match metadata.
 * @param {{ gameService: object, state: object }} deps
 * @returns {{ ensureSession: Function, recordPropUsage: Function }}
 */
export function use2048Persistence({ gameService, state }) {
  /**
   * Ensures a match session exists.
   * @returns {void}
   */
  function ensureSession() {
    gameService.ensureSession(state);
  }

  /**
   * Persists one prop usage entry.
   * @param {string} propCode
   * @param {string} label
   * @returns {void}
   */
  function recordPropUsage(propCode, label) {
    gameService.recordPropUsage(state, {
      propCode,
      label,
      timerSec: state.elapsedSec.value
    });
  }

  return { ensureSession, recordPropUsage };
}
