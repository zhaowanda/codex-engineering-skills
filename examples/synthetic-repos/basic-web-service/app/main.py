from fastapi import FastAPI


app = FastAPI(title="Synthetic Tasks API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/tasks")
def create_task(payload: dict[str, object]) -> dict[str, object]:
    return {"id": "task-demo-1", "payload": payload}
