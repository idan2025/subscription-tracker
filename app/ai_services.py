"""
AI Services - Business Logic for AI Features
Handles alternatives finding, spending analysis, recommendations, and chat
"""

import mysql.connector
from mysql.connector import Error
import os
import json
from ai_providers import AIProviderFactory


# Database configuration (same as app.py)
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'rootpassword'),
    'database': os.getenv('DB_NAME', 'subscription_tracker')
}


def get_db_connection():
    """Create and return a database connection"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None


def get_ai_settings():
    """
    Fetch AI settings from database
    Returns: dict with settings or None if AI disabled
    """
    connection = get_db_connection()
    if not connection:
        return None

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admin_settings WHERE id = 1")
        settings = cursor.fetchone()
        cursor.close()
        connection.close()

        if not settings or not settings.get('ai_enabled'):
            return None

        if not settings.get('api_key_encrypted') or settings.get('ai_provider') == 'none':
            return None

        return settings

    except Error as e:
        print(f"Error fetching AI settings: {e}")
        return None


def get_tool_settings():
    """
    Get tool calling configuration from database
    Returns: dict with tool settings or None
    """
    connection = get_db_connection()
    if not connection:
        return None

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT internet_access_enabled, search_method,
                   search_api_key, tool_calling_enabled
            FROM admin_settings WHERE id = 1
        """)
        settings = cursor.fetchone()
        cursor.close()
        connection.close()
        return settings
    except Error as e:
        print(f"Error fetching tool settings: {e}")
        return None


def should_use_tools(ai_settings):
    """
    Determine if tool calling should be used

    Args:
        ai_settings: Admin settings dict

    Returns:
        Boolean indicating if tools should be used
    """
    if not ai_settings:
        return False

    # Check if internet access is enabled
    if not ai_settings.get('internet_access_enabled', False):
        return False

    # Check if tool calling is globally enabled (dev flag)
    if not ai_settings.get('tool_calling_enabled', True):
        return False

    return True


def get_user_subscriptions_context(user_id):
    """
    Get user's subscriptions and build context for AI
    Returns: formatted string with subscription data
    """
    connection = get_db_connection()
    if not connection:
        return ""

    try:
        cursor = connection.cursor(dictionary=True)

        # Get all active subscriptions
        cursor.execute("""
            SELECT * FROM subscriptions
            WHERE user_id = %s AND status = 'active'
            ORDER BY cost DESC
        """, (user_id,))
        subscriptions = cursor.fetchall()

        # Calculate totals
        cursor.execute("""
            SELECT
                COUNT(*) as total_count,
                SUM(CASE
                    WHEN billing_cycle = 'monthly' THEN cost
                    WHEN billing_cycle = 'yearly' THEN cost / 12
                    WHEN billing_cycle = 'weekly' THEN cost * 4.33
                END) as monthly_cost,
                SUM(CASE
                    WHEN billing_cycle = 'monthly' THEN cost * 12
                    WHEN billing_cycle = 'yearly' THEN cost
                    WHEN billing_cycle = 'weekly' THEN cost * 52
                END) as yearly_cost
            FROM subscriptions
            WHERE user_id = %s AND status = 'active'
        """, (user_id,))
        totals = cursor.fetchone()

        cursor.close()
        connection.close()

        # Build context string
        context = f"User's Subscription Portfolio:\n"
        context += f"Total Active Subscriptions: {totals['total_count']}\n"
        context += f"Monthly Cost: ${float(totals['monthly_cost'] or 0):.2f}\n"
        context += f"Yearly Cost: ${float(totals['yearly_cost'] or 0):.2f}\n\n"
        context += "Individual Subscriptions:\n"

        for sub in subscriptions:
            context += f"- {sub['name']}: ${sub['cost']}/{sub['billing_cycle']}"
            if sub['category']:
                context += f" ({sub['category']})"
            context += "\n"

        return context

    except Error as e:
        print(f"Error getting user subscriptions: {e}")
        return ""


def find_alternatives(subscription_id, user_id):
    """
    Find cheaper alternatives for a subscription using AI

    Args:
        subscription_id: int - ID of the subscription
        user_id: int - User ID for authorization

    Returns:
        dict with alternatives array or error
    """
    # Check AI settings
    settings = get_ai_settings()
    if not settings:
        return {"error": "AI features are disabled", "status": 403}

    if not settings.get('feature_alternatives'):
        return {"error": "Alternatives finder feature is disabled", "status": 403}

    # Get subscription details
    connection = get_db_connection()
    if not connection:
        return {"error": "Database connection failed", "status": 503}

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM subscriptions
            WHERE id = %s AND user_id = %s
        """, (subscription_id, user_id))
        subscription = cursor.fetchone()
        cursor.close()
        connection.close()

        if not subscription:
            return {"error": "Subscription not found", "status": 404}

        # Create AI provider instance
        provider = AIProviderFactory.get_provider(
            settings['ai_provider'],
            settings['api_key_encrypted'],
            settings.get('ollama_model')
        )

        # Check if we should use tools
        use_tools = should_use_tools(settings)

        if use_tools and provider.supports_tool_calling:
            # Tool calling path
            from web_tools import get_tool_definitions_for_provider, ToolExecutor

            tools = get_tool_definitions_for_provider(settings['ai_provider'])
            tool_executor = ToolExecutor(
                search_method=settings.get('search_method', 'free_scraping'),
                search_api_key=settings.get('search_api_key')
            )

            prompt = f"""The user has a subscription to: {subscription['name']}
Current cost: ${subscription['cost']} per {subscription['billing_cycle']}
Category: {subscription.get('category', 'Unknown')}

Find 3-5 cheaper or better-value alternatives. Use the available tools to search for current pricing and real alternatives.

After gathering information, respond with a JSON array in this format:
[
    {{
        "name": "Alternative Service Name",
        "description": "Brief description",
        "price": "$X.XX/month",
        "differences": "Key differences"
    }}
]"""

            context = "You are a subscription cost optimization assistant with access to real-time web search. Use the tools to find current, accurate information about alternatives and pricing."

            # Generate response with tools
            response = provider.generate_response_with_tools(
                prompt=prompt,
                context=context,
                tools=tools,
                tool_executor=tool_executor
            )
        else:
            # Fallback to prompt-based approach
            prompt = f"""You are a subscription cost optimization assistant.

The user has a subscription to: {subscription['name']}
Current cost: ${subscription['cost']} per {subscription['billing_cycle']}
Category: {subscription.get('category', 'Unknown')}

Please suggest 3-5 cheaper or better-value alternatives. For each alternative, provide:
1. Name of the service
2. Brief description (1-2 sentences)
3. Pricing information
4. Key differences from the original service

IMPORTANT: Respond ONLY with a valid JSON array. No other text.
Format your response exactly like this:
[
    {{
        "name": "Alternative Service Name",
        "description": "Brief description of what this service offers",
        "price": "$9.99/month",
        "differences": "Key differences from {subscription['name']}"
    }}
]"""

            response = provider.generate_response(prompt)

        # Parse JSON response
        try:
            # Try to extract JSON from response
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                alternatives = json.loads(json_str)
                return {"alternatives": alternatives, "source": "ai", "status": 200}
            else:
                # Fallback: return response as text
                return {
                    "alternatives": [{
                        "name": "AI Suggestions",
                        "description": response,
                        "price": "Varies",
                        "differences": "See description for details"
                    }],
                    "source": "ai",
                    "status": 200
                }
        except json.JSONDecodeError:
            # Fallback: return response as single alternative
            return {
                "alternatives": [{
                    "name": "AI Suggestions",
                    "description": response,
                    "price": "Varies",
                    "differences": "See AI response for alternatives"
                }],
                "source": "ai",
                "status": 200
            }

    except Exception as e:
        return {"error": str(e), "status": 503}


def get_spending_analysis(user_id):
    """
    Get AI-powered spending analysis for user

    Args:
        user_id: int - User ID

    Returns:
        dict with insights array or error
    """
    # Check AI settings
    settings = get_ai_settings()
    if not settings:
        return {"error": "AI features are disabled", "status": 403}

    if not settings.get('feature_analysis'):
        return {"error": "Analysis feature is disabled", "status": 403}

    try:
        # Get user subscription context
        context = get_user_subscriptions_context(user_id)

        if not context or "Total Active Subscriptions: 0" in context:
            return {
                "insights": [{
                    "title": "No Subscriptions Yet",
                    "description": "Add some subscriptions to get AI-powered insights on your spending patterns."
                }],
                "status": 200
            }

        # Create AI provider instance
        provider = AIProviderFactory.get_provider(
            settings['ai_provider'],
            settings['api_key_encrypted'],
            settings.get('ollama_model')
        )

        # Check if we should use tools
        use_tools = should_use_tools(settings)

        if use_tools and provider.supports_tool_calling:
            # Tool calling path
            from web_tools import get_tool_definitions_for_provider, ToolExecutor

            tools = get_tool_definitions_for_provider(settings['ai_provider'])
            tool_executor = ToolExecutor(
                search_method=settings.get('search_method', 'free_scraping'),
                search_api_key=settings.get('search_api_key')
            )

            prompt = f"""{context}

Analyze this user's subscription spending and provide 3-5 key insights. Use tools to check if any services have had recent price increases.

Respond with JSON:
{{
    "insights": [
        {{
            "title": "Brief insight title",
            "description": "Detailed explanation"
        }}
    ]
}}"""

            system_context = "You are a subscription spending analyst with access to real-time price change information. Use tools when needed."

            response = provider.generate_response_with_tools(
                prompt=prompt,
                context=system_context,
                tools=tools,
                tool_executor=tool_executor
            )
        else:
            # Fallback to prompt-based approach
            prompt = f"""{context}

Analyze this user's subscription spending and provide 3-5 key insights about their spending patterns, potential areas for cost reduction, and any concerning trends.

IMPORTANT: Respond ONLY with a valid JSON object. No other text.
Format your response exactly like this:
{{
    "insights": [
        {{
            "title": "Brief insight title",
            "description": "Detailed explanation of the insight"
        }}
    ]
}}"""

            response = provider.generate_response(prompt)

        # Parse JSON response
        try:
            # Try to extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
                return {"insights": data.get('insights', []), "status": 200}
            else:
                # Fallback
                return {
                    "insights": [{
                        "title": "AI Analysis",
                        "description": response
                    }],
                    "status": 200
                }
        except json.JSONDecodeError:
            return {
                "insights": [{
                    "title": "AI Analysis",
                    "description": response
                }],
                "status": 200
            }

    except Exception as e:
        return {"error": str(e), "status": 503}


def get_recommendations(user_id):
    """
    Get personalized AI recommendations for user

    Args:
        user_id: int - User ID

    Returns:
        dict with recommendations array or error
    """
    # Check AI settings
    settings = get_ai_settings()
    if not settings:
        return {"error": "AI features are disabled", "status": 403}

    if not settings.get('feature_recommendations'):
        return {"error": "Recommendations feature is disabled", "status": 403}

    try:
        # Get user subscription context
        context = get_user_subscriptions_context(user_id)

        if not context or "Total Active Subscriptions: 0" in context:
            return {
                "recommendations": [{
                    "title": "Start Adding Subscriptions",
                    "description": "Add your subscriptions to get personalized AI recommendations for optimizing your spending.",
                    "savings": "N/A",
                    "priority": "low"
                }],
                "status": 200
            }

        # Create AI provider instance
        provider = AIProviderFactory.get_provider(
            settings['ai_provider'],
            settings['api_key_encrypted'],
            settings.get('ollama_model')
        )

        # Check if we should use tools
        use_tools = should_use_tools(settings)

        if use_tools and provider.supports_tool_calling:
            # Tool calling path
            from web_tools import get_tool_definitions_for_provider, ToolExecutor

            tools = get_tool_definitions_for_provider(settings['ai_provider'])
            tool_executor = ToolExecutor(
                search_method=settings.get('search_method', 'free_scraping'),
                search_api_key=settings.get('search_api_key')
            )

            prompt = f"""{context}

Provide 3-5 personalized recommendations to help reduce costs and optimize value. Use tools to find current deals or pricing.

Respond with JSON:
{{
    "recommendations": [
        {{
            "title": "Recommendation title",
            "description": "Detailed explanation",
            "savings": "$10/month",
            "priority": "high"
        }}
    ]
}}"""

            system_context = "You are a subscription optimization advisor with access to real-time pricing and deals. Use tools when helpful."

            response = provider.generate_response_with_tools(
                prompt=prompt,
                context=system_context,
                tools=tools,
                tool_executor=tool_executor
            )
        else:
            # Fallback to prompt-based approach
            prompt = f"""{context}

Based on this subscription portfolio, provide 3-5 personalized recommendations to help the user:
1. Reduce costs
2. Optimize value
3. Consolidate services
4. Cancel underused subscriptions

For each recommendation, include:
- title: Brief title
- description: Detailed explanation
- savings: Estimated savings (if applicable, e.g., "$10/month" or "N/A")
- priority: high, medium, or low

IMPORTANT: Respond ONLY with a valid JSON object. No other text.
Format your response exactly like this:
{{
    "recommendations": [
        {{
            "title": "Recommendation title",
            "description": "Detailed explanation",
            "savings": "$10/month",
            "priority": "high"
        }}
    ]
}}"""

            response = provider.generate_response(prompt)

        # Parse JSON response
        try:
            # Try to extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
                return {"recommendations": data.get('recommendations', []), "status": 200}
            else:
                # Fallback
                return {
                    "recommendations": [{
                        "title": "AI Recommendations",
                        "description": response,
                        "savings": "Varies",
                        "priority": "medium"
                    }],
                    "status": 200
                }
        except json.JSONDecodeError:
            return {
                "recommendations": [{
                    "title": "AI Recommendations",
                    "description": response,
                    "savings": "Varies",
                    "priority": "medium"
                }],
                "status": 200
            }

    except Exception as e:
        return {"error": str(e), "status": 503}


def chat_with_ai(message, user_id, conversation_history=None):
    """
    Chat with AI assistant about subscriptions

    Args:
        message: str - User's message
        user_id: int - User ID
        conversation_history: list - Optional conversation history

    Returns:
        dict with response or error
    """
    # Check AI settings
    settings = get_ai_settings()
    if not settings:
        return {"error": "AI features are disabled", "status": 403}

    if not settings.get('feature_chat'):
        return {"error": "Chat feature is disabled", "status": 403}

    try:
        # Get user subscription context
        context = get_user_subscriptions_context(user_id)

        # Create AI provider instance
        provider = AIProviderFactory.get_provider(
            settings['ai_provider'],
            settings['api_key_encrypted'],
            settings.get('ollama_model')
        )

        # Check if we should use tools
        use_tools = should_use_tools(settings)

        # Build system message with context
        if use_tools and provider.supports_tool_calling:
            system_context = f"""You are a helpful subscription management assistant with access to real-time web search.

{context}

You can use the available tools to search for current pricing, alternatives, and price changes. Answer the user's questions about their subscriptions, help them optimize costs, suggest alternatives, and provide insights. Be concise, friendly, and helpful."""
        else:
            system_context = f"""You are a helpful subscription management assistant.

{context}

Answer the user's questions about their subscriptions, help them optimize costs, suggest alternatives, and provide insights. Be concise, friendly, and helpful."""

        # Build full prompt with conversation history
        if conversation_history:
            full_prompt = system_context + "\n\nConversation history:\n"
            for msg in conversation_history[-10:]:  # Last 10 messages
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                full_prompt += f"{role.capitalize()}: {content}\n"
            full_prompt += f"\nUser: {message}\nAssistant:"
        else:
            full_prompt = system_context + f"\n\nUser: {message}\nAssistant:"

        # Generate response
        if use_tools and provider.supports_tool_calling:
            from web_tools import get_tool_definitions_for_provider, ToolExecutor

            tools = get_tool_definitions_for_provider(settings['ai_provider'])
            tool_executor = ToolExecutor(
                search_method=settings.get('search_method', 'free_scraping'),
                search_api_key=settings.get('search_api_key')
            )

            response = provider.generate_response_with_tools(
                prompt=message,
                context=system_context,
                tools=tools,
                tool_executor=tool_executor
            )
        else:
            response = provider.generate_response(full_prompt)

        return {
            "response": response,
            "status": 200
        }

    except Exception as e:
        return {"error": str(e), "status": 503}
