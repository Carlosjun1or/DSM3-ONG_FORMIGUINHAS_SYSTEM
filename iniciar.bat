@echo off
echo ==========================================
echo A iniciar o ambiente da ONG Formiguinhas...
echo ==========================================

REM 1. Cria o venv se nao existir
if not exist "venv" (
    echo Criando ambiente virtual...
    python -m venv venv
)

REM 2. Ativa o venv e instala requisitos
call venv\Scripts\activate
echo Instalando dependencias...
pip install -r requirements.txt

REM 3. Aplica migracoes no banco de dados
echo Atualizando banco de dados...
python manage.py migrate

REM 4. Inicia o servidor
echo Iniciando o servidor Django...
python manage.py runserver