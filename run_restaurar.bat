@echo off
chcp 65001 > nul
cd /d "c:\Users\carol\OneDrive\Documentos\GitHub\DSM3-ONG_FORMIGUINHAS_SYSTEM\formiguinhas_projeto"
echo === TESTE DE CONEXAO === > ..\restaurar_output.txt 2>&1
venv\Scripts\python.exe testar_atlas.py >> ..\restaurar_output.txt 2>&1
echo. >> ..\restaurar_output.txt
echo === RESTAURAR SQLITE DO MONGO === >> ..\restaurar_output.txt 2>&1
venv\Scripts\python.exe manage.py restaurar_sqlite_do_mongo >> ..\restaurar_output.txt 2>&1
echo. >> ..\restaurar_output.txt
echo Concluido. >> ..\restaurar_output.txt 2>&1
