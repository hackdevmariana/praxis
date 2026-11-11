from fastapi import FastAPI

app = FastAPI(title="Backend Hola Mundo")

@app.get("/hola")
def hola():
    """Devuelve un saludo"""
    return {"mensaje": "Hola, mundo"}

@app.get("/hola/{nombre}")
def hola_nombre(nombre: str):
    return {"mensaje": f"Hola, {nombre}"}

@app.get("/health")
def health():
    return {"status": "ok"}
