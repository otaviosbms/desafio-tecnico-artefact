import uuid

from django.core.management import BaseCommand

from agent.service import get_agent


class Command(BaseCommand):
    help = 'Conversa com o agente de atendimento pelo terminal.'

    def add_arguments(self, parser):
        parser.add_argument('--thread', help='Id da conversa (retoma o histórico). Padrão: nova conversa.')
        parser.add_argument('-m', '--message', action='append', default=[],
                            help='Envia esta mensagem e sai (pode repetir para uma conversa roteirizada).')
        parser.add_argument('--show-tools', action='store_true', help='Mostra as ferramentas chamadas.')

    def handle(self, *args, thread, message, show_tools, **options):
        thread = thread or f'cli-{uuid.uuid4().hex[:8]}'
        agent = get_agent()
        self.stdout.write(self.style.NOTICE(f'Conversa: {thread}  (Ctrl+C ou "sair" para encerrar)\n'))

        def send(text):
            self.stdout.write(f'Você: {text}')
            reply = agent.reply(thread, text)
            if show_tools:
                for call in reply.tool_calls:
                    self.stdout.write(self.style.WARNING(f'  [ferramenta] {call["nome"]} {call["argumentos"]}'))
            self.stdout.write(self.style.SUCCESS('Empório: ') + reply.text + '\n')

        if message:
            for text in message:
                send(text)
            return

        try:
            while True:
                text = input('> ').strip()
                if text.lower() in {'sair', 'exit', 'quit'}:
                    break
                if text:
                    send(text)
        except (KeyboardInterrupt, EOFError):
            self.stdout.write('')
