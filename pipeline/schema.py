"""
pipeline/schema.py
==================
CAMADA 1 — Leitura Universal de Esquema.

Conecta a qualquer SGBD relacional via SQLAlchemy e extrai os metadados
da estrutura: tabelas, colunas, tipos, chaves primárias, chaves
estrangeiras e contagem de registros.

A saída é um dicionário serializável em JSON, consumido pela Camada 2.
"""

import json
from sqlalchemy import create_engine, inspect, text


def extrair_schema(db_url: str) -> dict:
    """
    Lê o esquema completo de um banco relacional.

    Retorna um dicionário no formato:
    {
        "nome_tabela": {
            "colunas": [{"nome": str, "tipo": str, "nullable": bool}],
            "pk": [str],
            "fks": [{"coluna": str, "tabela_ref": str, "coluna_ref": str}],
            "total_registros": int
        }
    }
    """
    engine = create_engine(db_url)
    inspector = inspect(engine)
    schema = {}

    for tabela in inspector.get_table_names():
        colunas = inspector.get_columns(tabela)
        fks = inspector.get_foreign_keys(tabela)
        pk = inspector.get_pk_constraint(tabela)

        # contagem de registros
        with engine.connect() as conn:
            total = conn.execute(
                text(f"SELECT COUNT(*) FROM {tabela}")
            ).scalar()

        schema[tabela] = {
            "colunas": [
                {
                    "nome": c["name"],
                    "tipo": str(c["type"]),
                    "nullable": c.get("nullable", True),
                }
                for c in colunas
            ],
            "pk": pk.get("constrained_columns", []),
            "fks": [
                {
                    "coluna": fk["constrained_columns"][0],
                    "tabela_ref": fk["referred_table"],
                    "coluna_ref": fk["referred_columns"][0],
                }
                for fk in fks
                if fk["constrained_columns"]
            ],
            "total_registros": total,
        }

    return schema


def salvar_schema(schema: dict, caminho: str):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)


def resumir_schema(schema: dict) -> str:
    """Gera um resumo legível do esquema lido."""
    linhas = [f"Tabelas encontradas: {len(schema)}\n"]
    for tabela, info in schema.items():
        n_cols = len(info["colunas"])
        n_fks = len(info["fks"])
        linhas.append(
            f"  {tabela}: {n_cols} colunas, {n_fks} FKs, "
            f"{info['total_registros']} registros"
        )
    return "\n".join(linhas)


if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from config import DB_URL, ARQ_SCHEMA

    print("Lendo esquema do banco...")
    schema = extrair_schema(DB_URL)
    salvar_schema(schema, ARQ_SCHEMA)
    print(resumir_schema(schema))
    print(f"\nEsquema salvo em {ARQ_SCHEMA}")
