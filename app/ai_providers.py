"""
AI Provider Abstraction Layer
Supports Claude (Anthropic), OpenAI, and Ollama providers
"""

from abc import ABC, abstractmethod
import anthropic
from openai import OpenAI
import requests
import json


class BaseAIProvider(ABC):
    """Abstract base class for AI providers"""

    @abstractmethod
    def test_connection(self):
        """
        Test connection to AI provider
        Returns: dict with {success: bool, message: str, provider: str}
        """
        pass

    @abstractmethod
    def generate_response(self, prompt, context=None):
        """
        Generate AI response
        Args:
            prompt: The user prompt/question
            context: Optional context/system message
        Returns: str with AI response
        """
        pass


class ClaudeProvider(BaseAIProvider):
    """Anthropic Claude provider"""

    def __init__(self, api_key):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-3-5-sonnet-20241022"

    def test_connection(self):
        """Test Claude API connection"""
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}]
            )
            return {
                "success": True,
                "message": "Successfully connected to Claude API",
                "provider": "Claude"
            }
        except anthropic.AuthenticationError:
            return {
                "success": False,
                "message": "Invalid API key. Please check your Anthropic API key.",
                "provider": "Claude"
            }
        except anthropic.PermissionDeniedError:
            return {
                "success": False,
                "message": "Permission denied. Check your API key permissions.",
                "provider": "Claude"
            }
        except anthropic.RateLimitError:
            return {
                "success": False,
                "message": "Rate limit exceeded. Please try again later.",
                "provider": "Claude"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Connection failed: {str(e)}",
                "provider": "Claude"
            }

    def generate_response(self, prompt, context=None):
        """Generate response using Claude"""
        try:
            # Build the full prompt with context if provided
            full_prompt = f"{context}\n\n{prompt}" if context else prompt

            message = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": full_prompt}]
            )

            return message.content[0].text

        except anthropic.AuthenticationError:
            raise Exception("AI authentication failed. Please check API key in admin settings.")
        except anthropic.RateLimitError:
            raise Exception("AI rate limit reached. Please try again later.")
        except Exception as e:
            raise Exception(f"AI service error: {str(e)}")


class OpenAIProvider(BaseAIProvider):
    """OpenAI GPT provider"""

    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"

    def test_connection(self):
        """Test OpenAI API connection"""
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}]
            )
            return {
                "success": True,
                "message": "Successfully connected to OpenAI API",
                "provider": "OpenAI"
            }
        except Exception as e:
            error_message = str(e)
            if "authentication" in error_message.lower() or "api_key" in error_message.lower():
                return {
                    "success": False,
                    "message": "Invalid API key. Please check your OpenAI API key.",
                    "provider": "OpenAI"
                }
            elif "rate" in error_message.lower() or "limit" in error_message.lower():
                return {
                    "success": False,
                    "message": "Rate limit exceeded. Please try again later.",
                    "provider": "OpenAI"
                }
            else:
                return {
                    "success": False,
                    "message": f"Connection failed: {error_message}",
                    "provider": "OpenAI"
                }

    def generate_response(self, prompt, context=None):
        """Generate response using OpenAI"""
        try:
            messages = []
            if context:
                messages.append({"role": "system", "content": context})
            messages.append({"role": "user", "content": prompt})

            completion = self.client.chat.completions.create(
                model=self.model,
                max_tokens=2000,
                messages=messages
            )

            return completion.choices[0].message.content

        except Exception as e:
            error_message = str(e)
            if "authentication" in error_message.lower() or "api_key" in error_message.lower():
                raise Exception("AI authentication failed. Please check API key in admin settings.")
            elif "rate" in error_message.lower() or "limit" in error_message.lower():
                raise Exception("AI rate limit reached. Please try again later.")
            else:
                raise Exception(f"AI service error: {error_message}")


class OllamaProvider(BaseAIProvider):
    """Ollama (self-hosted) provider"""

    def __init__(self, server_url, model="llama3.2"):
        self.server_url = server_url.rstrip('/')
        self.model = model
        self.timeout = 60

    def test_connection(self):
        """Test Ollama server connection"""
        try:
            response = requests.post(
                f"{self.server_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": "Hi",
                    "stream": False
                },
                timeout=10
            )

            if response.status_code == 200:
                return {
                    "success": True,
                    "message": f"Successfully connected to Ollama server at {self.server_url}",
                    "provider": "Ollama"
                }
            elif response.status_code == 404:
                return {
                    "success": False,
                    "message": f"Model '{self.model}' not found. Please pull the model first: ollama pull {self.model}",
                    "provider": "Ollama"
                }
            else:
                return {
                    "success": False,
                    "message": f"Server returned status code {response.status_code}",
                    "provider": "Ollama"
                }

        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "message": f"Cannot connect to Ollama server at {self.server_url}. Is Ollama running?",
                "provider": "Ollama"
            }
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "message": "Connection timeout. Ollama server is not responding.",
                "provider": "Ollama"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Connection failed: {str(e)}",
                "provider": "Ollama"
            }

    def generate_response(self, prompt, context=None):
        """Generate response using Ollama"""
        try:
            # Build the full prompt with context if provided
            full_prompt = f"{context}\n\n{prompt}" if context else prompt

            response = requests.post(
                f"{self.server_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False
                },
                timeout=self.timeout
            )

            response.raise_for_status()
            result = response.json()
            return result.get('response', '')

        except requests.exceptions.ConnectionError:
            raise Exception("Cannot connect to Ollama server. Please check if Ollama is running.")
        except requests.exceptions.Timeout:
            raise Exception("Ollama request timed out. The model may be taking too long to respond.")
        except Exception as e:
            raise Exception(f"Ollama service error: {str(e)}")


class AIProviderFactory:
    """Factory class to create AI provider instances"""

    @staticmethod
    def get_provider(provider_name, api_key, ollama_model=None):
        """
        Create and return an AI provider instance

        Args:
            provider_name: str ('claude', 'openai', or 'ollama')
            api_key: str (API key for Claude/OpenAI, or server URL for Ollama)
            ollama_model: str (optional, model name for Ollama)

        Returns:
            BaseAIProvider instance

        Raises:
            ValueError: If provider_name is invalid
        """
        provider_name = provider_name.lower()

        if provider_name == 'claude':
            return ClaudeProvider(api_key)
        elif provider_name == 'openai':
            return OpenAIProvider(api_key)
        elif provider_name == 'ollama':
            model = ollama_model if ollama_model else "llama3.2"
            return OllamaProvider(api_key, model)
        else:
            raise ValueError(f"Unknown provider: {provider_name}. Supported providers: claude, openai, ollama")
