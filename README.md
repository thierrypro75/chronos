# Chronos - Analyseur de Cahier des Charges

Chronos est une application Flask qui permet d'analyser des cahiers des charges contenus dans des fichiers PDF. 
L'application extrait le texte du document et utilise l'API Anthropic Claude pour effectuer une analyse AMOA 
(Assistance à Maîtrise d'Ouvrage) détaillée, générant des artefacts de gestion de projet.

## Fonctionnalités

- Upload de documents PDF
- Extraction du texte contenu dans le PDF
- Analyse du cahier des charges via l'API Anthropic Claude
- Génération d'artefacts de projet:
  - Charte de projet
  - Backlog produit avec user stories et estimations d'effort
  - Estimation d'effort détaillée
  - Roadmap
  - Méthodologie
  - Gestion des risques

## Prérequis

- Python 3.7+
- Une clé API Anthropic Claude

## Installation

1. Cloner le dépôt:
```
git clone [URL du dépôt]
cd Chronos
```

2. Créer un environnement virtuel et l'activer:
```
python -m venv venv
source venv/bin/activate  # Sous Linux/Mac
venv\Scripts\activate     # Sous Windows
```

3. Installer les dépendances:
```
pip install -r requirements.txt
```

4. Configurer la clé API Anthropic:
```
# Sous Linux/Mac
export ANTHROPIC_API_KEY=votre_clé_api

# Sous Windows PowerShell
$env:ANTHROPIC_API_KEY="votre_clé_api"

# Sous Windows Command Prompt
set ANTHROPIC_API_KEY=votre_clé_api
```

## Utilisation

1. Démarrer l'application:
```
python app.py
```

2. Ouvrir un navigateur et accéder à http://127.0.0.1:5000
3. Uploader un fichier PDF contenant un cahier des charges
4. Cliquer sur "Analyser le cahier des charges" pour générer les artefacts de projet
5. Naviguer entre les différents onglets pour consulter les résultats

## Structure du projet

- `app.py` : Application principale Flask
- `templates/` : Templates HTML
  - `index.html` : Page d'accueil avec formulaire d'upload
  - `analyze.html` : Page d'analyse et affichage des résultats
- `static/` : Fichiers statiques
  - `css/style.css` : Styles CSS
- `uploads/` : Dossier où sont stockés les PDF uploadés (créé automatiquement)

## Technologie

- Flask : Framework web Python
- PyPDF2 : Bibliothèque d'extraction de texte de PDF
- Anthropic : API Claude pour l'analyse du cahier des charges

## Licence

[Indiquer la licence] 