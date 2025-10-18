"""Ollama LLM Client wrapper with JSON support and error handling."""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Union
import requests
from config.settings import get_settings

logger = logging.getLogger(__name__)


class OllamaClient:
    """Singleton wrapper for Ollama API with retry logic and JSON support."""
    
    _instance: Optional['OllamaClient'] = None
    
    def __new__(cls):
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the Ollama client."""
        if self._initialized:
            return
            
        self.settings = get_settings()
        self.base_url = self.settings.ollama_base_url
        self.model = self.settings.ollama_model
        self.timeout = self.settings.ollama_timeout
        self._initialized = True
        logger.info(f"Initialized OllamaClient with model: {self.model}")
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        model_override: Optional[str] = None
    ) -> str:
        """
        Generate text completion from Ollama.
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt for context
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response
            model_override: Optional model name to override default
            
        Returns:
            Generated text response
        """
        if temperature is None:
            temperature = self.settings.ollama_temperature
            
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": model_override or self.model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": temperature
            }
        }
        
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        
        try:
            response = self._make_request("/api/chat", payload)
            return response.get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"Error in generate: {e}")
            raise
    
    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        model_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate JSON output from Ollama with validation.
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            schema: Optional JSON schema for validation
            temperature: Sampling temperature
            model_override: Optional model name to override default
            
        Returns:
            Parsed JSON dictionary
        """
        if temperature is None:
            temperature = self.settings.ollama_temperature
        
        # Enhance prompt to request JSON
        enhanced_prompt = f"{prompt}\n\nRespond ONLY with valid JSON. Do not include any explanation or text outside the JSON structure."
        
        if schema:
            enhanced_prompt += f"\n\nFollow this schema: {json.dumps(schema, indent=2)}"
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": enhanced_prompt})
        
        payload = {
            "model": model_override or self.model,
            "messages": messages,
            "format": "json",  # Enable JSON mode in Ollama
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self._make_request("/api/chat", payload)
                content = response.get("message", {}).get("content", "")
                
                # Parse JSON
                result = json.loads(content)
                logger.debug(f"Successfully generated JSON on attempt {attempt + 1}")
                return result
                
            except json.JSONDecodeError as e:
                logger.warning(f"JSON decode error on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    # Last attempt, try to extract JSON from text
                    content = response.get("message", {}).get("content", "")
                    result = self._extract_json_from_text(content)
                    if result:
                        return result
                    raise ValueError(f"Failed to parse JSON after {max_retries} attempts: {content[:200]}")
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in generate_json on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(1)
        
        raise ValueError("Failed to generate valid JSON")
    
    def _extract_json_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Try to extract JSON from text that might have extra content."""
        try:
            # Find JSON object boundaries
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end > start:
                json_str = text[start:end]
                return json.loads(json_str)
        except Exception as e:
            logger.debug(f"Failed to extract JSON from text: {e}")
        return None
    
    def _make_request(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        retry_count: int = 3
    ) -> Dict[str, Any]:
        """Make HTTP request to Ollama API with retry logic."""
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(retry_count):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout on attempt {attempt + 1}")
                if attempt == retry_count - 1:
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error on attempt {attempt + 1}: {e}")
                if attempt == retry_count - 1:
                    raise
                time.sleep(2 ** attempt)
        
        raise RuntimeError("Max retries exceeded")
    
    def check_connection(self) -> bool:
        """Check if Ollama server is accessible."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Connection check failed: {e}")
            return False

