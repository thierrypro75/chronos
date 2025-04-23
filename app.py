from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
import PyPDF2
import re
import json
import uuid
import time
import traceback
from werkzeug.utils import secure_filename
from config import Config, save_config_to_json
from ai_providers import get_provider, AIProvider
import anthropic
import openai

app = Flask(__name__)
app.config.from_object(Config)

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
    """Analyse le cahier des charges en utilisant le provider d'IA configuré, en deux étapes si nécessaire."""
    provider_name = Config.AI_PROVIDER
    analysis_result_part1 = None
    analysis_result_part2 = None
    
    try:
        # --- Configuration Retrieval & Get Provider --- 
        provider_name = Config.AI_PROVIDER
        api_key = ''
        model = ''
        if provider_name == 'anthropic':
            api_key = Config.ANTHROPIC_API_KEY
            model = Config.ANTHROPIC_MODEL
        elif provider_name == 'openai':
            api_key = Config.OPENAI_API_KEY
            model = Config.OPENAI_MODEL
        elif provider_name == 'openrouter':
            api_key = Config.OPENROUTER_API_KEY
            model = Config.OPENROUTER_MODEL
        
        if not api_key:
            raise ValueError(f"Clé API non configurée pour le provider {provider_name}.")
            
        provider: AIProvider = get_provider(provider_name=provider_name, api_key=api_key, model=model)

        # --- Appel 1: Sections 1-3 --- 
        print("--- Calling AI for Part 1 (Charter, Backlog, Estimation) ---")
        prompt_part1 = f"""Analyse le cahier des charges suivant et génère les 3 premières sections demandées.

        Texte du cahier des charges:
        {pdf_content}
        
        Informations supplémentaires:
        {additional_info}
        
        Génère UNIQUEMENT les sections suivantes:
        1. Charte de projet (<project_charter>...</project_charter>)
        2. Backlog produit (<product_backlog>...</product_backlog>)
        3. Estimation d'effort (<effort_estimation>...</effort_estimation>)
        
        Format de sortie attendu (UNIQUEMENT ces 3 sections):
        <output_part1>
        <project_charter>
        ...
</project_charter>
<product_backlog>
        ...
</product_backlog>
<effort_estimation>
        ...
        </effort_estimation>
        </output_part1>
        """
        analysis_result_part1 = provider.analyze_text(prompt_part1, "")
        
        if not analysis_result_part1:
             raise Exception("Échec de la première partie de l'analyse.")
        print("--- Part 1 Analysis Received ---")

        # --- Appel 2: Sections 4-6 --- 
        print("--- Calling AI for Part 2 (Roadmap, Methodology, Risks) ---")
        prompt_part2 = f"""En te basant sur le cahier des charges original et la première partie de l'analyse fournie ci-dessous, génère les 3 DERNIÈRES sections demandées.
        
        Texte du cahier des charges original (pour référence):
        {pdf_content}

        Informations supplémentaires originales (pour référence):
        {additional_info}

        Première partie de l'analyse (Charte, Backlog, Estimation):
        {analysis_result_part1}

        Génère UNIQUEMENT les sections suivantes, en assurant la cohérence avec la première partie:
        4. Roadmap (<roadmap>...</roadmap>)
        5. Méthodologie (<methodology>...</methodology>)
        6. Gestion des risques (<risk_management>...</risk_management>)

        Format de sortie attendu (UNIQUEMENT ces 3 sections):
        <output_part2>
<roadmap>
        ...
</roadmap>
<methodology>
        ...
</methodology>
<risk_management>
        ...
        </risk_management>
        </output_part2>
        """
        analysis_result_part2 = provider.analyze_text(prompt_part2, "")

        if not analysis_result_part2:
             raise Exception("Échec de la deuxième partie de l'analyse.")
        print("--- Part 2 Analysis Received ---")

        # --- Robust Extraction & Combination --- 
        sections_content = {}
        section_names = ['project_charter', 'product_backlog', 'effort_estimation', 'roadmap', 'methodology', 'risk_management']
        
        # Extract from Part 1 result
        for i in range(3):
            section = section_names[i]
            pattern = f'<{section}>(.*?)</{section}>'
            match = re.search(pattern, analysis_result_part1, re.DOTALL)
            if match:
                sections_content[section] = match.group(1).strip()
            else:
                print(f"WARN: Section '{section}' not found in Part 1 result.")
                sections_content[section] = "" # Add empty string if not found
                
        # Extract from Part 2 result
        for i in range(3, 6):
            section = section_names[i]
            pattern = f'<{section}>(.*?)</{section}>'
            match = re.search(pattern, analysis_result_part2, re.DOTALL)
            if match:
                sections_content[section] = match.group(1).strip()
            else:
                print(f"WARN: Section '{section}' not found in Part 2 result.")
                sections_content[section] = "" # Add empty string if not found

        # Combine extracted sections into the final format
        final_result = "<output>\n"
        for section in section_names:
            final_result += f"<{section}>\n{sections_content.get(section, '')}\n</{section}>\n"
        final_result += "</output>"
        
        print("--- Analysis Parts Extracted and Combined ---")
        return final_result

    except Exception as e:
        print(f"--- ERROR in analyze_requirements ({provider_name}): {type(e).__name__} - {e} ---")
        if isinstance(e, ValueError) and "Clé API non configurée" in str(e):
             flash(str(e))
        elif isinstance(e, (anthropic.AuthenticationError, openai.AuthenticationError)):
             flash(f"Erreur d'authentification {provider_name.capitalize()}: Vérifiez votre clé API.")
        else:
             flash(f"Erreur lors de l'analyse ({provider_name}): {str(e)}") 
        return None

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

@app.route('/config')
def config():
    """Affiche la page de configuration"""
    return render_template('config.html', title='Configuration', config=Config)

@app.route('/save_config', methods=['POST'])
def save_config():
    """Sauvegarde la configuration en mémoire ET dans settings.json."""
    # --- Mise à jour en mémoire --- 
    Config.AI_PROVIDER = request.form.get('ai_provider', Config._defaults['AI_PROVIDER']) # Use default if missing
    Config.ANTHROPIC_API_KEY = request.form.get('anthropic_api_key', Config._defaults['ANTHROPIC_API_KEY'])
    # Utiliser la valeur par défaut correcte du config.py si le formulaire ne la renvoie pas
    Config.ANTHROPIC_MODEL = request.form.get('anthropic_model', Config._defaults['ANTHROPIC_MODEL'])
    
    Config.OPENAI_API_KEY = request.form.get('openai_api_key', Config._defaults['OPENAI_API_KEY'])
    Config.OPENAI_MODEL = request.form.get('openai_model', Config._defaults['OPENAI_MODEL'])
    
    Config.OPENROUTER_API_KEY = request.form.get('openrouter_api_key', Config._defaults['OPENROUTER_API_KEY'])
    Config.OPENROUTER_MODEL = request.form.get('openrouter_model', Config._defaults['OPENROUTER_MODEL'])

    # --- Sauvegarde persistante en JSON --- 
    current_config_data = {
        'AI_PROVIDER': Config.AI_PROVIDER,
        'ANTHROPIC_API_KEY': Config.ANTHROPIC_API_KEY,
        'ANTHROPIC_MODEL': Config.ANTHROPIC_MODEL,
        'OPENAI_API_KEY': Config.OPENAI_API_KEY,
        'OPENAI_MODEL': Config.OPENAI_MODEL,
        'OPENROUTER_API_KEY': Config.OPENROUTER_API_KEY,
        'OPENROUTER_MODEL': Config.OPENROUTER_MODEL
    }
    save_config_to_json(current_config_data)
    
    flash('Configuration sauvegardée avec succès.') # Message flash mis à jour
    return redirect(url_for('config'))

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
    
    additional_info = request.form.get('additional_info', '')
    
    # analyze_requirements gère maintenant les deux appels
    analysis_result = analyze_requirements(session['pdf_text'], additional_info)
    
    # --- Log Raw Output (Combined) --- 
    print("\n--- FINAL Combined Analysis Result ---")
    if analysis_result:
        print(analysis_result) # Log the combined result
    else:
        print("<No combined result generated>")
    print("--------------------------------------\n")
    # --- End Log Raw Output ---
    
    if analysis_result:
        result_id = save_analysis_result(analysis_result)
        session['analysis_id'] = result_id
        flash('Analyse terminée avec succès')
    else:
        pass # Error flash handled in analyze_requirements
    
    return redirect(url_for('analyze'))

if __name__ == '__main__':
    app.run(debug=True) 