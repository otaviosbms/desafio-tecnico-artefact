from django.apps import AppConfig


class ToolsConfig(AppConfig):
    name = 'tools'
    verbose_name = 'Ferramentas do agente'

    def ready(self):
        from . import registry
        from .handlers import TOOLS

        for handler in TOOLS:
            registry.register_tool(handler)
