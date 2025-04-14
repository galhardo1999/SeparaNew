import cv2
import face_recognition
import numpy as np
from PIL import Image
from pathlib import Path
import logging
from typing import Optional, Tuple, List, Union

logger = logging.getLogger(__name__)

class Configuracao:
    TAMANHO_MAXIMO: Tuple[int, int] = (2560, 1440)
    TOLERANCIA: float = 0.47
    MODELO: str = "cnn"  # Pode ser "hog" para processamento mais rápido # Pode ser "cnn" para processamento mais preciso

def validar_imagem(caminho: Path) -> bool:
    """Verifica se o arquivo é uma imagem válida."""
    try:
        if not caminho.exists():
            logger.warning(f"Arquivo não encontrado: {caminho}")
            return False
        if not caminho.is_file() or caminho.stat().st_size == 0:
            logger.warning(f"Arquivo inválido ou vazio: {caminho}")
            return False
        with Image.open(caminho) as img:
            img.verify()
        return True
    except Exception as e:
        logger.error(f"Erro ao validar imagem {caminho}: {e}")
        return False

def pre_processar_imagem(caminho_origem: Path, caminho_destino: Path) -> bool:
    """Pré-processa uma imagem: valida e redimensiona se necessário."""
    try:
        if not validar_imagem(caminho_origem):
            return False
        imagem = face_recognition.load_image_file(str(caminho_origem))
        imagem = cv2.cvtColor(imagem, cv2.COLOR_RGB2BGR)
        altura, largura = imagem.shape[:2]
        if largura <= Configuracao.TAMANHO_MAXIMO[0] and altura <= Configuracao.TAMANHO_MAXIMO[1]:
            cv2.imwrite(str(caminho_destino), imagem)
            logger.debug(f"Imagem sem redimensionamento salva em {caminho_destino}")
            return True
        proporcao = min(Configuracao.TAMANHO_MAXIMO[0] / largura, Configuracao.TAMANHO_MAXIMO[1] / altura)
        nova_largura = int(largura * proporcao)
        nova_altura = int(altura * proporcao)
        imagem = cv2.resize(imagem, (nova_largura, nova_altura), interpolation=cv2.INTER_AREA)
        if not cv2.imwrite(str(caminho_destino), imagem):
            logger.error(f"Erro ao salvar imagem pré-processada em {caminho_destino}")
            return False
        logger.debug(f"Imagem pré-processada salva em {caminho_destino}")
        return True
    except (cv2.error, ValueError, OSError) as e:
        logger.error(f"Erro ao pré-processar imagem {caminho_origem}: {e}")
        return False

def carregar_codificacoes_rostos(caminho: Path) -> List[np.ndarray]:
    """Carrega codificações de rostos de uma imagem."""
    try:
        if not validar_imagem(caminho):
            return []
        imagem = face_recognition.load_image_file(str(caminho))
        codificacoes = face_recognition.face_encodings(imagem, model=Configuracao.MODELO)
        if not codificacoes:
            logger.warning(f"Nenhum rosto detectado em {caminho}")
        return codificacoes
    except Exception as e:
        logger.error(f"Erro ao carregar codificações de {caminho}: {e}")
        return []

def comparar_rostos(codificacoes_conhecidas: List[np.ndarray], codificacao_rosto: np.ndarray) -> bool:
    """Compara uma codificação de rosto com codificações conhecidas."""
    resultados = face_recognition.compare_faces(codificacoes_conhecidas, codificacao_rosto, tolerance=Configuracao.TOLERANCIA)
    return any(resultados)