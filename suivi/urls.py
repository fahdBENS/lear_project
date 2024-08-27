from django.urls import path
from . import views
from .views import CustomLoginView, operateur_page, start_process, end_process, reclamer_lot, lot_messages, user_logout, upload_lots_from_file, add_lot, upload_lots

urlpatterns = [
    path('', CustomLoginView.as_view(), name='login'),  # Page de connexion
    path('index/', views.index, name='index'),
    path('add_lot/', views.add_lot, name='add_lot'),
    path('upload_lots/', views.upload_lots, name='upload_lots'),
    path('reclamer_lot/', views.reclamer_lot, name='reclamer_lot'),
    path('lot_messages/<str:lot_ref>/', views.lot_messages, name='lot_messages'),
    path('start_process/<str:lot_ref>/<int:processus_id>/', views.start_process, name='start_process'),
    path('end_process/<str:lot_ref>/<int:processus_id>/', views.end_process, name='end_process'),
    path('operateur/', operateur_page, name='operateur_page'),
    path('logout/', views.user_logout, name='logout'),  # Déconnexion
    path('upload_lots_from_file/', views.upload_lots_from_file, name='upload_lots_from_file'),
]
