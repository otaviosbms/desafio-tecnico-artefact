from django.urls import path

from . import views

app_name = 'agent'

urlpatterns = [
    path('', views.chat, name='chat'),
    path('nova-conversa/', views.new_conversation, name='new_conversation'),
    path('api/mensagem/', views.send_message, name='send_message'),
]
