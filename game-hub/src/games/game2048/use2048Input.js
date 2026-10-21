import { directionFromKey } from './game2048Engine.js';

/**
 * Creates keyboard input handlers for the 2048 page.
 * @param {{ moveInputLocked: import('vue').ComputedRef<boolean>, handleMoveInput: Function }} deps
 * @returns {{ onWindowKeydown: Function }}
 */
export function use2048Input({ moveInputLocked, handleMoveInput }) {
  /**
   * Handles page-level keyboard direction input.
   * @param {KeyboardEvent} event
   * @returns {void}
   */
  function onWindowKeydown(event) {
    if (moveInputLocked.value) {
      return;
    }
    const tag = event.target?.tagName?.toLowerCase?.() || '';
    if (tag === 'input' || tag === 'textarea' || tag === 'select') {
      return;
    }
    const direction = directionFromKey(event.key);
    if (direction) {
      event.preventDefault();
      handleMoveInput(direction);
    }
  }

  return { onWindowKeydown };
}
