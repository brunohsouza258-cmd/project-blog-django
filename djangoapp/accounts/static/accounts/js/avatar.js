// Ao escolher a imagem: mostra o nome do arquivo e uma prévia da foto,
// antes de enviar. A prévia usa uma URL local (blob:), nada sai do navegador.
(function () {
  const input = document.querySelector('.avatar-picker input[type=file]');
  if (!input) return;

  const fileName = document.querySelector('.avatar-file-name');
  let avatar = document.querySelector('.profile-head .user-avatar');
  let previewUrl = null;
  const MAX_BYTES = 2 * 1024 * 1024;

  input.addEventListener('change', () => {
    const file = input.files[0];
    if (!file) return;

    // Aviso rápido no navegador; a verificação de verdade é no servidor.
    if (file.size > MAX_BYTES) {
      fileName.textContent = 'Arquivo maior que 2 MB. Escolha outro.';
      input.value = '';
      return;
    }
    fileName.textContent = file.name;

    // Libera a prévia anterior da memória antes de criar outra.
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(file);

    const preview = document.createElement('img');
    preview.className = avatar.className;
    preview.alt = '';
    preview.src = previewUrl;
    avatar.replaceWith(preview);
    avatar = preview;  // para a próxima troca substituir a prévia atual
  });
})();
