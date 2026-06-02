"""
pipeline/inferencia.py
======================
CAMADA 2 — Inferência Semântica com Modelo de Linguagem.

Submete o esquema relacional a um LLM, que classifica cada tabela como
nó ou relacionamento associativo, nomeia os relacionamentos com verbos
de domínio, atribui propriedades e justifica cada decisão.

A saída é um mapeamento JSON auditável, consumido pelas Camadas 3 e 4.
"""

import json
import re
import google.generativeai as genai


PROMPT_TEMPLATE = """\
Você é um especialista em modelagem de bancos de dados em grafos Neo4j.

Analise o schema relacional abaixo e gere um mapeamento semântico completo
para Neo4j.

SCHEMA:
{schema_json}

REGRAS:
1. Tabelas que representam entidades com identidade e atributos próprios viram NÓS.
2. Tabelas com apenas chaves estrangeiras e atributos de contexto da relação são
   ASSOCIATIVAS (N:N) e viram RELACIONAMENTOS com propriedades, nunca nós.
3. Nomeie relacionamentos com verbos no passado ou expressões de domínio em
   maiúsculas (ex: REALIZOU, CONTEM, PERTENCE_A, POSSUI_ENDERECO).
4. Para cada relacionamento via FK simples, identifique a direção correta
   (quem pratica a ação aponta para quem a recebe).
5. As propriedades de um nó são as colunas que não são chaves estrangeiras.
6. Forneça uma justificativa curta e objetiva para cada decisão.

Retorne APENAS um JSON válido, sem texto antes ou depois, sem marcação de código,
exatamente nesta estrutura:

{{
  "nos": [
    {{
      "label": "NomeDoNo",
      "tabela_origem": "nome_tabela",
      "propriedades": ["coluna1", "coluna2"],
      "motivo": "justificativa"
    }}
  ],
  "relacionamentos_fk": [
    {{
      "tipo": "NOME_REL",
      "de": "LabelOrigem",
      "para": "LabelDestino",
      "tabela_origem": "nome_tabela",
      "coluna_fk": "nome_coluna_fk",
      "motivo": "justificativa"
    }}
  ],
  "relacionamentos_associativos": [
    {{
      "tipo": "NOME_REL",
      "de": "LabelOrigem",
      "para": "LabelDestino",
      "tabela_origem": "nome_tabela",
      "fk_de": "coluna_fk_origem",
      "fk_para": "coluna_fk_destino",
      "propriedades": ["coluna1", "coluna2"],
      "motivo": "justificativa"
    }}
  ]
}}
"""


def _extrair_json(texto: str) -> dict:
    """Extrai o bloco JSON da resposta do modelo, de forma robusta."""
    # tenta parsear direto
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass

    # remove cercas de código markdown, se houver
    texto = re.sub(r"```(?:json)?", "", texto).strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass

    # tenta capturar do primeiro { ao último }
    inicio = texto.find("{")
    fim = texto.rfind("}")
    if inicio != -1 and fim != -1:
        return json.loads(texto[inicio:fim + 1])

    raise ValueError("Não foi possível extrair JSON válido da resposta do modelo.")


def _validar_mapeamento(mapeamento: dict) -> bool:
    """Garante que o mapeamento tem as chaves esperadas."""
    chaves = {"nos", "relacionamentos_fk", "relacionamentos_associativos"}
    if not chaves.issubset(mapeamento.keys()):
        raise ValueError(
            f"Mapeamento incompleto. Esperado: {chaves}, "
            f"recebido: {set(mapeamento.keys())}"
        )
    if not mapeamento["nos"]:
        raise ValueError("Mapeamento não contém nós.")
    return True


def inferir_mapeamento(schema: dict, api_key: str, model: str,
                        max_tokens: int = 4000) -> dict:
    """Chama o LLM e retorna o mapeamento semântico validado."""
    genai.configure(api_key=api_key)
    cliente = genai.GenerativeModel(model)
    prompt = PROMPT_TEMPLATE.format(
        schema_json=json.dumps(schema, indent=2, ensure_ascii=False)
    )

    resposta = cliente.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(max_output_tokens=max_tokens),
    )

    texto = resposta.text
    mapeamento = _extrair_json(texto)
    _validar_mapeamento(mapeamento)
    return mapeamento


def salvar_mapeamento(mapeamento: dict, caminho: str):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(mapeamento, f, indent=2, ensure_ascii=False)


def resumir_mapeamento(mapeamento: dict) -> str:
    linhas = []
    linhas.append(f"Nós: {[n['label'] for n in mapeamento['nos']]}")
    linhas.append("Relacionamentos via FK:")
    for r in mapeamento["relacionamentos_fk"]:
        linhas.append(f"  ({r['de']})-[:{r['tipo']}]->({r['para']})")
    linhas.append("Relacionamentos associativos:")
    for r in mapeamento["relacionamentos_associativos"]:
        props = ", ".join(r["propriedades"])
        linhas.append(f"  ({r['de']})-[:{r['tipo']} {{{props}}}]->({r['para']})")
    return "\n".join(linhas)


if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from config import (DB_URL, LLM_API_KEY, LLM_MODEL, LLM_MAX_TOKENS,
                        ARQ_SCHEMA, ARQ_MAPEAMENTO)
    from pipeline.schema import extrair_schema

    print("Lendo esquema...")
    schema = extrair_schema(DB_URL)

    print("Inferindo mapeamento semântico com o LLM...")
    mapeamento = inferir_mapeamento(schema, LLM_API_KEY, LLM_MODEL, LLM_MAX_TOKENS)
    salvar_mapeamento(mapeamento, ARQ_MAPEAMENTO)

    print("\n" + resumir_mapeamento(mapeamento))
    print(f"\nMapeamento salvo em {ARQ_MAPEAMENTO}")
