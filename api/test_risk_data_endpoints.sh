curl -X POST http://localhost:5008/query \
 -H "Content-Type: application/json" \
 -d '{"question":"What is the total Delta sensitivity by book for the last quarter?","source":"hive","query":"SELECT * FROM risk_sensitivities WHERE valuation_date >= date_sub(current_date,90)"}'
