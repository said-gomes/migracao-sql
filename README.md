# Pipeline de Migração Semântica Assistida por IA

Migração de bancos de dados relacionais para bancos em grafos (Neo4j) com
inferência semântica via Modelo de Linguagem e validação formal através do
índice proposto: Índice de Fidelidade Semântica (IFS).

## Arquitetura

```
Camada 1 — Leitura de schema          (SQLAlchemy)
Camada 2 — Inferência semântica       (LLM)
Camada 3 — Revisão humana             (terminal)
Camada 4 — Migração                   (CSV + Neo4j)
Camada 5 — Validação (IFS)            (4 dimensões)
Camada 6 — Recomendação via RWR       (opcional, pós-migração, requer GDS)
```

A Camada 6 é **opcional**, roda **apenas após uma migração validada** (IFS ≥ threshold) e **depende do plugin Neo4j Graph Data Science (GDS)**.

## Estrutura de pastas

```
migracao-sql/
├── pipeline/               # módulos das 6 camadas
│   ├── schema.py
│   ├── inferencia.py
│   ├── revisao.py
│   ├── migracao.py
│   ├── ifs.py
│   └── random_walk_reset.py
├── outputs/                # artefatos gerados em runtime
│   ├── schema.json
│   ├── mapeamento_semantico.json
│   ├── relatorio_ifs.json
│   ├── recomendacoes_rwr.json
│   └── csvs/
├── config.py
├── main.py
└── requirements.txt
```

## Instalação

```bash
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

## Configuração

Defina as variáveis de ambiente (ou edite `config.py`):

```bash
export DB_URL="mysql+pymysql://user:senha@localhost/bd_alvo"
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASS="sua_senha"
export GOOGLE_API_KEY="sua_chave"
```

## Uso

Pipeline completo (com revisão humana):
```bash
python main.py
```

Modo automático (sem revisão, útil para testes):
```bash
python main.py --sem-revisao
```

Pipeline completo com recomendação RWR ativada para o cliente padrão:
```bash
python main.py --com-rwr
```

Especificar outro cliente alvo para o RWR:
```bash
python main.py --com-rwr --cliente-rwr 42
```

Executar camadas isoladamente:
```bash
python pipeline/schema.py       # gera outputs/schema.json
python pipeline/inferencia.py   # gera outputs/mapeamento_semantico.json
python pipeline/revisao.py      # revisa o mapeamento
python pipeline/migracao.py     # executa a migração
python pipeline/ifs.py          # calcula e salva o IFS
python pipeline/random_walk_reset.py 1  # executa apenas o RWR para o cliente 1
```

## Artefatos gerados

| Arquivo | Conteúdo |
|---|---|
| `outputs/schema.json` | Esquema lido do banco relacional |
| `outputs/mapeamento_semantico.json` | Mapeamento inferido pelo LLM (auditável) |
| `outputs/relatorio_ifs.json` | Resultado da validação com as 4 dimensões |
| `outputs/csvs/` | Tabelas exportadas como CSV |
| `outputs/recomendacoes_rwr.json` | Top-N recomendações para o cliente alvo, geradas pela Camada 6 |

## Índice de Fidelidade Semântica

```
IFS = (C + E + R + P) / 4
```

- **C: Completude**: nós migrados / registros de origem
- **E: Exatidão estrutural**: cardinalidade dos relacionamentos
- **R: Riqueza**: conectividade preservada
- **P: Preservação**: valores idênticos em amostragem

Migração aprovada quando `IFS >= 0.95` (parâmetro ajustável via `IFS_THRESHOLD`).

## Camada 6 — Recomendação via Random Walk with Restart

### O que é o RWR

O Random Walk with Restart (RWR) é um algoritmo de travessia probabilística que simula passeios aleatórios a partir de um nó cliente, com probabilidade α de reiniciar no nó de origem a cada passo. Após muitos passeios, produtos mais visitados ao longo das caminhadas representam maior afinidade com o perfil daquele cliente.

A implementação usa **Personalized PageRank** via Neo4j GDS, que é o equivalente matemático do RWR e escala para grafos de grande porte.

### Por que está no projeto

A Camada 6 demonstra que o grafo gerado pelo pipeline suporta algoritmos sofisticados de recomendação nativamente, validando que a qualidade da migração (IFS alto) se traduz em capacidade analítica real.

### Pré-requisito

O plugin **Neo4j Graph Data Science (GDS)** deve estar instalado e ativo na instância Neo4j.
Instruções de instalação: https://neo4j.com/docs/graph-data-science/current/installation/

### Hiperparâmetros configuráveis

| Parâmetro | Variável de ambiente | Padrão | Descrição |
|---|---|---|---|
| Probabilidade de restart (α) | `RWR_PROBABILIDADE_RESTART` | `0.15` | Chance de voltar ao nó cliente a cada passo |
| Tamanho da caminhada | `RWR_TAMANHO_CAMINHADA` | `80` | Número de passos por caminhada |
| Número de caminhadas | `RWR_NUM_CAMINHADAS` | `1000` | Quantas caminhadas executar |
| Top-N resultados | `RWR_TOP_N` | `10` | Quantos produtos retornar |
| Cliente alvo | `RWR_CLIENTE_ID` | `1` | ID do cliente para recomendação |

### Exemplos de uso

```bash
# Pipeline completo com RWR ativado para cliente padrão
python main.py --com-rwr

# Especificar outro cliente
python main.py --com-rwr --cliente-rwr 42

# Executar APENAS a Camada 6 (assumindo que a migração já foi feita)
python pipeline/random_walk_reset.py 1

# Ativar via variável de ambiente
RWR_HABILITADO=true python main.py
```

## Bancos suportados

Qualquer SGBD com driver SQLAlchemy. Testado com MySQL; compatível com
PostgreSQL, SQLite, SQL Server e outros, basta alterar a `DB_URL`.

## Referências

- Tong, H., Faloutsos, C., Pan, J. (2006). *Random Walk with Restart: Fast Solutions and Applications*. ICDM 2006.
- Eksombatchai, C., Jindal, P., Liu, J. Z., Liu, Y., Sharma, R., Sugnet, C., Tseng, M., Leskovec, J. (2018). *Pixie: A System for Recommending 3+ Billion Items to 200+ Million Users in Real-Time*. WWW 2018.
