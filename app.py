from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
import PyPDF2
import re
import json
import uuid
import time
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'chronos_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['RESULTS_FOLDER'] = 'results'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}

# Cache buster pour les fichiers statiques
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['CACHE_BUSTER'] = int(time.time())

# Créer les dossiers nécessaires s'ils n'existent pas
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULTS_FOLDER'], exist_ok=True)

# Injecter le cache buster dans les templates
@app.context_processor
def inject_cache_buster():
    return {'cache_buster': app.config['CACHE_BUSTER']}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def extract_text_from_pdf(file_path):
    text = ""
    with open(file_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text()
    return text

def extract_analysis_sections(analysis_result):
    """Extrait les différentes sections du résultat d'analyse"""
    sections = {
        'project_charter': '',
        'product_backlog': '',
        'effort_estimation': '',
        'roadmap': '',
        'methodology': '',
        'risk_management': ''
    }
    
    # Extraire le contenu entre les balises XML
    for section in sections.keys():
        pattern = f'<{section}>(.*?)</{section}>'
        match = re.search(pattern, analysis_result, re.DOTALL)
        if match:
            sections[section] = match.group(1).strip()
    
    return sections

def format_markdown_tables(text):
    """Formate les tableaux Markdown en HTML"""
    # Recherche les tableaux Markdown
    table_pattern = r'(\|[^\n]+\|\n\|[-:| ]+\|\n(?:\|[^\n]+\|\n)+)'
    
    def format_table(match):
        table_text = match.group(1)
        lines = table_text.strip().split('\n')
        
        # Commence le tableau HTML
        html = '<table class="markdown-table">\n'
        
        # Traitement de l'en-tête
        header = lines[0]
        cells = [cell.strip() for cell in header.split('|')[1:-1]]  # Enlève les | aux extrémités
        html += '<thead>\n<tr>\n'
        for cell in cells:
            html += f'<th>{cell}</th>\n'
        html += '</tr>\n</thead>\n'
        
        # Ignorer la ligne de séparation (|---|---|...)
        
        # Traitement du corps
        html += '<tbody>\n'
        for i in range(2, len(lines)):
            row = lines[i]
            if not row.strip():  # Ignorer les lignes vides
                continue
                
            # Extraire les cellules et supprimer les espaces en trop
            cells = [cell.strip() for cell in row.split('|')[1:-1]]
            
            # S'assurer qu'il y a le bon nombre de cellules
            if not cells:
                continue
                
            html += '<tr>\n'
            for cell in cells:
                html += f'<td>{cell}</td>\n'
            html += '</tr>\n'
        html += '</tbody>\n'
        
        html += '</table>'
        return html
    
    # Remplacer tous les tableaux Markdown par leur équivalent HTML
    formatted_text = re.sub(table_pattern, format_table, text, flags=re.DOTALL)
    
    return formatted_text

def format_markdown_text(text):
    """Formate le texte Markdown en HTML basique (titres, listes, gras, italique)"""
    # Remplacer les sauts de ligne Windows par des sauts de ligne Unix
    text = text.replace('\r\n', '\n')
    
    # Formatter les tableaux d'abord
    text = format_markdown_tables(text)
    
    # Titres avec ancres pour navigation
    text = re.sub(r'^# (.+)$', r'<h1 id="\1">\1</h1>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.+)$', r'<h2 id="\1">\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r'^### (.+)$', r'<h3 id="\1">\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^#### (.+)$', r'<h4 id="\1">\1</h4>', text, flags=re.MULTILINE)
    
    # Listes à puces avec meilleure structuration
    bullet_items = []
    
    def replace_bullet(match):
        bullet_items.append(match.group(1))
        return f'<li>{match.group(1)}</li>'
    
    # Remplacer chaque item de liste
    text = re.sub(r'^- (.+)$', replace_bullet, text, flags=re.MULTILINE)
    
    # Envelopper les listes contigües dans une balise <ul>
    if bullet_items:
        for item in bullet_items:
            text = text.replace(f'<li>{item}</li>', f'<li>{item}</li>\n')
        text = re.sub(r'(<li>.*?</li>\n)+', r'<ul>\n\g<0></ul>', text, flags=re.DOTALL)
    
    # Gras et italique
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    
    # Paragraphes plus proprement
    paragraphs = text.split('\n\n')
    for i, paragraph in enumerate(paragraphs):
        if paragraph.strip() and not paragraph.strip().startswith('<'):
            paragraphs[i] = f'<p>{paragraph}</p>'
    
    text = '\n\n'.join(paragraphs)
    
    return text

def analyze_requirements(pdf_content, additional_info=""):
    """Simule l'analyse du cahier des charges (version de démonstration)"""
    # Extrait quelques mots-clés du PDF pour personnaliser la démo
    keywords = []
    if "web" in pdf_content.lower():
        keywords.append("site web")
    if "mobile" in pdf_content.lower():
        keywords.append("application mobile")
    if "api" in pdf_content.lower():
        keywords.append("API")
    if "database" in pdf_content.lower() or "données" in pdf_content.lower():
        keywords.append("base de données")
    
    if not keywords:
        keywords = ["application"]
    
    project_type = " et ".join(keywords)
    
    # Extraction des technologies si mentionnées dans les informations supplémentaires
    technologies = []
    if additional_info:
        tech_keywords = ["react", "angular", "vue", "node", "java", "spring", "python", "django", "flask", 
                        "php", "laravel", "symfony", ".net", "c#", "golang", "ruby", "rails", "html", "css", 
                        "javascript", "typescript", "sql", "nosql", "mongodb", "postgresql", "mysql", "oracle", 
                        "aws", "azure", "gcp", "docker", "kubernetes"]
        
        for tech in tech_keywords:
            if tech.lower() in additional_info.lower():
                technologies.append(tech)
    
    # Génère un résultat de démonstration
    demo_result = f"""<output>
<project_charter>
# Charte de Projet

## Informations générales
- **Nom du projet**: Développement d'une {project_type}
- **Date de début**: 01/05/2023
- **Date de fin prévue**: 01/11/2023
- **Chef de projet**: À déterminer

## Objectifs
Le projet vise à développer une {project_type} répondant aux besoins décrits dans le cahier des charges. 
L'objectif principal est de fournir une solution robuste, évolutive et conforme aux standards actuels.

## Périmètre du projet

### Dans le périmètre (In Scope)
- Analyse détaillée des besoins fonctionnels et techniques
- Conception de l'architecture système
- Développement des fonctionnalités identifiées dans le backlog
- Tests unitaires, d'intégration et de validation
- Déploiement en environnement de production
- Formation des utilisateurs
- Documentation technique et utilisateur
- Support post-déploiement pour une durée de 3 mois

### Hors périmètre (Out of Scope)
- Maintenance évolutive au-delà de la période de support
- Développement de fonctionnalités non spécifiées dans le backlog initial
- Migration des données existantes (sauf mention contraire dans le cahier des charges)
- Formation avancée pour les administrateurs système
- Support technique au-delà de la période convenue
- Intégration avec des systèmes tiers non mentionnés dans le cahier des charges

## Contraintes
- **Contraintes de temps**: Livraison nécessaire avant la fin de l'année fiscale
- **Contraintes budgétaires**: Budget fixe, sans possibilité d'extension
- **Contraintes techniques**: {", ".join(technologies) if technologies else "À définir selon les exigences du client"}
- **Contraintes légales**: Conformité au RGPD et autres réglementations applicables
- **Contraintes de ressources**: Équipe limitée à un maximum de 8 personnes
- **Contraintes d'infrastructure**: Déploiement sur l'infrastructure existante du client

## Livrables
- Spécifications techniques détaillées
- Code source complet et documenté
- Documentation utilisateur et technique
- Rapport de tests
- Solution déployée et opérationnelle

## Parties prenantes
- Client: Direction et utilisateurs finaux
- Équipe projet: Développeurs, designers, testeurs, chef de projet
- Partenaires techniques éventuels

## Budget estimé
À déterminer suite à l'analyse détaillée des besoins et à la planification du projet.
</project_charter>

<product_backlog>
# Backlog Produit

## Epic 1: Architecture et Infrastructure
- **US1.1**: En tant qu'administrateur système, je veux une architecture scalable afin de supporter la charge attendue de 1000 utilisateurs simultanés. (M)
  - Critères d'acceptation:
    - L'application doit supporter au moins 1000 connexions simultanées
    - Le temps de réponse doit rester inférieur à 2 secondes sous charge
    - Le système doit pouvoir être facilement étendu horizontalement
  - Tâches techniques:
    - Conception de l'architecture système
    - Configuration du load balancer
    - Tests de performance sous charge

- **US1.2**: En tant que développeur, je veux un environnement de développement configuré afin de commencer le développement rapidement. (S)
  - Critères d'acceptation:
    - Documentation complète du processus d'installation
    - Configuration automatisée via des scripts
    - Environnements de développement, test et production distincts
  - Tâches techniques:
    - Création des scripts d'automatisation
    - Configuration des environnements
    - Documentation du processus

- **US1.3**: En tant qu'administrateur, je veux une solution de déploiement automatisée afin de faciliter les mises à jour. (L)
  - Critères d'acceptation:
    - Pipeline CI/CD fonctionnel
    - Déploiement en un clic
    - Possibilité de rollback en cas d'échec
  - Tâches techniques:
    - Configuration de Jenkins/GitLab CI
    - Écriture des scripts de déploiement
    - Tests de déploiement automatique

## Epic 2: Authentification et Gestion des Utilisateurs
- **US2.1**: En tant qu'utilisateur, je veux pouvoir créer un compte afin d'accéder aux fonctionnalités. (M)
  - Critères d'acceptation:
    - Formulaire d'inscription avec validation des champs
    - Confirmation par email
    - Respect des normes RGPD pour le stockage des données
  - Tâches techniques:
    - Développement du formulaire d'inscription
    - Intégration avec le service d'emails
    - Stockage sécurisé des données utilisateur

- **US2.2**: En tant qu'utilisateur, je veux pouvoir me connecter de façon sécurisée afin de protéger mes données. (M)
  - Critères d'acceptation:
    - Authentification à deux facteurs
    - Verrouillage de compte après plusieurs tentatives échouées
    - Session timeout après période d'inactivité
  - Tâches techniques:
    - Implémentation du système d'authentification
    - Configuration des politiques de sécurité
    - Tests de pénétration du système d'authentification

- **US2.3**: En tant qu'utilisateur, je veux pouvoir réinitialiser mon mot de passe afin de récupérer l'accès à mon compte. (S)
  - Critères d'acceptation:
    - Processus de réinitialisation par email
    - Lien à usage unique et limité dans le temps
    - Instructions claires pour l'utilisateur
  - Tâches techniques:
    - Développement du flux de réinitialisation
    - Génération sécurisée des tokens
    - Intégration avec le service d'emails

- **US2.4**: En tant qu'administrateur, je veux pouvoir gérer les utilisateurs afin de maintenir la sécurité du système. (L)
  - Critères d'acceptation:
    - Interface d'administration complète
    - Possibilité de bloquer/débloquer des comptes
    - Gestion des rôles et permissions
  - Tâches techniques:
    - Développement du tableau de bord admin
    - Implémentation du système de rôles
    - Tests des fonctionnalités administratives

## Epic 3: Fonctionnalités Principales
- **US3.1**: En tant qu'utilisateur, je veux pouvoir naviguer facilement dans l'interface afin de trouver rapidement ce que je cherche. (M)
  - Critères d'acceptation:
    - Navigation intuitive et responsive
    - Temps de chargement des pages < 1 seconde
    - Compatibilité multi-navigateurs
  - Tâches techniques:
    - Conception de l'interface utilisateur
    - Optimisation des performances frontend
    - Tests cross-browser

- **US3.2**: En tant qu'utilisateur, je veux pouvoir effectuer des recherches précises afin de trouver rapidement l'information. (L)
  - Critères d'acceptation:
    - Moteur de recherche avec filtres avancés
    - Résultats pertinents et triables
    - Suggestions de recherche
  - Tâches techniques:
    - Implémentation de l'algorithme de recherche
    - Création de l'interface de recherche
    - Indexation des données pour performances

- **US3.3**: En tant qu'utilisateur, je veux pouvoir sauvegarder mes préférences afin de personnaliser mon expérience. (M)
  - Critères d'acceptation:
    - Paramètres de personnalisation accessibles
    - Sauvegarde automatique des préférences
    - Application immédiate des changements
  - Tâches techniques:
    - Développement du système de préférences
    - Stockage des préférences utilisateur
    - Tests des fonctionnalités de personnalisation

## Epic 4: Gestion des Données
- **US4.1**: En tant qu'utilisateur, je veux pouvoir importer des données afin de les utiliser dans le système. (L)
  - Critères d'acceptation:
    - Support des formats CSV, Excel et JSON
    - Validation des données importées
    - Gestion des erreurs avec feedback clair
  - Tâches techniques:
    - Développement des parsers pour différents formats
    - Implémentation de la validation des données
    - Création de l'interface d'import

- **US4.2**: En tant qu'utilisateur, je veux pouvoir exporter des données afin de les utiliser ailleurs. (M)
  - Critères d'acceptation:
    - Export en plusieurs formats (CSV, Excel, PDF)
    - Sélection des données à exporter
    - Options de formatage
  - Tâches techniques:
    - Développement des générateurs de fichiers
    - Création de l'interface d'export
    - Tests des différents formats d'export

- **US4.3**: En tant qu'administrateur, je veux des sauvegardes automatiques afin de prévenir la perte de données. (L)
  - Critères d'acceptation:
    - Sauvegardes quotidiennes automatisées
    - Procédure de restauration testée
    - Notifications en cas d'échec
  - Tâches techniques:
    - Configuration du système de backup
    - Implémentation des scripts de sauvegarde
    - Tests de restauration

## Epic 5: Rapports et Analyses
- **US5.1**: En tant qu'utilisateur, je veux générer des rapports personnalisés afin d'analyser les données selon mes besoins. (XL)
  - Critères d'acceptation:
    - Interface de création de rapports flexible
    - Multiples visualisations disponibles (graphiques, tableaux)
    - Export des rapports en PDF et Excel
  - Tâches techniques:
    - Développement du moteur de génération de rapports
    - Création des templates de visualisation
    - Intégration d'une bibliothèque de graphiques

- **US5.2**: En tant qu'administrateur, je veux consulter des statistiques d'utilisation afin d'optimiser les performances. (L)
  - Critères d'acceptation:
    - Tableau de bord temps réel
    - Historique des métriques
    - Alertes configurables
  - Tâches techniques:
    - Implémentation du système de collecte de métriques
    - Développement du tableau de bord
    - Configuration du système d'alertes

## Epic 6: Documentation et Support
- **US6.1**: En tant qu'utilisateur, je veux accéder à une documentation claire afin de comprendre comment utiliser l'application. (M)
  - Critères d'acceptation:
    - Documentation complète avec captures d'écran
    - Système d'aide contextuelle
    - FAQ et tutoriels vidéo
  - Tâches techniques:
    - Rédaction de la documentation
    - Développement du système d'aide contextuelle
    - Production des tutoriels vidéo

- **US6.2**: En tant qu'utilisateur, je veux pouvoir signaler un problème afin d'obtenir de l'aide. (S)
  - Critères d'acceptation:
    - Formulaire de rapport de bug accessible
    - Système de tickets avec suivi
    - Notifications par email des mises à jour
  - Tâches techniques:
    - Développement du système de tickets
    - Intégration email
    - Interface de gestion des tickets
</product_backlog>

<effort_estimation>
# Estimation de l'Effort par un Développeur Senior

## Introduction
L'estimation suivante a été réalisée par un développeur senior avec 10 ans d'expérience dans des projets similaires. Cette estimation tient compte de la complexité technique, des dépendances entre les tâches, et des contraintes identifiées dans le projet.

## Récapitulatif par Epic

| Epic | Titre | Nombre de User Stories | Effort Total |
|------|-------|------------------------|--------------|
| 1 | Architecture et Infrastructure | 3 | 1.75 jours |
| 2 | Authentification et Gestion des Utilisateurs | 4 | 2.5 jours |
| 3 | Fonctionnalités Principales | 3 | 2.25 jours |
| 4 | Gestion des Données | 3 | 2.5 jours |
| 5 | Rapports et Analyses | 2 | 2.25 jours |
| 6 | Documentation et Support | 2 | 1.25 jours |

## Détail des estimations

### Légende
- S (Small): 0.25 jour (1-2 heures) - Tâche simple avec peu de complexité
- M (Medium): 0.75 jour (5-6 heures) - Tâche standard avec complexité modérée
- L (Large): 1.25 jours (8-10 heures) - Tâche complexe nécessitant une expertise technique
- XL (Extra Large): 2 jours (16 heures) - Tâche très complexe avec risques techniques

### Justification des estimations clés
- **US1.1 (Architecture scalable)**: Estimé à M (0.75 jour) car bien que conceptuellement complexe, l'utilisation de patterns établis et de services cloud réduit l'effort de mise en œuvre.
- **US2.4 (Gestion des utilisateurs)**: Estimé à L (1.25 jours) en raison de la complexité de gestion des permissions et des considérations de sécurité.
- **US3.2 (Recherche avancée)**: Estimé à L (1.25 jours) car l'implémentation d'un système de recherche performant nécessite un travail significatif sur l'indexation et les algorithmes.
- **US5.1 (Rapports personnalisés)**: Estimé à XL (2 jours) en raison de la complexité de création d'un système flexible de génération de rapports et des diverses visualisations requises.

### Détails par User Story

| User Story | Estimation | Jours | Justification technique |
|------------|------------|-------|-------------------------|
| US1.1 | M | 0.75 | Conception d'architecture avec possibilité de mise à l'échelle horizontale |
| US1.2 | S | 0.25 | Scripts d'automatisation déjà disponibles, nécessitant des adaptations mineures |
| US1.3 | L | 1.25 | Configuration complète d'un pipeline CI/CD avec tests automatisés |
| US2.1 | M | 0.75 | Implémentation de formulaires et validation côté serveur avec sécurité RGPD |
| US2.2 | M | 0.75 | Authentification sécurisée avec 2FA et gestion des sessions |
| US2.3 | S | 0.25 | Système standard de réinitialisation de mot de passe |
| US2.4 | L | 1.25 | Interface d'administration complète avec gestion des rôles et permissions |
| US3.1 | M | 0.75 | UI/UX responsive avec optimisation des performances |
| US3.2 | L | 1.25 | Implémentation d'un moteur de recherche performant avec filtres |
| US3.3 | M | 0.75 | Système de préférences utilisateur avec persistence |
| US4.1 | L | 1.25 | Système d'import multi-format avec validation robuste |
| US4.2 | M | 0.75 | Système d'export dans différents formats |
| US4.3 | L | 1.25 | Système de sauvegarde automatisé avec restauration testée |
| US5.1 | XL | 2.0 | Moteur complexe de génération de rapports personnalisés |
| US5.2 | L | 1.25 | Système de métriques en temps réel avec historique |
| US6.1 | M | 0.75 | Documentation complète avec aide contextuelle |
| US6.2 | S | 0.25 | Système simple de tickets de support |

## Total global: 12.5 jours de développement

À ce total, il convient d'ajouter:
- Gestion de projet: 2.5 jours (20%)
- Tests et assurance qualité: 3.75 jours (30%)
- Contingence: 2.5 jours (20%)

**Effort total estimé: 21.25 jours**

## Facteurs de complexité considérés
- Complexité des interfaces utilisateur
- Sécurité et protection des données
- Performance sous charge
- Intégration avec des systèmes existants
- Contraintes techniques identifiées: {", ".join(technologies) if technologies else "à définir"}
</effort_estimation>

<roadmap>
# Roadmap du Projet

## Phase 1: Initialisation et Fondations (4 semaines)
- Mise en place de l'environnement de développement
- Développement de l'architecture de base
- Implémentation du système d'authentification
- **Epics concernés**: Epic 1, Epic 2
- **User Stories**: US1.1, US1.2, US2.1, US2.2, US2.3

## Phase 2: Fonctionnalités Essentielles (6 semaines)
- Développement des fonctionnalités principales
- Mise en place de la gestion des données
- Développement des interfaces utilisateur
- **Epics concernés**: Epic 3, Epic 4
- **User Stories**: US3.1, US3.2, US3.3, US4.1, US4.2

## Phase 3: Fonctionnalités Avancées (4 semaines)
- Implémentation des rapports et analyses
- Finalisation de la gestion des utilisateurs
- Développement des fonctionnalités de sauvegarde
- **Epics concernés**: Epic 2, Epic 4, Epic 5
- **User Stories**: US2.4, US4.3, US5.1, US5.2

## Phase 4: Finalisation et Déploiement (3 semaines)
- Documentation complète
- Tests finaux et corrections de bugs
- Déploiement et configuration de l'infrastructure
- Formation des utilisateurs
- **Epics concernés**: Epic 1, Epic 6
- **User Stories**: US1.3, US6.1, US6.2

## Jalons Clés
- **M1** (Fin Phase 1): Prototype fonctionnel avec authentification
- **M2** (Fin Phase 2): Version bêta avec fonctionnalités essentielles
- **M3** (Fin Phase 3): Version complète prête pour tests finaux
- **M4** (Fin Phase 4): Déploiement en production

## Planning prévisionnel
- **Début du projet**: 01/05/2023
- **Fin de la Phase 1**: 31/05/2023
- **Fin de la Phase 2**: 15/07/2023
- **Fin de la Phase 3**: 15/08/2023
- **Fin de la Phase 4 / Livraison finale**: 01/09/2023
</roadmap>

<methodology>
# Méthodologie du Projet

## Approche Agile Scrum

Le projet sera géré selon la méthodologie Agile Scrum, permettant une adaptation rapide aux besoins changeants et une livraison itérative de valeur.

### Organisation des Sprints
- **Durée des sprints**: 2 semaines
- **Réunions quotidiennes** (Daily Stand-up): 15 minutes chaque matin
- **Planification de sprint** au début de chaque sprint
- **Revue de sprint** à la fin de chaque sprint
- **Rétrospective** après chaque sprint pour amélioration continue

### Équipe Scrum
- **Product Owner**: Représentant du client
- **Scrum Master**: À désigner
- **Équipe de développement**: 3-5 développeurs, 1 designer UX/UI, 1 testeur

### Outils de gestion
- **Gestion de projet**: Jira ou Trello
- **Référentiel de code**: GitHub ou GitLab
- **Communication**: Slack et Microsoft Teams
- **Documentation**: Confluence ou Wiki interne

## Pratiques de Développement

### Développement
- **Intégration continue / Déploiement continu** (CI/CD)
- **Revue de code par les pairs** avant toute fusion dans la branche principale
- **Tests automatisés** (unitaires, d'intégration, fonctionnels)
- **Approche TDD** (Test-Driven Development) quand applicable

### Qualité
- **Standards de codage** définis et appliqués
- **Mesures de qualité de code** via SonarQube ou équivalent
- **Tests de non-régression** systématiques
- **Tests de performance** pour les fonctionnalités critiques

## Communication et Reporting

### Avec le client
- **Démonstration** à la fin de chaque sprint
- **Rapports d'avancement** bimensuels
- **Comité de pilotage** mensuel

### En interne
- **Tableau de bord** de progression visible par tous
- **Indicateurs de performance** (vélocité, dette technique, etc.)
- **Gestion des risques** mise à jour régulièrement

## Livraison et Déploiement
- **Environnements séparés**: développement, test, préproduction, production
- **Stratégie de déploiement** avec possibilité de rollback
- **Période de stabilisation** avant chaque mise en production majeure
- **Monitoring** post-déploiement
</methodology>

<risk_management>
# Analyse et Gestion des Risques

## Matrice d'évaluation
- **Probabilité**: 1 (Très faible) à 5 (Très élevée)
- **Impact**: 1 (Minimal) à 5 (Critique)
- **Criticité** = Probabilité × Impact

## Risques Identifiés

| ID | Description du risque | Probabilité | Impact | Criticité | Stratégie de mitigation |
|----|------------------------|------------|--------|-----------|-------------------------|
| R1 | Changements majeurs des exigences en cours de projet | 3 | 4 | 12 | Validation régulière avec le client, approche agile pour s'adapter aux changements |
| R2 | Difficultés techniques imprévues | 3 | 3 | 9 | Prototypage précoce des composants critiques, expertise technique mobilisable |
| R3 | Indisponibilité de ressources clés | 2 | 4 | 8 | Documentation continue, partage des connaissances, polyvalence de l'équipe |
| R4 | Problèmes d'intégration avec des systèmes existants | 3 | 4 | 12 | Tests d'intégration précoces, spécifications détaillées des interfaces |
| R5 | Performance insuffisante du système | 2 | 5 | 10 | Tests de charge réguliers, conception orientée performance |
| R6 | Problèmes de sécurité | 2 | 5 | 10 | Audits de sécurité réguliers, développement selon les bonnes pratiques de sécurité |
| R7 | Retards dans le développement | 3 | 3 | 9 | Suivi rigoureux de l'avancement, alertes précoces, ajustement des priorités |
| R8 | Problèmes de qualité affectant l'expérience utilisateur | 3 | 4 | 12 | Tests utilisateurs réguliers, implication précoce des utilisateurs finaux |
| R9 | Sous-estimation de l'effort nécessaire | 3 | 4 | 12 | Estimation avec marge, révision régulière des estimations, suivi de la vélocité |
| R10 | Problèmes de communication avec le client | 2 | 4 | 8 | Points de contact clairs, réunions régulières, documentation des décisions |

## Plan de contingence pour les risques critiques (≥ 12)

### R1: Changements majeurs des exigences
- Établir un processus formel de gestion des changements
- Prévoir une contingence budgétaire et temporelle de 20%
- Prioriser régulièrement les exigences avec le client

### R4: Problèmes d'intégration
- Désigner un responsable d'intégration
- Créer des environnements de test reproduisant les conditions réelles
- Préparer des alternatives techniques si nécessaire

### R8: Problèmes de qualité UX
- Mettre en place des tests utilisateurs dès les premières versions
- Impliquer un expert UX/UI dès la phase de conception
- Définir des critères d'acceptation précis pour chaque fonctionnalité

### R9: Sous-estimation de l'effort
- Appliquer une marge de 30% sur les estimations critiques
- Effectuer des estimations collaboratives (Planning Poker)
- Réévaluer les estimations au fur et à mesure du projet

## Suivi des risques
- Révision de la liste des risques à chaque réunion de planification de sprint
- Rapport d'état des risques lors des comités de pilotage
- Désignation d'un responsable pour chaque risque identifié
</risk_management>
</output>"""
    
    return demo_result

def save_analysis_result(result):
    """Sauvegarde le résultat d'analyse dans un fichier temporaire"""
    # Générer un ID unique pour ce résultat
    result_id = str(uuid.uuid4())
    
    # Créer un fichier pour stocker le résultat
    result_file = os.path.join(app.config['RESULTS_FOLDER'], f"{result_id}.json")
    
    # Stocker le résultat et l'ID dans le fichier
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump({'result': result}, f, ensure_ascii=False)
    
    return result_id

def get_analysis_result(result_id):
    """Récupère le résultat d'analyse à partir de son ID"""
    if not result_id:
        return None
    
    # Construire le chemin du fichier
    result_file = os.path.join(app.config['RESULTS_FOLDER'], f"{result_id}.json")
    
    # Vérifier si le fichier existe
    if not os.path.exists(result_file):
        return None
    
    # Lire le résultat à partir du fichier
    with open(result_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('result')

@app.route('/reset')
def reset_analysis():
    """Réinitialise l'analyse et la session"""
    session.clear()
    flash('Analyse réinitialisée')
    return redirect(url_for('home'))

@app.route('/')
def home():
    return render_template('index.html', title='Chronos')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('Aucun fichier sélectionné')
        return redirect(request.url)
    
    file = request.files['file']
    
    if file.filename == '':
        flash('Aucun fichier sélectionné')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Extraire le texte du PDF
        extracted_text = extract_text_from_pdf(file_path)
        
        # Stocker dans la session uniquement les informations essentielles
        session['pdf_text'] = extracted_text
        session['pdf_filename'] = filename
        
        return redirect(url_for('analyze'))
    else:
        flash('Format de fichier non autorisé. Veuillez télécharger un PDF.')
        return redirect(request.url)

@app.route('/analyze')
def analyze():
    if 'pdf_text' not in session or 'pdf_filename' not in session:
        flash('Veuillez d\'abord télécharger un fichier PDF')
        return redirect(url_for('home'))
    
    # Initialiser l'analyse
    analysis_sections = None
    formatted_sections = {}
    
    # Récupérer le résultat d'analyse s'il existe
    if 'analysis_id' in session:
        analysis_result = get_analysis_result(session['analysis_id'])
        if analysis_result:
            # Extraire les sections du résultat
            analysis_sections = extract_analysis_sections(analysis_result)
            
            # Convertir chaque section Markdown en HTML
            for section, content in analysis_sections.items():
                formatted_sections[section] = format_markdown_text(content)
    
    return render_template('analyze.html', 
                          title='Analyse du cahier des charges',
                          filename=session['pdf_filename'],
                          text=session['pdf_text'],
                          analysis_sections=formatted_sections)

@app.route('/run_analysis', methods=['POST'])
def run_analysis():
    if 'pdf_text' not in session:
        flash('Veuillez d\'abord télécharger un fichier PDF')
        return redirect(url_for('home'))
    
    # Récupérer les informations supplémentaires si renseignées
    additional_info = request.form.get('additional_info', '')
    
    # Exécuter l'analyse AMOA avec les informations supplémentaires
    analysis_result = analyze_requirements(session['pdf_text'], additional_info)
    
    # Sauvegarder le résultat dans un fichier et obtenir son ID
    result_id = save_analysis_result(analysis_result)
    
    # Stocker seulement l'ID dans la session
    session['analysis_id'] = result_id
    
    return redirect(url_for('analyze'))

if __name__ == '__main__':
    app.run(debug=True) 