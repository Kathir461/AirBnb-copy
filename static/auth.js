'use strict';

document.querySelectorAll('.password-toggle').forEach((button) => {
  const input = document.getElementById(button.getAttribute('aria-controls'));
  if (!input) return;

  function setVisible(visible) {
    input.type = visible ? 'text' : 'password';
    button.textContent = visible ? 'Hide' : 'Show';
    button.setAttribute('aria-label', `${visible ? 'Hide' : 'Show'} ${button.dataset.label}`);
  }

  button.hidden = false;
  button.addEventListener('click', () => setVisible(input.type === 'password'));
  window.addEventListener('pageshow', () => setVisible(false));
});
