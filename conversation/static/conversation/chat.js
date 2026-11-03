(function () {
  'use strict';

  const page = JSON.parse(document.getElementById('page-data').textContent);
  const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
  const $ = (id) => document.getElementById(id);
  const app = $('app');

  // ---------- Configurações (por navegador) ----------

  const STORAGE_KEY = 'emporio-testes-config';
  const DEFAULTS = {
    agora: '',
    // Estágios: '' = padrão do .env
    guardrailsModo: '',
    roteadorModo: '',
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
  let turns = buildTurns(page.historico, page.rastro, page.decisoes);
  let selectedTurn = null;
  let busy = false;

  function buildTurns(history, trace, decisions) {
    const result = [];
    history.forEach((m) => {
      if (m.role === 'user') {
        result.push({ turno: result.length + 1, cliente: m.content, assistente: '', rastro: [], decisoes: [] });
      } else if (result.length) result[result.length - 1].assistente = m.content;
    });
    (trace || []).forEach((ev) => {
      const turn = result[ev.turno - 1];
      if (turn) turn.rastro.push(ev);
    });
    (decisions || []).forEach((d) => {
      const turn = result[d.turno - 1];
      if (turn) turn.decisoes.push(d);
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
  function formatCost(usd) {
    if (!usd) return 'custo US$ 0';
    return 'custo US$ ' + (usd < 0.01 ? usd.toPrecision(2) : usd.toFixed(4));
  }

  function costOf(events) {
    return events.reduce((acc, e) => acc + (Number(e.custo_usd) || 0), 0);
  }
  function formatUsd(usd) {
    if (!usd) return 'US$ 0';
    return 'US$ ' + (usd < 0.01 ? usd.toPrecision(2) : usd.toFixed(4));
  }

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
      messages.appendChild(emptyState());
      return;
    }
    turns.forEach((turn) => {
      messages.appendChild(userMessage(turn.cliente));
      if (turn.assistente || turn.erro) messages.appendChild(assistantMessage(turn));
    });
    scrollToBottom();
  }

  function emptyState() {
    const suggestions = page.cenarios.map((g) => g.mensagens[0]).slice(0, 4);
    return el('div', { class: 'empty' }, [
      el('span', { class: 'empty-logo', text: '♪' }),
      el('strong', { text: 'Como posso ajudar?' }),
      el('p', { text: 'Escreva como um cliente da loja ou comece por uma sugestão. ' +
        'O inspetor mostra cada chamada ao modelo, às ferramentas e o que cada estágio decidiu.' }),
      el('div', { class: 'suggestions' }, suggestions.map((text) => el('button', {
        type: 'button', class: 'suggestion', text, onclick: () => sendMessage(text),
      }))),
    ]);
  }

  function userMessage(text) {
    return el('div', { class: 'message user' }, [el('div', { class: 'bubble', text })]);
  }

  function assistantMessage(turn) {
    const node = el('div', {
      class: 'message assistant' + (turn.erro ? ' error' : '') + (selectedTurn === turn.turno ? ' selected' : ''),
      'data-turn': turn.erro ? null : turn.turno,
    }, [el('div', { class: 'bubble', html: renderMarkdown(turn.erro || turn.assistente) })]);
    node.prepend(el('span', { class: 'avatar', text: '♪', 'aria-hidden': 'true' }));

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
    const bubble = el('div', { class: 'bubble' }, [el('span', { class: 'dots', 'aria-hidden': 'true' }),
      el('span', { class: 'elapsed', text: '0 s' })]);
    const node = el('div', { class: 'message assistant typing' }, [
      el('span', { class: 'avatar', text: '♪', 'aria-hidden': 'true' }), bubble]);
    messages.querySelector('.empty')?.remove();
    messages.appendChild(node);
    scrollToBottom();
    const timer = setInterval(() => {
      bubble.querySelector('.elapsed').textContent = Math.round((Date.now() - started) / 1000) + ' s';
    }, 1000);
    return () => { clearInterval(timer); node.remove(); };
  }

  // ---------- Envio ----------

  const input = $('input');
  const sendBtn = $('send');

  function currentConfig() {
    return {
      agora: settings.agora || null,
      modo_guardrails: settings.guardrailsModo || null,
      modo_roteador: settings.roteadorModo || null,
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

    const turn = { turno: turns.length + 1, cliente: text, assistente: '', rastro: [], decisoes: [] };
    try {
      const { ok, data } = await postJson(page.urls.mensagem, { texto: text, config: currentConfig() });
      if (ok) {
        Object.assign(turn, {
          assistente: data.resposta, rastro: data.rastro || [], decisoes: data.decisoes || [], duracao_ms: data.duracao_ms,
        });
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
    document.querySelectorAll('.scenario, .suggestion').forEach((b) => { b.disabled = value; });
  }

  function autoResize() {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 160) + 'px';
  }

  $('composer').addEventListener('submit', (e) => { e.preventDefault(); sendMessage(input.value); });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
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
    renderDecisions();
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
    const perMessage = answered.length ? nf.format(Math.round(llm.length / answered.length * 10) / 10) : '—';
    const stats = [
      [turns.length, 'mensagens'],
      [llm.length, 'chamadas LLM'],
      [perMessage, 'LLM/mensagem'],
      [nf.format(tokensOf(events)), 'tokens'],
      [formatUsd(costOf(llm)), 'custo'],
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
      const parts = [ev.caller, ev.modelo].filter(Boolean);
      if (t.total_tokens) parts.push(nf.format(t.prompt_tokens || 0) + ' → ' + nf.format(t.completion_tokens || 0) + ' tokens');
      if (ev.custo_usd != null) parts.push(formatCost(Number(ev.custo_usd)));
      if (ev.finish_reason) parts.push('fim: ' + ev.finish_reason);
      if (ev.caller === 'agent.respond' && !ev.com_ferramentas) parts.push('sem ferramentas');
      if (ev.ferramentas_oferecidas) parts.push('ferramentas: ' + (ev.ferramentas_oferecidas.join(', ') || 'nenhuma'));
      row.appendChild(el('div', { class: 'detail', text: parts.join(' · ') }));
      if (ev.pediu_ferramentas && ev.pediu_ferramentas.length) {
        row.appendChild(el('div', { class: 'detail', text: 'Pediu: ' + ev.pediu_ferramentas.join(', ') }));
      }
      if (ev.erro) row.appendChild(el('div', { class: 'detail error', text: ev.erro }));
    } else if (ev.tipo === 'decisao') {
      row.appendChild(ev.estagio === 'guardrails' ? guardrailsRow(ev) : decisionRow(ev));
      return row;
    } else if (ev.tipo === 'bloqueio') {
      row.appendChild(el('div', { class: 'event-title' }, [
        el('span', { class: 'kind stage', text: 'Resposta de bloqueio' }),
        el('span', { class: 'time', text: ev.motivo }),
      ]));
      row.appendChild(el('div', { class: 'detail', text: 'Sem chamar o agente: ' + ev.resposta }));
      return row;
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

  // Decisão de um estágio do pipeline (por enquanto, o roteador de intenção).
  function decisionRow(ev) {
    const origins = { off: 'desligado', shortcut: 'atalho, sem LLM', llm: 'LLM', fallback: 'falhou: liberou tudo' };
    const box = el('div');
    box.appendChild(el('div', { class: 'event-title' }, [
      el('span', { class: 'kind stage', text: 'Roteador · ' + ev.modo }),
      el('span', { class: 'time', text: origins[ev.origem] || ev.origem }),
    ]));
    if (ev.intencoes && ev.intencoes.length) {
      const confidence = ev.confianca == null ? '' : ' (confiança ' + Math.round(ev.confianca * 100) + '%)';
      box.appendChild(el('div', { class: 'detail', text: 'Intenções: ' + ev.intencoes.join(', ') + confidence }));
    }
    const allowed = ev.ferramentas_liberadas;
    box.appendChild(el('div', { class: 'detail', text: 'Ferramentas liberadas: ' +
      (allowed == null ? 'todas' : (allowed.join(', ') || 'nenhuma')) }));
    if (ev.modo === 'shadow' && ev.ferramentas_propostas) {
      box.appendChild(el('div', { class: 'detail', text: 'Em enforce seriam: ' + (ev.ferramentas_propostas.join(', ') || 'nenhuma') }));
    }
    if (ev.justificativa) box.appendChild(el('div', { class: 'detail', text: ev.justificativa }));
    return box;
  }

  // Decisão do guardrails: avaliação, efeito (que só vale em enforce) e orientação ao agente.
  function guardrailsRow(ev) {
    const origins = { off: 'desligado', detector: 'regra, sem LLM', llm: 'LLM', fallback: 'falhou: seguiu' };
    const box = el('div');
    box.appendChild(el('div', { class: 'event-title' }, [
      el('span', { class: 'kind stage', text: 'Guardrails · ' + ev.modo }),
      el('span', { class: 'time', text: (origins[ev.origem] || ev.origem) + (ev.regra ? ' · ' + ev.regra : '') }),
    ]));
    if (ev.modo !== 'off') {
      const verdict = ev.permitido ? 'passa' : 'bloqueio ' + (ev.severidade === 'hard' ? 'duro' : 'leve');
      const effect = ev.permitido || ev.aplicada ? '' : ' (não aplicado: modo ' + ev.modo + ')';
      const row = el('div', { class: 'detail' + (ev.permitido ? '' : ' error'), text: 'Avaliação: ' + verdict +
        ' · ' + ev.categoria + effect });
      box.appendChild(row);
    }
    if (ev.requer_humano) box.appendChild(el('div', { class: 'detail', text: 'Pede atendimento humano' }));
    if (ev.bloqueios_seguidos) box.appendChild(el('div', { class: 'detail', text: 'Bloqueios seguidos: ' + ev.bloqueios_seguidos }));
    if (ev.orientacao) box.appendChild(el('div', { class: 'detail', text: 'Orientação: ' + ev.orientacao }));
    if (ev.justificativa) box.appendChild(el('div', { class: 'detail', text: ev.justificativa }));
    return box;
  }

  // ---------- Aba Decisões ----------

  function renderDecisions() {
    const container = $('decisions');
    container.innerHTML = '';
    const withDecisions = turns.filter((t) => t.decisoes && t.decisoes.length);
    if (!withDecisions.length) {
      container.appendChild(el('p', { class: 'hint', text: turns.length
        ? 'As mensagens desta conversa são de antes dos estágios: não há decisões registradas.'
        : 'As decisões aparecem aqui a cada mensagem.' }));
      return;
    }
    withDecisions.forEach((turn) => container.appendChild(decisionCard(turn)));
  }

  function decisionCard(turn) {
    const card = el('article', { class: 'decision-turn' + (selectedTurn === turn.turno ? ' selected' : ''),
      id: 'decision-' + turn.turno });
    card.appendChild(el('b', { text: '#' + turn.turno + ' · ' + turn.cliente }));
    const by = (stage) => turn.decisoes.filter((d) => d.estagio === stage);
    by('guardrails').forEach((d) => card.appendChild(decisionLine('Guardrails', d.modo, guardrailsSummary(d),
      !d.permitido)));
    by('router').forEach((d) => card.appendChild(decisionLine('Intenção', d.modo, routerSummary(d), d.origem === 'fallback')));
    const final = by('final')[0];
    if (final) {
      const transfer = final.transferencia ? 'Sim (' + final.motivo + ')' : 'Não';
      card.appendChild(decisionLine('Equipe', null, transfer + (final.bloqueada ? ' · resposta de bloqueio' : ''),
        final.transferencia));
      const usage = final.uso;
      if (usage) {
        card.appendChild(decisionLine('Uso', null, usage.llm_calls + (usage.llm_calls === 1 ? ' chamada' : ' chamadas') +
          ' · ' + nf.format((usage.tokens || {}).total_tokens || 0) + ' tokens · ' + formatUsd(Number(usage.cost_usd)),
          false));
      }
    }
    card.addEventListener('click', () => selectTurn(turn.turno, false));
    return card;
  }

  function decisionLine(label, mode, text, warn) {
    const value = el('span');
    if (mode) value.appendChild(el('span', { class: 'badge-mode', text: mode }));
    value.appendChild(el('span', { class: warn ? 'warn' : '', text }));
    return el('div', { class: 'decision-row' }, [el('span', { text: label }), value]);
  }

  function guardrailsSummary(d) {
    if (d.modo === 'off') return 'desligado';
    if (d.origem === 'fallback') return 'falhou: a mensagem seguiu';
    const verdict = d.permitido ? 'passa' : 'bloqueio ' + (d.severidade === 'hard' ? 'duro' : 'leve') + ' · ' + d.categoria;
    const source = d.origem === 'detector' ? ' (regra ' + d.regra + ')' : ' (LLM)';
    const applied = !d.permitido && !d.aplicada ? ' · não aplicado' : '';
    const guided = d.aplicada && !d.permitido && d.severidade === 'soft';
    return verdict + source + applied + (guided ? ' · orientação ao agente' : '');
  }

  function routerSummary(d) {
    if (d.modo === 'off') return 'desligado: todas as ferramentas';
    if (d.origem === 'fallback') return 'falhou: todas as ferramentas';
    const confidence = d.confianca == null ? '' : ' (' + Math.round(d.confianca * 100) + '%)';
    const tools = d.ferramentas_liberadas == null
      ? 'todas as ferramentas' + (d.modo === 'shadow' ? ' (enforce: ' + (d.ferramentas_propostas.join(', ') || 'nenhuma') + ')' : '')
      : (d.ferramentas_liberadas.join(', ') || 'nenhuma ferramenta');
    return (d.intencoes || []).join(', ') + confidence + ' → ' + tools;
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
    document.querySelectorAll('.message.selected, .turn.selected, .decision-turn.selected')
      .forEach((n) => n.classList.remove('selected'));
    $('decision-' + number)?.classList.add('selected');
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

  // Os modelos vêm só do .env (LLM_MODEL e LLM_MODEL_*): a pílula mostra o do agente e, no título, o de
  // cada camada.
  function renderModelPill() {
    const llm = page.llm || {};
    const model = llm.erro ? 'LLM não configurado' : (llm.modelo || '—');
    const pill = $('pill-model');
    pill.textContent = model.split('/').pop();
    const stages = page.estagios || {};
    const layer = (stage, key) => ((stages[stage] || {}).modelo || model) + ' · ' +
      (settings[key] || (stages[stage] || {}).modo || '?');
    pill.title = llm.erro || ('Conversa: ' + model + '\nGuardrails: ' + layer('guardrails', 'guardrailsModo') +
      '\nRoteador: ' + layer('roteador', 'roteadorModo') + '\n(modelos definidos no .env)');
    pill.classList.toggle('simulated', !!(settings.guardrailsModo || settings.roteadorModo));
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

    // Estágios: controle segmentado (padrão do .env, off, shadow, enforce)
    const stages = page.estagios || { modos: [], guardrails: {}, roteador: {} };
    [['guardrails', 'guardrailsModo'], ['roteador', 'roteadorModo']]
      .forEach(([stage, modeKey]) => {
        const defaults = stages[stage] || {};
        const group = $('stage-' + stage + '-mode');
        const options = [['', 'padrão', 'Padrão do .env: ' + (defaults.modo || '?')]]
          .concat(stages.modos.map((m) => [m, m, null]));
        const sync = () => group.querySelectorAll('button').forEach((b) => {
          b.setAttribute('aria-checked', String(b.dataset.value === settings[modeKey]));
        });
        options.forEach(([value, label, title]) => group.appendChild(el('button', {
          type: 'button', role: 'radio', 'data-value': value, text: label, title,
          onclick: () => { settings[modeKey] = value; saveSettings(); sync(); renderModelPill(); },
        })));
        sync();
      });

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

    // Tema: alterna entre claro e escuro (começa pelo do sistema)
    $('theme-toggle').addEventListener('click', () => {
      const dark = settings.theme === 'auto' ? window.matchMedia('(prefers-color-scheme: dark)').matches
        : settings.theme === 'dark';
      settings.theme = dark ? 'light' : 'dark';
      saveSettings();
      applyDisplay();
    });

    // Cenários: um grupo aberto por vez; clicar põe a mensagem no campo de texto
    const scenarios = $('scenarios');
    page.cenarios.forEach((group, index) => {
      const box = el('details', { class: 'scenario-group', open: index === 0 ? '' : null }, [
        el('summary', { text: group.grupo }),
      ]);
      group.mensagens.forEach((text) => box.appendChild(el('button', {
        type: 'button', class: 'scenario', text, onclick: () => insertText(text),
      })));
      box.addEventListener('toggle', () => {
        if (box.open) document.querySelectorAll('.scenario-group').forEach((d) => { if (d !== box) d.open = false; });
      });
      scenarios.appendChild(box);
    });

    // Dados de teste
    if (!page.pedidos_teste.length) {
      $('test-data-section').hidden = true;
    } else {
      page.pedidos_teste.forEach((o) => $('test-orders').appendChild(el('button', {
        type: 'button', class: 'order', title: o.status + ' · ' + o.email,
        onclick: () => insertText('Pedido ' + o.numero + ', e-mail ' + o.email),
        text: '#' + o.numero,
      })));
    }

    // Conversas
    $('new-conversation').addEventListener('click', async () => {
      if (busy) return;
      const { ok, data } = await postJson(page.urls.nova, {}, { Accept: 'application/json' });
      if (ok) loadConversation(data.thread_id, [], [], []);
    });
    $('export-md').addEventListener('click', exportMarkdown);
  }

  function loadConversation(id, history, trace, decisions) {
    threadId = id;
    $('thread-id').textContent = id;
    turns = buildTurns(history, trace, decisions);
    selectedTurn = null;
    renderConversation();
    renderInspector();
    showView('chat');
  }

  function applyDisplay() {
    if (settings.theme === 'auto') document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme', settings.theme);
  }

  // ---------- Exportação ----------

  function exportMarkdown() {
    const model = (page.llm && page.llm.modelo) || '';
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
