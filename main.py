"""
main.py
=======
Orquestra o pipeline completo de migração semântica:

  Camada 1 → Camada 2 → Camada 3 → Camada 4 → Camada 5 [→ Camada 6]

Uso:
    python main.py                        # pipeline completo, com revisão humana
    python main.py --sem-revisao          # pula a revisão humana (modo MVP/automático)
    python main.py --com-rwr              # inclui recomendação via RWR (requer GDS)
    python main.py --com-rwr --cliente-rwr 42  # RWR para cliente específico
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


def _parse_args():
    args = sys.argv[1:]
    interativo = "--sem-revisao" not in args
    com_rwr = "--com-rwr" in args or config.RWR_HABILITADO

    cliente_rwr = config.RWR_CLIENTE_ID
    if "--cliente-rwr" in args:
        idx = args.index("--cliente-rwr")
        try:
            cliente_rwr = int(args[idx + 1])
        except (IndexError, ValueError):
            print("  [erro] --cliente-rwr requer um ID inteiro. Usando padrão.")

    return interativo, com_rwr, cliente_rwr


def main():
    interativo, com_rwr, cliente_rwr = _parse_args()

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
    resultado_ifs = calcular_ifs(
        schema, mapeamento, config.DB_URL,
        config.NEO4J_URI, config.NEO4J_USER, config.NEO4J_PASS,
        config.AMOSTRA_PRESERVACAO,
    )
    imprimir_relatorio(resultado_ifs, config.IFS_THRESHOLD)

    with open(config.ARQ_RELATORIO, "w", encoding="utf-8") as f:
        json.dump(resultado_ifs.to_dict(config.IFS_THRESHOLD), f,
                  indent=2, ensure_ascii=False)

    ifs_aprovado = resultado_ifs.ifs >= config.IFS_THRESHOLD

    # ─── CAMADA 6 (opcional) ─────────────────────────────────────────
    if com_rwr and ifs_aprovado:
        print("\n[6/6] Executando Random Walk with Restart para recomendação...")
        try:
            from pipeline.random_walk_reset import recomendar, imprimir_relatorio as imprimir_rwr, ConfigRWR

            cfg_rwr = ConfigRWR(
                probabilidade_restart=config.RWR_PROBABILIDADE_RESTART,
                tamanho_caminhada=config.RWR_TAMANHO_CAMINHADA,
                num_caminhadas=config.RWR_NUM_CAMINHADAS,
                top_n=config.RWR_TOP_N,
            )

            resultado_rwr = recomendar(
                cliente_id=cliente_rwr,
                neo4j_uri=config.NEO4J_URI,
                user=config.NEO4J_USER,
                password=config.NEO4J_PASS,
                config=cfg_rwr,
            )

            imprimir_rwr(resultado_rwr)

            with open(config.ARQ_RWR_RESULTADO, "w", encoding="utf-8") as f:
                json.dump(resultado_rwr.to_dict(), f, indent=2, ensure_ascii=False)
            print(f"\n  Resultado RWR salvo em {config.ARQ_RWR_RESULTADO}")

        except ValueError as e:
            print(f"  [aviso] Camada 6 ignorada: {e}")
        except Exception as e:
            msg = str(e)
            if "gds" in msg.lower() or "procedure" in msg.lower() or "unknown" in msg.lower():
                print(
                    "  [aviso] Plugin Neo4j GDS não encontrado. Instale-o em:\n"
                    "  https://neo4j.com/docs/graph-data-science/current/installation/\n"
                    "  A Camada 6 foi ignorada; o restante do pipeline não é afetado."
                )
            else:
                print(f"  [aviso] Camada 6 falhou: {e}")

    elif com_rwr and not ifs_aprovado:
        print(
            f"\n[6/6] RWR ignorado — IFS abaixo do limiar "
            f"({resultado_ifs.ifs:.4f} < {config.IFS_THRESHOLD}). "
            "Execute sobre uma migração aprovada."
        )

    print(f"\nArtefatos gerados:")
    print(f"  {config.ARQ_SCHEMA}")
    print(f"  {config.ARQ_MAPEAMENTO}")
    print(f"  {config.ARQ_RELATORIO}")
    if com_rwr and ifs_aprovado:
        print(f"  {config.ARQ_RWR_RESULTADO}")
    print("\nPipeline concluído.")


if __name__ == "__main__":
    main()
