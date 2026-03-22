from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('get_agents/', views.get_agents, name='get_agents'),
    path('randomize_agents/', views.randomize_agents, name='randomize_agents'),

]