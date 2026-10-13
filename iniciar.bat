@echo off
setlocal
title Formiguinhas - Estoque - Inicializacao

set "ROOT_DIR=%~dp0"
set "PROJECT_DIR=%ROOT_DIR%formiguinhas_projeto"

if not exist "%PROJECT_DIR%\manage.py" (
    echo ERRO: nao foi encontrada a pasta do projeto em:
    echo %PROJECT_DIR%
    goto erro
)

set "PYTHON_CMD="
py -3 --version >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD (
    python --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
    echo ERRO: Python nao foi encontrado no computador.
    echo Instale o Python e marque a opcao "Add Python to PATH".
    goto erro
)

cd /d "%PROJECT_DIR%"

if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" --version >nul 2>&1
    if errorlevel 1 (
        echo Ambiente virtual invalido. Recriando...
        rmdir /s /q venv
    )
)

if not exist "venv\Scripts\python.exe" (
    echo Criando ambiente virtual...
    %PYTHON_CMD% -m venv venv
    if errorlevel 1 goto erro
)

echo Instalando dependencias...
"venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto erro

echo Atualizando banco de dados...
"venv\Scripts\python.exe" manage.py migrate
if errorlevel 1 goto erro

echo Iniciando sistema...
echo Acesse http://127.0.0.1:8000/
"venv\Scripts\python.exe" manage.py runserver
if errorlevel 1 goto erro

endlocal
exit /b 0

:erro
echo.
echo O sistema nao foi iniciado. Verifique a mensagem acima.
pause
endlocal
exit /b 1
