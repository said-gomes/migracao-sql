"""
5. Validação Semântica (IFS)

Calcula o Índice de Fidelidade Semântica
  C: Completude:               nós migrados / registros de origem
  E: Exatidão estrutural:      cardinalidade dos relacionamentos correta
  R: Riqueza de relacionamentos: conectividade preservada
  P: Preservação de propriedades: valores idênticos em amostragem

    IFS = (C + E + R + P) / 4
"""

import pandas as pd
from dataclasses import dataclass, field
from sqlalchemy import create_engine
from neo4j import GraphDatabase


@dataclass
class ResultadoIFS:
    completude: float
    exatidao_estrutural: float
    riqueza_relacionamentos: float
    preservacao_propriedades: float
    anomalias: list = field(default_factory=list)

    @property
    def ifs(self) -> float:
        return (
            self.completude
            + self.exatidao_estrutural
            + self.riqueza_relacionamentos
            + self.preservacao_propriedades
        ) / 4

    def status(self, threshold: float) -> str:
        return "APROVADO" if self.ifs >= threshold else "REVISAR"

    def to_dict(self, threshold: float) -> dict:
        return {
            "ifs": round(self.ifs, 4),
            "completude": round(self.completude, 4),
            "exatidao_estrutural": round(self.exatidao_estrutural, 4),
            "riqueza_relacionamentos": round(self.riqueza_relacionamentos, 4),
            "preservacao_propriedades": round(self.preservacao_propriedades, 4),
            "status": self.status(threshold),
            "anomalias": self.anomalias,
        }


def calcular_ifs(schema, mapeamento, db_url, neo4j_uri, user, password,
                 amostra=100) -> ResultadoIFS:
    engine = create_engine(db_url)
    driver = GraphDatabase.driver(neo4j_uri, auth=(user, password))
    anomalias = []

    # C: COMPLETUDE
    tabelas_no = {n["tabela_origem"] for n in mapeamento["nos"]}
    total_origem = sum(
        schema[t]["total_registros"] for t in tabelas_no if t in schema
    )
    with driver.session() as s:
        total_nos = s.run("MATCH (n) RETURN count(n) AS t").single()["t"]

    completude = min(total_nos / total_origem, 1.0) if total_origem else 0.0
    if total_nos != total_origem:
        anomalias.append(
            f"Completude: origem={total_origem}, nós={total_nos}"
        )

    # E: EXATIDÃO ESTRUTURAL
    violacoes = 0
    base = 0
    with driver.session() as s:
        for rel in mapeamento["relacionamentos_fk"]:
            n_origem = s.run(
                f"MATCH (n:{rel['de']}) RETURN count(n) AS t"
            ).single()["t"]
            base += n_origem
            viol = s.run(f"""
                MATCH (n:{rel['de']})
                WHERE size([(n)-[:{rel['tipo']}]->() | 1]) > 1
                RETURN count(n) AS t
            """).single()["t"]
            if viol:
                violacoes += viol
                anomalias.append(
                    f"Exatidão: {viol} nós {rel['de']} com cardinalidade "
                    f"inesperada em [:{rel['tipo']}]"
                )
    exatidao = 1.0 - (violacoes / base) if base else 1.0

    # R: RIQUEZA DE RELACIONAMENTOS
    rels_esperados = sum(
        schema[r["tabela_origem"]]["total_registros"]
        for r in mapeamento["relacionamentos_fk"]
        + mapeamento["relacionamentos_associativos"]
        if r["tabela_origem"] in schema
    )
    with driver.session() as s:
        rels_criados = s.run(
            "MATCH ()-[r]->() RETURN count(r) AS t"
        ).single()["t"]

    riqueza = min(rels_criados / rels_esperados, 1.0) if rels_esperados else 0.0
    if rels_criados < rels_esperados:
        anomalias.append(
            f"Riqueza: esperados={rels_esperados}, criados={rels_criados}"
        )

    # P: PRESERVAÇÃO DE PROPRIEDADES
    divergencias = 0
    amostras_total = 0
    with driver.session() as s:
        for no in mapeamento["nos"]:
            tabela = no["tabela_origem"]
            pk = schema[tabela]["pk"]
            if not pk or not no["propriedades"]:
                continue

            df = pd.read_sql(
                f"SELECT * FROM {tabela} ORDER BY RAND() LIMIT {amostra}",
                engine,
            )
            for _, row in df.iterrows():
                pk_val = row[pk[0]]
                rec = s.run(
                    f"MATCH (n:{no['label']} {{{pk[0]}: $v}}) RETURN n",
                    v=int(pk_val) if str(pk_val).isdigit() else pk_val,
                ).single()
                if not rec:
                    continue
                no_neo4j = dict(rec["n"])
                for prop in no["propriedades"]:
                    if prop in row and prop in no_neo4j:
                        amostras_total += 1
                        if str(row[prop]).strip() != str(no_neo4j[prop]).strip():
                            divergencias += 1

    preservacao = (
        1.0 - (divergencias / amostras_total) if amostras_total else 1.0
    )
    if divergencias:
        anomalias.append(
            f"Preservação: {divergencias}/{amostras_total} valores divergentes"
        )

    driver.close()

    return ResultadoIFS(
        completude=completude,
        exatidao_estrutural=exatidao,
        riqueza_relacionamentos=riqueza,
        preservacao_propriedades=preservacao,
        anomalias=anomalias,
    )


def imprimir_relatorio(r: ResultadoIFS, threshold: float):
    def marca(v, lim=0.99):
        return "OK" if v >= lim else "!!"

    print("\n" + "=" * 50)
    print("  RELATÓRIO DE MIGRAÇÃO — IFS")
    print("=" * 50)
    print(f"  Completude:               {r.completude:.4f}  {marca(r.completude, 1.0)}")
    print(f"  Exatidão estrutural:      {r.exatidao_estrutural:.4f}  {marca(r.exatidao_estrutural)}")
    print(f"  Riqueza relacionamentos:  {r.riqueza_relacionamentos:.4f}  {marca(r.riqueza_relacionamentos)}")
    print(f"  Preservação propriedades: {r.preservacao_propriedades:.4f}  {marca(r.preservacao_propriedades)}")
    print("-" * 50)
    print(f"  IFS FINAL:  {r.ifs:.4f}")
    print(f"  STATUS:     {r.status(threshold)}")
    print("=" * 50)
    if r.anomalias:
        print("\nANOMALIAS DETECTADAS:")
        for a in r.anomalias:
            print(f"  - {a}")


if __name__ == "__main__":
    import json
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from config import (DB_URL, NEO4J_URI, NEO4J_USER, NEO4J_PASS,
                        IFS_THRESHOLD, AMOSTRA_PRESERVACAO,
                        ARQ_SCHEMA, ARQ_MAPEAMENTO, ARQ_RELATORIO)

    with open(ARQ_SCHEMA, encoding="utf-8") as f:
        schema = json.load(f)
    with open(ARQ_MAPEAMENTO, encoding="utf-8") as f:
        mapeamento = json.load(f)

    resultado = calcular_ifs(
        schema, mapeamento, DB_URL,
        NEO4J_URI, NEO4J_USER, NEO4J_PASS, AMOSTRA_PRESERVACAO,
    )
    imprimir_relatorio(resultado, IFS_THRESHOLD)

    with open(ARQ_RELATORIO, "w", encoding="utf-8") as f:
        json.dump(resultado.to_dict(IFS_THRESHOLD), f,
                  indent=2, ensure_ascii=False)
    print(f"\nRelatório salvo em {ARQ_RELATORIO}")
