from sqlalchemy import create_engine, text

engine = create_engine("oracle+oracledb://riskintegov2:riskintegov2@localhost:1521/riskintegov2")

with engine.connect() as conn:
    result = conn.execute(text("SELECT * FROM sales WHERE ROWNUM <= 1"))
    for row in result:
        print(row)
