"""
pipeline/revisao.py
===================
CAMADA 3 — Revisão Humana do Mapeamento.

Apresenta o mapeamento inferido pelo LLM para o usuário, que pode aceitar,
editar ou rejeitar cada decisão. Mantém um humano no processo enquanto
preserva a automatização das demais etapas.

Versão de terminal (MVP). 
"""

import json


def revisar_mapeamento(mapeamento: dict, interativo: bool = True) -> dict:
    """
    Revisa o mapeamento. Se interativo=False, retorna sem alterações
    (útil para execução automatizada / testes).
    """
    if not interativo:
        return mapeamento

    print("\n" + "=" * 55)
    print("  REVISÃO DO MAPEAMENTO SEMÂNTICO")
    print("  (Enter = aceitar | digite novo nome = editar | x = remover)")
    print("=" * 55)

    # NÓS
    print("\n[ NÓS ]")
    nos_revisados = []
    for no in mapeamento["nos"]:
        print(f"\n  :{no['label']}  ←  {no['tabela_origem']}")
        print(f"  Propriedades: {no['propriedades']}")
        print(f"  Motivo: {no['motivo']}")
        resp = input("  > ").strip()
        if resp.lower() == "x":
            continue
        if resp:
            no["label"] = resp
        nos_revisados.append(no)
    mapeamento["nos"] = nos_revisados

    # RELACIONAMENTOS VIA FK
    print("\n[ RELACIONAMENTOS VIA FK ]")
    rels_revisados = []
    for rel in mapeamento["relacionamentos_fk"]:
        print(f"\n  ({rel['de']})-[:{rel['tipo']}]->({rel['para']})")
        print(f"  Motivo: {rel['motivo']}")
        resp = input("  > ").strip()
        if resp.lower() == "x":
            continue
        if resp:
            rel["tipo"] = resp
        rels_revisados.append(rel)
    mapeamento["relacionamentos_fk"] = rels_revisados

    # RELACIONAMENTOS ASSOCIATIVOS
    print("\n[ RELACIONAMENTOS ASSOCIATIVOS ]")
    assoc_revisados = []
    for rel in mapeamento["relacionamentos_associativos"]:
        print(f"\n  ({rel['de']})-[:{rel['tipo']}]->({rel['para']})")
        print(f"  Propriedades: {rel['propriedades']}")
        print(f"  Motivo: {rel['motivo']}")
        resp = input("  > ").strip()
        if resp.lower() == "x":
            continue
        if resp:
            rel["tipo"] = resp
        assoc_revisados.append(rel)
    mapeamento["relacionamentos_associativos"] = assoc_revisados

    print("\nRevisão concluída.")
    return mapeamento


def salvar_mapeamento(mapeamento: dict, caminho: str):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(mapeamento, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from config import ARQ_MAPEAMENTO

    with open(ARQ_MAPEAMENTO, encoding="utf-8") as f:
        mapeamento = json.load(f)

    mapeamento = revisar_mapeamento(mapeamento, interativo=True)
    salvar_mapeamento(mapeamento, ARQ_MAPEAMENTO)
    print(f"Mapeamento revisado salvo em {ARQ_MAPEAMENTO}")
