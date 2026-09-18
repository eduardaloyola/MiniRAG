"""Modo terminal do Mini RAG. Para o app web, veja app.py."""
import os
import sys

from dotenv import load_dotenv

from rag import buscar, carregar_documentos, criar_client, dividir_em_chunks, gerar_embeddings, responder

load_dotenv()

if not os.getenv("GEMINI_API_KEY"):
    sys.exit("Defina GEMINI_API_KEY no arquivo .env (veja .env.example).")


def main():
    client = criar_client()
    print("Carregando e indexando documentos...")
    chunks = dividir_em_chunks(carregar_documentos())
    vetores = gerar_embeddings(client, chunks, "RETRIEVAL_DOCUMENT")
    print(f"Pronto! {len(chunks)} trechos indexados. Digite 'sair' para encerrar.\n")

    while True:
        pergunta = input("Você: ").strip()
        if pergunta.lower() in {"sair", "exit", "quit"}:
            break
        if not pergunta:
            continue
        trechos = buscar(client, pergunta, chunks, vetores)
        print(f"\nGemini: {responder(client, pergunta, trechos)}\n")


if __name__ == "__main__":
    main()
