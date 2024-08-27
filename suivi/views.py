from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.http import HttpResponseForbidden
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView
from .models import Lot, Processus, LotProcessus, Message
from .forms import LotForm, ProcessForm, UploadFileForm, ReclamationForm
import pandas as pd
from .decorators import superviseur_required  # Importez votre décorateur personnalisé
from django.urls import reverse

@login_required
@superviseur_required
def index(request):
    if not request.user.groups.filter(name='Superviseur').exists():
        return redirect('login')  # Redirige vers la page de connexion si l'utilisateur n'est pas un superviseur

    lots = Lot.objects.all()
    processus = Processus.objects.all()
    data = []

    if request.method == 'POST':
        form = ProcessForm(request.POST)
        if form.is_valid():
            lot = form.cleaned_data['lot']
            processus = form.cleaned_data['processus']

            if 'start' in request.POST:
                previous_processus = Processus.objects.filter(id__lt=processus.id).order_by('-id').first()
                if previous_processus:
                    previous_lot_processus = LotProcessus.objects.filter(lot=lot, processus=previous_processus).first()
                    if previous_lot_processus and previous_lot_processus.temps_fin:
                        temps_debut = previous_lot_processus.temps_fin
                        messages.info(request, f"Le processus a commencé avec le temps de fin du processus précédent ({previous_processus.nom_proc}).")
                    else:
                        temps_debut = timezone.now()
                        messages.warning(request, "Le processus précédent n'est pas terminé. Démarrage avec le temps actuel.")
                else:
                    temps_debut = timezone.now()
                    messages.info(request, "Aucun processus précédent trouvé. Démarrage maintenant.")

                LotProcessus.objects.update_or_create(
                    lot=lot, processus=processus,
                    defaults={'temps_debut': temps_debut}
                )
                messages.success(request, f'Le processus "{processus.nom_proc}" a démarré pour le lot "{lot.ref}".')

            elif 'end' in request.POST:
                LotProcessus.objects.update_or_create(
                    lot=lot, processus=processus,
                    defaults={'temps_fin': timezone.now()}
                )
                messages.success(request, f'Le processus "{processus.nom_proc}" pour le lot "{lot.ref}" a été terminé.')

                next_processus = Processus.objects.filter(id__gt=processus.id).order_by('id').first()
                if next_processus:
                    LotProcessus.objects.update_or_create(
                        lot=lot, processus=next_processus,
                        defaults={'temps_debut': timezone.now()}
                    )
                    messages.success(request, f'Le processus suivant "{next_processus.nom_proc}" a démarré pour le lot "{lot.ref}".')
                else:
                    messages.info(request, f'Aucun processus suivant après "{processus.nom_proc}".')

            return redirect('index')

    else:
        form = ProcessForm()

    # Préparation des données pour l'affichage
    for lot in lots:
        processus_data = []
        tp1 = None
        tp2 = None

        process_ids = {proc.id: proc for proc in processus}

        for proc in processus:
            lot_proc = LotProcessus.objects.filter(lot=lot, processus=proc).first()
            debut = lot_proc.temps_debut if lot_proc else None
            fin = lot_proc.temps_fin if lot_proc else None
            temps_pris = None

            if debut and fin:
                delta = fin - debut
                temps_pris = int(delta.total_seconds() // 60)

            processus_data.append({
                'processus': proc,
                'debut': debut,
                'fin': fin,
                'temps_pris': temps_pris
            })

        # Calcul TP1
        debut_proc_1 = next((p['debut'] for p in processus_data if p['processus'].id == 1), None)
        fin_proc_6 = next((p['fin'] for p in processus_data if p['processus'].id == 6), None)
        if debut_proc_1 and fin_proc_6:
            tp1 = (fin_proc_6 - debut_proc_1).total_seconds() / (24 * 3600)  # Convertir en jours
            tp1 = round(tp1, 1)  # Arrondi à 1 chiffre après la virgule

        # Calcul TP2
        debut_proc_7 = next((p['debut'] for p in processus_data if p['processus'].id == 7), None)
        fin_proc_8 = next((p['fin'] for p in processus_data if p['processus'].id == 8), None)
        if debut_proc_7 and fin_proc_8:
            tp2 = (fin_proc_8 - debut_proc_7).total_seconds() / (24 * 3600)  # Convertir en jours
            tp2 = round(tp2, 1)  # Arrondi à 1 chiffre après la virgule

        data.append({
            'lot': lot,
            'processus': processus_data,
            'tp1': tp1 if tp1 is not None else "-",
            'tp2': tp2 if tp2 is not None else "-"
        })

    return render(request, 'index.html', {'data': data, 'form': form})

@login_required
@superviseur_required
def add_lot(request):
    if request.method == 'POST':
        form = LotForm(request.POST)
        if form.is_valid():
            # Enregistre les données du formulaire dans la base de données
            new_lot = form.save()

            try:
                planning_input_processus = Processus.objects.get(nom_proc='Planning input')
            except Processus.DoesNotExist:
                messages.error(request, 'Le processus "Planning input" n\'existe pas.')
                return redirect('add_lot')

            current_time = timezone.now()

            # Créer une instance de LotProcessus pour "Planning input"
            LotProcessus.objects.create(
                lot=new_lot,
                processus=planning_input_processus,
                temps_debut=current_time,
                temps_fin=current_time
            )

            # Trouver le processus suivant dans la séquence
            next_processus = Processus.objects.filter(id__gt=planning_input_processus.id).order_by('id').first()

            if next_processus:
                # Mettre à jour le temps de début du processus suivant avec le temps de fin du processus actuel
                LotProcessus.objects.create(
                    lot=new_lot,
                    processus=next_processus,
                    temps_debut=current_time,
                    temps_fin=None  # Le temps de fin du processus suivant est encore indéfini
                )

            messages.success(request, 'Le lot a été ajouté avec succès.')
            return redirect('index')
    else:
        form = LotForm()
    return render(request, 'add_lot.html', {'form': form})

@login_required
@superviseur_required
def upload_lots(request):
    if request.method == 'POST':
        file = request.FILES.get('file')
        if file:
            try:
                df = pd.read_excel(file)
                print(f"Colonnes du fichier Excel : {df.columns.tolist()}")
                print(f"Fichier lu avec succès. {df.shape[0]} lignes trouvées.")
                print("Aperçu des données lues:")
                print(df.head())
            except Exception as e:
                messages.error(request, f'Erreur lors de la lecture du fichier : {str(e)}')
                print(f'Erreur lors de la lecture du fichier : {str(e)}')
                return redirect('upload_lots')

            try:
                planning_input_processus = Processus.objects.get(nom_proc='Planning input')
                print(f'Processus "Planning input" trouvé: {planning_input_processus}')
            except Processus.DoesNotExist:
                messages.error(request, 'Le processus "Planning input" n\'existe pas.')
                print('Le processus "Planning input" n\'existe pas.')
                return redirect('upload_lots')

            current_time = timezone.now()
            success_count = 0
            failure_count = 0
            
            for _, row in df.iterrows():
                week = row.get('week')
                projet = row.get('Projet')
                ref = row.get('Référence')
                type_lot = row.get('Types')
                planificateur = row.get('Plannificateur')
                epn = row.get('EPN')
                cpn = row.get('CPN')
                quantite = row.get('quantite')

                # Affichage pour débogage
                print(f"Traitement de la ligne: week={week}, projet={projet}, ref={ref}, type_lot={type_lot}, planificateur={planificateur}, EPN={epn}, CPN={cpn}, quantite={quantite}")

                if ref and quantite is not None:
                    try:
                        lot, created = Lot.objects.update_or_create(
                            ref=ref,
                            defaults={
                                'week': week,  # Ajout de la semaine
                                'quantite': quantite,
                                'epn': epn,
                                'cpn': cpn,
                                'planificateur': planificateur,
                                'projet': projet,  # Assurez-vous que le champ 'projet' est bien défini dans votre modèle
                                'type': type_lot  # Assurez-vous que le champ 'type' est bien défini dans votre modèle
                            }
                        )
                        if created:
                            print(f"Nouveau lot créé: {lot}")
                            LotProcessus.objects.create(
                                lot=lot,
                                processus=planning_input_processus,
                                temps_debut=current_time,
                                temps_fin=current_time
                            )
                            # Gestion du processus suivant
                            current_lot_processus = LotProcessus.objects.get(lot=lot, processus=planning_input_processus)
                            next_processus = Processus.objects.filter(id__gt=planning_input_processus.id).order_by('id').first()
                            
                            if next_processus:
                                print(f"Processus suivant trouvé: {next_processus}")
                                LotProcessus.objects.update_or_create(
                                    lot=lot,
                                    processus=next_processus,
                                    defaults={'temps_debut': current_lot_processus.temps_fin}
                                )
                                messages.success(request, f'Le processus suivant "{next_processus.nom_proc}" pour le lot "{lot.ref}" a été démarré automatiquement.')
                            else:
                                messages.info(request, f'Aucun processus suivant après "{planning_input_processus.nom_proc}" pour le lot "{lot.ref}".')

                        success_count += 1
                    except Exception as e:
                        messages.error(request, f'Erreur lors de l\'importation de la référence {ref}: {str(e)}')
                        print(f'Erreur lors de l\'importation de la référence {ref}: {str(e)}')
                        failure_count += 1

            if success_count > 0:
                messages.success(request, f'Les lots ont été importés avec succès. ({success_count} ajoutés)')
            if failure_count > 0:
                messages.error(request, f'{failure_count} erreurs lors de l\'importation.')

            return redirect('index')
        else:
            messages.error(request, 'Aucun fichier n\'a été téléchargé.')
            print('Aucun fichier n\'a été téléchargé.')

    return render(request, 'upload_lots.html')

def start_process(request, lot_ref, processus_id):
    if request.method == 'POST':
        lot = get_object_or_404(Lot, ref=lot_ref)
        processus = get_object_or_404(Processus, id=processus_id)
        
        # Chercher le processus précédent
        previous_processus = Processus.objects.filter(id__lt=processus.id).order_by('-id').first()
        
        # Si un processus précédent existe
        if previous_processus:
            # Récupérer le LotProcessus associé au processus précédent
            previous_lot_processus = LotProcessus.objects.filter(lot=lot, processus=previous_processus).first()

            # Vérifier si le processus précédent est bien terminé
            if previous_lot_processus and previous_lot_processus.temps_fin:
                temps_debut = previous_lot_processus.temps_fin
                messages.info(request, f"Le temps de début du processus actuel est basé sur la fin du processus précédent ({previous_processus.nom_proc}).")
            else:
                # Si le processus précédent n'est pas terminé ou n'existe pas, utiliser l'heure actuelle
                temps_debut = timezone.now()
                messages.warning(request, f"Le processus précédent n'est pas encore terminé. Utilisation du temps actuel pour le début.")
        else:
            # S'il n'y a pas de processus précédent, démarrer avec l'heure actuelle
            temps_debut = timezone.now()
            messages.info(request, f"Pas de processus précédent trouvé. Le processus démarre maintenant.")

        # Créer ou mettre à jour l'entrée LotProcessus pour le processus actuel
        LotProcessus.objects.update_or_create(
            lot=lot, processus=processus,
            defaults={'temps_debut': temps_debut}
        )

        messages.success(request, f'Le processus "{processus.nom_proc}" a commencé pour le lot "{lot.ref}".')
        return redirect('index')

    return HttpResponseForbidden()


def end_process(request, lot_ref, processus_id):
    if request.method == 'POST':
        # Récupérer le lot et le processus actuel
        lot = get_object_or_404(Lot, ref=lot_ref)
        processus = get_object_or_404(Processus, id=processus_id)

        # Terminer le processus en mettant à jour le temps de fin
        lot_processus, created = LotProcessus.objects.update_or_create(
            lot=lot, processus=processus,
            defaults={'temps_fin': timezone.now()}
        )

        messages.success(request, f'Le processus "{processus.nom_proc}" pour le lot "{lot.ref}" a été terminé.')

        # Récupérer le processus suivant
        next_processus = Processus.objects.filter(id__gt=processus.id).order_by('id').first()

        if next_processus:
            # Démarrer le processus suivant avec le temps de fin du processus actuel comme début
            LotProcessus.objects.update_or_create(
                lot=lot,
                processus=next_processus,
                defaults={'temps_debut': lot_processus.temps_fin}
            )

            messages.success(request, f'Le processus suivant "{next_processus.nom_proc}" pour le lot "{lot.ref}" a démarré avec un début à {lot_processus.temps_fin}.')

        else:
            messages.info(request, f'Aucun processus suivant après "{processus.nom_proc}" pour le lot "{lot.ref}".')

        return redirect('index')

    return HttpResponseForbidden()


@login_required
def reclamer_lot(request):
    if request.method == 'POST':
        form = ReclamationForm(request.POST)
        if form.is_valid():
            lot_number = form.cleaned_data['lot']
            processus = form.cleaned_data['processus']
            le_message = form.cleaned_data['le_message']
            responsable = form.cleaned_data['responsable']
            
            # Vérifier si le lot existe
            try:
                lot_instance = Lot.objects.get(ref=lot_number)
            except Lot.DoesNotExist:
                messages.error(request, 'Numéro de lot erroné')
                return render(request, 'reclamer_lot.html', {'form': form})
            
            # Créer et sauvegarder l'objet Message
            Message.objects.create(
                lot=lot_instance,
                processus=processus,
                temps_reclamation=timezone.now(),
                le_message=le_message,
                responsable=responsable
            )
            
            messages.success(request, 'La réclamation a été enregistrée avec succès.')

            # Déterminer la redirection basée sur le groupe de l'utilisateur
            if request.user.groups.filter(name='Superviseur').exists():
                return redirect('index')
            elif request.user.groups.filter(name='Operateur').exists():
                return redirect('operateur_page')
            else:
                return redirect('index')  # Redirection par défaut si aucun groupe ne correspond
    else:
        form = ReclamationForm()

    return render(request, 'reclamer_lot.html', {'form': form})
def lot_messages(request, lot_ref):
    lot = get_object_or_404(Lot, ref=lot_ref)
    messages_list = Message.objects.filter(lot=lot).order_by('-temps_reclamation')
    return render(request, 'lot_messages.html', {
        'lot': lot,
        'messages': messages_list
    })

# Connexion et déconnexion

class CustomLoginView(LoginView):
    template_name = 'login.html'

    def form_valid(self, form):
        # Récupérer l'utilisateur après validation du formulaire
        user = form.get_user()

        # Connecter l'utilisateur
        login(self.request, user)

        # Redirection basée sur les groupes de l'utilisateur
        if user.groups.filter(name='Superviseur').exists():
            return redirect('index')
        elif user.groups.filter(name='Operateur').exists():
            return redirect('operateur_page')

        # Si l'utilisateur ne correspond à aucun groupe spécifique
        return redirect('login')

def user_logout(request):
    logout(request)
    return redirect('login')

@login_required
def upload_lots_from_file(request):
    if request.method == 'POST':
        file = request.FILES.get('file')
        processus_id = request.POST.get('processus')

        if not processus_id:
            messages.error(request, 'Le processus doit être sélectionné.')
            return redirect('operateur_page')

        try:
            processus = Processus.objects.get(id=processus_id)
        except Processus.DoesNotExist:
            messages.error(request, 'Le processus sélectionné n\'existe pas.')
            return redirect('operateur_page')

        if file:
            try:
                # Lire le fichier Excel
                df = pd.read_excel(file)

                # Afficher les colonnes pour débogage
                print("Excel file loaded successfully")
                print("Columns in the DataFrame:", df.columns)

                # Adapter la lecture des références
                # Si les en-têtes existent, utilisez leur nom
                if 'Référence' in df.columns:
                    ref_column = 'Référence'
                else:
                    # Sinon, utilisez l'index (index 1 correspond à la colonne B si zéro-indexé)
                    ref_column = df.columns[1]  # Assumant que la colonne B est à l'index 1

                current_time = timezone.now()
                success_count = 0
                failure_count = 0

                for _, row in df.iterrows():
                    ref = row.get(ref_column)
                    print(f"Processing row with reference: {ref}")  # Affiche la référence du lot
                    if ref:
                        try:
                            lot, created = Lot.objects.get_or_create(ref=ref)
                            lot_processus, created = LotProcessus.objects.get_or_create(
                                lot=lot,
                                processus=processus
                            )
                            print(f"LotProcessus entry for lot {lot.ref}: created={created}, temps_debut={lot_processus.temps_debut}, temps_fin={lot_processus.temps_fin}")

                            if created:
                                lot_processus.temps_debut = current_time
                                lot_processus.temps_fin = current_time
                                lot_processus.save()
                                print(f"Lot {lot.ref} started and ended.")
                            else:
                                if not lot_processus.temps_debut and not lot_processus.temps_fin:
                                    lot_processus.temps_debut = current_time
                                    lot_processus.save()
                                    print(f"Lot {lot.ref} started.")
                                elif lot_processus.temps_debut and not lot_processus.temps_fin:
                                    lot_processus.temps_fin = current_time
                                    lot_processus.save()
                                    next_processus = Processus.objects.filter(id__gt=processus.id).order_by('id').first()
                                    if next_processus:
                                        LotProcessus.objects.update_or_create(
                                            lot=lot,
                                            processus=next_processus,
                                            defaults={'temps_debut': lot_processus.temps_fin}
                                        )
                                        print(f"Lot {lot.ref} process finished, next process started.")
                                    else:
                                        print(f"No subsequent process found for lot {lot.ref}.")
                                else:
                                    print(f"Lot {lot.ref} already processed.")
                            
                            success_count += 1
                        except Exception as e:
                            messages.error(request, f'Erreur lors de l\'importation de la référence {ref}: {str(e)}')
                            failure_count += 1

                if success_count > 0:
                    messages.success(request, f'Les lots ont été confirmés avec succès. ({success_count} confirmés)')
                if failure_count > 0:
                    messages.error(request, f'{failure_count} erreurs lors de la confirmation.')

                return redirect('operateur_page')
            except Exception as e:
                messages.error(request, f'Erreur lors de la lecture du fichier : {str(e)}')
                return redirect('operateur_page')
        else:
            messages.error(request, 'Aucun fichier n\'a été téléchargé.')

    return redirect('operateur_page')


@login_required
def operateur_page(request):
    if not request.user.groups.filter(name='Operateur').exists():
        return redirect('login')

    lots = Lot.objects.all()
    processus = Processus.objects.all()

    if request.method == 'POST':
        form = ProcessForm(request.POST)
        if form.is_valid():
            lot = form.cleaned_data.get('lot')
            processus = form.cleaned_data.get('processus')

            if lot and processus:
                try:
                    lot_processus_instance, created = LotProcessus.objects.get_or_create(
                        lot=lot,
                        processus=processus
                    )

                    if not lot_processus_instance.temps_debut:
                        lot_processus_instance.temps_debut = timezone.now()
                        lot_processus_instance.save()
                        messages.success(request, 'Processus démarré avec succès.')
                    elif lot_processus_instance.temps_debut and not lot_processus_instance.temps_fin:
                        lot_processus_instance.temps_fin = timezone.now()
                        lot_processus_instance.save()

                        next_processus = Processus.objects.filter(id__gt=processus.id).order_by('id').first()
                        if next_processus:
                            LotProcessus.objects.update_or_create(
                                lot=lot,
                                processus=next_processus,
                                defaults={'temps_debut': lot_processus_instance.temps_fin}
                            )
                            messages.success(request, 'Processus terminé et processus suivant démarré.')
                        else:
                            messages.info(request, 'Le processus est terminé mais aucun processus suivant n\'a été trouvé.')
                    else:
                        messages.warning(request, 'Le processus est déjà terminé.')

                except Exception as e:
                    messages.error(request, f'Une erreur est survenue : {str(e)}')

            else:
                messages.error(request, 'Veuillez entrer une référence de lot et un ID de processus.')

        else:
            messages.error(request, 'Données du formulaire invalides.')

        return redirect('operateur_page')

    else:
        form = ProcessForm()

    return render(request, 'operateur_page.html', {
        'lots': lots,
        'processus': processus,
        'form': form
    })