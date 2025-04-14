import cv2
import numpy as np
from PIL import Image
from pathlib import Path
import logging
from typing import Optional, Tuple, List, Union
from deepface import DeepFace

logger = logging.getLogger(__name__)

class Configuracao:
    TAMANHO_MAXIMO: Tuple[int, int] = (2560, 1440)
    TOLERANCIA: float = 0.50
    MODELO: str = "VGG-Face"
    DETECTOR: str = "opencv"  # Alterar para "opencv" ou "retinaface"
    
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
        logger.debug(f"Tentando validar imagem: {caminho_origem}")
        if not validar_imagem(caminho_origem):
            logger.error(f"Validação falhou para {caminho_origem}")
            return False
        logger.debug(f"Carregando imagem com cv2.imread: {caminho_origem}")
        imagem = cv2.imread(str(caminho_origem))
        if imagem is None:
            logger.error(f"cv2.imread retornou None para {caminho_origem}. Verifique se o arquivo é uma imagem válida.")
            return False
        altura, largura = imagem.shape[:2]
        logger.debug(f"Imagem carregada: {caminho_origem}, tamanho: {largura}x{altura}")
        if largura <= Configuracao.TAMANHO_MAXIMO[0] and altura <= Configuracao.TAMANHO_MAXIMO[1]:
            logger.debug(f"Salvando imagem sem redimensionamento: {caminho_destino}")
            if not cv2.imwrite(str(caminho_destino), imagem):
                logger.error(f"Falha ao salvar imagem sem redimensionamento: {caminho_destino}")
                return False
            logger.debug(f"Imagem salva em {caminho_destino}")
            return True
        proporcao = min(Configuracao.TAMANHO_MAXIMO[0] / largura, Configuracao.TAMANHO_MAXIMO[1] / altura)
        nova_largura = int(largura * proporcao)
        nova_altura = int(altura * proporcao)
        logger.debug(f"Redimensionando para {nova_largura}x{nova_altura}")
        imagem = cv2.resize(imagem, (nova_largura, nova_altura), interpolation=cv2.INTER_AREA)
        logger.debug(f"Salvando imagem redimensionada: {caminho_destino}")
        if not cv2.imwrite(str(caminho_destino), imagem):
            logger.error(f"Falha ao salvar imagem redimensionada: {caminho_destino}")
            return False
        logger.debug(f"Imagem pré-processada salva em {caminho_destino}")
        return True
    except (cv2.error, ValueError, OSError) as e:
        logger.error(f"Erro ao pré-processar imagem {caminho_origem}: {str(e)}")
        return False

def carregar_codificacoes_rostos(caminho: Path) -> List[np.ndarray]:
    """Carrega codificações de rostos de uma imagem usando DeepFace."""
    try:
        if not validar_imagem(caminho):
            return []
        # Extrair embeddings de rostos com DeepFace
        imagem = cv2.imread(str(caminho))
        resultados = DeepFace.represent(
            img_path=str(caminho),
            model_name=Configuracao.MODELO,
            detector_backend=Configuracao.DETECTOR,
            enforce_detection=False
        )
        codificacoes = []
        for resultado in resultados:
            embedding = np.array(resultado["embedding"])
            codificacoes.append(embedding)
        if not codificacoes:
            logger.warning(f"Nenhum rosto detectado em {caminho}")
        return codificacoes
    except Exception as e:
        logger.error(f"Erro ao carregar codificações de {caminho}: {e}")
        return []

def comparar_rostos(codificacoes_conhecidas: List[np.ndarray], codificacao_rosto: np.ndarray) -> bool:
    """Compara uma codificação de rosto com codificações conhecidas usando DeepFace."""
    try:
        for codificacao_conhecida in codificacoes_conhecidas:
            # DeepFace usa distância euclidiana ou cosseno; aqui usamos a função verify para consistência
            resultado = DeepFace.verify(
                img1_path=None,
                img2_path=None,
                model_name=Configuracao.MODELO,
                detector_backend=Configuracao.DETECTOR,
                enforce_detection=False,
                embeddings=(codificacao_conhecida, codificacao_rosto),
                distance_metric="cosine"
            )
            if resultado["verified"]:
                return True
        return False
    except Exception as e:
        logger.error(f"Erro ao comparar rostos: {e}")
        return False