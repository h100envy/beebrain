// the complete address is built into the page from token-settings.json.
(() => {
  const button = document.getElementById('copy-token-ca');
  const address = document.getElementById('token-address');
  const feedback = document.getElementById('token-feedback');
  if (!button || !address || !feedback || button.disabled) return;
  button.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(address.textContent.trim());
      feedback.textContent = 'CA copied';
    } catch {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(address);
      selection.removeAllRanges();
      selection.addRange(range);
      feedback.textContent = 'address selected; copy it manually';
    }
  });
})();
