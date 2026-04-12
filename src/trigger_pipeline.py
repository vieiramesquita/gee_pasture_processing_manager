import time, subprocess, core, os
from loguru import logger

def run_pipeline():
    logger.info("🚀 GEE finalizado! Iniciando Rclone sync...")
    # 1. Download
    if not os.path.exists("./tile_download"):
        os.mkdir("./tile_download")
    # os.system("rclone config")
    # subprocess.run("rclone sync gdrive:MAPBIOMAS_TEST_PASTURE ./tile_download --progress", shell=True)
    
    logger.info("🛠️ Iniciando Mosaico e Filtro 3x3x5...")
    # 2. Aqui você chamaria seu script de GDAL e Scipy
    # subprocess.run("python3 process_mosaics.py", shell=True)
    
    logger.info("🤖 Enviando métricas para Gemma/OpenInterpreter...")
    # 3. Dispara a análise de IA que discutimos

while True:
    tasks = core.load_state()
    # Verifica se há algo rodando ou na fila
    active = [t for t in tasks if t['state'] in ['RUNNING', 'IN_QUEUE', 'PENDING']]
    
    if len(tasks) > 0 and len(active) == 0:
        run_pipeline()
        break # Para o sentinela após o gatilho, ou limpe o banco para o próximo lote
        
    logger.info(f"⏳ Aguardando... {len(active)} tarefas restantes.")
    time.sleep(600) # Checa a cada 10 min