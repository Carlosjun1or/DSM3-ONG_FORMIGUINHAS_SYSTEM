@echo off
setlocal

cd /d "%~dp0formiguinhas_projeto"

if not exist "venv\Scripts\python.exe" (
    echo Criando ambiente virtual...
    python -m venv venv
    if errorlevel 1 exit /b 1
)

echo Instalando dependencias...
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo Atualizando banco de dados...
venv\Scripts\python.exe manage.py migrate
if errorlevel 1 exit /b 1

echo Iniciando sistema...
venv\Scripts\python.exe manage.py runserver

endlocal