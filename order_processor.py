"""
Order processing functionality for product assistant.

This module handles order validation, product availability checking, and order persistence
to CSV files. It provides error handling for invalid products and out-of-stock scenarios.
"""

import json
import csv
import os
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import uuid
from dotenv import load_dotenv

try:
    from .data_models import Product, Order, StoredOrder
except ImportError:
    from data_models import Product, Order, StoredOrder


class OrderProcessor:
    """Handles order processing, validation, and persistence."""
    
    def __init__(self, catalog_path: Optional[str] = None, 
                 orders_csv_path: Optional[str] = None):
        """
        Initialize the order processor.
        
        Args:
            catalog_path: Path to the product catalog JSON file
            orders_csv_path: Path to the orders CSV file
        """
        # Load environment variables from local .env file
        load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))
        
        # Get paths from environment or use defaults
        env_catalog_path = os.getenv('CATALOG_PATH', 'test_catalog.json')
        env_orders_path = os.getenv('ORDERS_CSV_PATH', 'orders.csv')
        
        # Resolve paths relative to this file's directory if not provided
        if catalog_path:
            self.catalog_path = catalog_path
        else:
            self.catalog_path = os.path.join(os.path.dirname(__file__), env_catalog_path)
            
        if orders_csv_path:
            self.orders_csv_path = orders_csv_path
        else:
            self.orders_csv_path = os.path.join(os.path.dirname(__file__), env_orders_path)
        self.products = {}
        self.logger = logging.getLogger(__name__)
        
        # Load product catalog
        self._load_catalog()
        
        # Ensure CSV file exists with headers
        self._initialize_csv_file()
    
    def _load_catalog(self) -> None:
        """Load product catalog from JSON file."""
        try:
            with open(self.catalog_path, 'r', encoding='utf-8') as file:
                catalog_data = json.load(file)
                
            for product_data in catalog_data.get('products', []):
                product = Product.from_dict(product_data)
                self.products[product.product_id] = product
                
            self.logger.info(f"Loaded {len(self.products)} products from catalog")
            
        except FileNotFoundError:
            self.logger.error(f"Catalog file not found: {self.catalog_path}")
            print(f"Error: Catalog file not found at {self.catalog_path}")
            self.products = {}
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in catalog file: {e}")
            print(f"Error: Invalid JSON format in catalog file: {e}")
            self.products = {}
        except Exception as e:
            self.logger.error(f"Error loading catalog: {e}")
            print(f"Error loading catalog: {e}")
            self.products = {}
    
    def _initialize_csv_file(self) -> None:
        """Initialize CSV file with headers if it doesn't exist."""
        if not os.path.exists(self.orders_csv_path):
            try:
                with open(self.orders_csv_path, 'w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow([
                        'order_id', 'product_id', 'product_name', 'quantity',
                        'delivery_address', 'order_date', 'total_price'
                    ])
                self.logger.info(f"Created new orders CSV file: {self.orders_csv_path}")
            except Exception as e:
                self.logger.error(f"Error creating CSV file: {e}")
                print(f"Error creating orders CSV file: {e}")
    
    def validate_product_availability(self, product_id: str, quantity: int) -> Tuple[bool, str, Optional[Product]]:
        """
        Validate if a product exists and has sufficient stock.
        
        Args:
            product_id: The product ID to validate
            quantity: The requested quantity
            
        Returns:
            Tuple of (is_valid, message, product_object)
        """
        # Check if product exists
        if product_id not in self.products:
            available_products = self._get_similar_products(product_id)
            message = f"Product {product_id} not found."
            if available_products:
                message += f" Did you mean one of these: {', '.join(available_products[:5])}?"
            return False, message, None
        
        product = self.products[product_id]
        
        # Check stock availability
        if not product.is_in_stock(quantity):
            message = f"Insufficient stock for {product.name}. Available: {product.stock_quantity}, Requested: {quantity}"
            if product.stock_quantity > 0:
                message += f". You can order up to {product.stock_quantity} units."
            else:
                # Suggest alternatives from same category
                alternatives = self._get_category_alternatives(product.category, product_id)
                if alternatives:
                    message += f" Consider these alternatives: {', '.join(alternatives[:3])}"
            return False, message, product
        
        return True, "Product available", product
    
    def _get_similar_products(self, product_id: str) -> List[str]:
        """Get products with similar IDs for suggestions."""
        similar = []
        product_id_lower = product_id.lower()
        
        for pid, product in self.products.items():
            # Check for similar product IDs or names
            if (product_id_lower in pid.lower() or 
                product_id_lower in product.name.lower() or
                any(word in product.name.lower() for word in product_id_lower.split())):
                similar.append(f"{pid} ({product.name})")
        
        return similar
    
    def _get_category_alternatives(self, category: str, exclude_product_id: str) -> List[str]:
        """Get alternative products from the same category."""
        alternatives = []
        
        for pid, product in self.products.items():
            if (product.category == category and 
                pid != exclude_product_id and 
                product.stock_quantity > 0):
                alternatives.append(f"{pid} ({product.name})")
        
        return alternatives
    
    def process_order(self, product_id: str, quantity: int, delivery_address: str, 
                     product_name: Optional[str] = None) -> Dict[str, any]:
        """
        Process a new order with validation and persistence.
        
        Args:
            product_id: The product ID to order
            quantity: The quantity to order
            delivery_address: The delivery address
            product_name: Optional product name (for validation)
            
        Returns:
            Dictionary with success status, message, and order details
        """
        try:
            # Create order object for validation
            order = Order(
                product_id=product_id,
                quantity=quantity,
                delivery_address=delivery_address,
                product_name=product_name
            )
            
            # Validate product availability
            is_valid, message, product = self.validate_product_availability(product_id, quantity)
            
            if not is_valid:
                self.logger.warning(f"Order validation failed: {message}")
                return {
                    'success': False,
                    'message': message,
                    'order_id': None,
                    'total_price': None
                }
            
            # Validate product name if provided
            if product_name and product_name.lower() != product.name.lower():
                self.logger.warning(f"Product name mismatch: expected '{product.name}', got '{product_name}'")
                return {
                    'success': False,
                    'message': f"Product name mismatch. Expected '{product.name}' for product ID {product_id}",
                    'order_id': None,
                    'total_price': None
                }
            
            # Create stored order
            stored_order = StoredOrder.from_order(order, product)
            
            # Save to CSV
            if self.save_order_to_csv(stored_order):
                # Update product stock (in memory only for this session)
                self.products[product_id].stock_quantity -= quantity
                
                self.logger.info(f"Order processed successfully: {stored_order.order_id}")
                return {
                    'success': True,
                    'message': f"Order {stored_order.order_id} placed successfully for {product.name}",
                    'order_id': stored_order.order_id,
                    'total_price': stored_order.total_price,
                    'order_details': {
                        'product_name': product.name,
                        'quantity': quantity,
                        'unit_price': product.price,
                        'total_price': stored_order.total_price,
                        'delivery_address': delivery_address,
                        'order_date': stored_order.order_date
                    }
                }
            else:
                return {
                    'success': False,
                    'message': "Failed to save order. Please try again.",
                    'order_id': None,
                    'total_price': None
                }
                
        except ValueError as e:
            self.logger.error(f"Order validation error: {e}")
            return {
                'success': False,
                'message': f"Invalid order data: {str(e)}",
                'order_id': None,
                'total_price': None
            }
        except Exception as e:
            self.logger.error(f"Unexpected error processing order: {e}")
            return {
                'success': False,
                'message': "An unexpected error occurred while processing your order. Please try again.",
                'order_id': None,
                'total_price': None
            }
    
    def save_order_to_csv(self, stored_order: StoredOrder) -> bool:
        """
        Save a stored order to the CSV file.
        
        Args:
            stored_order: The StoredOrder object to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.orders_csv_path, 'a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(stored_order.to_csv_row())
            
            self.logger.info(f"Order saved to CSV: {stored_order.order_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving order to CSV: {e}")
            print(f"Error saving order to CSV: {e}")
            return False
    
    def get_product_info(self, product_id: str) -> Optional[Product]:
        """
        Get product information by ID.
        
        Args:
            product_id: The product ID to look up
            
        Returns:
            Product object if found, None otherwise
        """
        return self.products.get(product_id)
    
    def get_all_products(self) -> Dict[str, Product]:
        """Get all products in the catalog."""
        return self.products.copy()
    
    def get_products_by_category(self, category: str) -> List[Product]:
        """
        Get all products in a specific category.
        
        Args:
            category: The category to filter by
            
        Returns:
            List of products in the category
        """
        return [product for product in self.products.values() 
                if product.category.lower() == category.lower()]
    
    def get_in_stock_products(self) -> List[Product]:
        """Get all products that are currently in stock."""
        return [product for product in self.products.values() 
                if product.stock_quantity > 0]
    
    def reload_catalog(self) -> bool:
        """
        Reload the product catalog from file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self._load_catalog()
            return len(self.products) > 0
        except Exception as e:
            self.logger.error(f"Error reloading catalog: {e}")
            return False


# Convenience functions for direct use
def create_order_processor(catalog_path: Optional[str] = None,
                          orders_csv_path: Optional[str] = None) -> OrderProcessor:
    """Create and return an OrderProcessor instance."""
    return OrderProcessor(catalog_path, orders_csv_path)


def quick_process_order(product_id: str, quantity: int, delivery_address: str,
                       product_name: Optional[str] = None,
                       catalog_path: Optional[str] = None,
                       orders_csv_path: Optional[str] = None) -> Dict[str, any]:
    """
    Quick function to process an order without creating a persistent processor.
    
    Args:
        product_id: The product ID to order
        quantity: The quantity to order
        delivery_address: The delivery address
        product_name: Optional product name
        catalog_path: Path to catalog file
        orders_csv_path: Path to orders CSV file
        
    Returns:
        Dictionary with order processing results
    """
    processor = OrderProcessor(catalog_path, orders_csv_path)
    return processor.process_order(product_id, quantity, delivery_address, product_name)