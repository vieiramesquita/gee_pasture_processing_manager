# scheduler.py

import ee, time, core
from core import save_state, logger

# --- CONFIGURAÇÕES DE CONTROLE ---
MAX_GEE_SLOTS = 40     # Limite de tarefas registradas no GEE (Submissão)
SLEEP_TIME = 30        # Intervalo entre checagens globais

# 🟢 LISTA DE ERROS FATAIS RESTAURADA
FATAL_ERRORS = [
    'No valid training data were found',
    'Expected 2 classes for PROBABILITY',
    'Invalid numInputs: 0',
    'Parameter \'image\' is required',
    'image is required and may not be null'
]

def check_status(gee_id):
    """Consulta profunda via Operations API para garantir registro de SUCCEEDED/DONE."""
    if not gee_id: return "IN_QUEUE", "", 0
    try:
        op = ee.data.getOperation(f"projects/earthengine-legacy/operations/{gee_id}")
        if op:
            metadata = op.get("metadata", {})
            state = metadata.get("state", "UNKNOWN")
            usage = metadata.get("batchEecuUsageSeconds", 0) # Coleta EECU-seconds
            error = op.get("error", {}).get("message", "")
            
            # Mapeamento robusto de estados terminais
            if state in ['SUCCEEDED', 'DONE']: return "COMPLETED", "", usage
            if state in ['FAILED', 'ERROR']: return "FAILED", error, usage
            if state in ['CANCELLED', 'CANCELLING']: return "CANCELLED", "", usage
            
            return "RUNNING", "", usage
        return "UNKNOWN", "No data", 0
    except Exception: return "RUNNING", "API Lag", 0

def scheduler(submit_fn):
    while True:
        all_tasks = core.load_state()
        
        # Separação por estados para gestão das duas filas
        internal_queue = [t for t in all_tasks if t['state'] == 'IN_QUEUE']
        active_gee = [t for t in all_tasks if t['state'] in ['RUNNING', 'PENDING']]
        others = [t for t in all_tasks if t['state'] not in ['IN_QUEUE', 'RUNNING', 'PENDING']]
        
        # 1. Varredura Geral de Status
        updated_active = []
        for task in active_gee:
            state, error, usage = check_status(task["gee_id"])
            task["state"], task["error_msg"], task["usage_seconds"] = state, error, usage
            
            if state == "FAILED":
                # 🟢 Lógica de checagem de Erro Fatal
                err_msg_clean = (error or "").lower()
                is_fatal = any(fatal.lower() in err_msg_clean for fatal in FATAL_ERRORS)
                
                if not is_fatal and task.get("retries", 0) < 3:
                    logger.info(f"♻️ Falha temporária. Retornando {task['name']} para fila interna.")
                    task["state"], task["gee_id"] = "IN_QUEUE", None
                    task["retries"] += 1
                else:
                    logger.error(f"🚨 FALHA DEFINITIVA em {task['name']}: {error}")
                    task["state"] = "ERROR" # Marca como erro definitivo no Dashboard
            
            updated_active.append(task)

        # 2. Submissão Controlada (Gatekeeper)
        current_active_slots = len([t for t in updated_active if t['state'] == 'RUNNING'])
        available = MAX_GEE_SLOTS - current_active_slots
        
        if available > 0 and internal_queue:
            to_submit = internal_queue[:available]
            for task in to_submit:
                logger.info(f"📤 Submetendo ao GEE: {task['name']}")
                new_gee = submit_fn(task["config"])
                if new_gee:
                    task.update({"gee_id": new_gee["gee_id"], "state": "RUNNING"})
                    updated_active.append(task)
                    internal_queue.remove(task)
                time.sleep(1)

        # 3. Persistência Final
        save_state(updated_active + others + internal_queue)
        
        # Encerra o loop se não houver mais nada pendente
        if not internal_queue and not [t for t in updated_active if t['state'] == 'RUNNING']:
            logger.info("✅ Todas as tarefas foram processadas.")
            break
            
        time.sleep(SLEEP_TIME)