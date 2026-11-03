from django.core.management import BaseCommand

from conversation.snapshots import SNAPSHOTS, write_all


class Command(BaseCommand):
    help = 'Regenera os snapshots de prompts e schemas (depois de uma mudança feita de propósito).'

    def handle(self, *args, **options):
        changed = write_all()
        for path in changed:
            self.stdout.write(self.style.WARNING(f'atualizado: {path}'))
        self.stdout.write(f'{len(changed)} de {len(SNAPSHOTS)} snapshots mudaram. Revise o diff antes do commit.')
