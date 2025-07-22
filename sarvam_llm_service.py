"""
Stripped-down Sarvam LLM Service for product assistant.
Provides synchronous API calls with retry logic and error handling.
"""

import os
import time
import json
import logging
from typing import Dict, List, Optional, Any
import requests
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass
class SarvamConfig:
    """Configuration for Sarvam LLM service loaded from environment variables."""
    api_key: str
    api_url: str
    model: str
    timeout: int
    max_retries: int


class SarvamLLMService:
    """
    Synchronous Sarvam LLM service with retry logic and error handling.
    Loads configuration from environment variables.
    """
    
    def __init__(self):
        """Initialize the service with configuration from environment variables."""
        # Load environment variables from local .env file
        load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))
        
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config()
        self.session = requests.Session()
        
        # Set up session headers
        self.session.headers.update({
            'Authorization': f'Bearer {self.config.api_key}',
            'Content-Type': 'application/json'
        })
    
    def _load_config(self) -> SarvamConfig:
        """Load configuration from environment variables."""
        try:
            config = SarvamConfig(
                api_key=os.getenv('SARVAM_API_KEY', ''),
                api_url=os.getenv('SARVAM_API_URL', 'https://api.sarvam.ai/v1/chat/completions'),
                model=os.getenv('SARVAM_MODEL', 'sarvam-m'),
                timeout=int(os.getenv('SARVAM_TIMEOUT', '30')),
                max_retries=int(os.getenv('SARVAM_MAX_RETRIES', '3'))
            )
            
            if not config.api_key:
                raise ValueError("SARVAM_API_KEY environment variable is required")
            
            return config
            
        except (ValueError, TypeError) as e:
            self.logger.error(f"Configuration error: {e}")
            raise
    
    def simple_completion(
        self, 
        prompt: str, 
        system_message: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """
        Generate a simple completion for a given prompt.
        
        Args:
            prompt: The user prompt
            system_message: Optional system message
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens in response
            
        Returns:
            Generated text response
            
        Raises:
            Exception: If API call fails after all retries
        """
        messages = []
        
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            response_data = self._make_request_with_retry(payload)
            return self._extract_content_from_response(response_data)
            
        except Exception as e:
            self.logger.error(f"Simple completion failed: {e}")
            raise
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> Dict[str, Any]:
        """
        Generate a chat completion for a conversation.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens in response
            
        Returns:
            Full response dictionary from API
            
        Raises:
            Exception: If API call fails after all retries
        """
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            response_data = self._make_request_with_retry(payload)
            return response_data
            
        except Exception as e:
            self.logger.error(f"Chat completion failed: {e}")
            raise
    
    def _make_request_with_retry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make API request with exponential backoff retry mechanism.
        
        Args:
            payload: Request payload
            
        Returns:
            Response data dictionary
            
        Raises:
            Exception: If all retries fail
        """
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                self.logger.debug(f"API request attempt {attempt + 1}")
                
                response = self.session.post(
                    self.config.api_url,
                    json=payload,
                    timeout=self.config.timeout
                )
                
                # Handle different HTTP status codes
                if response.status_code == 200:
                    return response.json()
                
                elif response.status_code == 401:
                    error_msg = "Authentication failed. Please check your SARVAM_API_KEY."
                    self.logger.error(error_msg)
                    raise Exception(error_msg)
                
                elif response.status_code == 429:
                    # Rate limiting - should retry
                    self.logger.warning(f"Rate limited (429). Attempt {attempt + 1}")
                    if attempt < self.config.max_retries:
                        self._wait_with_backoff(attempt)
                        continue
                    else:
                        raise Exception("Rate limit exceeded after all retries")
                
                elif 500 <= response.status_code < 600:
                    # Server errors - should retry
                    self.logger.warning(f"Server error {response.status_code}. Attempt {attempt + 1}")
                    if attempt < self.config.max_retries:
                        self._wait_with_backoff(attempt)
                        continue
                    else:
                        raise Exception(f"Server error {response.status_code} after all retries")
                
                else:
                    # Other client errors - don't retry
                    error_msg = f"API request failed with status {response.status_code}: {response.text}"
                    self.logger.error(error_msg)
                    raise Exception(error_msg)
                    
            except requests.exceptions.Timeout:
                self.logger.warning(f"Request timeout. Attempt {attempt + 1}")
                last_exception = Exception("Request timeout")
                if attempt < self.config.max_retries:
                    self._wait_with_backoff(attempt)
                    continue
                    
            except requests.exceptions.ConnectionError:
                self.logger.warning(f"Connection error. Attempt {attempt + 1}")
                last_exception = Exception("Connection error")
                if attempt < self.config.max_retries:
                    self._wait_with_backoff(attempt)
                    continue
                    
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request exception: {e}")
                last_exception = e
                if attempt < self.config.max_retries:
                    self._wait_with_backoff(attempt)
                    continue
                    
            except json.JSONDecodeError as e:
                self.logger.error(f"JSON decode error: {e}")
                last_exception = e
                break  # Don't retry JSON decode errors
                
        # If we get here, all retries failed
        if last_exception:
            raise last_exception
        else:
            raise Exception("API request failed after all retries")
    
    def _wait_with_backoff(self, attempt: int) -> None:
        """
        Wait with exponential backoff between retries.
        
        Args:
            attempt: Current attempt number (0-based)
        """
        # Exponential backoff: 1s, 2s, 4s, 8s, etc.
        wait_time = 2 ** attempt
        self.logger.debug(f"Waiting {wait_time} seconds before retry")
        time.sleep(wait_time)
    
    def _extract_content_from_response(self, response_data: Dict[str, Any]) -> str:
        """
        Extract content from API response.
        
        Args:
            response_data: Full API response
            
        Returns:
            Extracted content string
            
        Raises:
            Exception: If response format is unexpected
        """
        try:
            choices = response_data.get('choices', [])
            if not choices:
                raise Exception("No choices in API response")
            
            message = choices[0].get('message', {})
            content = message.get('content', '')
            
            if not content:
                raise Exception("No content in API response")
            
            return content.strip()
            
        except (KeyError, IndexError, TypeError) as e:
            self.logger.error(f"Error parsing API response: {e}")
            self.logger.debug(f"Response data: {response_data}")
            raise Exception(f"Invalid API response format: {e}")