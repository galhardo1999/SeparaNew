import os
import shutil
import logging
import numpy as np
from logging.handlers import QueueHandler
import json
from datetime import datetime
from multiprocessing import Pool, cpu_count, Manager
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import math
import threading
from queue import Queue

from image_processing import preprocess_image, load_face_encodings, compare_faces, Config
from file_utils import normalize_path, temp_directory, list_images, load_known_faces, save_known_faces

logger = logging.getLogger(__name__)

# Standalone function for preprocessing in Pool
def processar_imagem_pre(args: Tuple[Path, Path, int, int, 'multiprocessing.Value', 'multiprocessing.Queue']) -> Optional[Path]:
    caminho, temp_dir, indice, total, cancelado, progresso_queue = args
    with cancelado.get_lock():
        if cancelado.value:
            return None
    nome_arquivo = caminho.name
    caminho_dest = temp_dir / f"pre_{nome_arquivo}"
    if preprocess_image(caminho, caminho_dest):
        logger.info(f"[{indice}/{total}] Imagem pré-processada: {nome_arquivo}")
        progresso_queue.put(1)
        return caminho_dest
    return None

class Separador:
    def __init__(self):
        self.manager = Manager()
        self.cancelado = self.manager.Value('b', False)  # Managed synchronized value
        self.progresso_queue = self.manager.Queue()      # Managed queue for progress
        self.log_queue = self.manager.Queue()            # Managed queue for logs
        self.processamento_event = threading.Event()
        self.processamento_event.set()

        # Configurar logging
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        logging.getLogger().handlers = [handler, QueueHandler(self.log_queue)]
        logging.getLogger().setLevel(logging.INFO)

    def get_log_queue(self) -> Queue:
        """Retorna a fila de logs para a interface."""
        return self.log_queue

    def get_progresso_queue(self) -> Queue:
        """Retorna a fila de progresso para a interface."""
        return self.progresso_queue

    def pausar_processamento(self) -> None:
        self.processamento_event.clear()
        logger.info("Processamento pausado")
        self.log_queue.put("Processamento pausado.")

    def retomar_processamento(self) -> None:
        self.processamento_event.set()
        logger.info("Processamento retomado")
        self.log_queue.put("Processamento retomado.")

    def cancelar_processamento(self) -> None:
        with self.cancelado.get_lock():
            self.cancelado.value = True
        self.processamento_event.set()
        logger.info("Processamento cancelado")
        self.log_queue.put("Processamento cancelado.")

    def pre_processar_imagens_em_lote(self, arquivos: List[Path], temp_dir: Path) -> List[Path]:
        """Pré-processa imagens em paralelo."""
        total = len(arquivos)
        logger.info(f"Iniciando pré-processamento de {total} imagens")
        with Pool(processes=cpu_count()) as pool:
            resultados = pool.starmap(
                processar_imagem_pre,
                [(caminho, temp_dir, i + 1, total, self.cancelado, self.progresso_queue) for i, caminho in enumerate(arquivos)]
            )
        caminhos_pre_processados = [r for r in resultados if r is not None]
        logger.info(f"Pré-processamento concluído: {len(caminhos_pre_processados)}/{total} imagens válidas")
        return caminhos_pre_processados

    def processar_imagem(self, args: Tuple[Path, Dict[str, List[np.ndarray]], Path, int, int, Path]) -> None:
        """Processa uma imagem para reconhecimento facial e cópia."""
        caminho_imagem, rostos_conhecidos, pasta_saida, indice, total, caminho_original = args
        with self.cancelado.get_lock():
            if self.cancelado.value:
                return
        while not self.processamento_event.is_set():
            with self.cancelado.get_lock():
                if self.cancelado.value:
                    return
            threading.Event().wait(0.1)
        try:
            codificacoes = load_face_encodings(caminho_imagem)
            if not codificacoes:
                logger.info(f"[{indice}/{total}] Nenhum rosto em {caminho_imagem.name}")
                self.progresso_queue.put(1)
                return
            pessoas_identificadas = set()
            for codificacao in codificacoes:
                for nome, codificacoes_conhecidas in rostos_conhecidos.items():
                    if compare_faces(codificacoes_conhecidas, codificacao):
                        pessoas_identificadas.add(nome)
            if pessoas_identificadas:
                for nome in pessoas_identificadas:
                    pasta_pessoa = pasta_saida / nome
                    pasta_pessoa.mkdir(parents=True, exist_ok=True)
                    shutil.copy(caminho_original, pasta_pessoa)
                    logger.info(f"[{indice}/{total}] {caminho_original.name} copiada para {nome}")
            else:
                pasta_desconhecidos = pasta_saida / "desconhecidos"
                pasta_desconhecidos.mkdir(parents=True, exist_ok=True)
                shutil.copy(caminho_original, pasta_desconhecidos)
                logger.info(f"[{indice}/{total}] {caminho_original.name} copiada para 'desconhecidos'")
            self.progresso_queue.put(1)
        except (PermissionError, OSError) as e:
            logger.error(f"Erro ao processar {caminho_imagem}: {e}")

    def gerar_relatorio(self, pasta_saida: Path, erros: List[str]) -> None:
        """Gera um relatório com o número de fotos por pessoa."""
        relatorio = {}
        try:
            for pasta in pasta_saida.iterdir():
                if pasta.is_dir():
                    qtd_fotos = len([f for f in pasta.iterdir() if f.suffix.lower() in {'.jpg', '.jpeg', '.png'}])
                    relatorio[pasta.name] = qtd_fotos
            with open("relatorio.txt", "w", encoding='utf-8') as f:
                f.write("Relatório de Separação\n")
                f.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                for pessoa, qtd in relatorio.items():
                    f.write(f"{pessoa}: {qtd} fotos\n")
                if erros:
                    f.write("\nErros Encontrados:\n")
                    for erro in erros:
                        f.write(f"- {erro}\n")
            logger.info("Relatório gerado em 'relatorio.txt'")
        except (PermissionError, OSError) as e:
            logger.error(f"Erro ao gerar relatório: {e}")
            erros.append(f"Erro ao gerar relatório: {e}")

    def separar_fotos(self, pasta_referencia: str, pasta_entrada: str, pasta_saida: str) -> None:
        """Separa fotos por pessoa com base em reconhecimento facial."""
        with self.cancelado.get_lock():
            self.cancelado.value = False
        erros = []
        pasta_referencia = Path(normalize_path(pasta_referencia))
        pasta_entrada = Path(normalize_path(pasta_entrada))
        pasta_saida = Path(normalize_path(pasta_saida))
        arquivo_json = Path("rostos_conhecidos.json")
        logger.info(f"Iniciando separação: Ref={pasta_referencia}, In={pasta_entrada}, Out={pasta_saida}")

        try:
            pasta_saida.mkdir(parents=True, exist_ok=True)
            pasta_referencia.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as e:
            erros.append(f"Sem permissão para criar pastas: {e}")
            logger.error(f"Erro ao criar pastas: {e}")
            self.gerar_relatorio(pasta_saida, erros)
            return

        with temp_directory() as temp_dir:
            rostos_conhecidos = load_known_faces(pasta_referencia, arquivo_json, temp_dir)
            imagens_referencia = {}
            if not rostos_conhecidos:
                logger.info(f"Verificando imagens de referência em {pasta_referencia}")
                for arquivo_ref in pasta_referencia.glob("*.jpg") or pasta_referencia.glob("*.jpeg") or pasta_referencia.glob("*.png"):
                    caminho_temp = temp_dir / f"ref_{arquivo_ref.name}"
                    if preprocess_image(arquivo_ref, caminho_temp):
                        codificacoes = load_face_encodings(caminho_temp)
                        if codificacoes:
                            nome_base = arquivo_ref.stem.split('_')[0]
                            rostos_conhecidos.setdefault(nome_base, []).extend(codificacoes)
                            imagens_referencia.setdefault(nome_base, []).append(arquivo_ref)
                if rostos_conhecidos:
                    save_known_faces(rostos_conhecidos, pasta_referencia, arquivo_json, imagens_referencia)
                else:
                    logger.warning("Nenhum rosto conhecido encontrado")
                    erros.append("Nenhum rosto conhecido válido encontrado")

            arquivos_imagem = list_images(pasta_entrada)
            if not arquivos_imagem:
                erros.append("Nenhuma imagem válida na pasta de entrada")
                logger.warning("Nenhuma imagem válida encontrada")
                self.gerar_relatorio(pasta_saida, erros)
                return

            arquivos_pre_processados = self.pre_processar_imagens_em_lote(arquivos_imagem, temp_dir)
            if not arquivos_pre_processados:
                erros.append("Nenhuma imagem válida após pré-processamento")
                logger.warning("Nenhuma imagem válida após pré-processamento")
                self.gerar_relatorio(pasta_saida, erros)
                return

            total_fotos = len(arquivos_pre_processados)
            num_nucleos = cpu_count()
            num_processos = max(1, math.floor(num_nucleos * 0.8))
            logger.info(f"Usando {num_processos}/{num_nucleos} núcleos para {total_fotos} fotos")
            args = [
                (caminho, rostos_conhecidos, pasta_saida, i + 1, total_fotos, arquivos_imagem[i])
                for i, caminho in enumerate(arquivos_pre_processados)
            ]
            try:
                with Pool(processes=num_processos) as pool:
                    pool.map(self.processar_imagem, args)
            except Exception as e:
                erros.append(f"Erro no processamento paralelo: {e}")
                logger.error(f"Erro no processamento paralelo: {e}")

        if self.cancelado.value:
            erros.append("Processamento cancelado pelo usuário")
            logger.info("Processamento cancelado pelo usuário")
        else:
            logger.info(f"Separação concluída: {pasta_saida}")
        self.gerar_relatorio(pasta_saida, erros)