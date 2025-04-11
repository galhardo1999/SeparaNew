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

def normalize_path(caminho: str, base_dir: Optional[str] = None) -> str:
    """Normaliza o caminho para compatibilidade e segurança."""
    try:
        caminho = unicodedata.normalize('NFC', str(caminho))
        caminho = os.path.abspath(caminho)
        if base_dir and not caminho.startswith(os.path.abspath(base_dir)):
            raise ValueError(f"Caminho {caminho} fora do diretório permitido {base_dir}")
        return caminho.replace('\\', '/')
    except Exception as e:
        logger.error(f"Erro ao normalizar caminho {caminho}: {e}")
        return str(caminho)

@contextmanager
def temp_directory() -> Iterator[Path]:
    """Cria um diretório temporário que é removido automaticamente."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def list_images(pasta: Path) -> List[Path]:
    """Lista todas as imagens válidas em uma pasta e subpastas."""
    imagens = []
    try:
        for raiz, _, arquivos in os.walk(pasta):
            for arquivo in arquivos:
                if arquivo.lower().endswith(('.jpg', '.jpeg', '.png')):
                    caminho = Path(raiz) / arquivo
                    from image_processing import validate_image
                    if validate_image(caminho):
                        imagens.append(caminho)
                    else:
                        logger.warning(f"Ignorando arquivo inválido: {caminho}")
        logger.info(f"Encontradas {len(imagens)} imagens válidas em {pasta}")
        return imagens
    except (PermissionError, OSError) as e:
        logger.error(f"Erro ao listar imagens em {pasta}: {e}")
        return []

def load_known_faces(pasta_referencia: Path, arquivo_json: Path, temp_dir: Path) -> Dict[str, List[np.ndarray]]:
    """Carrega codificações de rostos conhecidos do arquivo JSON."""
    from image_processing import preprocess_image, load_face_encodings
    rostos = {}
    if not arquivo_json.exists():
        return rostos
    try:
        with arquivo_json.open('r', encoding='utf-8') as f:
            dados = json.load(f)
        for nome, info in dados.items():
            codificacoes = []
            for caminho in info['imagens']:
                caminho = Path(normalize_path(caminho, str(pasta_referencia)))
                if not caminho.exists():
                    continue
                caminho_temp = temp_dir / f"ref_{caminho.name}"
                if preprocess_image(caminho, caminho_temp):
                    codificacoes.extend(load_face_encodings(caminho_temp))
            if codificacoes:
                rostos[nome] = codificacoes
            else:
                logger.warning(f"Nenhuma codificação válida para {nome}")
        logger.info("Rostos conhecidos carregados com sucesso")
    except (json.JSONDecodeError, PermissionError, OSError) as e:
        logger.error(f"Erro ao carregar {arquivo_json}: {e}")
    return rostos

def save_known_faces(rostos: Dict[str, List[np.ndarray]], pasta_referencia: Path, arquivo_json: Path, imagens: Dict[str, List[Path]]) -> None:
    """Salva codificações de rostos conhecidos no arquivo JSON."""
    try:
        dados = {nome: {"imagens": [str(img) for img in imagens.get(nome, [])]} for nome in rostos}
        with arquivo_json.open('w', encoding='utf-8') as f:
            json.dump(dados, f, indent=2)
        logger.info(f"Rostos conhecidos salvos em {arquivo_json}")
    except (PermissionError, OSError) as e:
        logger.error(f"Erro ao salvar {arquivo_json}: {e}")