# Product Assistant API

A FastAPI-based REST API wrapper around an intelligent product assistant that can help users search for products and place orders. The assistant uses LlamaIndex with RAG (Retrieval-Augmented Generation) for product search and Sarvam-m LLM for natural language processing.

## Features

- **Product Search**: Semantic search through product catalogs using BAAI embeddings
- **Order Processing**: Complete order placement with validation and persistence
- **Natural Language Interface**: Chat with the assistant using natural language
- **REST API**: HTTP endpoints for integration with web applications
- **Function Calling**: Intelligent agent that can call appropriate functions based on user intent
- **Error Handling**: Comprehensive error handling and validation
- **Session Management**: Maintain conversation context across API calls

## Architecture

The system consists of several key components:

- **Chat Interface**: Terminal and API interface for user interactions
- **LlamaIndex Agent**: ReAct agent with function calling capabilities
- **RAG Engine**: Semantic search using BAAI embeddings and vector indexing
- **Order Processor**: Order validation, processing, and CSV persistence
- **Sarvam LLM Service**: Integration with Sarvam-m language model
- **Data Models**: Structured data models for products and orders

## Prerequisites

- Python 3.8 or higher
- pip package manager
- Internet connection for downloading embedding models
- Sarvam API key (for LLM functionality)

## Installation

1. **Clone or download the project files**

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   The project includes a `.env` file with default configuration. Update the `SARVAM_API_KEY` if needed:
   ```
   SARVAM_API_KEY=your_api_key_here
   ```

4. **Verify data files**:
   Ensure these files exist in the project directory:
   - `test_catalog.json` - Product catalog
   - `orders.csv` - Will be created automatically for order storage

## Usage

### Running as Terminal Chat Interface

```bash
python chat_interface.py
```

When prompted, press Enter (don't type "API") to run the terminal interface.

### Running as REST API

```bash
python chat_interface.py
```

When prompted, type `API` to start the REST API server.

The API will be available at:
- **Local**: http://127.0.0.1:8000
- **Public URL**: A ngrok tunnel URL will be displayed in the console

### API Endpoints

#### Health Check
```http
GET /
```
Returns API status.

#### Chat with Assistant
```http
POST /respond
```

**Request Body**:
```json
{
  "password": "########",
  "query": "Show me some chairs"
}
```

**Response**:
```json
{
  "result": "I found several chairs in our catalog..."
}
```

#### API Documentation
- **Swagger UI**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc

## Example Interactions

### Product Search
```
User: "Show me some office chairs under $200"
Assistant: "I found several office chairs under $200:

1. Ergonomic Office Chair (ID: P001)
   Price: $149.99
   Stock: 15 units (In Stock)
   Description: Comfortable ergonomic chair with lumbar support..."
```

### Order Placement
```
User: "I want to order 2 units of product P001 to be delivered to 123 Main St, City, State 12345"
Assistant: "Order ORD123ABC placed successfully for Ergonomic Office Chair

Order Details:
- Product: Ergonomic Office Chair
- Quantity: 2
- Unit Price: $149.99
- Total Price: $299.98
- Delivery Address: 123 Main St, City, State 12345
- Order Date: 2024-01-15"
```

## Configuration

### Environment Variables

The application uses the following environment variables (configured in `.env`):

| Variable | Description | Default |
|----------|-------------|---------|
| `SARVAM_API_KEY` | API key for Sarvam LLM service | Required |
| `SARVAM_API_URL` | Sarvam API endpoint | https://api.sarvam.ai/v1/chat/completions |
| `SARVAM_MODEL` | LLM model to use | sarvam-m |
| `CATALOG_PATH` | Path to product catalog JSON | test_catalog.json |
| `ORDERS_CSV_PATH` | Path to orders CSV file | orders.csv |
| `LOG_LEVEL` | Logging level | INFO |

### Product Catalog Format

The `test_catalog.json` file should contain products in this format:

```json
{
  "products": [
    {
      "product_id": "P001",
      "name": "Ergonomic Office Chair",
      "description": "Comfortable chair with lumbar support",
      "price": 149.99,
      "stock_quantity": 15,
      "category": "Furniture"
    }
  ]
}
```

## Development

### Project Structure

```
.
├── chat_interface.py          # Main interface (terminal + API)
├── llamaindex_agent.py        # LlamaIndex agent with function calling
├── rag_engine.py             # RAG-based product search
├── order_processor.py         # Order processing and validation
├── sarvam_llm_service.py      # Sarvam LLM integration
├── data_models.py             # Data models and validation
├── test_catalog.json          # Sample product catalog
├── orders.csv                 # Order storage (created automatically)
├── .env                       # Environment configuration
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

### Adding New Products

Edit `test_catalog.json` and add products following the existing format. The RAG engine will automatically index new products when restarted.

### Customizing Responses

The assistant's behavior can be customized by modifying:
- System messages in `rag_engine.py`
- Function descriptions in `llamaindex_agent.py`
- Response templates throughout the codebase

## License

This project is provided as-is for educational and development purposes.