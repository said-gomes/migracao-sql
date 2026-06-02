"""
config.py
=========
Configurações centralizadas do pipeline de migração.
Credenciais devem vir de variáveis de ambiente sempre que possível.
"""

import os

# Banco de origem (qualquer SGBD suportado pelo SQLAlchemy)
# Exemplos:
#   MySQL:      mysql+pymysql://user:senha@localhost/bd_vendas
#   PostgreSQL: postgresql+psycopg2://user:senha@localhost/bd_vendas
#   SQLite:     sqlite:///caminho/bd_vendas.db
DB_URL = os.getenv("DB_URL", "mysql+pymysql://root:senha@localhost/bd_vendas")

# Banco de destino (Neo4j)
NEO4J_URI  = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASS", "senha")

# Modelo de Linguagem
LLM_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LLM_MODEL   = os.getenv("LLM_MODEL", "claude-sonnet-4-20250514")
LLM_MAX_TOKENS = 4000

# Migração
CSV_DIR = os.getenv("CSV_DIR", "outputs/csvs")
BATCH_SIZE = 10000  # tamanho do lote para tabelas grandes

# Validação
IFS_THRESHOLD = 0.95     # limiar de aprovação do Índice de Fidelidade Semântica
AMOSTRA_PRESERVACAO = 100  # nº de registros amostrados por tabela na dimensão P

# Arquivos de saída intermediários
ARQ_SCHEMA      = "outputs/schema.json"
ARQ_MAPEAMENTO  = "outputs/mapeamento_semantico.json"
ARQ_RELATORIO   = "outputs/relatorio_ifs.json"
