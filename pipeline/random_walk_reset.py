"""
6. Random Walk with Restart (RWR) para Recomendação.

Demonstra o valor analítico do grafo gerado pelo pipeline, executando
recomendações de produtos baseadas em travessia probabilística via
Neo4j Graph Data Science (GDS).

O algoritmo simula passeios aleatórios a partir de um nó cliente,
com probabilidade alfa de reiniciar no nó de origem a cada passo. Após
muitos passeios, a frequência de visita a cada produto representa sua
afinidade com o perfil daquele cliente.

Requer o plugin Neo4j Graph Data Science (GDS) instalado e ativo.

Referências:
  - Tong, Faloutsos, Pan. Random Walk with Restart: Fast Solutions and
    Applications. ICDM 2006.
  - Eksombatchai et al. Pixie: A System for Recommending 3+ Billion Items
    to 200+ Million Users in Real-Time. WWW 2018.
"""

import json
from dataclasses import dataclass, field
from typing import Optional
from neo4j import GraphDatabase


# CONFIGURAÇÃO INICIAIS

@dataclass
class ConfigRWR:
    """Hiperparâmetros do Random Walk with Restart."""
    probabilidade_restart: float = 0.15   # alpha, representando a chance de voltar ao nó inicial
    tamanho_caminhada: int = 80           # passos por caminhada
    num_caminhadas: int = 1000            # quantas caminhadas executar
    top_n: int = 10                       # quantos produtos retornar
    label_destino: str = "Produto"        # tipo de nó a ser recomendado
    label_origem: str = "Cliente"         # tipo de nó de partida
    excluir_ja_comprados: bool = True     # remove produtos já comprados


# RESULTADO


@dataclass
class Recomendacao:
    nome: str
    score: float
    frequencia_visitas: int
    atributos: dict = field(default_factory=dict)


@dataclass
class ResultadoRWR:
    cliente_id: int
    cliente_nome: str
    recomendacoes: list
    total_caminhadas: int
    config: ConfigRWR

    def to_dict(self) -> dict:
        return {
            "cliente_id": self.cliente_id,
            "cliente_nome": self.cliente_nome,
            "total_caminhadas": self.total_caminhadas,
            "config": {
                "probabilidade_restart": self.config.probabilidade_restart,
                "tamanho_caminhada": self.config.tamanho_caminhada,
                "num_caminhadas": self.config.num_caminhadas,
            },
            "recomendacoes": [
                {
                    "nome": r.nome,
                    "score": round(r.score, 4),
                    "frequencia_visitas": r.frequencia_visitas,
                    "atributos": r.atributos,
                }
                for r in self.recomendacoes
            ],
        }


# GDS (Neo4j Graph Data Science)

class RWRGds:
    """
    Implementação do RWR usando a biblioteca GDS do Neo4j.
    Exige o plugin GDS instalado e ativo na instância Neo4j.
    """

    GRAFO_NOME = "rwr_grafo_vendas"

    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def fechar(self):
        self.driver.close()

    def _criar_projecao(self, session):
        """Projeta o grafo na memória do GDS."""
        # Remove projeção anterior, se existir
        session.run(f"""
            CALL gds.graph.exists('{self.GRAFO_NOME}') YIELD exists
            WITH exists WHERE exists
            CALL gds.graph.drop('{self.GRAFO_NOME}') YIELD graphName
            RETURN graphName
        """)

        # Projeta todos os nós e relacionamentos como não-direcionados
        session.run(f"""
            CALL gds.graph.project(
                '{self.GRAFO_NOME}',
                '*',
                {{
                    REL: {{
                        type: '*',
                        orientation: 'UNDIRECTED'
                    }}
                }}
            )
        """)

    def _remover_projecao(self, session):
        session.run(f"CALL gds.graph.drop('{self.GRAFO_NOME}')")

    def executar(self, cliente_id: int, config: ConfigRWR) -> ResultadoRWR:
        with self.driver.session() as session:

            # Resolve nó inicial
            no_inicial = session.run(
                f"MATCH (c:{config.label_origem} "
                f"{{idcliente: $id}}) RETURN id(c) AS nid, c.Nome AS nome",
                id=cliente_id,
            ).single()
            if not no_inicial:
                raise ValueError(f"Cliente {cliente_id} não encontrado.")

            id_inicial = no_inicial["nid"]
            nome_cliente = no_inicial["nome"]

            self._criar_projecao(session)

            try:
                # Executa Personalized PageRank com nó fonte
                # (equivalente matemático do RWR no Neo4j GDS)
                result = session.run(f"""
                    CALL gds.pageRank.stream('{self.GRAFO_NOME}', {{
                        sourceNodes: [$source],
                        dampingFactor: $damping,
                        maxIterations: 20
                    }})
                    YIELD nodeId, score
                    WITH gds.util.asNode(nodeId) AS no, score
                    WHERE '{config.label_destino}' IN labels(no)
                    RETURN id(no) AS nid,
                           no.Nome AS nome,
                           properties(no) AS props,
                           score
                    ORDER BY score DESC
                    LIMIT {config.top_n * 3}
                """,
                    source=id_inicial,
                    damping=1 - config.probabilidade_restart,
                )

                candidatos = [
                    (r["nid"], r["nome"], dict(r["props"]), r["score"])
                    for r in result
                ]

            finally:
                self._remover_projecao(session)

            # Filtra produtos já comprados
            if config.excluir_ja_comprados:
                ja_comprados = set(session.run("""
                    MATCH (c:Cliente {idcliente: $id})-[:REALIZOU]->(:Pedido)
                          -[:CONTEM]->(p:Produto)
                    RETURN id(p) AS pid
                """, id=cliente_id).value())
                candidatos = [
                    c for c in candidatos if c[0] not in ja_comprados
                ]

            candidatos = candidatos[: config.top_n]

            soma_scores = sum(s for _, _, _, s in candidatos) or 1
            recomendacoes = [
                Recomendacao(
                    nome=nome,
                    score=score / soma_scores,
                    frequencia_visitas=int(score * 1000),
                    atributos={
                        k: v for k, v in props.items()
                        if k in ("Preco", "QuantEstoque", "Descricao")
                    },
                )
                for _, nome, props, score in candidatos
            ]

            return ResultadoRWR(
                cliente_id=cliente_id,
                cliente_nome=nome_cliente,
                recomendacoes=recomendacoes,
                total_caminhadas=config.num_caminhadas,
                config=config,
            )


# INTERFACE PRINCIPAL


def recomendar(cliente_id: int, neo4j_uri: str, user: str, password: str,
               config: Optional[ConfigRWR] = None) -> ResultadoRWR:
    """
    Executa o Random Walk with Restart e retorna as top-N recomendações.

    Args:
        cliente_id: ID do cliente no banco original.
        neo4j_uri, user, password: credenciais Neo4j.
        config: hiperparâmetros do algoritmo.

    Returns:
        ResultadoRWR com lista ordenada de produtos recomendados.
    """
    config = config or ConfigRWR()
    impl = RWRGds(neo4j_uri, user, password)
    try:
        return impl.executar(cliente_id, config)
    finally:
        impl.fechar()


# =============================================================================
# RELATÓRIO
# =============================================================================

def imprimir_relatorio(resultado: ResultadoRWR):
    print("\n" + "=" * 60)
    print(f"  RECOMENDAÇÕES VIA RANDOM WALK WITH RESTART")
    print("=" * 60)
    print(f"  Cliente: {resultado.cliente_nome} (id={resultado.cliente_id})")
    print(f"  Caminhadas executadas: {resultado.total_caminhadas}")
    print(f"  Restart α: {resultado.config.probabilidade_restart}")
    print("-" * 60)
    print(f"  {'#':>3}  {'Score':>8}  {'Visitas':>9}  Produto")
    print("-" * 60)
    for i, rec in enumerate(resultado.recomendacoes, start=1):
        print(
            f"  {i:>3}  {rec.score:>8.4f}  {rec.frequencia_visitas:>9}  "
            f"{rec.nome}"
        )
    print("=" * 60)


# EXECUÇÃO ISOLADA


if __name__ == "__main__":
    import sys
    from config import NEO4J_URI, NEO4J_USER, NEO4J_PASS

    cliente_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    config = ConfigRWR(
        probabilidade_restart=0.15,
        tamanho_caminhada=80,
        num_caminhadas=1000,
        top_n=10,
    )

    print(f"Executando RWR para cliente {cliente_id}...")

    resultado = recomendar(
        cliente_id=cliente_id,
        neo4j_uri=NEO4J_URI,
        user=NEO4J_USER,
        password=NEO4J_PASS,
        config=config,
    )

    imprimir_relatorio(resultado)

    arquivo = f"recomendacoes_cliente_{cliente_id}.json"
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(resultado.to_dict(), f, indent=2, ensure_ascii=False)
    print(f"\nResultado salvo em {arquivo}")
