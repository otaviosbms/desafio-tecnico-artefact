"""Regra de camadas: um pacote só importa os pacotes abaixo dele.

    conversation ──► guardrails, router ──► llm ──► core
         │       ──► tools ──► store, knowledge ──► core

Testes (`tests.py`) e comandos de gerenciamento ficam de fora: podem montar o sistema inteiro.
"""

import ast
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

PROJECT = {'core', 'llm', 'store', 'knowledge', 'tools', 'router', 'guardrails', 'conversation', 'config'}

# pacote -> pacotes do projeto que ele pode importar
ALLOWED = {
    'core': set(),
    'llm': {'core'},
    'store': {'core'},
    'knowledge': {'core', 'store'},
    'tools': {'core', 'llm', 'store', 'knowledge'},
    'router': {'core', 'llm'},
    'guardrails': {'core', 'llm'},
    'conversation': {'core', 'llm', 'store', 'knowledge', 'tools', 'router', 'guardrails'},
}


def project_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        else:
            continue
        found |= {name.split('.')[0] for name in names} & PROJECT
    return found


def source_files(package: str):
    for path in (Path(settings.BASE_DIR) / package).rglob('*.py'):
        parts = path.relative_to(settings.BASE_DIR).parts
        if path.name == 'tests.py' or 'management' in parts or 'migrations' in parts:
            continue
        yield path


class LayersTests(SimpleTestCase):
    def test_cada_pacote_so_importa_camadas_abaixo(self):
        violations = []
        for package, allowed in ALLOWED.items():
            for path in source_files(package):
                for imported in project_imports(path) - allowed - {package}:
                    violations.append(f'{path.relative_to(settings.BASE_DIR)} importa {imported}')
        self.assertEqual(violations, [])

    def test_leitura_dos_imports(self):
        # Sanidade do próprio teste: imports relativos não contam; absolutos do projeto, sim.
        sample = Path(settings.BASE_DIR) / 'core' / 'logging.py'
        self.assertEqual(project_imports(sample), set())
        self.assertIn('llm', project_imports(Path(settings.BASE_DIR) / 'router' / 'service.py'))
