from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from typing import List
from fastapi.responses import HTMLResponse
import uvicorn
import core, engine, scheduler

app = FastAPI()

class TaskRequest(BaseModel):
    projeto: str
    cartas: List[str]
    anos: List[int]

task_queue = []

@app.post("/api/start")
def start(request: TaskRequest, bg: BackgroundTasks):
    core.init_gee(request.projeto)
    
    # Carrega o estado atual para saber o que já está rodando
    existing = {t["name"]: t["state"] for t in core.load_state()}
    
    new = []
    for c in request.cartas:
        for a in request.anos:
            task_name = f"{c.strip()}_{a}"
            status_atual = existing.get(task_name)
            
            # 🟢 SÓ IGNORA se já estiver RUNNING, COMPLETED ou IN_QUEUE
            if status_atual not in ["RUNNING", "COMPLETED", "IN_QUEUE"]:
                new.append({"carta": c.strip(), "year": a})
    
    if not new:
        return {"message": "As tarefas informadas já estão em processamento ou concluídas."}
        
    task_queue.extend(new)
    bg.add_task(scheduler.scheduler, task_queue, engine.submit_task)
    return {"message": f"{len(new)} tarefas enviadas para a fila!"}

@app.get("/api/summary")
def summary():
    tasks = core.load_state()
    stats = {"RUNNING": 0, "COMPLETED": 0, "ERROR": 0, "IN_QUEUE": 0, "CANCELLED": 0}
    
    for t in tasks:
        raw_state = (t.get("state") or "IN_QUEUE").upper()
        
        final = "IN_QUEUE"
        if raw_state == "RUNNING": 
            final = "RUNNING"
        elif raw_state in ["COMPLETED", "SUCCEEDED"]: 
            final = "COMPLETED"
        elif raw_state in ["FAILED", "ERROR"]: 
            final = "ERROR"
        # 🔴 ATUALIZAÇÃO: Agrupa CANCELLING no contador de CANCELLED
        elif raw_state in ["CANCELLED", "CANCELLING"]: 
            final = "CANCELLED"
            
        stats[final] += 1
        t["state"] = final 
        
    return {"stats": stats, "tasks": tasks}
    
@app.delete("/api/clear")
def clear():
    task_queue.clear()
    core.save_state([])
    return {"message": "Limpo!"}

@app.get("/", response_class=HTMLResponse)
def home():
    with open("index.html", "r", encoding="utf-8") as f: return f.read()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)