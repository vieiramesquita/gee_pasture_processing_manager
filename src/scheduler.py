import ee
import time
from core import save_state, logger # Removido o send_alert

MAX_RUNNING, MAX_QUEUE, SLEEP_TIME = 15, 250, 30

FATAL_ERRORS = [
    'No valid training data were found',
    'Expected 2 classes for PROBABILITY',
    'Invalid numInputs: 0',
    'Parameter \'image\' is required',
    'image is required and may not be null'
]

def check_status(gee_id):
    try:
        # Tenta pegar pelos metadados da operação (comportamento padrão para exports)
        op = ee.data.getOperation(f"projects/earthengine-legacy/operations/{gee_id}")
        if op:
            metadata = op.get("metadata", {})
            state = metadata.get("state", "UNKNOWN")
            error = op.get("error", {}).get("message", "")
            usage = metadata.get("batchEecuUsageSeconds", 0) # 🟢 Extrai EECU
            return state, error, usage
            
        return "UNKNOWN", "No data", 0
    except Exception as e:
        logger.error(f"Erro na consulta: {e}")
        return "UNKNOWN", str(e), 0

def scheduler(task_queue, submit_fn):
    active_tasks, finished_tasks = [], []

    while task_queue or active_tasks:
        while len(active_tasks) < MAX_RUNNING and task_queue:
            task_config = task_queue.pop(0)
            task = submit_fn(task_config)
            task["state"] = "PENDING"
            active_tasks.append(task)
            time.sleep(2)

        new_active = []
        for task in active_tasks:
            state, error, usage = check_status(task["gee_id"]) # 🟢 Recebe usage
            task["state"], task["error_msg"], task["usage_seconds"] = state, error, usage
            
            if state in ["COMPLETED", "SUCCEEDED"]:
                finished_tasks.append(task)
            elif state in ["CANCELLED", "CANCELLING"]:
                finished_tasks.append(task)
            elif state in ["FAILED", "ERROR"]:
                err_msg_clean = (error or "").lower()
                is_fatal = any(fatal.lower() in err_msg_clean for fatal in FATAL_ERRORS)
                
                if not is_fatal and task.get("retries", 0) < 3:
                    logger.info(f"♻️ Reiniciando {task['name']}")
                    new_task = submit_fn(task["config"])
                    new_task["retries"] = task.get("retries", 0) + 1
                    new_task["state"] = "PENDING"
                    new_active.append(new_task)
                else:
                    # Em vez de enviar Telegram, registramos o erro crítico no log
                    logger.error(f"🚨 FALHA DEFINITIVA em {task['name']}: {error}")
                    finished_tasks.append(task)
            else:
                new_active.append(task)
            
        active_tasks = new_active
        save_state(active_tasks + finished_tasks)
        time.sleep(SLEEP_TIME)