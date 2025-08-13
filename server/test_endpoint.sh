curl -X POST http://localhost:3000/api/generate -H "Content-Type: application/json" -d '{"prompt": "Hello", "model": "llama3.2:1b", "mode": "direct"}'



curl -X POST http://localhost:3000/api/generate -H "Content-Type: application/json" -d '{"prompt": "list all sales", "model": "llama3.2:1b", "mode": "langchain"}'


curl -X POST http://localhost:3000/api/generate -H "Content-Type: application/json" -d '{"prompt": "list all sales", "model": "llama3.2:1b", "mode": "embedded_narrated"}'
