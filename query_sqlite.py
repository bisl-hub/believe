import sqlite3

conn = sqlite3.connect("data/articles.db")
c = conn.cursor()
c.execute("SELECT count(*) FROM articles WHERE faiss_id <= 2000010199999999;")
res = c.fetchone()
print(res[0])
conn.close()
