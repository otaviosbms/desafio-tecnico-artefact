from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from conversation.snapshots import SNAPSHOTS


class SnapshotTests(TestCase):
    """Prompts e schemas que vão ao LLM são iguais aos de referência.

    Mudou de propósito? `python manage.py update_snapshots` e revise o diff antes do commit.
    """

    @classmethod
    def setUpTestData(cls):
        call_command('load_data', stdout=StringIO())  # o enum de categorias vem do banco

    def test_snapshots(self):
        for path, render in SNAPSHOTS.items():
            with self.subTest(snapshot=path.name, pacote=path.parent.parent.name):
                self.assertTrue(path.exists(), f'{path} não existe: rode update_snapshots.')
                self.assertEqual(render(), path.read_text(encoding='utf-8'))
