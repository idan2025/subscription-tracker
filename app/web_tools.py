"""
Web Tools for AI Function Calling
Provides web search, pricing, reviews, and alternative finding capabilities
"""

import requests
from bs4 import BeautifulSoup
import json
from typing import Dict, List, Any, Optional
import time
import re
from datetime import datetime


class ToolExecutionError(Exception):
    """Custom exception for tool execution failures"""
    pass


class RateLimiter:
    """Simple rate limiter for web requests"""
    def __init__(self, max_calls_per_minute=10):
        self.max_calls = max_calls_per_minute
        self.calls = []

    def wait_if_needed(self):
        now = time.time()
        # Remove calls older than 1 minute
        self.calls = [t for t in self.calls if now - t < 60]

        if len(self.calls) >= self.max_calls:
            sleep_time = 60 - (now - self.calls[0])
            if sleep_time > 0:
                time.sleep(sleep_time)

        self.calls.append(now)


# Global rate limiter
rate_limiter = RateLimiter(max_calls_per_minute=10)


# ============ TOOL DEFINITIONS ============

TOOL_DEFINITIONS = {
    "search_web": {
        "name": "search_web",
        "description": "Search the web for current information about subscriptions, pricing, or alternatives. Use this when you need up-to-date information that may have changed since your knowledge cutoff.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query. Be specific and include keywords like 'subscription pricing 2026' or 'alternative to Netflix'"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (1-10)",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    },
    "get_subscription_pricing": {
        "name": "get_subscription_pricing",
        "description": "Get current pricing information for a specific subscription service. More focused than general web search.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Name of the subscription service (e.g., 'Netflix', 'Spotify Premium')"
                },
                "region": {
                    "type": "string",
                    "description": "Region/country for pricing (e.g., 'US', 'UK')",
                    "default": "US"
                }
            },
            "required": ["service_name"]
        }
    },
    "find_alternatives": {
        "name": "find_alternatives",
        "description": "Find alternative subscription services in a specific category. Returns real current alternatives with pricing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Current subscription service name"
                },
                "category": {
                    "type": "string",
                    "description": "Service category (e.g., 'streaming', 'music', 'productivity')"
                }
            },
            "required": ["service_name", "category"]
        }
    },
    "check_price_changes": {
        "name": "check_price_changes",
        "description": "Check if a subscription service has had recent price changes or increases.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Name of the subscription service"
                }
            },
            "required": ["service_name"]
        }
    }
}


# ============ FREE WEB SCRAPING IMPLEMENTATION ============

class FreeWebSearch:
    """Free web scraping implementation using requests + BeautifulSoup"""

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.timeout = 10

    def search_web(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        Search web using DuckDuckGo HTML (no API key needed)
        Returns list of search results
        """
        rate_limiter.wait_if_needed()

        try:
            # Use DuckDuckGo HTML (more reliable than scraping Google)
            url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            results = []

            # Parse DuckDuckGo results
            for result_div in soup.find_all('div', class_='result')[:max_results]:
                title_elem = result_div.find('a', class_='result__a')
                snippet_elem = result_div.find('a', class_='result__snippet')

                if title_elem:
                    results.append({
                        'title': title_elem.get_text(strip=True),
                        'url': title_elem.get('href', ''),
                        'snippet': snippet_elem.get_text(strip=True) if snippet_elem else ''
                    })

            return results

        except Exception as e:
            raise ToolExecutionError(f"Web search failed: {str(e)}")

    def get_subscription_pricing(self, service_name: str, region: str = "US") -> Dict:
        """Get pricing info by searching and parsing results"""
        query = f"{service_name} subscription pricing {region} 2026"
        results = self.search_web(query, max_results=3)

        # Extract pricing information from results
        pricing_info = {
            'service': service_name,
            'region': region,
            'sources': results,
            'estimated_price': self._extract_price_from_results(results),
            'last_updated': datetime.now().isoformat()
        }

        return pricing_info

    def _extract_price_from_results(self, results: List[Dict]) -> Optional[str]:
        """Try to extract price from search result snippets"""
        price_pattern = r'\$\d+\.?\d*\s*(?:per\s+)?(?:month|year|week)?'

        for result in results:
            text = f"{result.get('title', '')} {result.get('snippet', '')}"
            matches = re.findall(price_pattern, text, re.IGNORECASE)
            if matches:
                return matches[0]

        return None

    def find_alternatives(self, service_name: str, category: str) -> List[Dict]:
        """Find alternatives by searching"""
        query = f"alternatives to {service_name} {category} subscription 2026"
        results = self.search_web(query, max_results=5)

        # Parse results to extract alternative services
        alternatives = []
        for result in results:
            alternatives.append({
                'title': result['title'],
                'description': result['snippet'],
                'source_url': result['url']
            })

        return alternatives

    def check_price_changes(self, service_name: str) -> Dict:
        """Check for price changes"""
        query = f"{service_name} price increase 2025 2026"
        results = self.search_web(query, max_results=3)

        return {
            'service': service_name,
            'has_recent_changes': len(results) > 0,
            'news': results,
            'checked_at': datetime.now().isoformat()
        }


# ============ PAID API IMPLEMENTATIONS ============

class SerpAPISearch:
    """SerpAPI implementation (paid)"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://serpapi.com/search"

    def search_web(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search using SerpAPI"""
        rate_limiter.wait_if_needed()

        params = {
            'api_key': self.api_key,
            'q': query,
            'num': max_results
        }

        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get('organic_results', [])[:max_results]:
                results.append({
                    'title': item.get('title', ''),
                    'url': item.get('link', ''),
                    'snippet': item.get('snippet', '')
                })

            return results

        except Exception as e:
            raise ToolExecutionError(f"SerpAPI search failed: {str(e)}")

    def get_subscription_pricing(self, service_name: str, region: str = "US") -> Dict:
        """Get pricing using SerpAPI"""
        query = f"{service_name} subscription pricing {region} 2026"
        results = self.search_web(query, max_results=3)

        return {
            'service': service_name,
            'region': region,
            'sources': results,
            'last_updated': datetime.now().isoformat()
        }

    def find_alternatives(self, service_name: str, category: str) -> List[Dict]:
        """Find alternatives using SerpAPI"""
        query = f"alternatives to {service_name} {category} subscription 2026"
        results = self.search_web(query, max_results=5)

        alternatives = []
        for result in results:
            alternatives.append({
                'title': result['title'],
                'description': result['snippet'],
                'source_url': result['url']
            })

        return alternatives

    def check_price_changes(self, service_name: str) -> Dict:
        """Check for price changes using SerpAPI"""
        query = f"{service_name} price increase 2025 2026"
        results = self.search_web(query, max_results=3)

        return {
            'service': service_name,
            'has_recent_changes': len(results) > 0,
            'news': results,
            'checked_at': datetime.now().isoformat()
        }


class GoogleCustomSearch:
    """Google Custom Search API implementation (paid)"""

    def __init__(self, api_key: str, search_engine_id: str = None):
        self.api_key = api_key
        self.search_engine_id = search_engine_id or "default"
        self.base_url = "https://www.googleapis.com/customsearch/v1"

    def search_web(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search using Google Custom Search"""
        rate_limiter.wait_if_needed()

        params = {
            'key': self.api_key,
            'cx': self.search_engine_id,
            'q': query,
            'num': min(max_results, 10)  # Google Custom Search max is 10
        }

        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get('items', [])[:max_results]:
                results.append({
                    'title': item.get('title', ''),
                    'url': item.get('link', ''),
                    'snippet': item.get('snippet', '')
                })

            return results

        except Exception as e:
            raise ToolExecutionError(f"Google Custom Search failed: {str(e)}")

    def get_subscription_pricing(self, service_name: str, region: str = "US") -> Dict:
        """Get pricing using Google Custom Search"""
        query = f"{service_name} subscription pricing {region} 2026"
        results = self.search_web(query, max_results=3)

        return {
            'service': service_name,
            'region': region,
            'sources': results,
            'last_updated': datetime.now().isoformat()
        }

    def find_alternatives(self, service_name: str, category: str) -> List[Dict]:
        """Find alternatives using Google Custom Search"""
        query = f"alternatives to {service_name} {category} subscription 2026"
        results = self.search_web(query, max_results=5)

        alternatives = []
        for result in results:
            alternatives.append({
                'title': result['title'],
                'description': result['snippet'],
                'source_url': result['url']
            })

        return alternatives

    def check_price_changes(self, service_name: str) -> Dict:
        """Check for price changes using Google Custom Search"""
        query = f"{service_name} price increase 2025 2026"
        results = self.search_web(query, max_results=3)

        return {
            'service': service_name,
            'has_recent_changes': len(results) > 0,
            'news': results,
            'checked_at': datetime.now().isoformat()
        }


# ============ TOOL EXECUTOR ============

class ToolExecutor:
    """
    Executes tools and logs results
    Handles different search implementations
    """

    def __init__(self, search_method='free_scraping', search_api_key=None):
        self.search_method = search_method

        # Initialize appropriate search implementation
        if search_method == 'free_scraping':
            self.search_impl = FreeWebSearch()
        elif search_method == 'serpapi':
            if not search_api_key:
                raise ValueError("SerpAPI requires an API key")
            self.search_impl = SerpAPISearch(search_api_key)
        elif search_method == 'google_custom':
            if not search_api_key:
                raise ValueError("Google Custom Search requires an API key")
            self.search_impl = GoogleCustomSearch(search_api_key)
        else:
            raise ValueError(f"Unknown search method: {search_method}")

    def execute_tool(self, tool_name: str, tool_input: Dict) -> Dict:
        """
        Execute a tool and return results

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool

        Returns:
            Dict with tool execution results
        """
        start_time = time.time()

        try:
            if tool_name == "search_web":
                result = self.search_impl.search_web(
                    query=tool_input['query'],
                    max_results=tool_input.get('max_results', 5)
                )
            elif tool_name == "get_subscription_pricing":
                result = self.search_impl.get_subscription_pricing(
                    service_name=tool_input['service_name'],
                    region=tool_input.get('region', 'US')
                )
            elif tool_name == "find_alternatives":
                result = self.search_impl.find_alternatives(
                    service_name=tool_input['service_name'],
                    category=tool_input['category']
                )
            elif tool_name == "check_price_changes":
                result = self.search_impl.check_price_changes(
                    service_name=tool_input['service_name']
                )
            else:
                raise ToolExecutionError(f"Unknown tool: {tool_name}")

            execution_time = int((time.time() - start_time) * 1000)

            return {
                'success': True,
                'result': result,
                'execution_time_ms': execution_time,
                'tool_name': tool_name
            }

        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            return {
                'success': False,
                'error': str(e),
                'execution_time_ms': execution_time,
                'tool_name': tool_name
            }


# ============ HELPER FUNCTIONS ============

def get_tool_definitions_for_provider(provider: str) -> List[Dict]:
    """
    Get tool definitions formatted for specific AI provider

    Args:
        provider: 'claude', 'openai', or 'ollama'

    Returns:
        List of tool definitions in provider-specific format
    """
    if provider == 'claude':
        # Claude uses tools parameter with specific format
        return [
            {
                "name": tool_def["name"],
                "description": tool_def["description"],
                "input_schema": tool_def["input_schema"]
            }
            for tool_def in TOOL_DEFINITIONS.values()
        ]

    elif provider == 'openai':
        # OpenAI uses functions parameter with different format
        tools = []
        for tool_def in TOOL_DEFINITIONS.values():
            tools.append({
                "type": "function",
                "function": {
                    "name": tool_def["name"],
                    "description": tool_def["description"],
                    "parameters": tool_def["input_schema"]
                }
            })
        return tools

    elif provider == 'ollama':
        # Ollama uses similar format to OpenAI
        return [
            {
                "type": "function",
                "function": {
                    "name": tool_def["name"],
                    "description": tool_def["description"],
                    "parameters": tool_def["input_schema"]
                }
            }
            for tool_def in TOOL_DEFINITIONS.values()
        ]

    else:
        raise ValueError(f"Unknown provider: {provider}")
