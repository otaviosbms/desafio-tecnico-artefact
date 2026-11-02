(function () {
  const messages = document.getElementById('messages');
  const form = document.getElementById('composer');
  const input = document.getElementById('input');
  const send = document.getElementById('send');
  const suggestions = document.getElementById('suggestions');
  const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Markdown mínimo (negrito, itálico e listas com hífen), aplicado sobre texto já escapado.
  function renderMarkdown(text) {
    const inline = (line) => line
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/(^|[^*])\*([^*\s][^*]*?)\*(?!\*)/g, '$1<em>$2</em>');
    const blocks = escapeHtml(text.trim()).split(/\n{2,}/);
    return blocks.map((block) => {
      const lines = block.split('\n');
      const items = lines.filter((l) => /^\s*[-•]\s+/.test(l));
      if (items.length && items.length === lines.filter((l) => l.trim()).length) {
        return '<ul>' + items.map((l) => '<li>' + inline(l.replace(/^\s*[-•]\s+/, '')) + '</li>').join('') + '</ul>';
      }
      return '<p>' + lines.map(inline).join('<br>') + '</p>';
    }).join('');
  }

  function addMessage(role, text, extra = {}) {
    const wrapper = document.createElement('div');
    wrapper.className = 'message ' + role + (extra.error ? ' error' : '');
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    if (role === 'assistant') {
      bubble.innerHTML = renderMarkdown(text);
    } else {
      bubble.textContent = text;
    }
    wrapper.appendChild(bubble);

    if (extra.tools && extra.tools.length) {
      const tools = document.createElement('div');
      tools.className = 'tools';
      extra.tools.forEach((call) => {
        const tag = document.createElement('span');
        tag.className = 'tool';
        tag.textContent = 'consultou: ' + call.nome;
        tag.title = JSON.stringify(call.argumentos);
        tools.appendChild(tag);
      });
      wrapper.appendChild(tools);
    }
    messages.appendChild(wrapper);
    messages.scrollTop = messages.scrollHeight;
    return wrapper;
  }

  function showTyping() {
    const wrapper = document.createElement('div');
    wrapper.className = 'message assistant typing';
    wrapper.innerHTML = '<div class="bubble">Digitando<span class="dots"></span></div>';
    messages.appendChild(wrapper);
    messages.scrollTop = messages.scrollHeight;
    return wrapper;
  }

  function setBusy(busy) {
    input.disabled = busy;
    send.disabled = busy;
    suggestions.querySelectorAll('button').forEach((b) => { b.disabled = busy; });
  }

  async function sendMessage(text) {
    text = text.trim();
    if (!text) return;
    suggestions.hidden = true;
    addMessage('user', text);
    input.value = '';
    autoResize();
    setBusy(true);
    const typing = showTyping();

    try {
      const response = await fetch(window.SEND_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
        body: JSON.stringify({ texto: text }),
      });
      const data = await response.json().catch(() => ({}));
      typing.remove();
      if (!response.ok) {
        addMessage('assistant', data.erro || 'Não consegui responder agora. Tente novamente.', { error: true });
      } else {
        addMessage('assistant', data.resposta, { tools: data.ferramentas });
      }
    } catch (err) {
      typing.remove();
      addMessage('assistant', 'Sem conexão com o servidor. Verifique sua internet e tente de novo.', { error: true });
    } finally {
      setBusy(false);
      input.focus();
    }
  }

  function autoResize() {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 140) + 'px';
  }

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    sendMessage(input.value);
  });

  // Enter envia; Shift+Enter quebra linha.
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  input.addEventListener('input', autoResize);

  suggestions.addEventListener('click', (event) => {
    if (event.target.matches('.chip')) sendMessage(event.target.textContent);
  });

  JSON.parse(document.getElementById('history').textContent)
    .forEach((m) => addMessage(m.role, m.content));
  input.focus();
})();
