import cv2
import face_recognition
import numpy as np
from PIL import Image
from pathlib import Path
import logging
from typing import Optional, Tuple, List, Union

logger = logging.getLogger(__name__)

class Config:
    MAX_SIZE: Tuple[int, int] = (640, 480)
    TOLERANCE: float = 0.4
    MODEL: str = "cnn"  # Can be "hog" for faster processing

def validate_image(caminho: Path) -> bool:
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

def preprocess_image(caminho_orig: Path, caminho_dest: Path) -> bool:
    """Pré-processa uma imagem: valida e redimensiona se necessário."""
    try:
        if not validate_image(caminho_orig):
            return False
        imagem = cv2.imread(str(caminho_orig), cv2.IMREAD_COLOR)
        if imagem is None:
            logger.warning(f"cv2.imread falhou para {caminho_orig}. Tentando fallback.")
            imagem = face_recognition.load_image_file(str(caminho_orig))
            imagem = cv2.cvtColor(imagem, cv2.COLOR_RGB2BGR)
        altura, largura = imagem.shape[:2]
        if largura <= Config.MAX_SIZE[0] and altura <= Config.MAX_SIZE[1]:
            cv2.imwrite(str(caminho_dest), imagem)
            logger.debug(f"Imagem sem redimensionamento salva em {caminho_dest}")
            return True
        proporcao = min(Config.MAX_SIZE[0] / largura, Config.MAX_SIZE[1] / altura)
        nova_largura = int(largura * proporcao)
        nova_altura = int(altura * proporcao)
        imagem = cv2.resize(imagem, (nova_largura, nova_altura), interpolation=cv2.INTER_AREA)
        if not cv2.imwrite(str(caminho_dest), imagem):
            logger.error(f"Erro ao salvar imagem pré-processada em {caminho_dest}")
            return False
        logger.debug(f"Imagem pré-processada salva em {caminho_dest}")
        return True
    except (cv2.error, ValueError, OSError) as e:
        logger.error(f"Erro ao pré-processar imagem {caminho_orig}: {e}")
        return False

def load_face_encodings(caminho: Path) -> List[np.ndarray]:
    """Carrega codificações de rostos de uma imagem."""
    try:
        if not validate_image(caminho):
            return []
        imagem = face_recognition.load_image_file(str(caminho))
        encodings = face_recognition.face_encodings(imagem, model=Config.MODEL)
        if not encodings:
            logger.warning(f"Nenhum rosto detectado em {caminho}")
        return encodings
    except Exception as e:
        logger.error(f"Erro ao carregar codificações de {caminho}: {e}")
        return []

def compare_faces(known_encodings: List[np.ndarray], face_encoding: np.ndarray) -> bool:
    """Compara uma codificação de rosto com codificações conhecidas."""
    results = face_recognition.compare_faces(known_encodings, face_encoding, tolerance=Config.TOLERANCE)
    return any(results)