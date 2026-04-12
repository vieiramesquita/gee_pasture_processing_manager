# GEE Pasture Processing Monitor 🛰️🌱

O **GEE Pasture Processing Monitor** é uma infraestrutura robusta para automação, gestão e auditoria de processamentos geoespaciais de larga escala no Google Earth Engine (GEE). Especializado na geração de mapas probabilísticos de pastagem, o sistema evoluiu de um simples monitor para um orquestrador de pipeline multisensor.

## 🚀 Funcionalidades Atuais (Core)

* **Arquitetura Multisensor**: Suporte nativo para Sentinel-2 (C4) e Landsat Series (C11 - Anual e Decadal).
* **Fila Dupla (Gatekeeper)**: Separação entre a fila de submissão interna (suporta milhares de tiles) e a janela de execução no GEE (limitada a 40 tarefas simultâneas para evitar bloqueios de cota).
* **Monitorização Financeira (Billing)**: Cálculo em tempo real do consumo de recursos em EECU-seconds, EECU-hours e estimativa de custo em dólares (USD).
* **Resiliência de Auto-Resume**: Persistência de configurações de projeto e estado das tarefas em SQLite. O sistema retoma o processamento automaticamente após quedas ou reinicializações do servidor.
* **Motor de Auto-Retentativa Inteligente**: Gere falhas temporárias de rede e identifica Erros Fatais (ex: falta de amostras) para interromper tarefas inviáveis e economizar recursos.
* **Dashboard Avançado**: Interface interativa com ordenação de status/tentativas e cartões de resumo financeiro.

## 🛠️ Tecnologias

* **Backend**: FastAPI (Python) com processamento Singleton Thread.
* **Frontend**: Dashboard reativo (HTML5, Tailwind CSS, JS).
* **Base de Dados**: SQLite com persistência de metadados e configurações.
* **SIG/Cloud**: Google Earth Engine High-Volume API.

## ⚙️ Guia de Instalação e Uso

### 1. Requisitos
```bash
pip install fastapi uvicorn earthengine-api loguru requests pydantic dynaconf
earthengine authenticate
```

### 2. Execução
```bash
python src/app.py
```

Acesse a interface em <http://localhost:8000>


## 🗺️ Roadmap de Implementação (Pipeline Automática)
Este roadmap define os próximos passos para a automação total "Hands-Free", integrando o processamento em nuvem com análise local por IA.

🟢 Fase 4: Download Bot (Em Desenvolvimento)
- [ ] Criar o script download_bot.py para monitorar a base de dados SQLite.

- [ ] Integrar o Rclone para acionar o download (sync) da pasta no Google Drive/Google Cloud Storage assim que as tarefas terminarem no GEE.

🟡 Fase 5: Moisaico e filtragem multidimensional com GDAL/Scipy
- [ ] Implementar mosaico automático via gdalbuildvrt e gdal_translate.

- [ ] Aplicar o Filtro Multidimensional de Mediana (3x3x5) usando Scipy para suavização espectro-temporal.

🟡 Fase 6: Otimização de Limiar (Soft-to-Hard)
- [ ] Cálculo automático de métricas de precisão (AUROC, Precision/Recall AUC).

- [ ] Definição do ponto de corte ideal (Cutting Point) via Youden's J Statistic.

🔴 Fase 7: Auditoria por IA (Gemma + OpenInterpreter)
- [ ] Geração de relatórios automáticos de área por Tile, Bioma e País.

- [ ] Auditoria de consistência temporal e espacial por LLM Local.

- [ ]  Alertas automáticos via Telegram/Email em caso de inconsistências.

## 📂 Visão Geral dos Ficheiros
app.py: Servidor API e despachante de tarefas multisensor.

core.py: Infraestrutura de base de dados, logs e persistência de settings.

scheduler.py: O Gatekeeper que controla o fluxo entre a fila local e a nuvem.

engine_s2_c4.py: Motor de classificação Sentinel-2.

engine_ls_c11_year.py: Motor Landsat Anual.

engine_ls_c11_decade.py: Motor Landsat Decadal.

Desenvolvido para fluxos de trabalho MapBiomas Pastagem.
