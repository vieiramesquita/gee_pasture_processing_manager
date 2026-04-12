# app.py

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from fastapi.responses import HTMLResponse
import uvicorn
import core, scheduler
import threading # 🟢 Adicionado para controlo de processo único
from loguru import logger

import engine_s2_c4
import engine_ls_c11_year
import engine_ls_c11_decade

app = FastAPI()

# 🟢 Variável global para garantir que apenas UM scheduler rode de cada vez
scheduler_thread = None

class TaskRequest(BaseModel):
    projeto: str
    cartas: List[str]
    anos: List[int]
    engine: str

def task_dispatcher(config):
    engine_type = config.get("engine_type")
    if engine_type == "s2_c4": return engine_s2_c4.submit_task(config)
    elif engine_type == "ls_c11_year": return engine_ls_c11_year.submit_task(config)
    elif engine_type == "ls_c11_decade": return engine_ls_c11_decade.submit_task(config)
    else: logger.error(f"Motor desconhecido: {engine_type}")

def start_scheduler_if_needed():
    """Garante que a fila de processamento comece a rodar, evitando duplicações."""
    global scheduler_thread
    if scheduler_thread is None or not scheduler_thread.is_alive():
        scheduler_thread = threading.Thread(target=scheduler.scheduler, args=(task_dispatcher,))
        scheduler_thread.daemon = True
        scheduler_thread.start()
        logger.info("⚙️ Motor do Scheduler iniciado/retomado em background.")

# 🟢 EVENTO DE STARTUP: O Auto-Resume!
@app.on_event("startup")
def resume_on_startup():
    project = core.get_setting("gee_project")
    tasks = core.load_state()
    
    # Avalia se há algo a fazer no banco
    pending = [t for t in tasks if t['state'] in ['IN_QUEUE', 'RUNNING', 'PENDING']]
    
    if pending:
        logger.info(f"🔄 Auto-Resume: Encontradas {len(pending)} tarefas paradas.")
        if project and core.init_gee(project):
            start_scheduler_if_needed()
        else:
            logger.warning("⚠️ Tarefas pendentes, mas sem projeto GEE registado. Abra o Dashboard para autenticar.")

@app.post("/api/start")
def start(request: TaskRequest): # 🟢 BackgroundTasks removido daqui
    core.init_gee(request.projeto)
    core.save_setting("gee_project", request.projeto) # 🟢 Salva o projeto para o Auto-Resume
    
    existing = {t["name"]: t["state"] for t in core.load_state()}
    new_configs = []
    
    for c in request.cartas:
        for a in request.anos:
            if request.engine == "s2_c4":
                task_id, config = f"{c.strip()}_{a}", {"year": a, "carta": c.strip(), "engine_type": "s2_c4"}
            elif request.engine == "ls_c11_year":
                task_id, config = f"{c.strip()}_Y{a}", {"grid": c.strip(), "year": a, "engine_type": "ls_c11_year"}
            else:
                task_id, config = f"{c.strip()}_D{a}", {"grid": c.strip(), "decade": a, "engine_type": "ls_c11_decade"}
            
            if existing.get(task_id) not in ["RUNNING", "COMPLETED", "IN_QUEUE"]:
                new_configs.append({
                    "name": task_id, "state": "IN_QUEUE", "config": config,
                    "retries": 0, "gee_id": None, "usage_seconds": 0
                })
    
    if new_configs:
        current_tasks = core.load_state()
        core.save_state(current_tasks + new_configs)
        start_scheduler_if_needed() # 🟢 Gatilha a thread singleton
        
    return {"message": f"{len(new_configs)} tarefas registadas na fila de submissão!"}
    
@app.get("/api/summary")
def summary():
    tasks = core.load_state()
    stats = {"RUNNING": 0, "COMPLETED": 0, "ERROR": 0, "IN_QUEUE": 0, "CANCELLED": 0}
    total_seconds = 0
    
    for t in tasks:
        raw_state = (t.get("state") or "IN_QUEUE").upper()
        total_seconds += t.get("usage_seconds", 0)
        
        final = "IN_QUEUE"
        if raw_state == "RUNNING": final = "RUNNING"
        elif raw_state in ["COMPLETED", "SUCCEEDED"]: final = "COMPLETED"
        elif raw_state in ["FAILED", "ERROR"]: final = "ERROR"
        elif raw_state in ["CANCELLED", "CANCELLING"]: final = "CANCELLED"
            
        stats[final] += 1
        t["state"] = final 

    total_hours = total_seconds / 3600
    return {
        "stats": stats, "tasks": tasks,
        "usage": {
            "seconds": round(total_seconds, 2),
            "hours": round(total_hours, 2),
            "cost": round(total_hours * 0.40, 2)
        }
    }

@app.delete("/api/clear")
def clear():
    core.save_state([])
    return {"message": "Limpo!"}

@app.get("/", response_class=HTMLResponse)
def home():
    with open("index.html", "r", encoding="utf-8") as f: return f.read()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)