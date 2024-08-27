from django.contrib import admin
from .models import Lot, Processus, LotProcessus, Message

@admin.register(Lot)
class LotAdmin(admin.ModelAdmin):
    list_display = ('ref', 'quantite', 'epn', 'cpn', 'planificateur', 'projet', 'type')
    search_fields = ('ref', 'epn', 'cpn', 'planificateur', 'projet', 'type')
    list_filter = ('projet', 'type')
    ordering = ('ref',)

@admin.register(Processus)
class ProcessusAdmin(admin.ModelAdmin):
    list_display = ('id', 'nom_proc', 'responsable', 'duree')
    search_fields = ('nom_proc', 'responsable')
    ordering = ('id',)

@admin.register(LotProcessus)
class LotProcessusAdmin(admin.ModelAdmin):
    list_display = ('lot', 'processus', 'temps_debut', 'temps_fin')
    search_fields = ('lot__ref', 'processus__nom_proc')
    list_filter = ('processus',)
    ordering = ('lot', 'processus')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('lot', 'processus', 'temps_reclamation', 'le_message', 'responsable')
    search_fields = ('lot__ref', 'processus__nom_proc', 'le_message', 'responsable')
    list_filter = ('processus', 'responsable')
    ordering = ('lot', 'processus', 'temps_reclamation')
