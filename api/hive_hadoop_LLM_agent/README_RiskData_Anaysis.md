# Flask Data QA Agent with Hive + HDFS + Ollama LLM

## Setup

1. Create a Python 3.8+ virtual environment and install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
Set your environment variables for Hive, Kerberos, and keytab:
export HIVE_HOST=your.hive.server
export HIVE_PORT=10000
export HIVE_USERNAME=your_username
export HIVE_DATABASE=default
export KERBEROS_KEYTAB=/path/to/your.keytab
export KERBEROS_PRINCIPAL=your_principal@YOUR.REALM
Make sure you have a valid Kerberos ticket:
kinit -kt $KERBEROS_KEYTAB $KERBEROS_PRINCIPAL
Run the Flask app:
python app.py
Example POST request to test:
curl -X POST http://localhost:5001/api/agent/data-qa \
 -H "Content-Type: application/json" \
 -d '{
   "question": "What is the total risk exposure?",
   "source": "hive",
   "query": "SELECT exposure_amount, risk_type FROM risk_table LIMIT 1000"
 }'


 Questions for Analysis on Risk Sensitivities Data
1. General Overview
What is the total sensitivity exposure by measure (e.g., Delta, Gamma)?
How are sensitivities distributed across different books and deals?
What is the breakdown of sensitivity values by risk factor?
How many unique deals and books are currently active in the data?

2. Attribution and Concentration
Which counterparties or desks contribute most to the portfolio's sensitivities?
What is the attribution of total sensitivity exposure by attribution factor?
Are there any concentration risks by measure, book, or counterparty?
How do sensitivities vary by currency or scenario?

3. Measure Points and Greeks Analysis
What are the top measure points contributing to high Delta or Gamma values?
How do Greeks (Delta, Gamma, Vega, Theta, Rho) compare across different risk factors?
Which measure points have the highest sensitivity value fluctuations over time?

4. Trend and Time Series
How have sensitivities for key risk factors evolved over the past months/quarters?
Are there any noticeable trends or spikes in sensitivities for specific deals or books?
How stable are attribution values over different valuation dates?

5. Scenario and Stress Testing
How do sensitivities change across different scenario IDs?
What is the impact of worst-case scenarios on the portfolio’s total sensitivities?
Which measures and risk factors show the most stress under extreme scenarios?

6. Risk Factor and Correlation Analysis
Which risk factors have the largest combined sensitivity exposure?
How correlated are sensitivities between different risk factors or measures?
Are there offsetting sensitivities within the portfolio that reduce overall risk?

7. Portfolio and Deal-Level Analysis
What is the sensitivity profile of a specific deal or book?
Which deals have the highest net sensitivity exposure for a given measure?
How do sensitivities vary within a book across different risk factors?

8. Validation and Data Quality
Are there any outliers or unexpected values in sensitivity or attribution data?
Are there missing or inconsistent records for valuation dates or scenarios?
How frequently is sensitivity data updated for each deal/book?

9. Regulatory and Reporting
What are the key sensitivity exposures relevant for regulatory capital calculations?
Can we produce a summary report of sensitivities by measure and risk factor for audit?



Bonus: Examples of Specific Natural Language Questions You Can Feed Your Agent
"Show me the total Delta sensitivity by book for the last quarter."
"Which counterparty has the highest Vega exposure?"
"How did the portfolio's Gamma sensitivity change over the past 6 months?"
"List the top 5 measure points contributing to the Rho sensitivity."
"What is the attribution of sensitivities for Desk_X under scenario SCEN3?"
"Are there any deals with unusually high exposure in the FX_EURUSD risk factor?"
"Compare the Theta sensitivity between scenario SCEN1 and SCEN5."
"Provide a time series of total sensitivity values for book BOOK12."
"Which risk factors have offsetting sensitivities in deal DEAL1234?"
"Generate a summary of expected losses and sensitivities for regulatory reporting."


Best practices for applying AI models on very large datasets (GBs to TBs):



1. Don’t dump raw data directly into the prompt.
LLMs work best with concise, relevant context.
Extract, summarize, or preprocess data before feeding it in.

2. Use a retrieval-augmented approach with vector search / embeddings
Break data into small chunks (e.g., a few hundred tokens or rows).
Generate embeddings for each chunk using an embedding model.
Store embeddings in a vector DB (e.g., Pinecone, FAISS, Weaviate).
When a question comes, embed the question, retrieve top relevant chunks.
Build prompt from only those relevant chunks and question.
This way, the model never sees the entire dataset — only the relevant subset.

3. Pre-aggregate and summarize the data
For risk data, precompute summary tables: averages, max/min, percentile, attribution summaries.
Store these aggregated summaries.
Feed summaries to the model for question answering.

4. Use specialized data stores for querying
Use SQL engines like Hive, Presto, or Spark SQL to quickly filter and aggregate data.
Only pass the small filtered result or summary to LLM.

5. Chunk and stream the data in manageable parts
If full data context is needed, chunk it into pieces.
Incrementally feed chunks to the model if it supports streaming or multi-turn conversation.

6. Use hybrid approach: LLM + classical analytics
Let the LLM do natural language parsing, explanation, interpretation.
Use classic DB/engine to do heavy lifting of data crunching.
For your case, a recommended architecture would be:
User Question
    ↓
Parse question → Identify relevant fields/time ranges/entities
    ↓
Run SQL query / Spark job on Hive or Oracle to fetch **aggregated, filtered data**
    ↓
If needed, embed query and retrieve relevant chunks from vector DB (for deep doc data)
    ↓
Build prompt with schema + aggregated data + relevant chunks
    ↓
Send prompt to LLM (ollama or llama)
    ↓
Return answer to frontend
Summary
Approach	Why	Tools/Tech
Chunk data + vector search	Focus on relevant info	FAISS, Pinecone, Weaviate
Aggregate/summarize before prompt	Reduce data volume	Hive, Spark, SQL, Pandas
Use SQL engines for filtering	Fast big data queries	Hive, Presto, Spark SQL
Combine classical analytics + LLM	Best of both worlds	SQL + LLM
Stream data in parts	Avoid memory overload	Prompt engineering + streaming APIs
If you want, I can help you:
Design a vector search pipeline for your risk data,
Show example code for chunking, embedding, and retrieval,
Write efficient SQL queries for aggregation,
Design prompt templates for these scenarios.
Would you like me to help with that?
