"""Description generator using Perplexity AI API."""

import logging
import time
from typing import Dict, Optional
import requests
from config.settings import get_settings
from config.prompts import DESCRIPTION_GENERATOR_PROMPT

logger = logging.getLogger(__name__)


class DescriptionGenerator:
    """Generate descriptions using Perplexity AI API."""
    
    def __init__(self):
        """Initialize description generator with settings."""
        self.settings = get_settings()
        self.api_key = self.settings.perplexity_api_key
        self.api_url = self.settings.perplexity_api_url
        self.model = self.settings.perplexity_model
        self.temperature = self.settings.perplexity_temperature
        
        if not self.api_key:
            logger.warning("Perplexity API key not configured. Description generation will fail.")
    
    def generate_description(self, user_config: Dict[str, str]) -> str:
        """
        Generate environmental description using Perplexity API based on user configuration.
        Focuses on environmental impacts and consequences of subject area on the action plan title.
        
        Args:
            user_config: Dictionary containing:
                - name: the action plan title
                - subject: war | sanction
        
        Returns:
            Generated environmental description string, or "Not provided" if API call fails
        """
        if not self.api_key:
            logger.error("Cannot generate description: Perplexity API key not configured")
            return "Not provided"
        
        # Format subject with explanation if it's "sanction" (like orchestrator does)
        subject_value = user_config.get("subject", "")
        sanction_explanation = "externally imposed economic and trade restrictions that block access to essential medicines, cripple health infrastructure, drive health workers to leave"
        
        if subject_value and subject_value.lower() == "sanction":
            subject_display = f"sanction: {sanction_explanation}"
        else:
            subject_display = subject_value
        
        # Format the prompt (only name and subject needed for environmental description)
        user_message = DESCRIPTION_GENERATOR_PROMPT.format(
            name=user_config.get("name", ""),
            subject=subject_display
        )
        
        # Prepare API payload
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert-level Health Command System architect and crisis operations strategist. list direct answers without introductions or self-identification."
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            "search_mode": "web",
            "reasoning_effort": "medium",
            "temperature": self.temperature,
            "top_p": 0.9,
            "return_images": False,
            "return_related_questions": False,
            "top_k": 0,
            "stream": False,
            "presence_penalty": 0,
            "frequency_penalty": 0,
            "disable_search": False,
            "enable_search_classifier": False,
            "web_search_options": {
                "search_context_size": "low",
                "image_search_relevance_enhanced": False
            },
            "media_response": {
                "overrides": {
                    "return_videos": False,
                    "return_images": False
                }
            }
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Make API call with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"Calling Perplexity API (attempt {attempt + 1}/{max_retries})")
                response = requests.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=60
                )
                response.raise_for_status()
                
                result = response.json()
                description = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                if description:
                    logger.info("Successfully generated description from Perplexity API")
                    return description.strip()
                else:
                    logger.warning("Perplexity API returned empty description")
                    return "Not provided"
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Perplexity API timeout on attempt {attempt + 1}")
                if attempt == max_retries - 1:
                    logger.error("Perplexity API timeout after all retries")
                    return "Not provided"
                time.sleep(2 ** attempt)  # Exponential backoff
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Perplexity API error on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    logger.error("Perplexity API failed after all retries")
                    return "Not provided"
                time.sleep(2 ** attempt)
                
            except Exception as e:
                logger.error(f"Unexpected error calling Perplexity API: {e}")
                return "Not provided"
        
        return "Not provided"

