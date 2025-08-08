curl -X POST http://localhost:5005/execute/customer_sales \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "1",
    "sale_date": "'2025-07-01'"
  }'
