import secrets
import sqlite3
from pydantic import BaseModel
from fastapi import FastAPI, Depends, HTTPException, Header, Request, BackgroundTasks
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI()

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    return FileResponse(os.path.join(static_dir,"index.html"))

conn = sqlite3.connect("inventory.db")
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        defLow INTEGER DEFAULT 5
    )
""")
conn.commit()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS api_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT NOT NULL UNIQUE,
        owner TEXT NOT NULL
    )
""")
conn.commit()

def create_api_key(owner: str) -> str:
    key = secrets.token_hex(16)
    cursor.execute(
        "INSERT INTO api_keys (key, owner) VALUES (?, ?)",
        (key, owner)
    )
    conn.commit()
    return key

class RegisterBody(BaseModel):
    name: str

class ItemBody(BaseModel):
    name: str
    quantity: int
    defLow: int = 5

def get_api_key(request: Request) -> str:
    return request.headers.get("x-api-key", "unknown")

limiter = Limiter(key_func=get_api_key)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Try again later!"}
    )

@app.post("/register")
@limiter.limit("5/minute")
async def register(body: RegisterBody, request: Request):
    key = create_api_key(body.name)
    return {"api_key": key, "message": "Save this key! You won't be able to see it again."}

async def verify_api_key(x_api_key: str = Header()):
    cursor.execute("SELECT * FROM api_keys WHERE key = ?", (x_api_key,))
    result = cursor.fetchone()
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return result



def logaction(message: str):
    log = open("inventory.log", "a")
    log.write(message + "\n")
    log.close()

@app.get("/items", dependencies=[Depends(verify_api_key)])
@limiter.limit("30/minute")
async def getitems(request: Request):
    conn = sqlite3.connect("inventory.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM items")
    items = cursor.fetchall()
    conn.close()
    return [{"id": i[0], "name": i[1], "quantity": i[2], "defLow": i[3]} for i in items]

@app.post("/items", dependencies=[Depends(verify_api_key)])
@limiter.limit("10/minute")
async def additem(body: ItemBody, request: Request,background_tasks:BackgroundTasks):
    conn = sqlite3.connect("inventory.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO items (name, quantity, defLow) VALUES (?, ?, ?)",
        (body.name, body.quantity, body.defLow)
    )
    conn.commit()
    itemid = cursor.lastrowid
    conn.close()
    background_tasks.add_task(logaction, f"Added {body.name}. (Quantity: {body.quantity})")
    return {"id": itemid, "name": body.name, "quantity": body.quantity}

@app.patch("/items/{itemid}/stock", dependencies=[Depends(verify_api_key)])
@limiter.limit("10/minute")
async def updatestock(itemid: int, request: Request, newquantity: int, background_tasks: BackgroundTasks):
    conn = sqlite3.connect("inventory.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM items WHERE id = ?", (itemid,))
    item = cursor.fetchone()
    if item is None:
        conn.close()
        raise HTTPException(status_code=404, detail="item not found")
    cursor.execute(
        "UPDATE items SET quantity = ? WHERE id = ?",
        (newquantity, itemid)
    )
    conn.commit()
    conn.close()
    background_tasks.add_task(logaction, f"Updated item {itemid} to {newquantity}")

    if newquantity <= item[3]:
        background_tasks.add_task(logaction, f"LOW stock warning: {item[1]} is now {newquantity}")
    return {"updated new quantity": newquantity}

@app.delete("/items/{itemid}", dependencies=[Depends(verify_api_key)])
@limiter.limit("5/minute")
async def deleteitem(itemid: int, request: Request):
    conn = sqlite3.connect("inventory.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM items WHERE id = ?", (itemid,))
    item = cursor.fetchone()
    if item is None:
        conn.close()
        raise HTTPException(status_code=404, detail = "item not found")
    cursor.execute("DELETE FROM items WHERE id = ?", (itemid,))
    conn.commit()
    conn.close()

    return {"message": f"item {itemid} deleted"}

@app.get("/items/lowstock", dependencies=[Depends(verify_api_key)])
async def lowstock():
    conn = sqlite3.connect("inventory.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM items")
    items = cursor.fetchall()
    conn.close()

    return[{"id": i[0], "name": i[1], "quantity": i[2]} for i in items if i[2] <= i[3]]


def main():
    import uvicorn
    uvicorn.run("resolution_week5_bacasss.main:app", host="127.0.0.1", port=8000)

if __name__ == "__main__":
    main()





# import secrets
# import sqlite3
# from pydantic import BaseModel
# from fastapi import FastAPI, Depends, HTTPException, Header

# conn = sqlite3.connect("app.db")
# cursor = conn.cursor()
# app = FastAPI()

# cursor.execute("""
#     CREATE TABLE IF NOT EXISTS books (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         title TEXT NOT NULL,
#         author TEXT NOT NULL,
#         read INTEGER DEFAULT 0
#     )
# """)
# conn.commit()

# cursor.execute("""
#     CREATE TABLE IF NOT EXISTS api_keys (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         key TEXT NOT NULL UNIQUE,
#         owner TEXT NOT NULL
#     )
# """)
# conn.commit()

# def create_api_key(owner: str) -> str:
#     key = secrets.token_hex(16)
#     cursor.execute(
#         "INSERT INTO api_keys (key, owner) VALUES (?, ?)",
#         (key, owner)
#     )
#     conn.commit()
#     return key

# # cursor.execute(
# #     "INSERT INTO books (title, author) VALUES (?, ?)",
# #     ("The Hobbit", "J.R.R. Tolkien")
# # )
# # conn.commit()

# # cursor.execute("SELECT * FROM books WHERE author = ?", ("J.R.R. Tolkien",))
# # results = cursor.fetchall()
# # for row in results:
# #     print(row)

# # cursor.execute("SELECT * FROM books")
# # all_books = cursor.fetchall()

# # cursor.execute(
# #     "UPDATE books SET read = 1 WHERE id = ?",
# #     (1,)
# # )
# # conn.commit()

# # cursor.execute("DELETE FROM books WHERE id = ?", (1,))
# # conn.commit()

# class RegisterBody(BaseModel):
#     name: str

# @app.post("/register")
# async def register(body: RegisterBody):
#     key = create_api_key(body.name)
#     return {"api_key": key, "message": "Save this key! You won't be able to see it again."}

# async def verify_api_key(x_api_key: str = Header()):
#     cursor.execute("SELECT * FROM api_keys WHERE key = ?", (x_api_key,))
#     result = cursor.fetchone()
#     if result is None:
#         raise HTTPException(status_code=401, detail="Invalid API key")
#     return result

# @app.get("/secret-data", dependencies=[Depends(verify_api_key)])
# async def get_secret_data():
#     return {"message": "You have access!"}