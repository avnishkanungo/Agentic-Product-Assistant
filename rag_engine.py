"""
RAG-based product lookup system using LlamaIndex and BAAI embeddings.

This module provides semantic search capabilities for product catalogs using:
- BAAI/bge-small-en-v1.5 embedding model for vector representations
- LlamaIndex for document indexing and retrieval
- Sarvam LLM service for natural language response generation
"""

import json
import logging
import os
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

from llama_index.core import Document, VectorStoreIndex, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.query_engine import RetrieverQueryEngine

from data_models import Product
from sarvam_llm_service import SarvamLLMService


class RAGEngine:
    """
    RAG-based product lookup system that provides semantic search and 
    natural language responses for product queries.
    """
    
    def __init__(self, catalog_path: Optional[str] = None):
        """
        Initialize the RAG engine with embedding model and LLM service.
        
        Args:
            catalog_path: Path to product catalog JSON file
        """
        # Load environment variables from local .env file
        load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))
        
        self.logger = logging.getLogger(__name__)
        
        # Get catalog path from environment or use default
        env_catalog_path = os.getenv('CATALOG_PATH', 'test_catalog.json')
        
        # If catalog_path is provided, use it; otherwise resolve relative to this file's directory
        if catalog_path:
            self.catalog_path = catalog_path
        else:
            # Resolve path relative to this file's directory
            self.catalog_path = os.path.join(os.path.dirname(__file__), env_catalog_path)
        
        # Initialize components
        self.products: List[Product] = []
        self.index: Optional[VectorStoreIndex] = None
        self.llm_service = SarvamLLMService()
        
        # Configure LlamaIndex settings
        self._configure_llamaindex()
        
        # Load and index catalog
        self.initialize_index()
    
    def _configure_llamaindex(self) -> None:
        """Configure LlamaIndex with BAAI embedding model."""
        try:
            # Initialize BAAI embedding model
            embed_model = HuggingFaceEmbedding(
                model_name="BAAI/bge-small-en-v1.5",
                trust_remote_code=True
            )
            
            # Set global settings
            Settings.embed_model = embed_model
            Settings.chunk_size = 512
            Settings.chunk_overlap = 50
            
            self.logger.info("LlamaIndex configured with BAAI embedding model")
            
        except Exception as e:
            self.logger.error(f"Failed to configure LlamaIndex: {e}")
            raise
    
    def initialize_index(self, catalog_path: Optional[str] = None) -> None:
        """
        Load product catalog and create vector index.
        
        Args:
            catalog_path: Optional path to catalog file (overrides default)
        """
        if catalog_path:
            self.catalog_path = catalog_path
        
        try:
            # Load products from catalog
            self.products = self._load_catalog()
            self.logger.info(f"Loaded {len(self.products)} products from catalog")
            
            # Create documents for indexing
            documents = self._create_documents()
            self.logger.info(f"Created {len(documents)} documents for indexing")
            
            # Build vector index
            self.index = VectorStoreIndex.from_documents(documents)
            self.logger.info("Vector index created successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize index: {e}")
            raise
    
    def _load_catalog(self) -> List[Product]:
        """
        Load products from JSON catalog file.
        
        Returns:
            List of Product instances
            
        Raises:
            FileNotFoundError: If catalog file doesn't exist
            json.JSONDecodeError: If catalog file is invalid JSON
            ValueError: If product data is invalid
        """
        try:
            with open(self.catalog_path, 'r', encoding='utf-8') as f:
                catalog_data = json.load(f)
            
            products = []
            for product_data in catalog_data.get('products', []):
                try:
                    product = Product.from_dict(product_data)
                    products.append(product)
                except ValueError as e:
                    self.logger.warning(f"Skipping invalid product {product_data.get('product_id', 'unknown')}: {e}")
                    continue
            
            if not products:
                raise ValueError("No valid products found in catalog")
            
            return products
            
        except FileNotFoundError:
            error_msg = f"Catalog file not found: {self.catalog_path}"
            self.logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in catalog file: {e}"
            self.logger.error(error_msg)
            raise
        
        except Exception as e:
            self.logger.error(f"Error loading catalog: {e}")
            raise
    
    def _create_documents(self) -> List[Document]:
        """
        Create LlamaIndex documents from product data.
        
        Returns:
            List of Document instances for indexing
        """
        documents = []
        
        for product in self.products:
            # Create rich text representation for better semantic search
            content = self._format_product_for_indexing(product)
            
            # Create document with metadata
            doc = Document(
                text=content,
                metadata={
                    'product_id': product.product_id,
                    'name': product.name,
                    'category': product.category,
                    'price': product.price,
                    'stock_quantity': product.stock_quantity
                }
            )
            
            documents.append(doc)
        
        return documents
    
    def _format_product_for_indexing(self, product: Product) -> str:
        """
        Format product data for optimal semantic search indexing.
        
        Args:
            product: Product instance
            
        Returns:
            Formatted text representation
        """
        # Create comprehensive text representation
        content_parts = [
            f"Product: {product.name}",
            f"Category: {product.category}",
            f"Description: {product.description}",
            f"Price: ${product.price:.2f}",
            f"Stock: {product.stock_quantity} units available"
        ]
        
        # Add availability status
        if product.stock_quantity > 0:
            content_parts.append("Status: In stock")
        else:
            content_parts.append("Status: Out of stock")
        
        return " | ".join(content_parts)
    
    def search_products(self, query: str, top_k: int = 10) -> List[Product]:
        """
        Search for products using semantic similarity.
        
        Args:
            query: Natural language search query
            top_k: Maximum number of products to return
            
        Returns:
            List of most similar products
            
        Raises:
            ValueError: If index is not initialized
            Exception: If search fails
        """
        if not self.index:
            raise ValueError("Index not initialized. Call initialize_index() first.")
        
        try:
            # Create retriever with specified top_k
            retriever = VectorIndexRetriever(
                index=self.index,
                similarity_top_k=top_k
            )
            
            # Retrieve similar documents
            nodes = retriever.retrieve(query)
            
            # Extract products from retrieved nodes
            products = []
            seen_product_ids = set()
            
            for node in nodes:
                product_id = node.metadata.get('product_id')
                if product_id and product_id not in seen_product_ids:
                    # Find the full product object
                    product = self._get_product_by_id(product_id)
                    if product:
                        products.append(product)
                        seen_product_ids.add(product_id)
            
            self.logger.info(f"Found {len(products)} products for query: {query}")
            return products
            
        except Exception as e:
            self.logger.error(f"Product search failed: {e}")
            raise
    
    def _get_product_by_id(self, product_id: str) -> Optional[Product]:
        """
        Get product by ID from loaded catalog.
        
        Args:
            product_id: Product identifier
            
        Returns:
            Product instance or None if not found
        """
        for product in self.products:
            if product.product_id == product_id:
                return product
        return None
    
    def generate_response(self, query: str, products: List[Product]) -> str:
        """
        Generate natural language response using Sarvam LLM.
        
        Args:
            query: Original user query
            products: List of relevant products
            
        Returns:
            Generated response text
            
        Raises:
            Exception: If response generation fails
        """
        try:
            if not products:
                return self._generate_no_results_response(query)
            
            # Create context from products
            context = self._format_products_for_response(products)
            
            # Create system message for response generation
            system_message = """You are a helpful product assistant. Based on the provided product information, give a natural and informative response to the user's query. 

Guidelines:
- Be conversational and helpful
- Highlight key product features and benefits
- Mention prices and availability
- If multiple products match, present them in a organized way
- Keep responses concise but informative
- Use natural language, not technical jargon
- When providing product details ensure that the ID of the product is always included."""
            
            # Create user prompt
            user_prompt = f"""User Query: {query}

Available Products:
{context}

Please provide a helpful response about these products based on the user's query."""
            
            # Generate response using Sarvam LLM
            response = self.llm_service.simple_completion(
                prompt=user_prompt,
                system_message=system_message,
                temperature=0.7,
                max_tokens=800
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Response generation failed: {e}")
            # Return fallback response
            return self._generate_fallback_response(query, products)
    
    def _format_products_for_response(self, products: List[Product]) -> str:
        """
        Format products for LLM context.
        
        Args:
            products: List of products
            
        Returns:
            Formatted product information
        """
        formatted_products = []
        
        for i, product in enumerate(products, 1):
            stock_status = "In Stock" if product.stock_quantity > 0 else "Out of Stock"
            
            product_info = f"""{i}. {product.name} (ID: {product.product_id})
   Category: {product.category}
   Price: ${product.price:.2f}
   Stock: {product.stock_quantity} units ({stock_status})
   Description: {product.description}"""
            
            formatted_products.append(product_info)
        
        return "\n\n".join(formatted_products)
    
    def _generate_no_results_response(self, query: str) -> str:
        """
        Generate response when no products are found.
        
        Args:
            query: Original user query
            
        Returns:
            No results response
        """
        return f"""I couldn't find any products matching "{query}" in our catalog. 

Here are some suggestions:
- Try using different keywords or synonyms
- Check for spelling errors
- Use more general terms (e.g., "chair" instead of specific model names)
- Browse our categories: {', '.join(self._get_available_categories())}

Would you like me to show you our popular products or help you search for something else?"""
    
    def _generate_fallback_response(self, query: str, products: List[Product]) -> str:
        """
        Generate fallback response when LLM fails.
        
        Args:
            query: Original user query
            products: List of products
            
        Returns:
            Fallback response
        """
        if not products:
            return self._generate_no_results_response(query)
        
        response_parts = [f"I found {len(products)} product(s) for your query '{query}':\n"]
        
        for i, product in enumerate(products[:5], 1):  # Limit to top 5
            stock_info = f"{product.stock_quantity} in stock" if product.stock_quantity > 0 else "Out of stock"
            response_parts.append(
                f"{i}. {product.name} - ${product.price:.2f} ({stock_info})\n"
                f"   {product.description[:100]}{'...' if len(product.description) > 100 else ''}"
            )
        
        if len(products) > 5:
            response_parts.append(f"\n... and {len(products) - 5} more products.")
        
        return "\n\n".join(response_parts)
    
    def _get_available_categories(self) -> List[str]:
        """
        Get list of available product categories.
        
        Returns:
            List of unique categories
        """
        categories = set()
        for product in self.products:
            categories.add(product.category)
        return sorted(list(categories))
    
    def get_product_by_id(self, product_id: str) -> Optional[Product]:
        """
        Public method to get product by ID.
        
        Args:
            product_id: Product identifier
            
        Returns:
            Product instance or None if not found
        """
        return self._get_product_by_id(product_id)
    
    def get_all_products(self) -> List[Product]:
        """
        Get all products from catalog.
        
        Returns:
            List of all products
        """
        return self.products.copy()
    
    def get_products_by_category(self, category: str) -> List[Product]:
        """
        Get products by category.
        
        Args:
            category: Product category
            
        Returns:
            List of products in the category
        """
        return [p for p in self.products if p.category.lower() == category.lower()]
    
    def is_initialized(self) -> bool:
        """
        Check if the RAG engine is properly initialized.
        
        Returns:
            True if initialized, False otherwise
        """
        return self.index is not None and len(self.products) > 0


# Convenience function for quick setup
def create_rag_engine(catalog_path: Optional[str] = None) -> RAGEngine:
    """
    Create and initialize a RAG engine instance.
    
    Args:
        catalog_path: Optional path to catalog file
        
    Returns:
        Initialized RAGEngine instance
    """
    return RAGEngine(catalog_path=catalog_path)