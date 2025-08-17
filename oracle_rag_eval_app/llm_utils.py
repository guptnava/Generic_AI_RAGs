import ollama
import json

def llm_generate_synonyms_batch(q_map, max_synonyms=5):
    """
    Generate synonyms for a batch of questions using Ollama.
    q_map: list of (id, question) tuples
    Returns: dict {question_id: [synonym1, synonym2, ...]}
    """
    syns_map = {}

    for qid, question in q_map:
        prompt = f"""
        Generate up to {max_synonyms} synonyms or paraphrased versions of this question.
        Return the output strictly as a JSON list of strings. No extra text.

        Question: "{question}"
        """

        try:
            response = ollama.chat(
                model="llama3.2:1b",
                messages=[{"role": "user", "content": prompt}]
            )

            # Extract assistant reply
            raw_text = response['message']['content']
            print(f"Raw response for QID {qid}: {raw_text}")

            # Try to parse as JSON
            try:
                synonyms = json.loads(raw_text)
                if isinstance(synonyms, list):
                    syns_map[qid] = synonyms
                else:
                    syns_map[qid] = []
                    print(f"⚠️ Unexpected format for QID {qid}: {raw_text}")
            except json.JSONDecodeError:
                # fallback: split by line
                synonyms = [line.strip("-• ") for line in raw_text.split("\n") if line.strip()]
                syns_map[qid] = synonyms[:max_synonyms]

        except Exception as e:
            print(f"❌ Failed to generate synonyms for QID {qid}: {e}")
            syns_map[qid] = []

    return syns_map
