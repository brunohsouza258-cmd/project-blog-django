// Botão "Copiar link": usa a Clipboard API. Se o navegador não suportar
// (raro, hoje em dia), o botão simplesmente não faz nada — o link já está
// visível e clicável nos botões de WhatsApp/X ao lado.
(function () {
  const button = document.querySelector('.share-copy');
  if (!button || !navigator.clipboard) return;

  const originalText = button.textContent;
  let resetTimer = null;

  button.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(button.dataset.url);
      button.textContent = 'Copiado!';
    } catch (error) {
      button.textContent = 'Não deu certo';
    }
    clearTimeout(resetTimer);
    resetTimer = setTimeout(() => {
      button.textContent = originalText;
    }, 2000);
  });
})();
