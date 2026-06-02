# Pipeline de Migração Semântica Assistida por IA

Migração de bancos de dados relacionais para bancos em grafos (Neo4j) com
inferência semântica via Modelo de Linguagem e validação formal através do
Índice de Fidelidade Semântica (IFS).

## Arquitetura

```
Camada 1: Leitura universal de esquema    (SQLAlchemy)
Camada 2: Inferência semântica            (LLM)
Camada 3: Revisão humana                  (terminal)
Camada 4: Migração                        (CSV + Neo4j)
Camada 5: Validação (IFS)                 (4 dimensões)
```

## Estrutura de pastas

```
migracao-sql/
├── pipeline/               # módulos das 5 camadas
│   ├── schema.py
│   ├── inferencia.py
│   ├── revisao.py
│   ├── migracao.py
│   └── ifs.py
├── outputs/                # artefatos gerados em runtime
│   ├── schema.json
│   ├── mapeamento_semantico.json
│   ├── relatorio_ifs.json
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
export NEO4J_URI="bolt://localhost:0000"
export NEO4J_USER="neo4j"
export NEO4J_PASS="sua_senha"
export ANTHROPIC_API_KEY="sua_chave"
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

Executar camadas isoladamente:
```bash
python pipeline/schema.py       # gera outputs/schema.json
python pipeline/inferencia.py   # gera outputs/mapeamento_semantico.json
python pipeline/revisao.py      # revisa o mapeamento
python pipeline/migracao.py     # executa a migração
python pipeline/ifs.py          # calcula e salva o IFS
```

## Artefatos gerados

| Arquivo | Conteúdo |
|---|---|
| `outputs/schema.json` | Esquema lido do banco relacional |
| `outputs/mapeamento_semantico.json` | Mapeamento inferido pelo LLM (auditável) |
| `outputs/relatorio_ifs.json` | Resultado da validação com as 4 dimensões |
| `outputs/csvs/` | Tabelas exportadas como CSV |

## Índice de Fidelidade Semântica

```
IFS = (C + E + R + P) / 4
```

- **C: Completude**: nós migrados / registros de origem
- **E: Exatidão estrutural**: cardinalidade dos relacionamentos
- **R: Riqueza**: conectividade preservada
- **P: Preservação**: valores idênticos em amostragem

Migração aprovada quando `IFS >= 0.95` (parâmetro ajustável).

## Bancos suportados

Qualquer SGBD com driver SQLAlchemy. Testado com MySQL; compatível com
PostgreSQL, SQLite, SQL Server e outros, basta alterar a `DB_URL`.
