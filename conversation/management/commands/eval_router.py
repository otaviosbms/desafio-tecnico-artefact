"""Avalia o roteador de intenção contra mensagens rotuladas (evals/router.jsonl).

Cada caso tem as intenções esperadas e, quando a mensagem é ambígua, `alternativas` também
aceitas. Métricas:
- **acerto:** o conjunto de intenções previsto é igual ao esperado ou a uma alternativa;
- **cobertura:** as ferramentas liberadas incluem todas as que o caso precisa (o agente não fica
  sem a ferramenta certa, mesmo que a intenção não bata exatamente).

Falhas do roteador (fail-open) contam como erro: liberam tudo, mas não classificaram.
"""

import json
import time
from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.utils import timezone

from llm import LLMService
from router.intents import Intent, tools_for
from router.service import ENFORCE, IntentRouter

DEFAULT_DATASET = settings.BASE_DIR / 'evals' / 'router.jsonl'


def load_cases(path: Path) -> list[dict]:
    cases = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    for case in cases:
        for option in [case['intencoes'], *case.get('alternativas', [])]:
            for intent in option:
                Intent(intent)  # rótulo inválido no dataset = erro já na leitura
    return cases


def score(case: dict, predicted: list[str]) -> dict:
    options = [case['intencoes'], *case.get('alternativas', [])]
    granted = set(tools_for([Intent(i) for i in predicted]))
    return {
        'acerto': any(set(predicted) == set(option) for option in options),
        'cobertura': any(set(tools_for([Intent(i) for i in option])) <= granted for option in options),
    }


class Command(BaseCommand):
    help = 'Mede a acurácia do roteador de intenção (chama o LLM do papel router).'

    def add_arguments(self, parser):
        parser.add_argument('--dataset', default=DEFAULT_DATASET)
        parser.add_argument('--ids', nargs='*', help='Só estes casos.')
        parser.add_argument('--limit', type=int, help='Só os N primeiros casos (economiza cota).')
        parser.add_argument('--min', dest='min_accuracy', type=float, default=0.85, help='Acerto mínimo (padrão 0.85); abaixo, sai com erro.')
        parser.add_argument('--report', action='store_true', help='Grava um relatório em evals/reports/.')

    def handle(self, *args, dataset, ids, limit, min_accuracy, report, **options):
        cases = load_cases(Path(dataset))
        if ids:
            cases = [c for c in cases if c['id'] in ids]
        cases = cases[:limit] if limit else cases
        if not cases:
            raise CommandError('Nenhum caso selecionado.')

        service = LLMService()
        router = IntentRouter(service, mode=ENFORCE)
        model = service.client_for('router').config.model
        self.stdout.write(f'Roteador: {model} · {len(cases)} casos\n')

        rows = []
        for case in cases:
            start = time.perf_counter()
            decision = router.classify(case['mensagem'], case.get('ultima_resposta'))
            elapsed = time.perf_counter() - start
            failed = decision.source == 'fallback'
            result = {'acerto': False, 'cobertura': False} if failed else score(case, decision.intents)
            rows.append({**case, **result, 'previsto': decision.intents, 'origem': decision.source,
                         'confianca': decision.confidence, 'segundos': round(elapsed, 1)})
            mark = self.style.SUCCESS('ok  ') if result['acerto'] else self.style.ERROR('ERRO')
            predicted = 'FALHOU (fail-open)' if failed else ', '.join(decision.intents)
            self.stdout.write(f'{mark} {case["id"]:<8} esperado={",".join(case["intencoes"]):<28} '
                              f'previsto={predicted:<28} {elapsed:5.1f}s  {case["mensagem"][:50]}')

        total = len(rows)
        accuracy = sum(r['acerto'] for r in rows) / total
        coverage = sum(r['cobertura'] for r in rows) / total
        failures = sum(r['origem'] == 'fallback' for r in rows)
        summary = (f'\nAcerto: {accuracy:.0%} · Cobertura de ferramentas: {coverage:.0%} · '
                   f'Falhas do LLM: {failures} · Meta de acerto: {min_accuracy:.0%}')
        self.stdout.write(self.style.SUCCESS(summary) if accuracy >= min_accuracy else self.style.ERROR(summary))

        if report:
            path = self._write_report(rows, model, accuracy, coverage, failures)
            self.stdout.write(f'Relatório: {path}')
        if accuracy < min_accuracy:
            raise CommandError(f'Acerto {accuracy:.0%} abaixo da meta de {min_accuracy:.0%}.')

    def _write_report(self, rows, model, accuracy, coverage, failures) -> Path:
        folder = settings.BASE_DIR / 'evals' / 'reports'
        folder.mkdir(parents=True, exist_ok=True)
        now = timezone.localtime()
        path = folder / f'router-{now:%Y%m%d-%H%M%S}.md'
        lines = [
            f'# eval_router · {now:%d/%m/%Y %H:%M}',
            '',
            f'- Modelo: `{model}`',
            f'- Casos: {len(rows)} · Acerto: **{accuracy:.0%}** · Cobertura de ferramentas: {coverage:.0%} · '
            f'Falhas do LLM: {failures}',
            '',
            '| Caso | Esperado | Previsto | Confiança | Acerto | Cobertura | Tempo |',
            '|---|---|---|---|---|---|---|',
        ]
        for r in rows:
            predicted = 'falhou' if r['origem'] == 'fallback' else ', '.join(r['previsto'])
            confidence = '' if r['confianca'] is None else f'{r["confianca"]:.2f}'
            lines.append(f'| {r["id"]} | {", ".join(r["intencoes"])} | {predicted} | {confidence} | '
                         f'{"✔" if r["acerto"] else "✘"} | {"✔" if r["cobertura"] else "✘"} | {r["segundos"]}s |')
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        return path
