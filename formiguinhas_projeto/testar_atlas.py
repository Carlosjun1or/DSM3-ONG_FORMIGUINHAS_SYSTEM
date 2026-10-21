import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

uri = os.getenv("MONGODB_URI")
nome_banco = os.getenv("MONGODB_DATABASE", "formiguinhas_db")

if not uri:
    raise RuntimeError(
        "MONGODB_URI não foi encontrada no arquivo .env"
    )

tls_kwargs = {}
try:
    import certifi
    tls_kwargs["tlsCAFile"] = certifi.where()
except ImportError:
    pass

cliente = MongoClient(
    uri,
    serverSelectionTimeoutMS=5000,
    **tls_kwargs,
)

try:
    cliente.admin.command("ping")
    print("Conexão com o MongoDB Atlas funcionando!")

    banco = cliente[nome_banco]
    print(f"Banco selecionado: {nome_banco}")
    print("Collections existentes:", banco.list_collection_names())

except Exception as erro:
    erro_str = str(erro)
    print("Não foi possível conectar ao MongoDB Atlas.")
    if "TLSV1_ALERT_INTERNAL_ERROR" in erro_str or "SSL handshake failed" in erro_str:
        ip_atual = "desconhecido"
        try:
            import urllib.request
            ip_atual = urllib.request.urlopen("https://api.ipify.org", timeout=2).read().decode("utf-8")
        except Exception:
            pass
        print("\n[MOTIVO IDENTIFICADO]")
        print(f"O seu endereço IP público atual ({ip_atual}) NÃO está liberado no MongoDB Atlas.")
        print("\n[COMO RESOLVER EM 1 MINUTO]")
        print("1. Acesse o painel: https://cloud.mongodb.com")
        print("2. No menu esquerdo, vá em 'Security' -> 'Network Access'")
        print("3. Clique no botão verde '+ Add IP Address'")
        print("4. Selecione 'Allow Access from Anywhere' (0.0.0.0/0) ou adicione o IP atual")
        print("5. Clique em 'Confirm' e aguarde cerca de 1 minuto até o status ficar verde ('Active')")
        print("6. Execute este teste ou o comando 'sincronizar_auditoria_mongo' novamente!")
    else:
        print(f"Detalhes: {erro}")

finally:
    cliente.close()
