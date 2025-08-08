from flask import Flask, request, Response, jsonify, stream_with_context
from sqlalchemy import create_engine, text
import os
import json
import datetime
import decimal

app = Flask(__name__)

# Oracle DB connection
db_user = os.getenv("DB_USER", "your_user")
db_password = os.getenv("DB_PASSWORD", "your_pass")
db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "1521")
db_service = os.getenv("DB_SERVICE", "orclpdb1")
db_uri = f"oracle+oracledb://{db_user}:{db_password}@{db_host}:{db_port}/{db_service}"
engine = create_engine(db_uri)

# Helpers
def serialize_value(val):
    if isinstance(val, (datetime.date, datetime.datetime)):
        return val.isoformat()
    elif isinstance(val, decimal.Decimal):
        return float(val)
    return val

def serialize_row(row, columns):
    return {col: serialize_value(val) for col, val in zip(columns, row)}

# Main endpoint
@app.route("/execute/<endpoint_name>", methods=["POST"])
def execute_param_query(endpoint_name):
    params = request.get_json() or {}

    try:
        # First fetch the SQL template (short-lived connection)
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT sql_text FROM rado_sql_queries WHERE endpoint_name = :name"),
                {"name": endpoint_name}
            ).fetchone()

        if not result:
            return jsonify({"error": f"No SQL found for endpoint '{endpoint_name}'"}), 404

        sql_template = result[0]

        try:
            final_sql = sql_template.format(**params)
        except KeyError as e:
            return jsonify({
                "error": f"Missing parameter: {e.args[0]}",
                "required_sql": sql_template
            }), 400
        except Exception as e:
            return jsonify({"error": f"Parameter substitution failed: {str(e)}"}), 400

        def generate():
            try:
                with engine.connect() as conn:
                    result_proxy = conn.execution_options(stream_results=True).execute(text(final_sql))
                    columns = result_proxy.keys()
                    for row in result_proxy:
                        yield json.dumps(serialize_row(row, columns)) + "\n"
            except Exception as e:
                yield json.dumps({"error": str(e), "sql": final_sql}) + "\n"

        return Response(stream_with_context(generate()), content_type="application/x-ndjson")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Healthcheck
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

# Entry point
if __name__ == "__main__":
    app.run(debug=True, port=5005)
