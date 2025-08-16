curl -X POST http://127.0.0.1:5000/query \
     -H "Content-Type: application/json" \
     -d '{"prompt": "list all employees"}'

curl -X POST http://127.0.0.1:5000/query \
     -H "Content-Type: application/json" \
     -d '{"prompt": "list all sales"}'

curl -X POST http://127.0.0.1:5000/query \
     -H "Content-Type: application/json" \
     -d '{"prompt": "top 5 sales by amount"}'


curl -X POST http://127.0.0.1:5000/query \
     -H "Content-Type: application/json" \
     -d '{"prompt": "employee count"}'


     curl -X POST http://127.0.0.1:5010/query \
     -H "Content-Type: application/json" \
     -d '{"prompt": "show all reports" , "model_name": "llama3.2:1b" }'