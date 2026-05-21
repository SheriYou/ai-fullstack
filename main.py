from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def home():
    return {"message": "Hello World","username": "ray"}

@app.get("/search")
def search(keyword: str):
    return {
        "keyword": keyword
    }

@app.get("/user/{user_id}")
def get_user(user_id: int):
    return {
        "user_id": user_id,
        "name": "Ray"
    }

@app.get("/user/product")
def product(product_id: int):
    return {
        "user_id": product_id,
        "name": "Ray11"
    }