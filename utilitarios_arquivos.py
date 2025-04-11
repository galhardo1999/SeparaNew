import os
import shutil
import json
import unicodedata
import numpy as np
from pathlib import Path
from contextlib import contextmanager
import tempfile
import logging
from typing import Dict, List, Iterator, Optional

logger = logging.getLogger(__name__)

def normalizar_caminho(caminho: str, diretorio_base: Optional[str] = None) -> str:
    """Normaliza o caminho para compatibilidade e segurança."""
    try:
        caminho = unicodedata.normalize('NFC', str(caminho))
        caminho = os.path.abspath(caminho)
        if diretorio_base and not caminho.startswith(os.path.abspath(diretorio_base)):
            raise ValueError(f"Caminho {caminho} fora do diretório permitido {diretorio_base}")
        return caminho.replace('\\', '/')
    except Exception as e:
        logger.error(f"Erro ao normalizar caminho {caminho}: {e}")
        return str(caminho)

@contextmanager
def diretorio_temporario() -> Iterator[Path]:
    """Cria um diretório temporário que é removido automaticamente."""
    diretorio_temp = Path(tempfile.mkdtemp())
    try:
        yield diretorio_temp
    finally:
        shutil.rmtree(diretorio_temp, ignore_errors=True)

def listar_imagens(pasta: Path) -> List[Path]:
    """Lista todas as imagens válidas em uma pasta e subpastas."""
    imagens = []
    try:
        for raiz, _, arquivos in os.walk(pasta):
            for arquivo in arquivos:
                if arquivo.lower().endswith(('.jpg', '.jpeg', '.png')):
                    caminho = Path(raiz) / arquivo
                    from processamento_imagem import validar_imagem
                    if validar_imagem(caminho):
                        imagens.append(caminho)
                    else:
                        logger.warning(f"Ignorando arquivo inválido: {caminho}")
        logger.info(f"Encontradas {len(imagens)} imagens válidas em {pasta}")
        return imagens
    except (PermissionError, OSError) as e:
        logger.error(f"Erro ao listar imagens em {pasta}: {e}")
        return []

def carregar_rostos_conhecidos(pasta_referencia: Path, arquivo_json: Path, diretorio_temp: Path) -> Dict[str, List[np.ndarray]]:
    """Carrega codificações de rostos conhecidos do arquivo JSON."""
    from processamento_imagem import pre_processar_imagem, carregar_codificacoes_rostos
    rostos = {}
    if not arquivo_json.exists():
        return rostos
    try:
        with arquivo_json.open('r', encoding='utf-8') as f:
            dados = json.load(f)
        for nome, info in dados.items():
            codificacoes = []
            for caminho in info['imagens']:
                caminho = Path(normalizar_caminho(caminho, str(pasta_referencia)))
                if not caminho.exists():
                    continue
                caminho_temp = diretorio_temp / f"ref_{caminho.name}"
                if pre_processar_imagem(caminho, caminho_temp):
                    codificacoes.extend(carregar_codificacoes_rostos(caminho_temp))
            if codificacoes:
                rostos[nome] = codificacoes
            else:
                logger.warning(f"Nenhuma codificação válida para {nome}")
        logger.info("Rostos conhecidos carregados com sucesso")
    except (json.JSONDecodeError, PermissionError, OSError) as e:
        logger.error(f"Erro ao carregar {arquivo_json}: {e}")
    return rostos

def salvar_rostos_conhecidos(rostos: Dict[str, List[np.ndarray]], pasta_referencia: Path, arquivo_json: Path, imagens: Dict[str, List[Path]]) -> None:
    """Salva codificações de rostos conhecidos no arquivo JSON."""
    try:
        dados = {nome: {"imagens": [str(img) for img in imagens.get(nome, [])]} for nome in rostos}
        with arquivo_json.open('w', encoding='utf-8') as f:
            json.dump(dados, f, indent=2)
        logger.info(f"Rostos conhecidos salvos em {arquivo_json}")
    except (PermissionError, OSError) as e:
        logger.error(f"Erro ao salvar {arquivo_json}: {e}")