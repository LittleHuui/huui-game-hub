import { onBeforeUnmount, watch } from 'vue';

/** Register after the opening click; cancel both pending registration and the listener. */
export function useOutsideClick(open, anchor, onOutside) {
  let registrationTimer = null;

  function onClick(event) {
    if (!anchor.value?.contains(event.target)) onOutside(event);
  }

  function clear() {
    if (registrationTimer !== null) clearTimeout(registrationTimer);
    registrationTimer = null;
    document.removeEventListener('click', onClick, true);
  }

  watch(open, (visible) => {
    clear();
    if (visible) {
      registrationTimer = setTimeout(() => {
        registrationTimer = null;
        if (open.value) document.addEventListener('click', onClick, true);
      }, 0);
    }
  });
  onBeforeUnmount(clear);
}
