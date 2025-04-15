import cv2
import numpy as np
from numpy.linalg import norm
from PIL import Image
from pathlib import Path
import logging
from typing import Optional, Tuple, List, Union
from deepface import DeepFace

logger = logging.getLogger(__name__)

class Configuracao:
    MODELO: str = "Facenet512"  # Já configurado
    DETECTOR: str = "dlib"
    TOLERANCIA: float = 0.35
    TAMANHO_MAXIMO: Tuple[int, int] = (1280, 720)


def validar_imagem(caminho: Path) -> bool:
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
    try:
        logger.debug(f"Tentando validar imagem: {caminho_origem}")
        if not validar_imagem(caminho_origem):
            logger.error(f"Validação falhou para {caminho_origem}")
            return False

        try:
            with Image.open(caminho_origem) as pil_img:
                pil_img = pil_img.convert("RGB")
                imagem = np.array(pil_img)[:, :, ::-1]  # RGB para BGR
        except Exception as e:
            logger.error(f"Erro ao abrir imagem com PIL {caminho_origem}: {e}")
            return False

        altura, largura = imagem.shape[:2]
        logger.debug(f"Imagem carregada: {caminho_origem}, tamanho: {largura}x{altura}")

        if largura <= Configuracao.TAMANHO_MAXIMO[0] and altura <= Configuracao.TAMANHO_MAXIMO[1]:
            logger.debug(f"Salvando imagem sem redimensionamento: {caminho_destino}")
            if not cv2.imwrite(str(caminho_destino), imagem):
                logger.error(f"Falha ao salvar imagem sem redimensionamento: {caminho_destino}")
                return False
            return True

        proporcao = min(Configuracao.TAMANHO_MAXIMO[0] / largura, Configuracao.TAMANHO_MAXIMO[1] / altura)
        nova_largura = int(largura * proporcao)
        nova_altura = int(altura * proporcao)
        imagem = cv2.resize(imagem, (nova_largura, nova_altura), interpolation=cv2.INTER_AREA)

        logger.debug(f"Salvando imagem redimensionada: {caminho_destino}")
        if not cv2.imwrite(str(caminho_destino), imagem):
            logger.error(f"Falha ao salvar imagem redimensionada: {caminho_destino}")
            return False

        return True
    except (cv2.error, ValueError, OSError) as e:
        logger.error(f"Erro ao pré-processar imagem {caminho_origem}: {str(e)}")
        return False

def carregar_codificacoes_rostos(caminho: Path) -> List[np.ndarray]:
    try:
        if not validar_imagem(caminho):
            return []
        resultados = DeepFace.represent(
            img_path=str(caminho),
            model_name=Configuracao.MODELO,
            detector_backend=Configuracao.DETECTOR,
            enforce_detection=False
        )
        codificacoes = [np.array(r["embedding"]) for r in resultados if "embedding" in r]
        if not codificacoes:
            logger.warning(f"Nenhum rosto detectado em {caminho}")
        return codificacoes
    except Exception as e:
        logger.error(f"Erro ao carregar codificações de {caminho}: {e}")
        return []

def comparar_rostos(codificacoes_conhecidas: List[np.ndarray], codificacao_rosto: np.ndarray) -> bool:
    """Compara a codificação de um rosto com uma lista de codificações conhecidas usando distância cosseno."""
    try:
        for codificacao_conhecida in codificacoes_conhecidas:
            # Distância cosseno
            dot = np.dot(codificacao_conhecida, codificacao_rosto)
            norma_a = norm(codificacao_conhecida)
            norma_b = norm(codificacao_rosto)
            if norma_a == 0 or norma_b == 0:
                continue
            similaridade = dot / (norma_a * norma_b)
            distancia = 1 - similaridade  # quanto menor, mais parecido
            if distancia <= Configuracao.TOLERANCIA:
                return True
        return False
    except Exception as e:
        logger.error(f"Erro ao comparar rostos manualmente: {e}")
        return False
