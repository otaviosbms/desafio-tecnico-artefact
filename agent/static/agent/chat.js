(function () {
  'use strict';

  const page = JSON.parse(document.getElementById('page-data').textContent);
  const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
  const $ = (id) => document.getElementById(id);
  const app = $('app');

  // ---------- Configurações (por navegador) ----------

  const STORAGE_KEY = 'emporio-testes-config';
  const DEFAULTS = {
    modelo: '',
    temperatura: null, // null = padrão do .env
    agora: '',
    showTools: true,
    showMetrics: true,
    enterSends: true,
    autosend: false,
    theme: 'auto',
  };
  const settings = Object.assign({}, DEFAULTS, loadSettings());

  function loadSettings() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}; } catch (e) { return {}; }
  }
  function saveSettings() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(settings)); } catch (e) { /* modo privado */ }
  }

  // ---------- Estado da conversa ----------

  let threadId = page.thread_id;
  let turns = buildTurns(page.historico, page.rastro);
  let selectedTurn = null;
  let busy = false;

  function buildTurns(history, trace) {
    const result = [];
    history.forEach((m) => {
      if (m.role === 'user') result.push({ turno: result.length + 1, cliente: m.content, assistente: '', rastro: [] });
      else if (result.length) result[result.length - 1].assistente = m.content;
    });
    (trace || []).forEach((ev) => {
      const turn = result[ev.turno - 1];
      if (turn) turn.rastro.push(ev);
    });
    result.forEach((t) => { t.duracao_ms = sumDurations(t.rastro); });
    return result;
  }

  // ---------- Formatação ----------

  const nf = new Intl.NumberFormat('pt-BR');
  function seconds(ms) {
    if (ms == null) return '—';
    return ms < 1000 ? ms + ' ms' : nf.format(Math.round(ms / 100) / 10) + ' s';
  }
  function sumDurations(events) { return events.reduce((acc, e) => acc + (e.duracao_ms || 0), 0); }
  function tokensOf(events) {
    return events.reduce((acc, e) => acc + ((e.tokens && e.tokens.total_tokens) || 0), 0);
  }
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
  }
  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([k, v]) => {
      if (k === 'class') node.className = v;
      else if (k === 'text') node.textContent = v;
      else if (k === 'html') node.innerHTML = v;
      else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
      else if (v !== null && v !== undefined && v !== false) node.setAttribute(k, v);
    });
    (children || []).forEach((c) => c && node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c));
    return node;
  }
  // Formata 'AAAA-MM-DDTHH:MM[...]' como está (horário de Campo Grande), sem converter
  // para o fuso do navegador.
  function formatDateTime(value) {
    const [y, mo, d, h, mi] = String(value).match(/\d+/g).map(Number);
    return new Date(y, mo - 1, d, h, mi).toLocaleString('pt-BR', {
      weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  }

  // Markdown mínimo (negrito, itálico, listas com hífen) sobre texto já escapado.
  function renderMarkdown(text) {
    const inline = (line) => line
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/(^|[^*])\*([^*\s][^*]*?)\*(?!\*)/g, '$1<em>$2</em>');
    return escapeHtml((text || '').trim()).split(/\n{2,}/).map((block) => {
      const lines = block.split('\n');
      const isList = lines.every((l) => !l.trim() || /^\s*[-•]\s+/.test(l));
      if (isList) {
        return '<ul>' + lines.filter((l) => l.trim())
          .map((l) => '<li>' + inline(l.replace(/^\s*[-•]\s+/, '')) + '</li>').join('') + '</ul>';
      }
      return '<p>' + lines.map(inline).join('<br>') + '</p>';
    }).join('');
  }

  // ---------- Conversa ----------

  const messages = $('messages');

  function renderConversation() {
    messages.innerHTML = '';
    if (!turns.length) {
      messages.appendChild(el('div', { class: 'empty', html:
        '<strong>Nenhuma mensagem ainda</strong>Escreva como se fosse um cliente ou escolha um cenário de teste ' +
        'na configuração. O inspetor mostra cada chamada ao modelo e às ferramentas.' }));
      return;
    }
    turns.forEach((turn) => {
      messages.appendChild(userMessage(turn.cliente));
      if (turn.assistente || turn.erro) messages.appendChild(assistantMessage(turn));
    });
    scrollToBottom();
  }

  function userMessage(text) {
    return el('div', { class: 'message user' }, [el('div', { class: 'bubble', text })]);
  }

  function assistantMessage(turn) {
    const node = el('div', {
      class: 'message assistant' + (turn.erro ? ' error' : '') + (selectedTurn === turn.turno ? ' selected' : ''),
      'data-turn': turn.erro ? null : turn.turno,
    }, [el('div', { class: 'bubble', html: renderMarkdown(turn.erro || turn.assistente) })]);

    if (!turn.erro) {
      const llmCalls = turn.rastro.filter((e) => e.tipo === 'llm').length;
      const tokens = tokensOf(turn.rastro);
      const meta = el('div', { class: 'meta' });
      const failure = turn.rastro.find((e) => e.erro);
      if (failure) meta.appendChild(el('span', { class: 'tag error', text: '⚠ erro no modelo', title: failure.erro }));
      turn.rastro.filter((e) => e.tipo === 'ferramenta')
        .forEach((e) => meta.appendChild(el('span', { class: 'tag tool', text: '⚙ ' + e.nome, title: JSON.stringify(e.argumentos) })));
      if (turn.rastro.length) {
        meta.appendChild(el('span', { class: 'tag metric', text: '⏱ ' + seconds(turn.duracao_ms) }));
        meta.appendChild(el('span', { class: 'tag metric', text: llmCalls + (llmCalls === 1 ? ' chamada' : ' chamadas') + ' LLM' }));
        if (tokens) meta.appendChild(el('span', { class: 'tag metric', text: nf.format(tokens) + ' tokens' }));
      }
      if (meta.childNodes.length) node.appendChild(meta);
      node.querySelector('.bubble').addEventListener('click', () => selectTurn(turn.turno, true));
    }
    return node;
  }

  function scrollToBottom() { messages.scrollTop = messages.scrollHeight; }

  function showTyping() {
    const started = Date.now();
    const bubble = el('div', { class: 'bubble', text: 'Pensando… 0 s' });
    const node = el('div', { class: 'message assistant typing' }, [bubble]);
    messages.querySelector('.empty')?.remove();
    messages.appendChild(node);
    scrollToBottom();
    const timer = setInterval(() => {
      bubble.textContent = 'Pensando… ' + Math.round((Date.now() - started) / 1000) + ' s';
    }, 1000);
    return () => { clearInterval(timer); node.remove(); };
  }

  // ---------- Envio ----------

  const input = $('input');
  const sendBtn = $('send');

  function currentConfig() {
    return {
      modelo: settings.modelo || null,
      temperatura: settings.temperatura,
      agora: settings.agora || null,
    };
  }

  async function postJson(url, body, extraHeaders) {
    const response = await fetch(url, {
      method: 'POST',
      headers: Object.assign({ 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken }, extraHeaders || {}),
      body: JSON.stringify(body || {}),
    });
    const data = await response.json().catch(() => ({}));
    return { ok: response.ok, data };
  }

  async function sendMessage(text) {
    text = text.trim();
    if (!text || busy) return;
    setBusy(true);
    showView('chat');
    messages.querySelector('.empty')?.remove();
    messages.appendChild(userMessage(text));
    input.value = '';
    autoResize();
    const stopTyping = showTyping();

    const turn = { turno: turns.length + 1, cliente: text, assistente: '', rastro: [] };
    try {
      const { ok, data } = await postJson(page.urls.mensagem, { texto: text, config: currentConfig() });
      if (ok) {
        Object.assign(turn, { assistente: data.resposta, rastro: data.rastro || [], duracao_ms: data.duracao_ms });
        turns.push(turn);
      } else {
        turn.erro = data.erro || 'Não consegui responder agora.';
      }
    } catch (err) {
      turn.erro = 'Sem conexão com o servidor.';
    }
    stopTyping();
    messages.appendChild(assistantMessage(turn));
    scrollToBottom();
    if (!turn.erro) {
      renderInspector();
      selectTurn(turn.turno, false);
      notifyInspector();
    }
    setBusy(false);
    input.focus();
  }

  function setBusy(value) {
    busy = value;
    input.disabled = value;
    sendBtn.disabled = value;
    document.querySelectorAll('.scenario-group .chip').forEach((b) => { b.disabled = value; });
  }

  function autoResize() {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 160) + 'px';
  }

  $('composer').addEventListener('submit', (e) => { e.preventDefault(); sendMessage(input.value); });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey && settings.enterSends) {
      e.preventDefault();
      $('composer').requestSubmit();
    }
  });
  input.addEventListener('input', autoResize);

  function insertText(text) {
    showView('chat');
    input.value = input.value ? input.value.trimEnd() + ' ' + text : text;
    autoResize();
    input.focus();
  }

  // ---------- Inspetor ----------

  function renderInspector() {
    renderStats();
    const container = $('trace');
    container.innerHTML = '';
    if (!turns.length) {
      container.appendChild(el('p', { class: 'hint', text: 'O rastro de cada resposta aparece aqui: chamadas ao modelo, ferramentas usadas, argumentos, resultados, tempos e tokens.' }));
      return;
    }
    turns.forEach((turn) => container.appendChild(turnCard(turn)));
  }

  function renderStats() {
    const events = turns.flatMap((t) => t.rastro);
    const llm = events.filter((e) => e.tipo === 'llm');
    const answered = turns.filter((t) => t.rastro.length);
    const avg = answered.length ? sumDurations(events) / answered.length : null;
    const stats = [
      [turns.length, 'mensagens'],
      [llm.length, 'chamadas LLM'],
      [nf.format(tokensOf(events)), 'tokens'],
      [seconds(avg == null ? null : Math.round(avg)), 'média/resposta'],
    ];
    $('stats').innerHTML = stats.map(([v, l]) => '<div class="stat"><b>' + escapeHtml(v) + '</b><span>' + l + '</span></div>').join('');
  }

  function turnCard(turn) {
    const card = el('article', { class: 'turn' + (selectedTurn === turn.turno ? ' selected' : ''), id: 'turn-' + turn.turno });
    const tokens = tokensOf(turn.rastro);
    card.appendChild(el('div', { class: 'turn-head' }, [
      el('b', { text: '#' + turn.turno + ' · ' + turn.cliente }),
      el('span', { text: seconds(turn.duracao_ms) + (tokens ? ' · ' + nf.format(tokens) + ' tokens' : '') }),
    ]));
    if (!turn.rastro.length) {
      card.appendChild(el('div', { class: 'event' }, [el('div', { class: 'detail', text: 'Sem rastro registrado para esta mensagem.' })]));
    }
    turn.rastro.forEach((ev) => card.appendChild(eventRow(ev)));
    return card;
  }

  function eventRow(ev) {
    const row = el('div', { class: 'event' });
    if (ev.tipo === 'llm') {
      const t = ev.tokens || {};
      row.appendChild(el('div', { class: 'event-title' }, [
        el('span', { class: 'kind llm', text: 'Modelo' }),
        el('span', { class: 'time', text: seconds(ev.duracao_ms) }),
      ]));
      const parts = [ev.modelo];
      if (t.total_tokens) parts.push(nf.format(t.prompt_tokens || 0) + ' → ' + nf.format(t.completion_tokens || 0) + ' tokens');
      if (ev.finish_reason) parts.push('fim: ' + ev.finish_reason);
      if (!ev.com_ferramentas) parts.push('sem ferramentas (limite de rodadas)');
      row.appendChild(el('div', { class: 'detail', text: parts.join(' · ') }));
      if (ev.pediu_ferramentas && ev.pediu_ferramentas.length) {
        row.appendChild(el('div', { class: 'detail', text: 'Pediu: ' + ev.pediu_ferramentas.join(', ') }));
      }
      if (ev.erro) row.appendChild(el('div', { class: 'detail error', text: ev.erro }));
    } else {
      row.appendChild(el('div', { class: 'event-title' }, [
        el('span', { class: 'kind tool', text: ev.nome }),
        el('span', { class: 'time', text: seconds(ev.duracao_ms) }),
      ]));
      const hasError = ev.resultado && ev.resultado.erro;
      if (hasError) row.appendChild(el('div', { class: 'detail error', text: ev.resultado.erro }));
      row.appendChild(jsonBlock('Argumentos', ev.argumentos, true));
      row.appendChild(jsonBlock('Resultado', ev.resultado, false));
    }
    return row;
  }

  function jsonBlock(label, value, open) {
    const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
    return el('details', { open: open ? '' : null }, [
      el('summary', { text: label }),
      el('pre', { class: 'code', text }),
    ]);
  }

  function selectTurn(number, reveal) {
    selectedTurn = number;
    document.querySelectorAll('.message.selected, .turn.selected').forEach((n) => n.classList.remove('selected'));
    document.querySelector('.message.assistant[data-turn="' + number + '"]')?.classList.add('selected');
    const card = $('turn-' + number);
    if (!card) return;
    card.classList.add('selected');
    if (reveal) {
      selectTab('trace');
      openInspector();
    }
    card.scrollIntoView({ block: 'nearest', behavior: reveal ? 'smooth' : 'auto' });
  }

  // Abas do inspetor
  function selectTab(name) {
    document.querySelectorAll('.tab').forEach((t) => t.setAttribute('aria-selected', String(t.dataset.tab === name)));
    document.querySelectorAll('.tab-panel').forEach((p) => { p.hidden = p.dataset.panel !== name; });
  }
  document.querySelectorAll('.tab').forEach((t) => t.addEventListener('click', () => selectTab(t.dataset.tab)));

  // ---------- Contexto: system prompt, ferramentas, situação da loja ----------

  let contextTimer = null;

  async function refreshContext() {
    const params = settings.agora ? '?agora=' + encodeURIComponent(settings.agora) : '';
    try {
      const response = await fetch(page.urls.contexto + params);
      if (!response.ok) return;
      const data = await response.json();
      $('system-prompt').textContent = data.system_prompt;
      $('prompt-info').textContent = 'System prompt montado para ' + formatDateTime(data.agora) +
        (settings.agora ? ' (simulado)' : '') + '. É recalculado a cada mensagem e não fica salvo no histórico.';
      renderStoreStatus(data.situacao_loja);
      renderToolDefs(data.ferramentas);
    } catch (e) { /* servidor indisponível: mantém o que já está na tela */ }
  }

  function renderStoreStatus(status) {
    const pill = $('pill-store');
    pill.textContent = status.aberta ? 'Loja aberta' : 'Loja fechada';
    pill.className = 'pill ' + (status.aberta ? 'open' : 'closed');
    pill.title = status.aberta ? 'Fecha às ' + status.fecha_as : 'Abre ' + status.proxima_abertura;
  }

  let toolsRendered = false;
  function renderToolDefs(tools) {
    if (toolsRendered) return;
    toolsRendered = true;
    const container = $('tool-defs');
    container.appendChild(el('p', { class: 'hint', text: tools.length + ' ferramentas disponíveis para o modelo (schemas enviados no function calling).' }));
    tools.forEach((t) => container.appendChild(el('div', { class: 'tool-def' }, [
      el('h3', { text: t.name }),
      el('p', { text: t.description }),
      jsonBlock('Parâmetros', t.parameters, false),
    ])));
  }

  function scheduleContextRefresh() {
    clearInterval(contextTimer);
    refreshContext();
    renderClockPill();
    // Relógio real: atualiza a situação da loja a cada minuto.
    if (!settings.agora) {
      contextTimer = setInterval(() => { refreshContext(); renderClockPill(); }, 60000);
    }
  }

  // ---------- Painel de configuração ----------

  function renderModelPill() {
    const model = settings.modelo || (page.llm && page.llm.modelo) || '—';
    const temp = settings.temperatura == null ? '' : ' · t=' + settings.temperatura;
    const pill = $('pill-model');
    pill.textContent = model.split('/').pop() + temp;
    pill.title = 'Modelo: ' + model + (settings.modelo ? ' (sobrescrito na UI)' : ' (do .env)');
    pill.classList.toggle('simulated', !!settings.modelo || settings.temperatura != null);
  }

  function renderClockPill() {
    const pill = $('pill-clock');
    if (settings.agora) {
      pill.textContent = '⏲ ' + formatDateTime(settings.agora);
      pill.title = 'Data/hora simulada';
      pill.classList.add('simulated');
    } else {
      pill.textContent = '⏲ ' + new Date().toLocaleTimeString('pt-BR', {
        hour: '2-digit', minute: '2-digit', timeZone: 'America/Campo_Grande',
      }) + ' (real)';
      pill.title = 'Relógio real (o agente usa o fuso de Campo Grande)';
      pill.classList.remove('simulated');
    }
  }

  function initConfigPanel() {
    $('thread-id').textContent = threadId;
    $('copy-thread').addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(threadId); $('copy-thread').textContent = 'Copiado'; }
      catch (e) { $('copy-thread').textContent = 'Erro'; }
      setTimeout(() => { $('copy-thread').textContent = 'Copiar'; }, 1500);
    });

    // Modelo
    const llm = page.llm || {};
    $('llm-provider').textContent = llm.erro ? 'não configurado' : llm.provedor;
    $('llm-endpoint').textContent = llm.erro || llm.base_url;
    $('model').placeholder = llm.modelo || '';
    $('model').value = settings.modelo;
    if (llm.modelo) $('model-options').appendChild(el('option', { value: llm.modelo }));
    $('model').addEventListener('change', () => {
      settings.modelo = $('model').value.trim();
      saveSettings();
      renderModelPill();
    });

    const temp = $('temperature');
    const tempDefault = $('temperature-default');
    function syncTemperature() {
      const useDefault = settings.temperatura == null;
      tempDefault.checked = useDefault;
      temp.disabled = useDefault;
      temp.value = useDefault ? (llm.temperatura ?? 0.7) : settings.temperatura;
      $('temperature-value').textContent = useDefault
        ? (llm.temperatura == null ? 'padrão do provedor' : llm.temperatura + ' (.env)')
        : settings.temperatura;
    }
    temp.addEventListener('input', () => { settings.temperatura = Number(temp.value); syncTemperature(); });
    temp.addEventListener('change', () => { saveSettings(); renderModelPill(); });
    tempDefault.addEventListener('change', () => {
      settings.temperatura = tempDefault.checked ? null : Number(temp.value);
      saveSettings();
      syncTemperature();
      renderModelPill();
    });
    syncTemperature();

    // Data/hora simulada
    const simTime = $('sim-time');
    const presets = $('time-presets');
    function syncTime() {
      simTime.value = settings.agora;
      presets.querySelectorAll('.chip').forEach((c) => c.classList.toggle('active', c.dataset.value === settings.agora));
    }
    page.horarios.forEach((h) => presets.appendChild(el('button', {
      type: 'button', class: 'chip', 'data-value': h.valor, text: h.rotulo,
      onclick: () => { settings.agora = h.valor; saveSettings(); syncTime(); scheduleContextRefresh(); },
    })));
    simTime.addEventListener('change', () => {
      settings.agora = simTime.value;
      saveSettings();
      syncTime();
      scheduleContextRefresh();
    });
    syncTime();

    // Exibição
    [['show-tools', 'showTools'], ['show-metrics', 'showMetrics'], ['enter-sends', 'enterSends'], ['autosend', 'autosend']]
      .forEach(([id, key]) => {
        const box = $(id);
        box.checked = settings[key];
        box.addEventListener('change', () => { settings[key] = box.checked; saveSettings(); applyDisplay(); });
      });
    $('theme').value = settings.theme;
    $('theme').addEventListener('change', () => { settings.theme = $('theme').value; saveSettings(); applyDisplay(); });

    // Cenários
    const scenarios = $('scenarios');
    page.cenarios.forEach((group) => {
      const box = el('div', { class: 'scenario-group' }, [el('h3', { text: group.grupo })]);
      group.mensagens.forEach((text) => box.appendChild(el('button', {
        type: 'button', class: 'chip', text,
        onclick: () => (settings.autosend ? sendMessage(text) : insertText(text)),
      })));
      scenarios.appendChild(box);
    });

    // Dados de teste
    if (!page.pedidos_teste.length) {
      $('test-data-section').hidden = true;
    } else {
      page.pedidos_teste.forEach((o) => $('test-orders').appendChild(el('button', {
        type: 'button', class: 'order', title: o.cliente + ' · ' + o.telefone,
        onclick: () => insertText('Pedido ' + o.numero + ', e-mail ' + o.email),
      }, [
        el('b', { text: '#' + o.numero }),
        el('span', { text: o.status }),
        el('span', { text: o.email }),
      ])));
    }

    // Conversas
    $('new-conversation').addEventListener('click', async () => {
      if (busy) return;
      const { ok, data } = await postJson(page.urls.nova, {}, { Accept: 'application/json' });
      if (ok) loadConversation(data.thread_id, [], []);
    });
    $('open-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const id = $('open-thread').value.trim();
      if (!id || busy) return;
      const { ok, data } = await postJson(page.urls.abrir, { thread_id: id });
      if (ok) {
        $('open-thread').value = '';
        loadConversation(data.thread_id, data.historico, data.rastro);
      } else {
        alert(data.erro || 'Não foi possível abrir a conversa.');
      }
    });
    $('export-md').addEventListener('click', exportMarkdown);
  }

  function loadConversation(id, history, trace) {
    threadId = id;
    $('thread-id').textContent = id;
    turns = buildTurns(history, trace);
    selectedTurn = null;
    renderConversation();
    renderInspector();
    showView('chat');
  }

  function applyDisplay() {
    app.classList.toggle('show-tools', settings.showTools);
    app.classList.toggle('show-metrics', settings.showMetrics);
    if (settings.theme === 'auto') document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme', settings.theme);
  }

  // ---------- Exportação ----------

  function exportMarkdown() {
    const model = settings.modelo || (page.llm && page.llm.modelo) || '';
    const lines = [
      '# Conversa de teste — Empório da Música', '',
      '- Thread: `' + threadId + '`',
      '- Modelo: `' + model + '`',
      '- Data/hora usada: ' + (settings.agora ? formatDateTime(settings.agora) + ' (simulada)' : 'relógio real'),
      '- Exportado em: ' + new Date().toLocaleString('pt-BR'), '', '---', '',
    ];
    turns.forEach((t) => {
      lines.push('**Cliente:** ' + t.cliente, '');
      t.rastro.filter((e) => e.tipo === 'ferramenta')
        .forEach((e) => lines.push('> 🔧 Ferramenta: `' + e.nome + '` `' + JSON.stringify(e.argumentos) + '`'));
      if (t.rastro.some((e) => e.tipo === 'ferramenta')) lines.push('');
      lines.push('**Assistente:**', '', (t.assistente || '').trim(), '', '---', '');
    });
    const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' });
    const link = el('a', { href: URL.createObjectURL(blob), download: 'conversa-' + threadId + '.md' });
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  }

  // ---------- Navegação responsiva ----------

  const narrow = window.matchMedia('(max-width: 899px)');
  const medium = window.matchMedia('(max-width: 1199px)');
  const scrim = $('scrim');
  const inspectorNavBtn = document.querySelector('.bottom-nav [data-view="inspector"]');
  let unseen = 0;

  function showView(view) {
    app.dataset.view = view;
    document.querySelectorAll('.bottom-nav button').forEach((b) => {
      if (b.dataset.view === view) b.setAttribute('aria-current', 'page');
      else b.removeAttribute('aria-current');
    });
    if (view === 'inspector') { unseen = 0; renderBadge(); }
  }

  function openInspector() {
    if (narrow.matches) showView('inspector');
    else if (medium.matches) { app.dataset.drawer = 'inspector'; scrim.hidden = false; }
  }
  function closeDrawer() { delete app.dataset.drawer; scrim.hidden = true; }

  function notifyInspector() {
    if (narrow.matches && app.dataset.view !== 'inspector') { unseen += 1; renderBadge(); }
  }
  function renderBadge() {
    inspectorNavBtn.querySelector('.badge')?.remove();
    if (unseen) inspectorNavBtn.appendChild(el('span', { class: 'badge', text: String(unseen) }));
  }

  document.querySelectorAll('.bottom-nav button').forEach((b) => b.addEventListener('click', () => showView(b.dataset.view)));
  document.querySelectorAll('[data-open="inspector"]').forEach((b) => b.addEventListener('click', openInspector));
  document.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', closeDrawer));
  scrim.addEventListener('click', closeDrawer);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDrawer(); });
  medium.addEventListener('change', closeDrawer);

  // ---------- Início ----------

  applyDisplay();
  initConfigPanel();
  renderModelPill();
  renderConversation();
  renderInspector();
  showView('chat');
  scheduleContextRefresh();
  input.focus();
})();
