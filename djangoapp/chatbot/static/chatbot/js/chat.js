(function () {
  const root = document.getElementById('chat');
  if (!root) return;

  const toggle = document.getElementById('chat-toggle');
  const panel = document.getElementById('chat-panel');
  const messagesBox = document.getElementById('chat-messages');
  const form = document.getElementById('chat-form');
  const input = document.getElementById('chat-input');
  const sendButton = form.querySelector('.chat-send');
  const csrfToken = form.querySelector('[name=csrfmiddlewaretoken]').value;

  // Histórico da conversa, guardado na aba do navegador (sessionStorage)
  // para não sumir ao trocar de página. Some ao fechar a aba.
  const STORAGE_KEY = 'blog-chat-history';
  let history = [];

  function loadHistory() {
    try {
      history = JSON.parse(sessionStorage.getItem(STORAGE_KEY)) || [];
    } catch (error) {
      history = [];
    }
    history.forEach((item) => addMessage(item.role, item.content));
  }

  function saveHistory() {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(history.slice(-20)));
    } catch (error) {
      // Sem sessionStorage (ex.: aba anônima bloqueada): segue sem salvar.
    }
  }

  function addMessage(role, text) {
    const element = document.createElement('div');
    element.className = `chat-message chat-message-${role}`;
    // textContent (e não innerHTML) impede que HTML vindo da IA ou do
    // usuário seja executado na página (proteção contra XSS).
    element.textContent = text;
    messagesBox.appendChild(element);
    messagesBox.scrollTop = messagesBox.scrollHeight;
    return element;
  }

  function setOpen(open) {
    panel.hidden = !open;
    root.classList.toggle('is-open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'Fechar assistente' : 'Abrir assistente');
    if (open) input.focus();
  }

  toggle.addEventListener('click', () => setOpen(panel.hidden));

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !panel.hidden) setOpen(false);
  });

  // Enter envia; Shift+Enter quebra a linha.
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  // A caixa de texto cresce conforme a pessoa digita.
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message || sendButton.disabled) return;

    addMessage('user', message);
    input.value = '';
    input.style.height = 'auto';
    sendButton.disabled = true;

    const answer = addMessage('assistant', '');
    answer.classList.add('is-typing');

    let text = '';

    try {
      const response = await fetch(root.dataset.url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          // O Django exige o token CSRF em todo POST.
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({ message, history }),
      });

      if (!response.ok) {
        const contentType = response.headers.get('Content-Type') || '';
        text = contentType.includes('json')
          ? (await response.json()).error
          : await response.text();
        throw new Error(text);
      }

      // Lê a resposta aos poucos (streaming) e vai escrevendo na tela.
      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        text += decoder.decode(value, { stream: true });
        answer.classList.remove('is-typing');
        answer.textContent = text;
        messagesBox.scrollTop = messagesBox.scrollHeight;
      }

      history.push({ role: 'user', content: message });
      history.push({ role: 'assistant', content: text });
      saveHistory();
    } catch (error) {
      answer.textContent = text || 'Não consegui responder agora. Tente de novo.';
      answer.classList.add('is-error');
    } finally {
      answer.classList.remove('is-typing');
      sendButton.disabled = false;
      input.focus();
    }
  });

  loadHistory();
})();
