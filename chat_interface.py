"""
Terminal Chat Interface for Product Assistant.

This module provides a command-line interface for interacting with the product assistant
through natural language conversation.
"""

import logging
import sys
import os
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
from pyngrok import ngrok 

try:
    # Try relative imports first (when used as module)
    from .llamaindex_agent import LlamaIndexAgent, AgentResponse
    from .rag_engine import RAGEngine
    from .order_processor import OrderProcessor
except ImportError:
    # Fall back to absolute imports (when run directly)
    from llamaindex_agent import LlamaIndexAgent, AgentResponse
    from rag_engine import RAGEngine
    from order_processor import OrderProcessor



class APIInput(BaseModel):
    password:str
    query: str


class ChatInterface:
    """
    Terminal-based chat interface for the product assistant.
    
    Provides command-line interaction with session management,
    graceful exit functionality, and error handling.
    """
    
    def __init__(self):
        """Initialize the chat interface."""
        self.logger = logging.getLogger(__name__)
        self.agent: Optional[LlamaIndexAgent] = None
        self.session_active = False
        
        # Initialize components
        self._initialize_components()
    
    def _initialize_components(self) -> None:
        """Initialize the RAG engine, order processor, and agent."""
        try:
            print("Initializing product assistant...")
            
            # Load environment variables from local .env file
            load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))
            
            # Initialize RAG engine
            print("Setting up product search...")
            self.rag_engine = RAGEngine()
            
            # Initialize order processor
            print("Setting up order processing...")
            self.order_processor = OrderProcessor()
            
            # Initialize LlamaIndex agent
            print("Setting up intelligent agent...")
            self.agent = LlamaIndexAgent(
                rag_engine=self.rag_engine,
                order_processor=self.order_processor
            )
            
            print("Product assistant ready!")
            
        except Exception as e:
            print(f"Failed to initialize product assistant: {e}")
            self.logger.error(f"Component initialization failed: {e}")
            raise Exception(f"Chat interface initialization failed: {e}")
    
    def start_chat(self) -> None:
        """
        Start the terminal chat session.
        
        Implements requirement 6.1: Provide a command-line interface
        """
        if not self.agent or not self.agent.is_ready():
            print("Error: Product assistant is not ready. Please check your configuration.")
            return
        
        self.session_active = True
        
        # Display welcome message
        self._display_welcome_message()
        
        # Main chat loop
        while self.session_active:
            try:
                # Get user input
                user_input = self._get_user_input()
                
                # Check for exit command (requirement 6.2)
                if self._should_quit(user_input):
                    self._handle_quit()
                    break
                
                # Check for empty input (requirement 6.3)
                if self._is_empty_input(user_input):
                    self._handle_empty_input()
                    continue
                
                # Process valid input (requirement 6.4)
                self._process_user_input(user_input)
                
            except KeyboardInterrupt:
                # Handle Ctrl+C gracefully
                print("\n\nGoodbye! Thanks for using the product assistant.")
                break
            except Exception as e:
                # Handle errors gracefully (requirement 6.6)
                self._handle_error(e)
    
    def _display_welcome_message(self) -> None:
        """Display welcome message and instructions."""
        print("\n" + "="*60)
        print("🛍️  Welcome to the Product Assistant!")
        print("="*60)
        print("I can help you:")
        print("• Search for products in our catalog")
        print("• Place orders for products")
        print("• Answer questions about product details")
        print("\nType 'Q' to quit at any time.")
        print("="*60 + "\n")
    
    def _get_user_input(self) -> str:
        """
        Get input from the user with a prompt.
        
        Returns:
            User input string
        """
        try:
            return input("You: ").strip()
        except EOFError:
            # Handle EOF (Ctrl+D)
            return "Q"
    
    def _should_quit(self, user_input: str) -> bool:
        """
        Check if user wants to quit the session.
        
        Implements requirement 6.2: User enters 'Q' to quit
        
        Args:
            user_input: User's input string
            
        Returns:
            True if user wants to quit, False otherwise
        """
        return user_input.upper() == 'Q'
    
    def _is_empty_input(self, user_input: str) -> bool:
        """
        Check if user input is empty.
        
        Implements requirement 6.3: Handle empty prompts
        
        Args:
            user_input: User's input string
            
        Returns:
            True if input is empty, False otherwise
        """
        return len(user_input) == 0
    
    def _handle_quit(self) -> None:
        """Handle user quit command."""
        print("\nGoodbye! Thanks for using the product assistant. 👋")
        self.session_active = False
    
    def _handle_empty_input(self) -> None:
        """
        Handle empty user input.
        
        Implements requirement 6.3: Ask for input again when empty
        """
        print("Please enter your question or request. Type 'Q' to quit.")
    
    def _process_user_input(self, user_input: str) -> None:
        """
        Process valid user input using the LlamaIndex agent.
        
        Implements requirement 6.4: Call LlamaIndex agent for valid input
        Implements requirement 6.5: Display responses in readable format
        
        Args:
            user_input: User's input string
        """
        try:
            print("Assistant: ", end="", flush=True)
            
            # Call the LlamaIndex agent
            response: AgentResponse = self.agent.chat(user_input)
            
            # Display the response in a readable format
            self._display_response(response)
            
        except Exception as e:
            # Handle processing errors gracefully
            self._handle_processing_error(e)

    def agentic_endpoint(self, user_input:str) -> None:
        """
        Process valid user input using the LlamaIndex agent.

        Implements requirement 6.4: Call LlamaIndex agent for valid input
        Implements requirement 6.5: Display responses in readable format

        Args:
            user_input: User's input string
        """
        try:
            # Call the LlamaIndex agent
            response: AgentResponse = self.agent.chat(user_input)

            # Display the response in a readable format
            return response.content

        except Exception as e:
            # Handle processing errors gracefully
            return  self._handle_processing_error(e)
    
    def _display_response(self, response: AgentResponse) -> None:
        """
        Display agent response in a readable format.
        
        Implements requirement 6.5: Display responses in readable format
        
        Args:
            response: Agent response object
        """
        if response.success:
            # Display successful response
            print(response.content)
            
            # Add function call indicator if applicable
            if response.function_called:
                print(f"\n[Function used: {response.function_called}]")
        else:
            # Display error response
            print("I'm sorry, I encountered an issue while processing your request.")
            if response.error_message:
                print(f"Error details: {response.error_message}")
            print("Please try again or rephrase your question.")
        
        print()  # Add blank line for readability
    
    def _handle_processing_error(self, error: Exception) -> None:
        """
        Handle errors during input processing.
        
        Implements requirement 6.6: Handle errors gracefully
        
        Args:
            error: Exception that occurred
        """
        print("I'm sorry, I encountered an unexpected error while processing your request.")
        print("Please try again or contact support if the issue persists.")
        print()
        
        # Log the error for debugging
        self.logger.error(f"Processing error: {error}")
    
    def _handle_error(self, error: Exception) -> None:
        """
        Handle general errors in the chat loop.
        
        Implements requirement 6.6: Handle errors gracefully and continue session
        
        Args:
            error: Exception that occurred
        """
        print(f"\nAn error occurred: {error}")
        print("The chat session will continue. Please try again.")
        print()
        
        # Log the error
        self.logger.error(f"Chat loop error: {error}")
    
    def stop_chat(self) -> None:
        """Stop the chat session."""
        self.session_active = False
    
    def is_active(self) -> bool:
        """
        Check if the chat session is active.
        
        Returns:
            True if session is active, False otherwise
        """
        return self.session_active
    
    def get_agent_status(self) -> dict:
        """
        Get status information about the agent.
        
        Returns:
            Dictionary with agent status information
        """
        if not self.agent:
            return {"ready": False, "error": "Agent not initialized"}
        
        return {
            "ready": self.agent.is_ready(),
            "functions": self.agent.get_available_functions() if self.agent.is_ready() else []
        }


def main():
    """
    Main entry point for the chat interface.
    
    This function can be used to run the chat interface directly.
    """
    try:
        # Set up basic logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Create and start chat interface
        chat = ChatInterface()
        chat.start_chat()
        
    except Exception as e:
        print(f"Failed to start chat interface: {e}")
        sys.exit(1)


def agentic_implemenatation():
    app = FastAPI()

    @app.post("/respond")
    def response_endpoint(query:APIInput):
        if query.password != "abcd1234":
            return {"result: Incorrect Password"}
        chat = ChatInterface()
        result = chat.agentic_endpoint(query.query)
        return {"result": result}

    @app.get("/")
    def health_check():
        return {"status": "API is running!"}

    public_url = ngrok.connect(8000)
    print(f"Public URL: {public_url}")

    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    x = input("Enter API if you want to run this as an API:")
    if x == "API":
        agentic_implemenatation()
    else:
        main()