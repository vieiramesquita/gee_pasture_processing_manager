# GEE Pasture Processing Monitor 🛰️🌱

O **GEE Pasture Processing Monitor** é um sistema especializado para a automação e gestão de processamentos de larga escala voltados à geração de mapas de pastagem no Google Earth Engine (GEE). 

Este projeto foi desenvolvido para substituir fluxos de trabalho manuais por uma infraestrutura robusta que inclui monitoramento em tempo real, persistência de dados e inteligência de submissão em lotes.

## 🚀 Funcionalidades Principais

* **Fila de Processamento Inteligente**: Gerencia a submissão de tarefas respeitando as cotas do GEE (configurado para 15 tarefas simultâneas).
* **Dashboard em Tempo Real**: Interface dinâmica para acompanhar o progresso das classificações por "Carta/Ano".
* **Persistência com SQLite**: Utiliza o nome do Tile como chave primária, garantindo que o histórico seja único e impedindo duplicatas no banco de dados.
* **Motor de Auto-Retentativa**: Detecta falhas de rede ou timeouts e reinicia a tarefa automaticamente (limite de 3 tentativas).
* **Detecção de Erros Fatais**: Interrompe o processamento imediatamente ao detectar erros lógicos (ex: falta de dados de treinamento) para economizar recursos e cota.
* **Exportação Direta**: Configurado para exportar os resultados diretamente para o Google Drive na pasta `MAPBIOMAS_TEST_PASTURE`.

## 🛠️ Tecnologias

* **Backend**: FastAPI (Python).
* **Frontend**: HTML5, Tailwind CSS e JavaScript (Dashboard reativo).
* **Banco de Dados**: SQLite para armazenamento leve e eficiente.
* **Log**: Loguru para rastreamento detalhado de eventos e erros.

## ⚙️ Como Instalar e Usar

### 1. Preparação
Certifique-se de ter o Python 3.9+ e as dependências instaladas:
```bash
pip install fastapi uvicorn earthengine-api loguru requests pydantic
earthengine authenticate
```

### 2. Execução
Inicie o sistema rodando o servidor FastAPI:

```bash
python src/app.py
```
Acesse no navegador: `http://localhost:8000`

### 3. Fluxo de Trabalho
- **Inicialização:** Ao abrir o dashboard, informe o nome do seu projeto no Google Cloud para autenticar o GEE.
- **Configuração:** Insira os anos desejados e a lista de Cartas (Tiles) para processar.
- **Acompanhamento:** O sistema gerencia a fila automaticamente. Se uma tarefa falhar, ela ficará vermelha (ERROR) e o motivo detalhado será registrado no arquivo `app.log`.

## 🖥️ Guia de Uso do Dashboard
A interface foi projetada para ser intuitiva, dividindo-se entre controles de entrada e monitoramento de saída.

### 1. Configuração do Projeto (Setup)
- **Projeto Atual:** Ao acessar o sistema, clique no ícone de edição ou use o modal inicial para inserir o ID do seu projeto no Google Cloud (ex: `ee-meu-projeto`).
- **Inicialização:** Essa ação aciona a inicialização dinâmica da API do Earth Engine para a sessão atual.

### 2. Nova Execução de Pastagem
- **Anos para Processar:** Insira os anos desejados separados por vírgula (ex: `2020, 2021, 2022`).
- **Cartas (Tiles):** Cole a lista de cartas IBGE que deseja processar. Você pode inserir uma por linha ou separadas por vírgula.
- **Botão Iniciar:** Ao clicar em "Iniciar Processamento", o sistema valida os dados e os envia para a fila de execução em segundo plano.

### 3. Painel de Monitoramento (Dashboard)
**Cartões de Resumo:** Acompanhe o status geral através dos quatro contadores automáticos:
- 🔵 **Running:** Tarefas em processamento ativo no GEE.
- 🟡 **In Queue:** Tarefas aguardando vaga na fila de submissão.
- 🟢 **Completed:** Tarefas finalizadas com sucesso e exportadas para o Drive.
- 🔴 **Failed:** Tarefas que falharam permanentemente ou atingiram o limite de retentativas.
- ⚪ **Cancelled:** Tarefas que foram interrompidas manualmente no console do GEE.

**Tabela de Tarefas:** Lista detalhada mostrando o nome do Tile, o ID único gerado pelo Google, o status atual e o número de tentativas realizadas pelo motor de auto-retentativa.

### 4. Manutenção e Limpeza
- **Limpar Dados (Reset):** Localizado na parte inferior da barra lateral, este botão limpa o histórico do banco de dados SQLite e esvazia a fila de tarefas atual.
- **Logs Técnicos:** Em caso de erros (ERROR), o motivo detalhado não polui a interface, mas fica registrado para auditoria no arquivo local `app.log`.

## 📂 Visão Geral dos Arquivos
- `core.py`: Gerencia a conexão com o banco de dados e a inicialização segura do GEE.
- `engine.py`: Contém a inteligência de classificação espectro-temporal do MapBiomas Pastagem.
- `scheduler.py`: O "cérebro" que monitora o status no Google e decide sobre retentativas.
- `app.py`: Ponto de entrada que conecta a interface web ao motor de processamento.

## 🛡️ Segurança e Privacidade
Este repositório está configurado para não subir arquivos de banco de dados (`.db`) ou logs (`.log`), protegendo informações sensíveis sobre seus projetos e dados de processamento.

> Desenvolvido para fluxos de trabalho MapBiomas.
