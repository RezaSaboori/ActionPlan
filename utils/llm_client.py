"""LLM Client wrapper for Ollama and OpenAI-compatible APIs."""

import json
import logging
import time
import re
from typing import Any, Dict, List, Optional, Union

import requests
from openai import OpenAI
from config.settings import get_settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Per-agent LLM client with retry logic and JSON support."""
    
    def __init__(
        self,
        provider: str = "ollama",
        model: str = "gpt-oss:20b",
        temperature: float = 0.1,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout: int = 3000
    ):
        """
        Initialize LLM client with specific configuration.
        
        Args:
            provider: Provider type ('ollama' or 'openai')
            model: Model name to use
            temperature: Default temperature for generations
            api_key: API key for OpenAI-compatible provider
            api_base: Base URL for OpenAI-compatible provider
            timeout: Request timeout in seconds
        """
        self.settings = get_settings()
        self.provider = provider.lower()
        # Normalize gapgpt to openai internally
        if self.provider == "gapgpt":
            self.provider = "openai"
        
        self.model = model
        self.default_temperature = temperature
        self.timeout = timeout
        self.openai_client: Optional[OpenAI] = None
        
        # Initialize based on provider
        if self.provider == "openai":
            if not api_key or not api_base:
                logger.warning(f"OpenAI/GapGPT provider requires api_key and api_base. Falling back to Ollama.")
                self._initialize_ollama()
            else:
                try:
                    self.openai_client = OpenAI(
                        base_url=api_base,
                        api_key=api_key,
                    )
                    logger.info(f"Initialized OpenAI-compatible client: model={self.model}")
                except Exception as e:
                    logger.error(f"Failed to initialize OpenAI client: {e}. Falling back to Ollama.")
                    self._initialize_ollama()
        else:
            self._initialize_ollama()
    
    def _initialize_ollama(self):
        """Initialize the Ollama client."""
        self.provider = "ollama"
        self.base_url = self.settings.ollama_base_url
        self.timeout = self.settings.ollama_timeout
        logger.info(f"Initialized Ollama client: model={self.model}")
    
    @classmethod
    def create_for_agent(cls, agent_name: str, dynamic_settings=None) -> 'LLMClient':
        """
        Factory method to create LLMClient for a specific agent.
        
        Args:
            agent_name: Name of the agent (e.g., 'orchestrator', 'analyzer')
            dynamic_settings: DynamicSettingsManager instance (optional)
            
        Returns:
            Configured LLMClient instance
        """
        if dynamic_settings is not None:
            # Get configuration from dynamic settings
            config = dynamic_settings.get_agent_config(agent_name)
            return cls(
                provider=config.provider,
                model=config.model,
                temperature=config.temperature,
                api_key=config.api_key,
                api_base=config.api_base
            )
        else:
            # Fallback to base settings
            base_settings = get_settings()
            provider = getattr(base_settings, f"{agent_name}_provider", "ollama")
            model = getattr(base_settings, f"{agent_name}_model", "gpt-oss:20b")
            temperature = getattr(base_settings, f"{agent_name}_temperature", 0.1)
            api_key = getattr(base_settings, f"{agent_name}_api_key", None)
            api_base = getattr(base_settings, f"{agent_name}_api_base", None)
            
            return cls(
                provider=provider,
                model=model,
                temperature=temperature,
                api_key=api_key,
                api_base=api_base
            )

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
        Generate text completion from the configured LLM.
        """
        if self.provider == "openai" and self.openai_client:
            return self._generate_openai(prompt, system_prompt, temperature, max_tokens, stream, model_override)
        else:
            return self._generate_ollama(prompt, system_prompt, temperature, max_tokens, stream, model_override)

    def _generate_openai(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        model_override: Optional[str] = None
    ) -> str:
        """Generate text using OpenAI-compatible client."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self.openai_client.chat.completions.create(
                model=model_override or self.model,
                messages=messages,
                temperature=temperature or self.default_temperature,
                max_tokens=max_tokens,
                stream=stream
            )
            if stream:
                # Streaming not fully implemented for this example, handle as needed
                return "Streamed response handling not implemented."
            
            content = response.choices[0].message.content
            
            # Debug logging for empty responses
            if not content or not content.strip():
                logger.warning(
                    f"Model returned empty content. "
                    f"Finish reason: {response.choices[0].finish_reason}, "
                    f"Model: {response.model}, "
                    f"Prompt tokens: {response.usage.prompt_tokens if response.usage else 'N/A'}, "
                    f"Completion tokens: {response.usage.completion_tokens if response.usage else 'N/A'}"
                )
            
            return content or ""
        except Exception as e:
            logger.error(f"Error in OpenAI generate: {e}")
            raise

    def _generate_ollama(
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
        """
        if temperature is None:
            temperature = self.default_temperature
            
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
        model_override: Optional[str] = None,
        json_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Generate JSON output from the configured LLM with validation.
        """
        if self.provider == "openai" and self.openai_client:
            return self._generate_json_openai(prompt, system_prompt, schema, temperature, model_override)
        else:
            return self._generate_json_ollama(prompt, system_prompt, schema, temperature, model_override, json_mode)

    def _generate_json_openai(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        model_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate JSON using OpenAI-compatible client."""
        enhanced_prompt = f"{prompt}\n\nRespond ONLY with valid JSON."
        if schema:
             enhanced_prompt += f"\n\nFollow this schema: {json.dumps(schema, indent=2)}"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": enhanced_prompt})

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.openai_client.chat.completions.create(
                    model=model_override or self.model,
                    messages=messages,
                    temperature=temperature or self.default_temperature,
                    response_format={"type": "json_object"}
                )
                content = response.choices[0].message.content
                if content:
                    return json.loads(content)
                raise ValueError("Empty content from API")
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"JSON decode error on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                     raise ValueError(f"Failed to parse JSON after {max_retries} attempts")
            except Exception as e:
                logger.error(f"Error in generate_json_openai on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    raise
            time.sleep(1)
        raise ValueError("Failed to generate valid JSON")

    def _generate_json_ollama(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        model_override: Optional[str] = None,
        json_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Generate JSON output from Ollama with validation.
        """
        if temperature is None:
            temperature = self.default_temperature
        
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

    def _parse_json_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extract and parse a JSON object from a string, potentially wrapped in markdown.
        
        Args:
            text: The text containing the JSON object.
            
        Returns:
            A dictionary parsed from the JSON object.
        """
        # Regex to find JSON block within ```json ... ```
        json_match = re.search(r"```json\s*([\s\S]*?)\s*```", text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            # Fallback for plain JSON that might have surrounding text
            json_match = re.search(r"{\s*[\s\S]*?\s*}", text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                logger.error("No valid JSON found in the LLM response.")
                return {"error": "No valid JSON found in response", "raw_response": text}

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON after extraction: {e}")
            return {"error": "Failed to decode extracted JSON", "extracted_string": json_str}
    
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
        """Check if the configured LLM server is accessible."""
        if self.provider == "openai":
            try:
                # Make a simple request to check connectivity, e.g., list models
                self.openai_client.models.list()
                logger.info("OpenAI client connection successful.")
                return True
            except Exception as e:
                logger.error(f"OpenAI client connection check failed: {e}")
                return False
        else: # ollama
            try:
                response = requests.get(f"{self.base_url}/api/tags", timeout=5)
                return response.status_code == 200
            except Exception as e:
                logger.error(f"Ollama connection check failed: {e}")
                return False

