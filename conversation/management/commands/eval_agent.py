"""Avalia o agente de ponta a ponta contra perguntas com verificações simples (evals/agent.jsonl).

Cada caso é uma conversa (uma ou mais mensagens). Na última resposta, verifica:
- `ferramentas`: ferramentas que precisam ter sido chamadas na conversa (um item pode ser uma lista
  de alternativas, ex.: ["detalhes_produto", "buscar_produtos"]);
- `proibidas`: ferramentas que não podem ter sido chamadas;
- `contem` / `nao_contem`: expressões regulares (sem diferenciar maiúsculas) na última resposta.

Usa o LLM real e o pipeline completo; o histórico fica em memória (não suja as conversas salvas).
"""

import json
import re
import time
from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.utils import timezone
from langgraph.checkpoint.memory import InMemorySaver

from conversation.graph import FALLBACK_REPLY
from conversation.orchestrator import ConversationOrchestrator, TurnOptions
from core import clock

DEFAULT_DATASET = settings.BASE_DIR / 'evals' / 'agent.jsonl'
DEFAULT_REPORTS = settings.BASE_DIR / 'evals' / 'reports'


def load_cases(path: Path) -> list[dict]:
    cases = [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]
    for case in cases:
        if not case.get('mensagens'):
            raise ValueError(f'{case.get("id")}: caso sem mensagens.')
        for pattern in case.get('contem', []) + case.get('nao_contem', []):
            re.compile(pattern)
    return cases


def check(case: dict, reply: str, tools_called: list[str]) -> list[str]:
    """Falhas do caso (lista vazia = passou)."""
    failures = []
    called = set(tools_called)
    for expected in case.get('ferramentas', []):
        options = expected if isinstance(expected, list) else [expected]
        if not called & set(options):
            failures.append(f'não chamou {" ou ".join(options)}')
    for forbidden in case.get('proibidas', []):
        if forbidden in called:
            failures.append(f'chamou {forbidden} (proibida)')
    for pattern in case.get('contem', []):
        if not re.search(pattern, reply, re.IGNORECASE):
            failures.append(f'resposta sem /{pattern}/')
    for pattern in case.get('nao_contem', []):
        if re.search(pattern, reply, re.IGNORECASE):
            failures.append(f'resposta com /{pattern}/')
    if reply == FALLBACK_REPLY:
        failures.append('resposta de contingência (falha do LLM)')
    return failures


def build_orchestrator(router_mode: str | None, guardrails_mode: str | None) -> ConversationOrchestrator:
    return ConversationOrchestrator(checkpointer=InMemorySaver(), router_mode=router_mode,
                                    guardrails_mode=guardrails_mode)


class Command(BaseCommand):
    help = 'Avalia o agente de ponta a ponta com o LLM real (evals/agent.jsonl).'

    def add_arguments(self, parser):
        parser.add_argument('--dataset', default=DEFAULT_DATASET)
        parser.add_argument('--ids', nargs='*', help='Só estes casos.')
        parser.add_argument('--limit', type=int, help='Só os N primeiros casos (economiza cota).')
        parser.add_argument('--router-mode', choices=['off', 'shadow', 'enforce'], help='Padrão: o do .env.')
        parser.add_argument('--guardrails-mode', choices=['off', 'shadow', 'enforce'], help='Padrão: o do .env.')
        parser.add_argument('--report', action='store_true', help='Grava um relatório em evals/reports/.')
        parser.add_argument('--reports-dir', default=DEFAULT_REPORTS, help='Pasta dos relatórios.')

    def handle(self, *args, dataset, ids, limit, router_mode, guardrails_mode, report, reports_dir, **options):
        cases = load_cases(dataset)
        if ids:
            cases = [c for c in cases if c['id'] in ids]
        cases = cases[:limit] if limit else cases
        if not cases:
            raise CommandError('Nenhum caso selecionado.')

        orchestrator = build_orchestrator(router_mode, guardrails_mode)
        modes = f'guardrails={orchestrator.guardrails.mode} roteador={orchestrator.router.mode}'
        self.stdout.write(f'Agente: {orchestrator.model} · {modes} · {len(cases)} casos\n')

        rows = []
        for case in cases:
            thread = f'eval-{case["id"]}-{time.time_ns()}'
            options = TurnOptions(now=clock.parse(case.get('agora')))
            start = time.perf_counter()
            tools_called, result = [], None
            for message in case['mensagens']:
                result = orchestrator.run_turn(thread, message, options)
                tools_called += [call['nome'] for call in result.tool_calls]
            failures = check(case, result.text, tools_called)
            rows.append({**case, 'resposta': result.text, 'chamadas': tools_called, 'falhas': failures,
                         'custo': result.usage.get('cost_usd', '0'), 'segundos': round(time.perf_counter() - start, 1)})
            mark = self.style.SUCCESS('ok  ') if not failures else self.style.ERROR('ERRO')
            detail = '' if not failures else ' · ' + '; '.join(failures)
            self.stdout.write(f'{mark} {case["id"]:<12} ferramentas={",".join(tools_called) or "-"}{detail}')

        passed = sum(not r['falhas'] for r in rows)
        summary = f'\nPassaram: {passed}/{len(rows)}'
        self.stdout.write(self.style.SUCCESS(summary) if passed == len(rows) else self.style.ERROR(summary))
        if report:
            path = self._write_report(Path(reports_dir), rows, orchestrator.model, modes, passed)
            self.stdout.write(f'Relatório: {path}')

    def _write_report(self, folder: Path, rows, model, modes, passed) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        now = timezone.localtime()
        path = folder / f'agent-{now:%Y%m%d-%H%M%S}.md'
        lines = [
            f'# eval_agent · {now:%d/%m/%Y %H:%M}', '',
            f'- Modelo do agente: `{model}` · {modes}',
            f'- Passaram: **{passed}/{len(rows)}**', '',
            '| Caso | Ferramentas chamadas | Resultado | Tempo |', '|---|---|---|---|',
        ]
        for r in rows:
            result = '✔' if not r['falhas'] else '✘ ' + '; '.join(r['falhas'])
            lines.append(f'| {r["id"]} | {", ".join(r["chamadas"]) or "—"} | {result} | {r["segundos"]}s |')
        lines += ['', '## Respostas', '']
        for r in rows:
            lines += [f'### {r["id"]}', '']
            lines += [f'> **Cliente:** {message}' for message in r['mensagens']]
            lines += ['', r['resposta'].strip(), '']
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        return path
