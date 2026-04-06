import os
from sqlalchemy import create_engine, text

def main():
    try:
        engine = create_engine('postgresql://thai_app_user:ILoveThai@%2537@localhost:5432/ThaiApp')
        with engine.connect() as conn:
            res = conn.execute(text("SELECT title, image_path FROM events WHERE title LIKE '%Ребефинг%' OR title LIKE '%Венер%';"))
            for row in res:
                print(row)
    except Exception as e:
        print("Error:", e)

if __name__ == '__main__':
    main()
