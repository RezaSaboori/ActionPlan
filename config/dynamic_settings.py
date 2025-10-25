"""Dynamic Settings Manager for runtime LLM configuration per agent."""

import logging
from typing import Dict, Any, Optional
from config.settings import get_settings, Settings

logger = logging.getLogger(__name__)


class AgentLLMConfig:
    """Configuration for a single agent's LLM."""
    
    def __init__(
        self,
        provider: str = "ollama",
        model: str = "gpt-oss:20b",
        temperature: float = 0.1,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None
    ):
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.api_key = api_key
        self.api_base = api_base
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature,
            "api_key": self.api_key,
            "api_base": self.api_base
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentLLMConfig':
        """Create from dictionary."""
        return cls(
            provider=data.get("provider", "ollama"),
            model=data.get("model", "gpt-oss:20b"),
            temperature=data.get("temperature", 0.1),
            api_key=data.get("api_key"),
            api_base=data.get("api_base")
        )
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate configuration."""
        if self.provider not in ["ollama", "openai", "gapgpt"]:
            return False, f"Invalid provider: {self.provider}. Must be 'ollama', 'openai', or 'gapgpt'."
        
        if not self.model or not self.model.strip():
            return False, "Model name cannot be empty."
        
        if not (0.0 <= self.temperature <= 2.0):
            return False, f"Temperature must be between 0.0 and 2.0, got {self.temperature}."
        
        if self.provider in ["openai", "gapgpt"]:
            if not self.api_key or not self.api_key.strip():
                return False, f"API key is required for {self.provider} provider."
            if not self.api_base or not self.api_base.strip():
                return False, f"API base URL is required for {self.provider} provider."
        
        return True, None


class DynamicSettingsManager:
    """Manages dynamic per-agent LLM configurations with runtime updates."""
    
    # List of all configurable agents
    AGENT_NAMES = [
        "orchestrator",
        "analyzer",
        "extractor",
        "deduplicator",
        "prioritizer",
        "assigner",
        "quality_checker",
        "formatter",
        "phase3",
        "translator",
        "summarizer"
    ]
    
    def __init__(self, base_settings: Optional[Settings] = None):
        """
        Initialize dynamic settings manager.
        
        Args:
            base_settings: Base settings to use (defaults to get_settings())
        """
        self.base_settings = base_settings or get_settings()
        self._agent_configs: Dict[str, AgentLLMConfig] = {}
        self._load_from_base_settings()
    
    def _load_from_base_settings(self):
        """Load agent configurations from base settings."""
        for agent_name in self.AGENT_NAMES:
            provider = getattr(self.base_settings, f"{agent_name}_provider", "ollama")
            model = getattr(self.base_settings, f"{agent_name}_model", "gpt-oss:20b")
            temperature = getattr(self.base_settings, f"{agent_name}_temperature", 0.1)
            api_key = getattr(self.base_settings, f"{agent_name}_api_key", None)
            api_base = getattr(self.base_settings, f"{agent_name}_api_base", None)
            
            self._agent_configs[agent_name] = AgentLLMConfig(
                provider=provider,
                model=model,
                temperature=temperature,
                api_key=api_key,
                api_base=api_base
            )
        
        logger.info(f"Loaded configurations for {len(self._agent_configs)} agents")
    
    def get_agent_config(self, agent_name: str) -> AgentLLMConfig:
        """
        Get configuration for a specific agent.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            AgentLLMConfig for the agent
        """
        if agent_name not in self._agent_configs:
            logger.warning(f"Agent '{agent_name}' not found, returning default config")
            return AgentLLMConfig()
        
        return self._agent_configs[agent_name]
    
    def update_agent_config(
        self,
        agent_name: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Update configuration for a specific agent.
        
        Args:
            agent_name: Name of the agent
            provider: LLM provider (ollama/openai)
            model: Model name
            temperature: Temperature setting
            api_key: API key for OpenAI
            api_base: API base URL for OpenAI
            
        Returns:
            Tuple of (success, error_message)
        """
        if agent_name not in self.AGENT_NAMES:
            return False, f"Unknown agent: {agent_name}"
        
        # Get current config or create new one
        current_config = self._agent_configs.get(agent_name, AgentLLMConfig())
        
        # Update fields
        new_config = AgentLLMConfig(
            provider=provider if provider is not None else current_config.provider,
            model=model if model is not None else current_config.model,
            temperature=temperature if temperature is not None else current_config.temperature,
            api_key=api_key if api_key is not None else current_config.api_key,
            api_base=api_base if api_base is not None else current_config.api_base
        )
        
        # Validate
        is_valid, error_msg = new_config.validate()
        if not is_valid:
            return False, error_msg
        
        # Apply
        self._agent_configs[agent_name] = new_config
        logger.info(f"Updated configuration for agent '{agent_name}': provider={new_config.provider}, model={new_config.model}")
        
        return True, None
    
    def update_agent_config_dict(self, agent_name: str, config_dict: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Update agent configuration from dictionary.
        
        Args:
            agent_name: Name of the agent
            config_dict: Dictionary with config values
            
        Returns:
            Tuple of (success, error_message)
        """
        return self.update_agent_config(
            agent_name=agent_name,
            provider=config_dict.get("provider"),
            model=config_dict.get("model"),
            temperature=config_dict.get("temperature"),
            api_key=config_dict.get("api_key"),
            api_base=config_dict.get("api_base")
        )
    
    def reset_to_defaults(self, agent_name: Optional[str] = None):
        """
        Reset agent configuration(s) to defaults from base settings.
        
        Args:
            agent_name: Specific agent to reset, or None to reset all
        """
        if agent_name:
            if agent_name in self.AGENT_NAMES:
                provider = getattr(self.base_settings, f"{agent_name}_provider", "ollama")
                model = getattr(self.base_settings, f"{agent_name}_model", "gpt-oss:20b")
                temperature = getattr(self.base_settings, f"{agent_name}_temperature", 0.1)
                api_key = getattr(self.base_settings, f"{agent_name}_api_key", None)
                api_base = getattr(self.base_settings, f"{agent_name}_api_base", None)
                
                self._agent_configs[agent_name] = AgentLLMConfig(
                    provider=provider,
                    model=model,
                    temperature=temperature,
                    api_key=api_key,
                    api_base=api_base
                )
                logger.info(f"Reset agent '{agent_name}' to defaults")
        else:
            self._load_from_base_settings()
            logger.info("Reset all agents to defaults")
    
    def get_all_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all agent configurations as a dictionary.
        
        Returns:
            Dictionary mapping agent names to their configurations
        """
        return {
            agent_name: config.to_dict()
            for agent_name, config in self._agent_configs.items()
        }
    
    def set_all_provider(self, provider: str, keep_models: bool = True):
        """
        Set all agents to use the same provider.
        
        Args:
            provider: Provider to use (ollama/openai/gapgpt)
            keep_models: If True, keep existing model names; if False, use default for provider
        """
        if provider not in ["ollama", "openai", "gapgpt"]:
            logger.error(f"Invalid provider: {provider}")
            return
        
        for agent_name in self.AGENT_NAMES:
            config = self._agent_configs[agent_name]
            config.provider = provider
            
            if not keep_models:
                # Reset to default model for provider
                if provider == "ollama":
                    config.model = "gpt-oss:20b"
                elif provider in ["openai", "gapgpt"]:
                    config.model = "gemini-2.5-flash"
        
        logger.info(f"Set all agents to provider '{provider}'")
    
    def get_base_settings(self) -> Settings:
        """Get the base settings object."""
        return self.base_settings

