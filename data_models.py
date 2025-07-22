"""
Data models for product assistant.

This module defines the core data structures used throughout the application:
- Product: Represents a product in the catalog
- Order: Represents a new order being placed
- StoredOrder: Represents a persisted order with additional metadata
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import uuid


@dataclass
class Product:
    """Represents a product in the catalog."""
    product_id: str
    name: str
    description: str
    price: float
    stock_quantity: int
    category: str

    def __post_init__(self):
        """Validate product data after initialization."""
        if not self.product_id or not isinstance(self.product_id, str):
            raise ValueError("Product ID must be a non-empty string")
        
        if not self.name or not isinstance(self.name, str):
            raise ValueError("Product name must be a non-empty string")
        
        if not isinstance(self.price, (int, float)) or self.price < 0:
            raise ValueError("Price must be a non-negative number")
        
        if not isinstance(self.stock_quantity, int) or self.stock_quantity < 0:
            raise ValueError("Stock quantity must be a non-negative integer")
        
        if not self.category or not isinstance(self.category, str):
            raise ValueError("Category must be a non-empty string")

    def is_in_stock(self, quantity: int = 1) -> bool:
        """Check if the product has sufficient stock for the requested quantity."""
        return self.stock_quantity >= quantity

    def to_dict(self) -> dict:
        """Convert product to dictionary representation."""
        return {
            'product_id': self.product_id,
            'name': self.name,
            'description': self.description,
            'price': self.price,
            'stock_quantity': self.stock_quantity,
            'category': self.category
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Product':
        """Create Product instance from dictionary."""
        return cls(
            product_id=data['product_id'],
            name=data['name'],
            description=data['description'],
            price=float(data['price']),
            stock_quantity=int(data['stock_quantity']),
            category=data['category']
        )


@dataclass
class Order:
    """Represents a new order being placed."""
    product_id: str
    quantity: int
    delivery_address: str
    product_name: Optional[str] = None

    def __post_init__(self):
        """Validate order data after initialization."""
        if not self.product_id or not isinstance(self.product_id, str):
            raise ValueError("Product ID must be a non-empty string")
        
        if not isinstance(self.quantity, int) or self.quantity <= 0:
            raise ValueError("Quantity must be a positive integer")
        
        if not self.delivery_address or not isinstance(self.delivery_address, str):
            raise ValueError("Delivery address must be a non-empty string")

    def to_dict(self) -> dict:
        """Convert order to dictionary representation."""
        return {
            'product_id': self.product_id,
            'quantity': self.quantity,
            'delivery_address': self.delivery_address,
            'product_name': self.product_name
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Order':
        """Create Order instance from dictionary."""
        return cls(
            product_id=data['product_id'],
            quantity=int(data['quantity']),
            delivery_address=data['delivery_address'],
            product_name=data.get('product_name')
        )


@dataclass
class StoredOrder:
    """Represents a persisted order with additional metadata."""
    order_id: str
    product_id: str
    product_name: str
    quantity: int
    delivery_address: str
    order_date: str
    total_price: float

    def __post_init__(self):
        """Validate stored order data after initialization."""
        if not self.order_id or not isinstance(self.order_id, str):
            raise ValueError("Order ID must be a non-empty string")
        
        if not self.product_id or not isinstance(self.product_id, str):
            raise ValueError("Product ID must be a non-empty string")
        
        if not self.product_name or not isinstance(self.product_name, str):
            raise ValueError("Product name must be a non-empty string")
        
        if not isinstance(self.quantity, int) or self.quantity <= 0:
            raise ValueError("Quantity must be a positive integer")
        
        if not self.delivery_address or not isinstance(self.delivery_address, str):
            raise ValueError("Delivery address must be a non-empty string")
        
        if not isinstance(self.total_price, (int, float)) or self.total_price < 0:
            raise ValueError("Total price must be a non-negative number")

    def to_dict(self) -> dict:
        """Convert stored order to dictionary representation."""
        return {
            'order_id': self.order_id,
            'product_id': self.product_id,
            'product_name': self.product_name,
            'quantity': self.quantity,
            'delivery_address': self.delivery_address,
            'order_date': self.order_date,
            'total_price': self.total_price
        }

    def to_csv_row(self) -> list:
        """Convert stored order to CSV row format."""
        return [
            self.order_id,
            self.product_id,
            self.product_name,
            str(self.quantity),
            self.delivery_address,
            self.order_date,
            str(self.total_price)
        ]

    @classmethod
    def from_dict(cls, data: dict) -> 'StoredOrder':
        """Create StoredOrder instance from dictionary."""
        return cls(
            order_id=data['order_id'],
            product_id=data['product_id'],
            product_name=data['product_name'],
            quantity=int(data['quantity']),
            delivery_address=data['delivery_address'],
            order_date=data['order_date'],
            total_price=float(data['total_price'])
        )

    @classmethod
    def from_csv_row(cls, row: list) -> 'StoredOrder':
        """Create StoredOrder instance from CSV row."""
        if len(row) != 7:
            raise ValueError("CSV row must have exactly 7 columns")
        
        return cls(
            order_id=row[0],
            product_id=row[1],
            product_name=row[2],
            quantity=int(row[3]),
            delivery_address=row[4],
            order_date=row[5],
            total_price=float(row[6])
        )

    @classmethod
    def from_order(cls, order: Order, product: Product, order_id: Optional[str] = None) -> 'StoredOrder':
        """Create StoredOrder from Order and Product instances."""
        if order_id is None:
            order_id = f"ORD{uuid.uuid4().hex[:6].upper()}"
        
        total_price = product.price * order.quantity
        order_date = datetime.now().strftime("%Y-%m-%d")
        
        return cls(
            order_id=order_id,
            product_id=order.product_id,
            product_name=order.product_name or product.name,
            quantity=order.quantity,
            delivery_address=order.delivery_address,
            order_date=order_date,
            total_price=total_price
        )


# Helper functions for data validation and conversion
def validate_product_data(data: dict) -> bool:
    """Validate product data dictionary before creating Product instance."""
    required_fields = ['product_id', 'name', 'description', 'price', 'stock_quantity', 'category']
    
    for field in required_fields:
        if field not in data:
            return False
    
    try:
        # Validate data types
        float(data['price'])
        int(data['stock_quantity'])
        return True
    except (ValueError, TypeError):
        return False


def validate_order_data(data: dict) -> bool:
    """Validate order data dictionary before creating Order instance."""
    required_fields = ['product_id', 'quantity', 'delivery_address']
    
    for field in required_fields:
        if field not in data:
            return False
    
    try:
        # Validate data types
        int(data['quantity'])
        return True
    except (ValueError, TypeError):
        return False