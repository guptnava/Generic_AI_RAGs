curl -X POST http://127.0.0.1:5001/query \
     -H "Content-Type: application/json" \
     -d '{"prompt": "list all employees"}'

curl -X POST http://127.0.0.1:5001/query \
     -H "Content-Type: application/json" \
     -d '{"prompt": "list all sales"}'

curl -X POST http://127.0.0.1:5001/query \
     -H "Content-Type: application/json" \
     -d '{"prompt": "top 5 sales by amount"}'


curl -X POST http://127.0.0.1:5009/query \
     -H "Content-Type: application/json" \
     -d '{"prompt": "show sales by region"}'
