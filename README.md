# Application de Gestion Vegan

Une application web Flask pour la gestion d'entreprises véganes, comprenant la gestion des clients, fournisseurs, produits, factures et tâches.

## Fonctionnalités

### Gestion des clients
- Liste des clients avec leurs informations
- Ajout, modification et suppression de clients
- Historique des factures par client

### Gestion des fournisseurs
- Liste des fournisseurs
- Ajout, modification et suppression de fournisseurs
- Suivi des produits par fournisseur

### Gestion des produits
- Catalogue de produits organisé par catégories
- Prix et descriptions détaillées
- Gestion des stocks

### Gestion des factures
- Création de factures professionnelles
- Ajout de produits avec calcul automatique
- Numérotation automatique des factures
- Export PDF

### Gestion des tâches
- Liste des tâches avec dates d'échéance
- Statuts personnalisés (En attente, En cours, Terminée, Annulée)
- Interface intuitive avec filtres

### Paramètres
- Personnalisation des informations de l'entreprise
- Gestion du logo
- Configuration de la TVA et devise
- Options d'affichage

## Installation

1. Cloner le dépôt :
```bash
git clone [URL_DU_REPO]
```

2. Créer un environnement virtuel :
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Installer les dépendances :
```bash
pip install -r requirements.txt
```

4. Configurer les variables d'environnement :
```bash
cp .env.example .env
# Éditer .env avec vos paramètres
```

5. Initialiser la base de données :
```bash
flask db upgrade
```

## Lancement

```bash
flask run
```

L'application sera accessible à l'adresse : http://localhost:5000

## Technologies utilisées

- Flask 2.0+
- SQLAlchemy
- Bootstrap 5.3.2
- Bootstrap Icons
- JavaScript (ES6+)
- SQLite (développement)
- PostgreSQL (production)

## Licence

MIT
