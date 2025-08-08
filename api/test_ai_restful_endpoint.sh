curl -X POST http://localhost:5006/query \
  -H "Content-Type: application/json" \
  -d '{
        "prompt": "Show me total sales for customer 1 in 2025",
        "parameters": {
          "customer_id": "1",
          "sale_date": "2025-07-01"
        }
      }'
