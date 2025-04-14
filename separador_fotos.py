import multiprocessing
import os
import shutil
import logging
from logging.handlers import QueueHandler
import json
from datetime import datetime
from multiprocessing import Pool, cpu_count, Manager
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import math
from queue import Queue
import numpy as np

from processamento_imagem import pre_processar_imagem, carregar_codificacoes_rostos, comparar_rostos, Configuracao
from utilitarios_arquivos import normalizar_caminho, diretorio_temporario, listar_imagens, carregar_rostos_conhecidos, salvar_rostos_conhecidos

logger = logging.getLogger(__name__)

# Função independente para pré-processamento em Pool
def processar_imagem_pre(caminho: Path, diretorio_temp: Path, indice: int, total: int, cancelado: 'multiprocessing.managers.ValueProxy', fila_progresso: 'multiprocessing.managers.QueueProxy') -> Optional[Path]:
    if cancelado.value:
        return None
    nome_arquivo = caminho.name
    caminho_destino = diretorio_temp / f"pre_{nome_arquivo}"
    if pre_processar_imagem(caminho, caminho_destino):
        logger.info(f"[{indice}/{total}] Imagem pré-processada: {nome_arquivo}")
        fila_progresso.put(1)
        return caminho_destino
    return None

# Função independente para processamento de imagens em Pool
def processar_imagem(caminho_imagem: Path, rostos_conhecidos: Dict[str, List[np.ndarray]], pasta_saida: Path, indice: int, total: int, caminho_original: Path, cancelado: 'multiprocessing.managers.ValueProxy', fila_progresso: 'multiprocessing.managers.QueueProxy', evento_processamento: 'multiprocessing.managers.Event', contador_processadas: 'multiprocessing.managers.ValueProxy') -> None:
    if cancelado.value:
        return
    while not evento_processamento.is_set():
        if cancelado.value:
            return
        evento = Manager().Event()
        evento.wait(0.1)
    try:
        codificacoes = carregar_codificacoes_rostos(caminho_imagem)
        if not codificacoes:
            logger.info(f"[{indice}/{total}] Nenhum rosto em {caminho_imagem.name}")
            with contador_processadas.get_lock():  # Sincronizar acesso
                contador_processadas.value += 1
            fila_progresso.put(1)
            return
        pessoas_identificadas = set()
        for codificacao in codificacoes:
            for nome, codificacoes_conhecidas in rostos_conhecidos.items():
                if comparar_rostos(codificacoes_conhecidas, codificacao):
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
        with contador_processadas.get_lock():  # Sincronizar acesso
            contador_processadas.value += 1
        fila_progresso.put(1)
    except (PermissionError, OSError) as e:
        logger.error(f"Erro ao processar {caminho_imagem}: {e}")

class SeparadorFotos:
    def __init__(self):
        self.gerenciador = Manager()
        self.cancelado = self.gerenciador.Value('b', False)
        self.fila_progresso = self.gerenciador.Queue()
        self.fila_logs = self.gerenciador.Queue()
        self.evento_processamento = self.gerenciador.Event()
        self.evento_processamento.set()
        self.contador_processadas = self.gerenciador.Value('i', 0)  # Contador compartilhado

        # Configurar logging
        manipulador = logging.StreamHandler()
        manipulador.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        logging.getLogger().handlers = [manipulador, QueueHandler(self.fila_logs)]
        logging.getLogger().setLevel(logging.INFO)

    def obter_fila_logs(self) -> Queue:
        """Retorna a fila de logs para a interface."""
        return self.fila_logs

    def obter_fila_progresso(self) -> Queue:
        """Retorna a fila de progresso para a interface."""
        return self.fila_progresso

    def obter_contador_processadas(self):
        """Retorna o contador de imagens processadas."""
        return self.contador_processadas

    def pausar_processamento(self) -> None:
        self.evento_processamento.clear()
        logger.info("Processamento pausado")
        self.fila_logs.put("Processamento pausado.")

    def retomar_processamento(self) -> None:
        self.evento_processamento.set()
        logger.info("Processamento retomado")
        self.fila_logs.put("Processamento retomado.")

    def cancelar_processamento(self) -> None:
        self.cancelado.value = True
        self.evento_processamento.set()
        logger.info("Processamento cancelado")
        self.fila_logs.put("Processamento cancelado.")

    def pre_processar_imagens_em_lote(self, arquivos: List[Path], diretorio_temp: Path) -> List[Path]:
        """Pré-processa imagens em paralelo."""
        total = len(arquivos)
        logger.info(f"Iniciando pré-processamento de {total} imagens")
        with Pool(processes=cpu_count()) as pool:
            resultados = pool.starmap(
                processar_imagem_pre,
                [(caminho, diretorio_temp, i + 1, total, self.cancelado, self.fila_progresso) for i, caminho in enumerate(arquivos)]
            )
        caminhos_pre_processados = [r for r in resultados if r is not None]
        logger.info(f"Pré-processamento concluído: {len(caminhos_pre_processados)}/{total} imagens válidas")
        return caminhos_pre_processados

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
        self.cancelado.value = False
        self.contador_processadas.value = 0  # Resetar contador
        erros = []
        pasta_referencia = Path(normalizar_caminho(pasta_referencia))
        pasta_entrada = Path(normalizar_caminho(pasta_entrada))
        pasta_saida = Path(normalizar_caminho(pasta_saida))
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

        with diretorio_temporario() as diretorio_temp:
            rostos_conhecidos = carregar_rostos_conhecidos(pasta_referencia, arquivo_json, diretorio_temp)
            imagens_referencia = {}
            if not rostos_conhecidos:
                logger.info(f"Verificando imagens de referência em {pasta_referencia}")
                for arquivo_ref in pasta_referencia.glob("*.jpg") or pasta_referencia.glob("*.jpeg") or pasta_referencia.glob("*.png"):
                    caminho_temp = diretorio_temp / f"ref_{arquivo_ref.name}"
                    if pre_processar_imagem(arquivo_ref, caminho_temp):
                        codificacoes = carregar_codificacoes_rostos(caminho_temp)
                        if codificacoes:
                            nome_base = arquivo_ref.stem.split('_')[0]
                            rostos_conhecidos.setdefault(nome_base, []).extend(codificacoes)
                            imagens_referencia.setdefault(nome_base, []).append(arquivo_ref)
                if rostos_conhecidos:
                    salvar_rostos_conhecidos(rostos_conhecidos, pasta_referencia, arquivo_json, imagens_referencia)
                else:
                    logger.warning("Nenhum rosto conhecido encontrado")
                    erros.append("Nenhum rosto conhecido válido encontrado")

            arquivos_imagem = listar_imagens(pasta_entrada)
            if not arquivos_imagem:
                erros.append("Nenhuma imagem válida na pasta de entrada")
                logger.warning("Nenhuma imagem válida encontrada")
                self.gerar_relatorio(pasta_saida, erros)
                return

            arquivos_pre_processados = self.pre_processar_imagens_em_lote(arquivos_imagem, diretorio_temp)
            if not arquivos_pre_processadas:
                erros.append("Nenhuma imagem válida após pré-processamento")
                logger.warning("Nenhuma imagem válida após pré-processamento")
                self.gerar_relatorio(pasta_saida, erros)
                return

            total_fotos = len(arquivos_pre_processados)
            num_nucleos = cpu_count()
            num_processos = max(1, math.floor(num_nucleos * 0.8))
            logger.info(f"Usando {num_processos}/{num_nucleos} núcleos para {total_fotos} fotos")
            self.fila_logs.put(f"Processando {total_fotos} fotos com {num_processos} núcleos...")
            argumentos = [
                (caminho, rostos_conhecidos, pasta_saida, i + 1, total_fotos, arquivos_imagem[i], self.cancelado, self.fila_progresso, self.evento_processamento, self.contador_processadas)
                for i, caminho in enumerate(arquivos_pre_processadas)
            ]
            try:
                with Pool(processes=num_processos) as pool:
                    pool.starmap(processar_imagem, argumentos)
            except Exception as e:
                erros.append(f"Erro no processamento paralelo: {e}")
                logger.error(f"Erro no processamento paralelo: {e}")

            if self.cancelado.value:
                erros.append("Processamento cancelado pelo usuário")
                logger.info("Processamento cancelado pelo usuário")
            else:
                logger.info(f"Separação concluída: {pasta_saida}")
            self.gerar_relatorio(pasta_saida, erros)