from flask import Flask, redirect, render_template, url_for, make_response, session, request, send_from_directory
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, ServerSelectionTimeoutError, PyMongoError
from bson import ObjectId
from datetime import datetime
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)

# Configuration du dossier d'uploads
app.config['UPLOAD_FOLDER'] = 'static'

# Clé secrète pour les sessions
app.secret_key = "location_voiture"

# Connexion à MongoDB
client = MongoClient("mongodb://localhost:27017/")
database = client["location"]
reservations_collection = database["reservations"]
voitures_collection = database["voiture"]
utilisateur_collection = database["utilisateur"]
client_collection = database["clients"]

# Route pour la page d'accueil
@app.route('/')
def home_page():
    return render_template('first.htm')

# Route pour accepter une réservation
@app.route('/accepter_reservation/<reservation_id>')
def accepter_reservation(reservation_id):
    # Mettre à jour l'état de la réservation
    reservations_collection.update_one(
        {"_id": ObjectId(reservation_id)},
        {"$set": {"statut": "acceptée"}}
    )

    voiture_reservation = reservations_collection.find_one({"_id": ObjectId(reservation_id)})
    matricule = voiture_reservation['matricule']

    voitures_collection.update_one(
        {"matricule": matricule},
        {"$set": {"statut": "reserve"}}
    )

    # Rediriger vers la page des réservations
    return redirect('/liste_reservations')

# Route pour refuser une réservation
@app.route('/refuser/<reservation_id>')
def refuser_reservation(reservation_id):
    # Mettre à jour l'état de la réservation
    reservations_collection.update_one(
        {"_id": ObjectId(reservation_id)},
        {"$set": {"statut": "refusée"}}
    )

    # Rediriger vers la page des réservations
    return redirect('/liste_reservations')

# Route pour afficher la liste des clients
@app.route('/clients', methods=['GET'])
def client_list():
    if 'user_id' in session:
        clients = client_collection.find()
        success_message = request.args.get('success')
        return render_template('client_list.html', clients=clients, success=success_message)
    else:
        return redirect('/login')

# Route pour ajouter un client
@app.route('/add-client', methods=['GET', 'POST'])
def addClient():
    if 'user_id' in session:
        if request.method == 'POST':
            nom = request.form['nom']
            prenom = request.form['prenom']
            telephone = request.form['tel']
            cin = request.form['cin']
            email = request.form['email']

            if client_collection.find_one({'$or': [{'email': email}, {'cin': cin}]}):
                return render_template('client_add.html', error='L\'email ou le cin existe déjà dans la base de données.')

            client = {
                'nom': nom,
                'prenom': prenom,
                'cin': cin,
                'email': email,
                'telephone': telephone
            }

            try:
                # Insérer le client dans la base de données
                client_collection.insert_one(client)
                return redirect(url_for('client_list', success='Client ajouté avec succès !'))
            except DuplicateKeyError:
                return render_template('client_add.html', error='L\'email ou le cin existe déjà dans la base de données.')

        return render_template('client_add.html')
    else:
        return redirect('/login')

# Route pour modifier un client
@app.route('/edit-client/<client_id>', methods=['GET', 'POST'])
def edit_client(client_id):
    if 'user_id' in session:
        client = client_collection.find_one({'_id': ObjectId(client_id)})

        if request.method == 'POST':
            # Récupérer les informations mises à jour du formulaire
            nom = request.form['nom']
            prenom = request.form['prenom']
            telephone = request.form['telephone']
            email = request.form['email']

            # Mettre à jour les informations du client dans la base de données
            client_collection.update_one(
                {'_id': ObjectId(client_id)},
                {'$set': {
                    'nom': nom,
                    'prenom': prenom,
                    'telephone': telephone,
                    'email': email
                }}
            )

            # Rediriger vers la liste des clients ou afficher un message de succès
            return redirect(url_for('client_list', success='Client modifié avec succès'))

        # Gérer la requête GET pour afficher le formulaire de modification
        return render_template('edit_client.html', client=client)
    else:
        return redirect(url_for('login'))

# Route pour supprimer un client
@app.route('/delete-client/<client_id>', methods=['GET', 'POST'])
def delete_client(client_id):
    if request.method == 'POST':
        client_collection.delete_one({'_id': ObjectId(client_id)})
        return redirect(url_for('client_list'))
    else:
        # Code pour afficher la page de liste des clients
        clients = client_collection.find()
        return render_template('list.html', clients=clients)

# Route pour afficher la liste des managers
@app.route('/managers', methods=['GET'])
def list_manager():
    if 'user_id' in session:
        managers = utilisateur_collection.find({"role": "manager"})
        success_message = request.args.get('success')
        return render_template('managers.html', managers=managers, success=success_message)
    else:
        return redirect(url_for('login'))

# Route pour ajouter un utilisateur (Admin ou Manager)
@app.route('/add-user', methods=['GET', 'POST'])
def addUser():
    if 'user_id' in session:
        if request.method == 'POST':
            nom = request.form['nom']
            prenom = request.form['prenom']
            telephone = request.form['telephone']
            email = request.form['email']
            cin = request.form['cin']
            role = request.form['role']
            password = request.form['password']

            if utilisateur_collection.find_one({'$or': [{'email': email}, {'cin': cin}]}):
                return render_template('user_add.html', error='L\'email ou le cin existe déjà dans la base de données.')

            user = {
                'nom': nom,
                'prenom': prenom,
                'cin': cin,
                'email': email,
                'telephone': telephone,
                'password': password,
                'role': role
            }
            try:
                # Insérer l'utilisateur dans la base de données
                utilisateur_collection.insert_one(user)
                if role == 'admin':
                    return redirect(url_for('list_admin', success='Administrateur ajouté avec succès !'))
                elif role == 'manager':
                    return redirect(url_for('list_manager', success='Manager ajouté avec succès !'))
            except DuplicateKeyError:
                return render_template('user_add.html', error='L\'email ou le cin existe déjà dans la base de données.')
        return render_template('user_add.html')
    else:
        return redirect(url_for('login'))

# Route pour supprimer un manager
@app.route('/delete-manager/<manager_id>', methods=['GET', 'POST'])
def delete_manager(manager_id):
    if 'user_id' in session:
        if request.method == 'POST':
            utilisateur_collection.delete_one({'_id': ObjectId(manager_id)})
            return redirect(url_for('list_manager'))
        else:
            # Code pour afficher la page de liste des managers
            managers = utilisateur_collection.find({"role": "manager"})
            return render_template('managers.html', managers=managers)
    else:
        return redirect(url_for('login'))

# Route pour modifier un manager
@app.route('/edit-manager/<manager_id>', methods=['GET', 'POST'])
def edit_manager(manager_id):
    if 'user_id' in session:
        if request.method == 'POST':
            nom = request.form['nom']
            prenom = request.form['prenom']
            telephone = request.form['telephone']
            email = request.form['email']
            cin = request.form['cin']
            role = request.form['role']

            user = {
                'nom': nom,
                'prenom': prenom,
                'cin': cin,
                'email': email,
                'telephone': telephone,
                'role': role
            }

            try:
                # Mettre à jour le manager dans la base de données
                utilisateur_collection.update_one({'_id': ObjectId(manager_id)}, {'$set': user})
                return redirect(url_for('list_manager', success='Manager modifié avec succès'))
            except Exception as e:
                return 'Une erreur est survenue lors de la mise à jour du manager.'

        else:
            # Récupérer le manager depuis la base de données
            manager = utilisateur_collection.find_one({'_id': ObjectId(manager_id)})
            return render_template('manageer_edit.html', manager=manager)
    else:
        return redirect(url_for('login'))

# Route pour afficher la liste des admins
@app.route('/admins', methods=['GET'])
def list_admin():
    if 'user_id' in session:
        admins = utilisateur_collection.find({"role": "admin"})
        success_message = request.args.get('success')
        return render_template('admins.html', admins=admins, success=success_message)
    else:
        return redirect(url_for('login'))

# Route pour mettre à jour le mot de passe
@app.route('/update-password', methods=['POST', 'GET'])
def update_password():
    if 'user_id' in session:
        if request.method == 'POST':
            user_id = session['user_id']
            old_password = request.form.get('current_password')
            new_password = request.form.get('password')
            confirm_password = request.form.get('password_confirmation')

            user = utilisateur_collection.find_one({'_id': ObjectId(user_id)})
            if user and user['password'] == old_password:
                if new_password == confirm_password:
                    utilisateur_collection.update_one({'_id': user_id}, {'$set': {'password': new_password}})
                    return redirect('/')  # Rediriger vers la page de profil
                else:
                    return render_template('update_password.html', error='Le mot de passe de confirmation ne correspond pas')
            else:
                return render_template('update_password.html', error='Mot de passe actuel incorrect')
        else:
            user_id = session['user_id']
            user = utilisateur_collection.find_one({'_id': ObjectId(user_id)})
            return render_template('update_password.html', utilisateur=user)
    else:
        return redirect('/login')

# Route pour afficher et éditer le profil de l'utilisateur connecté
@app.route('/edit_mon_compte', methods=['GET', 'POST'])
def edit_mon_compte():
    if 'user_id' in session:
        user_id = session['user_id']
        if request.method == 'POST':
            nouveau_nom = request.form.get('nom')
            nouveau_email = request.form.get('email')
            nouveau_prenom = request.form.get('prenom')
            nouveau_cin = request.form.get('cin')
            nouveau_telephone = request.form.get('telephone')

            user = {
                'nom': nouveau_nom,
                'prenom': nouveau_prenom,
                'cin': nouveau_cin,
                'email': nouveau_email,
                'telephone': nouveau_telephone,
            }
            utilisateur_collection.update_one({'_id': ObjectId(user_id)}, {'$set': user})
            return redirect(url_for('show_reservations'))
        else:
            user = utilisateur_collection.find_one({'_id': ObjectId(user_id)})
            return render_template('profi_edit.html', user=user)
    else:
        return redirect(url_for('login'))

# Route pour se déconnecter
@app.route('/logout', methods=['GET'])
def logout():
    session.pop('user_id', None)
    return redirect('/login')

# Route pour se connecter
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password'].strip()

        try:
            user_doc = utilisateur_collection.find_one({"utilisateur.email": email})
            if user_doc:
                user = next((u for u in user_doc['utilisateur'] if u['email'] == email), None)
                if user and user['password'] == password:
                    session['user_id'] = str(user['_id'])
                    return redirect('/admin' if user['role'] == 'admin' else '/Manager')
            return render_template('login.html', error='Invalid credentials')
        except Exception as e:
            return render_template('login.html', error='Database connection issue')
    return render_template('login.html')

# Route pour afficher la liste des réservations
@app.route('/liste_reservations')
def liste_reservations():
    reservations = reservations_collection.aggregate([
        {"$match": {"statut": "en_attente"}},
        {"$lookup": {
            "from": "clients",
            "localField": "cin_client",
            "foreignField": "cin",
            "as": "clients"
        }},
        {"$lookup": {
            "from": "voiture",
            "localField": "matricule",
            "foreignField": "matricule",
            "as": "voiture"
        }},
        {"$unwind": "$clients"},
        {"$unwind": "$voiture"},
        {"$project": {
            "_id": 1,
            "matricule": 1,
            "cin_client": 1,
            "date_debut_reserv": 1,
            "date_fin_reserv": 1,
            "statut": 1,
            "clients.nom": 1,
            "clients.prenom": 1,
            "voiture.Nom": 1,
            "voiture.prix": 1
        }}
    ])
    return render_template('reservation_list.html', reservations=reservations)

# Route pour afficher l'historique des réservations
@app.route('/historique')
def show_historique():
    historique = reservations_collection.aggregate([
        {"$match": {"statut": {"$ne": "en_attente"}}},
        {"$lookup": {
            "from": "clients",
            "localField": "cin_client",
            "foreignField": "cin",
            "as": "clients"
        }},
        {"$lookup": {
            "from": "voiture",
            "localField": "matricule",
            "foreignField": "matricule",
            "as": "voiture"
        }},
        {"$unwind": "$clients"},
        {"$unwind": "$voiture"},
        {"$project": {
            "_id": 1,
            "matricule": 1,
            "cin_client": 1,
            "date_debut_reserv": 1,
            "date_fin_reserv": 1,
            "statut": 1,
            "client_nom": "$clients.nom",
            "client_prenom": "$clients.prenom",
            "voiture_nom": "$voiture.Nom",
            "voiture_prix": "$voiture.prix"
        }}
    ])
    return render_template('History.html', historique=historique)

# Route pour afficher le détail d'une réservation
@app.route('/show_detail/<reservation_id>')
def show_detail_reservation(reservation_id):
    reservation = reservations_collection.aggregate([
        {"$match": {"_id": ObjectId(reservation_id)}},
        {"$lookup": {
            "from": "clients",
            "localField": "cin_client",
            "foreignField": "cin",
            "as": "clients"
        }},
        {"$lookup": {
            "from": "voiture",
            "localField": "matricule",
            "foreignField": "matricule",
            "as": "voiture"
        }},
        {"$unwind": "$clients"},
        {"$unwind": "$voiture"},
        {"$project": {
            "_id": 1,
            "matricule": 1,
            "cin_client": 1,
            "date_debut_reserv": 1,
            "date_fin_reserv": 1,
            "statut": 1,
            "client_nom": "$clients.nom",
            "client_prenom": "$clients.prenom",
            "voiture_marque": "$voiture.Marque",
            "voiture_nom": "$voiture.Nom",
            "voiture_prix": "$voiture.prix",
            "photo": "$voiture.photo"
        }}
    ])

    reservation = list(reservation)
    if len(reservation) == 0:
        return "Reservation not found", 404

    reservation = reservation[0]

    if request.is_xhr:
        return render_template('reserv_detail.html', reservation=reservation)
    else:
        return render_template('show_detail_reservation_full.html', reservation=reservation)

# Route pour afficher la liste des voitures
@app.route('/voitures', methods=['GET'])
def get_voitures():
    voitures = voitures_collection.find()
    return render_template('cars.html', voitures=voitures)

# Route pour afficher les voitures en cours de réservation
@app.route('/voitures_encours_reservation', methods=['GET'])
def voitures_encours_reservation():
    voitures_non_disponibles = voitures_collection.find({"statut": {"$ne": "disponible"}})
    return render_template('fin-reserva.html', voitures=voitures_non_disponibles)

# Route pour terminer une réservation
@app.route('/terminer_reservation/<id>', methods=['GET'])
def terminer_reservation(id):
    # Mettre à jour l'état de la réservation
    voitures_collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": {"statut": "disponible"}}
    )

    # Rediriger vers la page des voitures en cours de réservation
    return redirect('/voitures_encours_reservation')

# Route pour afficher le formulaire de réservation
@app.route('/reserver')
def reserver():
    return render_template('reservation_form.html')

# Route pour afficher le formulaire de nouvelle réservation
@app.route('/new')
def new():
    return render_template('new_j.html')

# Route pour afficher la liste des voitures
@app.route('/liste_voitures', methods=['GET'])
def liste_voitures():
    voitures = voitures_collection.find()
    return render_template('car_list.html', voitures=voitures)

# Route pour supprimer une voiture
@app.route('/voitures/delete/<id>', methods=['POST', 'GET'])
def delete_voiture(id):
    voitures_collection.delete_one({'_id': ObjectId(id)})
    return redirect('/voitures')

# Route pour modifier une voiture
@app.route('/voitures/edit/<id>', methods=['GET', 'POST'])
def edit_voiture(id):
    voiture = voitures_collection.find_one({'_id': ObjectId(id)})
    if request.method == 'POST':
        updated_voiture = {
            'Nom': request.form['nom'],
            'Marque': request.form['marque'],
            'date_dispo_debut': request.form['date_debut'],
            'date_dispo_fin': request.form['date_fin'],
            'statut': request.form['statut'],
            'prix': request.form['prix']
        }
        voitures_collection.update_one({'_id': ObjectId(id)}, {'$set': updated_voiture})
        return redirect('/voitures')
    return render_template('car_edit.html', voiture=voiture)

# Route pour ajouter une voiture
@app.route('/voitures/add', methods=['GET', 'POST'])
def add_voiture():
    if request.method == 'POST':
        # Récupérer les données du formulaire
        nom = request.form['nom']
        marque = request.form['marque']
        matricule = request.form['matricule']
        date_debut = request.form['date_debut']
        date_fin = request.form['date_fin']
        statut = request.form['statut']
        prix = request.form['prix']

        # Créer un dictionnaire pour représenter la nouvelle voiture
        voiture = {
            'Nom': nom,
            'matricule': matricule,
            'Marque': marque,
            'date_dispo_debut': date_debut,
            'date_dispo_fin': date_fin,
            'statut': statut,
            'prix': prix
        }

        # Gérer le téléchargement de la photo
        photo = request.files['photo']
        if photo:
            filename = secure_filename(photo.filename)
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            voiture['photo'] = filename

        # Insérer la nouvelle voiture dans la base de données
        voitures_collection.insert_one(voiture)

        return redirect('/voitures')

    return render_template('cars_add.html', voiture={})

# Route pour afficher le tableau de bord du manager
@app.route('/Manager')
def manager_dash():
    # Effectuer les requêtes pour récupérer les informations nécessaires
    reservations_en_attente = reservations_collection.count_documents({"statut": "en_attente"})
    reservations_acceptees = reservations_collection.count_documents({"statut": "acceptée"})
    reservations_refuses = reservations_collection.count_documents({"statut": "refusée"})
    nombre_clients = client_collection.count_documents({})
    nombre_admin = utilisateur_collection.count_documents({"role": "admin"})
    nombre_manager = utilisateur_collection.count_documents({"role": "manager"})
    nombre_voitures = voitures_collection.count_documents({"statut": "disponible"})
    nombre_voitures_total = voitures_collection.count_documents({})

    # Passer les nombres de réservations et autres informations à la template 'm_dash.html'
    return render_template('m_dash.html', nombre_voitures=nombre_voitures, nombre_admin=nombre_admin, nombre_manager=nombre_manager, nombre_clients=nombre_clients, nombre_reservations_en_attente=reservations_en_attente, nombre_reservations_acceptees=reservations_acceptees, nombre_voitures_total=nombre_voitures_total, nombre_reservations_refuses=reservations_refuses)

# Route pour afficher le tableau de bord de l'admin
@app.route('/admin')
def admin():
    # Effectuer les requêtes pour récupérer les informations nécessaires
    reservations_en_attente = reservations_collection.count_documents({"statut": "en_attente"})
    reservations_acceptees = reservations_collection.count_documents({"statut": "acceptée"})
    reservations_refuses = reservations_collection.count_documents({"statut": "refusée"})
    nombre_clients = client_collection.count_documents({})
    nombre_admin = utilisateur_collection.count_documents({"role": "admin"})
    nombre_manager = utilisateur_collection.count_documents({"role": "manager"})
    nombre_voitures = voitures_collection.count_documents({"statut": "disponible"})
    nombre_voitures_total = voitures_collection.count_documents({})

    # Passer les nombres de réservations et autres informations à la template 'index.html'
    return render_template('index.html', nombre_voitures=nombre_voitures, nombre_admin=nombre_admin, nombre_manager=nombre_manager, nombre_clients=nombre_clients, nombre_reservations_en_attente=reservations_en_attente, nombre_reservations_acceptees=reservations_acceptees, nombre_voitures_total=nombre_voitures_total, nombre_reservations_refuses=reservations_refuses)

# Route pour afficher le formulaire de réservation d'une voiture spécifique
@app.route('/voitures/<voiture_id>/reserve', methods=['GET', 'POST'])
def afficher_formulaire_reservation(voiture_id):
    voiture_id = ObjectId(voiture_id)  # Convertir l'ID de la voiture en ObjectId
    reservation_effectuee = False  # Variable pour indiquer si la réservation a été effectuée avec succès
    clients = client_collection.find({})
    if request.method == 'POST':
        # Récupérer les détails de la voiture
        voiture = voitures_collection.find_one({'_id': voiture_id})
        if voiture:
            date_debut = datetime.strptime(request.form.get('date_debut_reservation'), '%Y-%m-%d')
            date_fin = datetime.strptime(request.form.get('date_fin_reservation'), '%Y-%m-%d')

            # Convertir la date de disponibilité de la voiture en datetime
            date_dispo_debut = datetime.strptime(voiture.get('date_dispo_debut'), '%Y-%m-%d')
            date_dispo_fin = datetime.strptime(voiture.get('date_dispo_fin'), '%Y-%m-%d')

            # Vérifier si la date de début est inférieure à la date de disponibilité de la voiture
            if date_debut < date_dispo_debut:
                error_message = "La date de début de réservation est antérieure à la date de disponibilité de la voiture."
                return render_template('reservation_form.html', nom_voiture=voiture.get('Nom', ''), error_message=error_message)

            # Vérifier si la date de fin est supérieure à la date de disponibilité de la voiture
            if date_fin > date_dispo_fin:
                error_message = "La date de fin de réservation dépasse la date de disponibilité de la voiture."
                return render_template('reservation_form.html', nom_voiture=voiture.get('Nom', ''), error_message=error_message)
        reservation = {
            'nom_voiture': voiture.get('Nom', ''),
            'matricule': voiture.get('matricule', ''),
            'prix': voiture.get('prix', ''),
            'cin_client': request.form.get('cin_client'),
            'date_debut_reserv': date_debut,
            'date_fin_reserv': date_fin,
            'statut': request.form.get('statut', 'en_attente')
        }
        reservations_collection.insert_one(reservation)
        reservation_effectuee = True  # Mettre la variable à True après l'enregistrement de la réservation

        return redirect('/voitures')

    voiture = voitures_collection.find_one({'_id': voiture_id})
    if voiture:
        nom_voiture = voiture.get('Nom', '')
        matricule = voiture.get('matricule', '')
        prix = voiture.get('prix', '')
        return render_template('reservation_form.html', clients=clients, nom_voiture=nom_voiture, matricule=matricule, prix=prix, voiture_id=voiture_id, reservation_effectuee=reservation_effectuee)
    else:
        return redirect('/voitures')

# Route pour rechercher les voitures disponibles par date
@app.route('/voitures/search_date', methods=['GET'])
def rechercher_voitures_par_date():
    date_debut_str = request.args.get('date_debut')
    date_fin_str = request.args.get('date_fin')

    query = {}
    if date_debut_str and date_fin_str:
        query['date_dispo_debut'] = {'$lte': date_debut_str}
        query['date_dispo_fin'] = {'$gte': date_fin_str}

    voitures = voitures_collection.find(query)

    return render_template('cars_cards.html', voitures=voitures)

# Route pour rechercher les voitures disponibles par prix
@app.route('/voitures/search_prix', methods=['GET'])
def rechercher_voitures_par_prix():
    prix_max_str = request.args.get('prix_max')

    try:
        prix_max = int(prix_max_str)
    except ValueError:
        return render_template('cars_cards.html', voitures=[])

    # Filtrage des voitures par prix maximum
    voitures = list(voitures_collection.find({
        '$expr': {
            '$lte': [{'$toInt': '$prix'}, prix_max]
        }
    }))

    return render_template('cars_cards.html', voitures=voitures)

# Route pour rechercher les voitures disponibles par critères combinés
@app.route('/voitures/search_combinee', methods=['GET'])
def rechercher_voitures_combinee():
    date_debut_str = request.args.get('date_debut')
    date_fin_str = request.args.get('date_fin')
    prix_max_str = request.args.get('prix_max')
    marque_str = request.args.get('marque')

    query = {}

    # Ajout du filtre de date si les dates sont fournies
    if date_debut_str and date_fin_str:
        query['date_dispo_debut'] = {'$lte': date_debut_str}
        query['date_dispo_fin'] = {'$gte': date_fin_str}

    # Ajout du filtre de prix si le prix max est fourni
    try:
        prix_max = int(prix_max_str)
        query['$expr'] = {'$lte': [{'$toInt': '$prix'}, prix_max]}
    except (ValueError, TypeError):
        pass

    # Ajout du filtre de marque si la marque est fournie
    if marque_str:
        query['Marque'] = marque_str

    voitures = list(voitures_collection.find(query))

    return render_template('cars_cards.html', voitures=voitures)

# Route pour obtenir les détails de réservation d'une voiture spécifique
@app.route('/get_reservation_details/<voiture_id>', methods=['GET'])
def get_reservation_details(voiture_id):
    reservation = reservations_collection.aggregate([
        {"$match": {"matricule": voiture_id, "statut": {"$ne": "en_attente"}}},
        {"$lookup": {
            "from": "clients",
            "localField": "cin_client",
            "foreignField": "cin",
            "as": "clients"
        }},
        {"$lookup": {
            "from": "voiture",
            "localField": "matricule",
            "foreignField": "matricule",
            "as": "voiture"
        }},
        {"$unwind": "$clients"},
        {"$unwind": "$voiture"},
        {"$project": {
            "_id": 1,
            "matricule": 1,
            "cin_client": 1,
            "date_debut_reserv": 1,
            "date_fin_reserv": 1,
            "statut": 1,
            "client_nom": "$clients.nom",
            "client_prenom": "$clients.prenom",
            "voiture_nom": "$voiture.Nom",
            "voiture_prix": "$voiture.prix",
            "voiture_photo": "$voiture.photo"
        }}
    ])

    reservation = list(reservation)
    if not reservation:
        return "<p>No reservation found</p>", 404

    reservation = reservation[0]
    return render_template('reservation_detail.html', reservation=reservation)

if __name__ == '__main__':
    app.run(debug=True)
