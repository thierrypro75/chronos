import os
import json # Import json
from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env (peut rester pour SECRET_KEY si besoin)
load_dotenv()

# --- JSON Config Handling --- 
CONFIG_FILE = 'settings.json'

def load_config_from_json():
    """Charge la configuration depuis settings.json si elle existe."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error loading {CONFIG_FILE}: {e}")
    return {}

def save_config_to_json(config_data):
    """Sauvegarde la configuration actuelle dans settings.json."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4)
        print(f"Configuration saved to {CONFIG_FILE}")
    except IOError as e:
        print(f"Error saving to {CONFIG_FILE}: {e}")
# --- End JSON Config Handling ---

class Config:
    # Configuration de base
    SECRET_KEY = os.getenv('SECRET_KEY', 'chronos_secret_key')
    UPLOAD_FOLDER = 'uploads'
    RESULTS_FOLDER = 'results'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'pdf'}

    # --- Valeurs par défaut --- (utilisées si rien dans settings.json)
    _defaults = {
        'AI_PROVIDER': 'anthropic',
        'ANTHROPIC_API_KEY': '',
        'ANTHROPIC_MODEL': 'claude-3.5-sonnet-20240620',
        'OPENAI_API_KEY': '',
        'OPENAI_MODEL': 'gpt-4-turbo-preview',
        'OPENROUTER_API_KEY': '',
        'OPENROUTER_MODEL': 'anthropic/claude-3-opus-20240229'
    }

    # --- Charger depuis JSON et définir les attributs --- 
    _loaded_config = load_config_from_json()
    
    AI_PROVIDER = _loaded_config.get('AI_PROVIDER', _defaults['AI_PROVIDER'])
    ANTHROPIC_API_KEY = _loaded_config.get('ANTHROPIC_API_KEY', _defaults['ANTHROPIC_API_KEY'])
    ANTHROPIC_MODEL = _loaded_config.get('ANTHROPIC_MODEL', _defaults['ANTHROPIC_MODEL'])
    OPENAI_API_KEY = _loaded_config.get('OPENAI_API_KEY', _defaults['OPENAI_API_KEY'])
    OPENAI_MODEL = _loaded_config.get('OPENAI_MODEL', _defaults['OPENAI_MODEL'])
    OPENROUTER_API_KEY = _loaded_config.get('OPENROUTER_API_KEY', _defaults['OPENROUTER_API_KEY'])
    OPENROUTER_MODEL = _loaded_config.get('OPENROUTER_MODEL', _defaults['OPENROUTER_MODEL'])

    # Les méthodes supprimées (get_api_key, get_model) restent supprimées
    # @staticmethod
    # def get_api_key():
    #     # ...

    # @staticmethod
    # def get_model():
    #     # ... 