@echo off
setlocal
title Formiguinhas - Inicializacao

set "ROOT_DIR=%~dp0"
set "PROJECT_DIR=%ROOT_DIR%formiguinhas_projeto"

if not exist "%PROJECT_DIR%\manage.py" (
    echo ERRO: nao foi encontrada a pasta do projeto em:
    echo %PROJECT_DIR%
    pause
    exit /b 1
)

where python >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
) else (
    where py >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD=py -3"
    ) else (
        echo ERRO: Python nao foi encontrado no computador.
        pause
        exit /b 1
    )
)

cd /d "%PROJECT_DIR%"

if not exist "venv\Scripts\python.exe" (
    echo Criando ambiente virtual...
    %PYTHON_CMD% -m venv venv
    if errorlevel 1 goto :erro
)

echo Instalando dependencias...
"%CD%\venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :erro

echo Atualizando banco de dados...
"%CD%\venv\Scripts\python.exe" manage.py migrate
if errorlevel 1 goto :erro

echo Iniciando sistema...
echo Acesse http://127.0.0.1:8000/
"%CD%\venv\Scripts\python.exe" manage.py runserver
if errorlevel 1 goto :erro

endlocal
exit /b 0

:erro
echo.
echo O sistema nao foi iniciado. Verifique a mensagem acima.
pause
endlocal
exit /b 1