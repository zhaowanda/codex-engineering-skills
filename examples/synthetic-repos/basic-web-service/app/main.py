from fastapi import FastAPI


app = FastAPI(title="Synthetic Orders API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/orders")
def create_order(payload: dict[str, object]) -> dict[str, object]:
    return {"id": "order-demo-1", "payload": payload}
