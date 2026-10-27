"""
Baixa os dados brutos e registra um manifesto (URL, data, tamanho, SHA-256).

Uso:
    python -m eleicoes.baixar                 # ano principal + comparação + fontes externas
    python -m eleicoes.baixar --ano 2022      # só os arquivos do TSE de 2022
    python -m eleicoes.baixar --forcar        # baixa de novo mesmo se já existir
                                              # (use quando o TSE publicar o 2º turno)

Arquivos do TSE vão para data/raw/; fontes externas para data/external/.
O manifesto fica em data/manifesto.json: com ele dá para saber exatamente
qual versão de cada arquivo gerou cada resultado.
"""

import argparse
import hashlib
import json
import shutil
import urllib.request
from datetime import datetime
from pathlib import Path

from eleicoes.config import arquivo_externo, arquivo_tse, config, dir_data, dir_external, dir_raw


def manifesto_path() -> Path:
    return dir_data() / "manifesto.json"


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _ler_manifesto() -> dict:
    if manifesto_path().exists():
        return json.loads(manifesto_path().read_text(encoding="utf-8"))
    return {}


def _registrar(destino: Path, url: str) -> dict:
    manifesto = _ler_manifesto()
    entrada = {
        "url": url,
        "baixado_em": datetime.now().isoformat(timespec="seconds"),
        "bytes": destino.stat().st_size,
        "sha256": sha256(destino),
    }
    manifesto[destino.name] = entrada
    manifesto_path().write_text(json.dumps(manifesto, indent=2, ensure_ascii=False), encoding="utf-8")
    return entrada


def baixar(url: str, destino: Path, forcar: bool = False, sha_esperado: str | None = None) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists() and not forcar:
        print(f"[ok] já existe: {destino.name}")
        if destino.name not in _ler_manifesto():
            _registrar(destino, url)
    else:
        print(f"[..] baixando {destino.name}")
        temp = destino.with_suffix(destino.suffix + ".parcial")
        req = urllib.request.Request(url, headers={"User-Agent": "eleicoes-analise/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp, open(temp, "wb") as f:
            total = int(resp.headers.get("Content-Length") or 0)
            baixado = 0
            for bloco in iter(lambda: resp.read(1 << 20), b""):
                f.write(bloco)
                baixado += len(bloco)
                if total:
                    print(f"\r     {baixado / 1e6:,.0f} de {total / 1e6:,.0f} MB", end="")
        print()
        shutil.move(temp, destino)
        entrada = _registrar(destino, url)
        print(f"[ok] {destino.name}: {entrada['bytes'] / 1e6:,.1f} MB, sha256 {entrada['sha256'][:12]}…")

    if sha_esperado:
        real = sha256(destino)
        if real != sha_esperado:
            raise ValueError(
                f"{destino.name}: SHA-256 diferente do esperado.\n"
                f"  esperado {sha_esperado}\n  obtido   {real}\n"
                "O arquivo foi alterado ou corrompido. Apague-o e baixe de novo."
            )
    return destino


def baixar_tse(ano: int, forcar: bool = False) -> None:
    for chave, modelo in config()["tse"].items():
        url = modelo.format(ano=ano)
        try:
            baixar(url, arquivo_tse(chave, ano), forcar)
        except Exception as e:  # noqa: BLE001 - mensagem amigável e segue para o próximo
            print(f"[erro] {url}\n       {e}")


def baixar_externas(forcar: bool = False) -> None:
    for chave, info in config()["externas"].items():
        baixar(info["url"], arquivo_externo(chave), forcar, info.get("sha256"))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ano", type=int, help="baixa só os arquivos do TSE deste ano")
    p.add_argument("--forcar", action="store_true", help="baixa de novo mesmo se já existir")
    a = p.parse_args(argv)

    dir_raw().mkdir(parents=True, exist_ok=True)
    dir_external().mkdir(parents=True, exist_ok=True)
    if a.ano:
        baixar_tse(a.ano, a.forcar)
        return
    cfg = config()
    for ano in filter(None, [cfg["ano_principal"], cfg.get("ano_comparacao")]):
        baixar_tse(int(ano), a.forcar)
    baixar_externas()


if __name__ == "__main__":
    main()
