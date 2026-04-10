from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from typing import List
from fastapi.responses import HTMLResponse
import uvicorn
import core, scheduler

import engine_s2_c4
import engine_ls_c11_year
import engine_ls_c11_decade

app = FastAPI()

task_queue = []

class TaskRequest(BaseModel):
    projeto: str
    cartas: List[str]
    anos: List[int]
    engine: str # "s2_c4", "ls_c11_year" ou "ls_c11_decade"

def task_dispatcher(task_wrapper):
    """Encaminha a tarefa para o motor correto baseado na escolha do usuário."""
    engine_type = task_wrapper["engine_type"]
    config = task_wrapper["config"]
    
    if engine_type == "s2_c4":
        return engine_s2_c4.submit_task(config)
    elif engine_type == "ls_c11_year":
        return engine_ls_c11_year.submit_task(config)
    elif engine_type == "ls_c11_decade":
        return engine_ls_c11_decade.submit_task(config)

@app.post("/api/start")
def start(request: TaskRequest, bg: BackgroundTasks):
    core.init_gee(request.projeto)
    existing = {t["name"]: t["state"] for t in core.load_state()}
    
    new_tasks_wrapped = []
    for c in request.cartas:
        for a in request.anos:
            # Define o nome único e o dicionário de config esperado por cada engine
            if request.engine == "s2_c4":
                task_id = f"{c.strip()}_{a}"
                internal_config = {"year": a, "carta": c.strip()}
            elif request.engine == "ls_c11_year":
                task_id = f"{c.strip()}_Y{a}"
                internal_config = {"grid": c.strip(), "year": a}
            else: # ls_c11_decade
                task_id = f"{c.strip()}_D{a}"
                internal_config = {"grid": c.strip(), "decade": a}
            
            if existing.get(task_id) not in ["RUNNING", "COMPLETED", "IN_QUEUE"]:
                new_tasks_wrapped.append({
                    "engine_type": request.engine, 
                    "config": internal_config
                })
    
    if not new_tasks_wrapped:
        return {"message": "Tarefas já em processamento ou concluídas."}
        
    task_queue.extend(new_tasks_wrapped)
    # Passamos o despachante para o scheduler
    bg.add_task(scheduler.scheduler, task_queue, task_dispatcher)
    return {"message": f"{len(new_tasks_wrapped)} tarefas iniciadas via {request.engine}!"}

@app.get("/api/summary")
def summary():
    tasks = core.load_state()
    stats = {"RUNNING": 0, "COMPLETED": 0, "ERROR": 0, "IN_QUEUE": 0, "CANCELLED": 0}
    total_seconds = 0
    
    for t in tasks:
        raw_state = (t.get("state") or "IN_QUEUE").upper()
        total_seconds += t.get("usage_seconds", 0) # 🟢 Soma o acumulado
        
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

    total_hours = total_seconds / 3600
    total_cost = total_hours * 0.40 # 🟢 Cálculo do custo (US$ 0,40/h)

    return {
        "stats": stats, 
        "tasks": tasks,
        "usage": {
            "seconds": round(total_seconds, 2),
            "hours": round(total_hours, 2),
            "cost": round(total_cost, 2)
        }
    }
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