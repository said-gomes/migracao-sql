"""
pipeline/migracao.py
====================
CAMADA 4 — Migração.

Exporta as tabelas para CSV via SQLAlchemy/pandas e cria nós e
relacionamentos no Neo4j conforme o mapeamento aprovado.
Cria índices para suportar a criação de relacionamentos em escala
e processa tabelas grandes em lotes.
"""

import os
import math
import pandas as pd
from sqlalchemy import create_engine
from neo4j import GraphDatabase


def exportar_csvs(schema: dict, db_url: str, csv_dir: str) -> dict:
    """Exporta cada tabela do banco para um CSV. Retorna {tabela: caminho}."""
    os.makedirs(csv_dir, exist_ok=True)
    engine = create_engine(db_url)
    caminhos = {}

    for tabela in schema:
        df = pd.read_sql(f"SELECT * FROM {tabela}", engine)
        caminho = os.path.join(csv_dir, f"{tabela}.csv")
        df.to_csv(caminho, index=False, encoding="utf-8")
        caminhos[tabela] = caminho
        print(f"  {tabela}.csv  →  {len(df)} registros")

    return caminhos


class MigradorNeo4j:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def fechar(self):
        self.driver.close()

    def limpar_banco(self):
        with self.driver.session() as s:
            s.run("MATCH (n) DETACH DELETE n")
        print("  Banco destino limpo.")

    def criar_indices(self, mapeamento, schema):
        with self.driver.session() as s:
            for no in mapeamento["nos"]:
                pk = schema[no["tabela_origem"]]["pk"]
                if pk:
                    s.run(
                        f"CREATE INDEX IF NOT EXISTS "
                        f"FOR (n:{no['label']}) ON (n.{pk[0]})"
                    )
        print("  Índices criados.")

    def importar_nos(self, mapeamento, schema, csv_dir):
        for no in mapeamento["nos"]:
            tabela = no["tabela_origem"]
            df = pd.read_csv(os.path.join(csv_dir, f"{tabela}.csv"))
            colunas = [c for c in no["propriedades"] if c in df.columns]

            registros = df[colunas].to_dict("records")
            registros = [_limpar_nulos(r) for r in registros]

            with self.driver.session() as s:
                for i in range(0, len(registros), 1000):
                    lote = registros[i:i + 1000]
                    s.run(
                        f"UNWIND $lote AS row "
                        f"CREATE (n:{no['label']}) SET n = row",
                        lote=lote,
                    )
            print(f"  :{no['label']}  →  {len(df)} nós criados")

    def criar_rels_fk(self, mapeamento, schema, csv_dir):
        for rel in mapeamento["relacionamentos_fk"]:
            tabela = rel["tabela_origem"]
            fk_info = next(
                (fk for fk in schema[tabela]["fks"]
                 if fk["coluna"] == rel["coluna_fk"]), None
            )
            if not fk_info:
                print(f"  [aviso] FK não encontrada para {rel['tipo']}, pulando.")
                continue

            df = pd.read_csv(os.path.join(csv_dir, f"{tabela}.csv"))
            pk_origem = schema[tabela]["pk"][0]
            pk_destino = fk_info["coluna_ref"]

            pares = df[[pk_origem, rel["coluna_fk"]]].dropna().to_dict("records")

            with self.driver.session() as s:
                for i in range(0, len(pares), 5000):
                    lote = pares[i:i + 5000]
                    s.run(f"""
                        UNWIND $lote AS row
                        MATCH (a:{rel['de']} {{{pk_origem}: row.{pk_origem}}})
                        MATCH (b:{rel['para']} {{{pk_destino}: row.{rel['coluna_fk']}}})
                        CREATE (a)-[:{rel['tipo']}]->(b)
                    """, lote=lote)
            print(f"  [:{rel['tipo']}]  →  {len(pares)} relacionamentos criados")

    def criar_rels_associativos(self, mapeamento, schema, csv_dir, batch_size):
        for rel in mapeamento["relacionamentos_associativos"]:
            tabela = rel["tabela_origem"]
            df = pd.read_csv(os.path.join(csv_dir, f"{tabela}.csv"))

            fk_de = next(fk for fk in schema[tabela]["fks"]
                         if fk["coluna"] == rel["fk_de"])
            fk_para = next(fk for fk in schema[tabela]["fks"]
                           if fk["coluna"] == rel["fk_para"])

            colunas = [rel["fk_de"], rel["fk_para"]] + rel["propriedades"]
            colunas = [c for c in colunas if c in df.columns]
            registros = df[colunas].to_dict("records")
            registros = [_limpar_nulos(r) for r in registros]

            props_set = ", ".join(
                [f"{p}: row.{p}" for p in rel["propriedades"] if p in df.columns]
            )
            props_clause = f" {{{props_set}}}" if props_set else ""

            with self.driver.session() as s:
                for i in range(0, len(registros), batch_size):
                    lote = registros[i:i + batch_size]
                    s.run(f"""
                        UNWIND $lote AS row
                        MATCH (a:{rel['de']} {{{fk_de['coluna_ref']}: row.{rel['fk_de']}}})
                        MATCH (b:{rel['para']} {{{fk_para['coluna_ref']}: row.{rel['fk_para']}}})
                        CREATE (a)-[:{rel['tipo']}{props_clause}]->(b)
                    """, lote=lote)
            print(f"  [:{rel['tipo']}]  →  {len(registros)} relacionamentos criados")


def _limpar_nulos(registro: dict) -> dict:
    """Remove NaN do pandas, que o Neo4j não aceita."""
    limpo = {}
    for k, v in registro.items():
        if isinstance(v, float) and math.isnan(v):
            continue
        limpo[k] = v
    return limpo


def migrar(mapeamento, schema, db_url, csv_dir,
           neo4j_uri, user, password, batch_size=10000):
    """Executa a migração completa."""
    print("  Exportando CSVs...")
    exportar_csvs(schema, db_url, csv_dir)

    print("  Carregando no Neo4j...")
    m = MigradorNeo4j(neo4j_uri, user, password)
    try:
        m.limpar_banco()
        m.criar_indices(mapeamento, schema)
        m.importar_nos(mapeamento, schema, csv_dir)
        m.criar_rels_fk(mapeamento, schema, csv_dir)
        m.criar_rels_associativos(mapeamento, schema, csv_dir, batch_size)
    finally:
        m.fechar()


if __name__ == "__main__":
    import json
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from config import (DB_URL, NEO4J_URI, NEO4J_USER, NEO4J_PASS,
                        CSV_DIR, BATCH_SIZE, ARQ_SCHEMA, ARQ_MAPEAMENTO)

    with open(ARQ_SCHEMA, encoding="utf-8") as f:
        schema = json.load(f)
    with open(ARQ_MAPEAMENTO, encoding="utf-8") as f:
        mapeamento = json.load(f)

    migrar(mapeamento, schema, DB_URL, CSV_DIR,
           NEO4J_URI, NEO4J_USER, NEO4J_PASS, BATCH_SIZE)
    print("Migração concluída.")
