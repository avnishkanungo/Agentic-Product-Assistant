"""
LlamaIndex Agent with Custom LLM Wrapper for Product Assistant.

This module provides a custom LLM wrapper that integrates Sarvam service with LlamaIndex
and implements the ReAct agent pattern for function calling.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from llama_index.core.llms.custom import CustomLLM
from llama_index.core.llms.callbacks import llm_completion_callback
from llama_index.core.base.llms.types import (
    LLMMetadata,
    CompletionResponse,
    CompletionResponseGen,
    ChatMessage,
    ChatResponse,
    ChatResponseGen,
    MessageRole
)
from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool

try:
    # Try relative imports first (when used as module)
    from .sarvam_llm_service import SarvamLLMService
    from .rag_engine import RAGEngine
    from .order_processor import OrderProcessor
except ImportError:
    # Fall back to absolute imports (when run directly)
    from sarvam_llm_service import SarvamLLMService
    from rag_engine import RAGEngine
    from order_processor import OrderProcessor


class SarvamLLMWrapper(CustomLLM):
    """
    Custom LLM wrapper to integrate Sarvam service with LlamaIndex.
    
    This wrapper allows LlamaIndex to use Sarvam-m LLM for function calling
    and response generation in the stripped-down version.
    """
    
    def __init__(self, sarvam_service: SarvamLLMService, **kwargs):
        """Initialize the Sarvam LLM wrapper."""
        super().__init__(**kwargs)
        # Use object.__setattr__ to bypass Pydantic validation
        object.__setattr__(self, 'sarvam_service', sarvam_service)
        object.__setattr__(self, 'logger', logging.getLogger(__name__))
    
    @property
    def metadata(self) -> LLMMetadata:
        """Get LLM metadata."""
        return LLMMetadata(
            context_window=4096,
            num_output=1024,
            model_name="sarvam-m"
        )
    
    @llm_completion_callback()
    def complete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        """Complete a prompt using Sarvam-m LLM."""
        try:
            response_text = self.sarvam_service.simple_completion(
                prompt=prompt,
                temperature=kwargs.get('temperature', 0.7),
                max_tokens=kwargs.get('max_tokens', 512)
            )
            return CompletionResponse(text=response_text)
        except Exception as e:
            self.logger.error(f"Sarvam completion failed: {e}")
            raise Exception(f"LLM completion failed: {e}")
    
    @llm_completion_callback()
    def stream_complete(self, prompt: str, **kwargs: Any) -> CompletionResponseGen:
        """Stream completion (not implemented for Sarvam)."""
        # Sarvam doesn't support streaming, so we return the complete response
        response = self.complete(prompt, **kwargs)
        yield response
    
    def chat(self, messages: List[ChatMessage], **kwargs: Any) -> ChatResponse:
        """Chat completion using Sarvam-m LLM."""
        try:
            # Convert ChatMessage objects to the format expected by Sarvam
            sarvam_messages = []
            for msg in messages:
                sarvam_messages.append({
                    "role": msg.role.value,
                    "content": msg.content
                })
            
            response = self.sarvam_service.chat_completion(
                messages=sarvam_messages,
                temperature=kwargs.get('temperature', 0.7),
                max_tokens=kwargs.get('max_tokens', 512)
            )
            
            # Extract content from response
            content = self._extract_content_from_response(response)
            
            return ChatResponse(
                message=ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content=content
                )
            )
        except Exception as e:
            self.logger.error(f"Sarvam chat failed: {e}")
            raise Exception(f"LLM chat failed: {e}")
    
    @llm_completion_callback()
    def stream_chat(self, messages: List[ChatMessage], **kwargs: Any) -> ChatResponseGen:
        """Stream chat (not implemented for Sarvam)."""
        # Sarvam doesn't support streaming, so we return the complete response
        response = self.chat(messages, **kwargs)
        yield response
    
    def _extract_content_from_response(self, response_data: Dict[str, Any]) -> str:
        """
        Extract content from API response.
        
        Args:
            response_data: Full API response
            
        Returns:
            Extracted content string
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
            raise Exception(f"Invalid API response format: {e}")


@dataclass
class AgentResponse:
    """Response from the LlamaIndex agent."""
    content: str
    function_called: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None


class LlamaIndexAgent:
    """
    LlamaIndex Agent with function calling for the stripped-down product assistant.
    
    Uses LlamaIndex's ReActAgent with custom functions for product lookup
    and order placement, integrated with Sarvam-m LLM.
    """
    
    def __init__(self, rag_engine: RAGEngine, order_processor: OrderProcessor):
        """
        Initialize the LlamaIndex agent.
        
        Args:
            rag_engine: RAG engine for product queries
            order_processor: Order processor for order placement
        """
        self.rag_engine = rag_engine
        self.order_processor = order_processor
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        
        # Initialize Sarvam service and LLM wrapper
        self.sarvam_service = SarvamLLMService()
        self.llm_wrapper = SarvamLLMWrapper(self.sarvam_service)
        
        # Initialize agent components
        self.agent: Optional[ReActAgent] = None
        self.tools: List[FunctionTool] = []
        
        # Initialize the agent
        self.initialize_agent()
    
    def initialize_agent(self) -> None:
        """Initialize the ReActAgent with function tools."""
        try:
            print("Initializing LlamaIndex agent with function calling...")
        
            # Create function tools
            self.tools = [
                self._create_product_lookup_tool(),
                self._create_order_placement_tool()
            ]
            
            # Create ReActAgent with tools
            self.agent = ReActAgent.from_tools(
                tools=self.tools,
                llm=self.llm_wrapper,
                verbose=True,
                max_iterations=10
            )
            
            print(f"Agent initialized with {len(self.tools)} tools")
            
        except Exception as e:
            print(f"Failed to initialize agent: {e}")
            raise Exception(f"Agent initialization failed: {e}")
    
    def _create_product_lookup_tool(self) -> FunctionTool:
        """Create function tool for product lookup."""
        def lookup_products(query: str) -> str:
            """
            Look up products based on user query using RAG.
            
            Args:
                query: User's product search query
                
            Returns:
                Formatted response with product information
            """
            try:
                print(f"Product lookup function called with query: {query}")
                
                # Use RAG engine to search for products
                products = self.rag_engine.search_products(query)
                
                # Generate formatted response using the LLM
                response = self.rag_engine.generate_response(query, products)
                return response
                
            except Exception as e:
                print(f"Product lookup failed: {e}")
                return f"I'm sorry, I encountered an error while searching for products: {str(e)}"
        
        return FunctionTool.from_defaults(
            fn=lookup_products,
            name="lookup_products",
            description="Search for products in the catalog based on user queries. Use this when users ask about product information, specifications, availability, or want to browse products."
        )
    
    def _create_order_placement_tool(self) -> FunctionTool:
        """Create function tool for order placement."""
        def process_order(
            product_id: str,
            quantity: int,
            delivery_address: str,
            product_name: Optional[str] = None
        ) -> str:
            """
            Place an order for a product.
            
            Args:
                product_id: Product identifier (e.g., P001)
                quantity: Number of items to order
                delivery_address: Customer delivery address
                product_name: Optional product name for confirmation
                
            Returns:
                Order confirmation or error message
            """
            try:
                print(f"Order placement function called for product: {product_id}")
                
                # Process the order
                result = self.order_processor.process_order(
                    product_id=product_id,
                    quantity=quantity,
                    delivery_address=delivery_address,
                    product_name=product_name
                )
                
                return result
                    
            except Exception as e:
                print(f"Order placement failed: {e}")
                return f"I'm sorry, I encountered an error while placing your order: {str(e)}"
        
        return FunctionTool.from_defaults(
            fn=process_order,
            name="process_order",
            description="Place an order for a product. Use this when users want to buy or order products. Requires product_id, quantity, and delivery_address."
        )
    
    def chat(self, user_message: str) -> AgentResponse:
        """
        Process user message using function calling agent.
        
        Args:
            user_message: User's input message
            
        Returns:
            AgentResponse with the result
        """
        if not self.agent:
            return AgentResponse(
                content="Sorry, the assistant is not available right now. Please try again later.",
                success=False,
                error_message="Agent not initialized"
            )
        
        try:
            print(f"Processing user message: {user_message}")
            
            # Use the agent to process the message
            response = self.agent.chat(user_message)
            
            # Extract information from the response
            content = str(response)
            
            # Try to determine which function was called (if any)
            function_called = self._extract_function_called(content)
            
            return AgentResponse(
                content=content,
                function_called=function_called,
                success=True
            )
            
        except Exception as e:
            print(f"Agent chat failed: {e}")
            
            # Fallback to manual processing
            return self._fallback_processing(user_message, str(e))
    
    def _extract_function_called(self, response_content: str) -> Optional[str]:
        """Extract which function was called from the response."""
        if "lookup_products" in response_content.lower() or "searching" in response_content.lower():
            return "lookup_products"
        elif "process_order" in response_content.lower() or "order placed" in response_content.lower():
            return "process_order"
        return None
    
    def _fallback_processing(self, user_message: str, error: str) -> AgentResponse:
        """
        Fallback processing when function calling fails.
        
        Uses simple keyword matching to determine intent.
        """
        print("Using fallback processing...")
        
        try:
            # Simple keyword-based intent detection
            message_lower = user_message.lower()
            
            # Check for product query keywords
            product_keywords = ['product', 'item', 'furniture', 'chair', 'table', 'sofa', 'search', 'find', 'show', 'what', 'tell me about']
            order_keywords = ['order', 'buy', 'purchase', 'place order', 'want to order']
            
            if any(keyword in message_lower for keyword in order_keywords):
                # Order intent
                return AgentResponse(
                    content="I understand you want to place an order. Please provide the product ID, quantity, and delivery address. For example: 'I want to order 2 units of product P001 to be delivered to 123 Main St, City, State 12345'",
                    success=True
                )
            elif any(keyword in message_lower for keyword in product_keywords):
                # Product query intent
                try:
                    products = self.rag_engine.search_products(user_message)
                    response = self.rag_engine.generate_response(user_message, products)
                    return AgentResponse(
                        content=response,
                        function_called="lookup_products",
                        success=True
                    )
                except Exception as rag_error:
                    return AgentResponse(
                        content="Sorry, I'm having trouble accessing the product catalog right now.",
                        success=False,
                        error_message=str(rag_error)
                    )
            else:
                # Unclear intent
                return AgentResponse(
                    content="I'm not sure how to help with that. You can ask me about products in our catalog or place an order. What would you like to do?",
                    success=True
                )
                
        except Exception as fallback_error:
            print(f"Fallback processing also failed: {fallback_error}")
            return AgentResponse(
                content="I'm sorry, I'm having trouble understanding your request right now. Please try again later.",
                success=False,
                error_message=f"Function calling failed: {error}. Fallback failed: {fallback_error}"
            )
    
    def get_available_functions(self) -> List[Dict[str, str]]:
        """
        Get information about available functions.
        
        Returns:
            List of function information dictionaries
        """
        functions = []
        for tool in self.tools:
            functions.append({
                "name": tool.metadata.name,
                "description": tool.metadata.description
            })
        return functions
    
    def is_ready(self) -> bool:
        """
        Check if the agent is ready to process requests.
        
        Returns:
            True if ready, False otherwise
        """
        return (
            self.agent is not None and
            len(self.tools) > 0
        )