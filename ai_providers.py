from abc import ABC, abstractmethod
import anthropic
import openai
import requests
from config import Config
import httpx
try:
    from importlib import metadata
except ImportError:
    import importlib_metadata as metadata

# Helper to mask API keys in logs
def mask_key(api_key):
    if not api_key or len(api_key) < 8:
        return "<empty_or_short>"
    return f"{api_key[:4]}...{api_key[-4:]}"

class AIProvider(ABC):
    @abstractmethod
    def analyze_text(self, text: str, additional_info: str = "") -> str:
        pass

class AnthropicProvider(AIProvider):
    # Accept api_key and model during initialization
    def __init__(self, api_key: str, model: str):
        # Removed debug prints
        self.api_key = api_key 
        self.model = model
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def analyze_text(self, text: str, additional_info: str = "") -> str:
        # Removed debug print
        prompt = f"""Analyse le cahier des charges suivant et génère les artefacts de projet demandés.
        
        Texte du cahier des charges:
        {text}
        
        Informations supplémentaires:
        {additional_info}
        
        Génère une analyse complète avec les sections suivantes:
        1. Charte de projet
        2. Backlog produit
        3. Estimation d'effort
        4. Roadmap
        5. Méthodologie
        6. Gestion des risques
        
        Format de sortie attendu:
        <output>
        <project_charter>
        # Charte de Projet
        ...
        </project_charter>
        
        <product_backlog>
        # Backlog Produit
        ...
        </product_backlog>
        
        <effort_estimation>
        # Estimation de l'Effort
        ...
        </effort_estimation>
        
        <roadmap>
        # Roadmap
        ...
        </roadmap>
        
        <methodology>
        # Méthodologie
        ...
        </methodology>
        
        <risk_management>
        # Gestion des Risques
        ...
        </risk_management>
        </output>
        """

        response = self.client.messages.create(
            model=self.model,
            max_tokens=8000,
            temperature=0.7,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        return response.content[0].text

class OpenAIProvider(AIProvider):
    # Accept api_key and model during initialization
    def __init__(self, api_key: str, model: str):
        # Removed debug prints
        self.api_key = api_key
        self.model = model
        self.client = openai.OpenAI(api_key=self.api_key)

    def analyze_text(self, text: str, additional_info: str = "") -> str:
        # Removed debug print
        prompt = f"""Analyse le cahier des charges suivant et génère les artefacts de projet demandés.
        
        Texte du cahier des charges:
        {text}
        
        Informations supplémentaires:
        {additional_info}
        
        Génère une analyse complète avec les sections suivantes:
        1. Charte de projet
        2. Backlog produit
        3. Estimation d'effort
        4. Roadmap
        5. Méthodologie
        6. Gestion des risques
        
        Format de sortie attendu:
        <output>
        <project_charter>
        # Charte de Projet
        ...
        </project_charter>
        
        <product_backlog>
        # Backlog Produit
        ...
        </product_backlog>
        
        <effort_estimation>
        # Estimation de l'Effort
        ...
        </effort_estimation>
        
        <roadmap>
        # Roadmap
        ...
        </roadmap>
        
        <methodology>
        # Méthodologie
        ...
        </methodology>
        
        <risk_management>
        # Gestion des Risques
        ...
        </risk_management>
        </output>
        """

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4000
        )
        
        return response.choices[0].message.content

class OpenRouterProvider(AIProvider):
    # Accept api_key and model during initialization
    def __init__(self, api_key: str, model: str):
        # Removed debug prints
        self.api_key = api_key 
        self.model = model
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"

    def analyze_text(self, text: str, additional_info: str = "") -> str:
        # Removed debug print
        prompt = f"""Analyse le cahier des charges suivant et génère les artefacts de projet demandés.
        
        Texte du cahier des charges:
        {text}
        
        Informations supplémentaires:
        {additional_info}
        
        Génère une analyse complète avec les sections suivantes:
        1. Charte de projet
        2. Backlog produit
        3. Estimation d'effort
        4. Roadmap
        5. Méthodologie
        6. Gestion des risques
        
        Format de sortie attendu:
        <output>
        <project_charter>
        # Charte de Projet
        ...
        </project_charter>
        
        <product_backlog>
        # Backlog Produit
        ...
        </product_backlog>
        
        <effort_estimation>
        # Estimation de l'Effort
        ...
        </effort_estimation>
        
        <roadmap>
        # Roadmap
        ...
        </roadmap>
        
        <methodology>
        # Méthodologie
        ...
        </methodology>
        
        <risk_management>
        # Gestion des Risques
        ...
        </risk_management>
        </output>
        """

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 4000
        }

        response = requests.post(self.api_url, headers=headers, json=data)
        response.raise_for_status()
        
        return response.json()["choices"][0]["message"]["content"]

# Accept api_key and model as arguments
def get_provider(provider_name: str, api_key: str, model: str) -> AIProvider:
    """Retourne le provider d'IA approprié selon la configuration"""
    provider_name = provider_name.lower()
    # Removed debug print
    
    if provider_name == 'anthropic':
        return AnthropicProvider(api_key=api_key, model=model)
    elif provider_name == 'openai':
        return OpenAIProvider(api_key=api_key, model=model)
    elif provider_name == 'openrouter':
        return OpenRouterProvider(api_key=api_key, model=model)
    else:
        raise ValueError(f"Provider d'IA non supporté: {provider_name}") 