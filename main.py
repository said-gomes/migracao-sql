"""
main.py
=======
Orquestra o pipeline completo de migração semântica:

  Camada 1 → Camada 2 → Camada 3 → Camada 4 → Camada 5

Uso:
    python main.py                 # pipeline completo, com revisão humana
    python main.py --sem-revisao   # pula a revisão humana (modo MVP/automático)
"""

import sys
import json

import config
from pipeline.schema import extrair_schema, salvar_schema, resumir_schema
from pipeline.inferencia import (inferir_mapeamento, salvar_mapeamento,
                                  resumir_mapeamento)
from pipeline.revisao import revisar_mapeamento
from pipeline.migracao import migrar
from pipeline.ifs import calcular_ifs, imprimir_relatorio


def main():
    interativo = "--sem-revisao" not in sys.argv

    print("=" * 55)
    print("  PIPELINE DE MIGRAÇÃO SEMÂNTICA ASSISTIDA POR IA")
    print("=" * 55)

    # ─── CAMADA 1 ────────────────────────────────────────────────────
    print("\n[1/5] Lendo esquema do banco relacional...")
    schema = extrair_schema(config.DB_URL)
    salvar_schema(schema, config.ARQ_SCHEMA)
    print(resumir_schema(schema))

    # ─── CAMADA 2 ────────────────────────────────────────────────────
    print("\n[2/5] Inferindo mapeamento semântico com o LLM...")
    if not config.LLM_API_KEY:
        print("  [erro] GOOGLE_API_KEY não configurada. Abortando.")
        sys.exit(1)
    mapeamento = inferir_mapeamento(
        schema, config.LLM_API_KEY, config.LLM_MODEL, config.LLM_MAX_TOKENS
    )
    salvar_mapeamento(mapeamento, config.ARQ_MAPEAMENTO)
    print(resumir_mapeamento(mapeamento))

    # ─── CAMADA 3 ────────────────────────────────────────────────────
    print("\n[3/5] Revisão humana do mapeamento...")
    mapeamento = revisar_mapeamento(mapeamento, interativo=interativo)
    salvar_mapeamento(mapeamento, config.ARQ_MAPEAMENTO)

    # ─── CAMADA 4 ────────────────────────────────────────────────────
    print("\n[4/5] Executando migração...")
    migrar(
        mapeamento, schema, config.DB_URL, config.CSV_DIR,
        config.NEO4J_URI, config.NEO4J_USER, config.NEO4J_PASS,
        config.BATCH_SIZE,
    )

    # ─── CAMADA 5 ────────────────────────────────────────────────────
    print("\n[5/5] Calculando Índice de Fidelidade Semântica...")
    resultado = calcular_ifs(
        schema, mapeamento, config.DB_URL,
        config.NEO4J_URI, config.NEO4J_USER, config.NEO4J_PASS,
        config.AMOSTRA_PRESERVACAO,
    )
    imprimir_relatorio(resultado, config.IFS_THRESHOLD)

    with open(config.ARQ_RELATORIO, "w", encoding="utf-8") as f:
        json.dump(resultado.to_dict(config.IFS_THRESHOLD), f,
                  indent=2, ensure_ascii=False)

    print(f"\nArtefatos gerados:")
    print(f"  {config.ARQ_SCHEMA}")
    print(f"  {config.ARQ_MAPEAMENTO}")
    print(f"  {config.ARQ_RELATORIO}")
    print("\nPipeline concluído.")


if __name__ == "__main__":
    main()
