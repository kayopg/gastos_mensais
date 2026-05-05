@echo off
REM =====================================================================
REM  Gastos Mensais - Cartao de Credito
REM  Cria/ativa venv, instala dependencias e roda o Streamlit.
REM  Uso: clique duas vezes em run.bat OU execute no PowerShell/CMD.
REM =====================================================================
setlocal
cd /d "%~dp0"

REM Cria venv se nao existir
if not exist ".venv" (
    echo [1/3] Criando ambiente virtual em .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo Falha ao criar venv. Verifique se o Python esta instalado e no PATH.
        pause
        exit /b 1
    )
)

REM Ativa
call .venv\Scripts\activate.bat

REM Instala/atualiza dependencias (silencioso na maioria do tempo)
echo [2/3] Verificando dependencias...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo Falha ao instalar dependencias.
    pause
    exit /b 1
)

REM Sobe o app — abre o navegador automaticamente em http://localhost:8501
echo [3/3] Iniciando o dashboard...
streamlit run app.py
pause
endlocal
