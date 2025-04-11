import cv2
import face_recognition
import os
import shutil
from pathlib import Path
import json
from multiprocessing import Pool, cpu_count, Queue
import math
import numpy as np
import threading
import tempfile
import unicodedata
import sys
import logging
from datetime import datetime
from PIL import Image

# Variáveis globais
cancelado = False
log_queue = Queue()
processamento_event = threading.Event()
processamento_event.set()

# Configurações iniciais
tolerance = 0.4
modelo_reconhecimento = "cnn"
TAMANHO_MAXIMO = (640, 480)
PASTA_TEMP = Path(tempfile.mkdtemp())

# Handler personalizado para enviar logs para log_queue
class QueueHandler(logging.Handler):
    def __init__(self, queue):
        super().__init__()
        self.queue = queue

    def emit(self, record):
        try:
            msg = self.format(record)
            self.queue.put(msg)
        except Exception:
            self.handleError(record)

def get_log_queue():
    """Retorna a fila de logs para uso na interface."""
    return log_queue

# Configurar logging
logging.getLogger().handlers = []
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("separador.log"),
        QueueHandler(log_queue),
    ]
)

def normalize_path(caminho):
    """Normaliza o caminho para lidar com caracteres Unicode e compatibilidade com OpenCV."""
    try:
        caminho = unicodedata.normalize('NFC', str(caminho))
        caminho = os.path.normpath(os.path.abspath(caminho))
        caminho = caminho.replace('\\', '/')
        if sys.platform == "win32":
            caminho = caminho.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
        logging.debug(f"Path normalizado: {caminho}")
        return caminho
    except Exception as e:
        logging.error(f"Erro ao normalizar caminho {caminho}: {e}")
        return str(caminho)

def pausar_processamento():
    processamento_event.clear()
    logging.info("Processamento pausado")

def retomar_processamento():
    processamento_event.set()
    logging.info("Processamento retomado")

def cancelar_processamento():
    global cancelado
    cancelado = True
    processamento_event.set()
    logging.info("Processamento cancelado")

def validar_arquivo(caminho):
    """Verifica se o arquivo existe, é acessível e é uma imagem válida."""
    caminho = normalize_path(caminho)
    try:
        if not os.path.exists(caminho):
            logging.warning(f"Arquivo não encontrado: {caminho}")
            return False
        if not os.access(caminho, os.R_OK):
            logging.warning(f"Permissão negada para arquivo: {caminho}")
            return False
        if os.path.getsize(caminho) == 0:
            logging.warning(f"Arquivo vazio: {caminho}")
            return False
        with open(caminho, 'rb') as f:
            header = f.read(4)
            if not header.startswith(b'\xff\xd8') and not header.startswith(b'\x89\x50\x4e\x47'):
                logging.warning(f"Formato inválido (cabeçalho: {header}): {caminho}")
                return False
        try:
            with Image.open(caminho) as img:
                img.verify()
            logging.debug(f"Arquivo validado com PIL: {caminho}")
        except Exception as e:
            logging.warning(f"Imagem corrompida ou inválida (PIL): {caminho} - {e}")
            return False
        return True
    except PermissionError as e:
        logging.error(f"Erro de permissão ao validar arquivo {caminho}: {e}")
        return False
    except Exception as e:
        logging.error(f"Erro ao validar arquivo {caminho}: {e}")
        return False

def pre_processar_imagem(caminho_orig, caminho_dest):
    """Pré-processa uma imagem: redimensiona e valida."""
    try:
        caminho_orig = normalize_path(caminho_orig)
        if not validar_arquivo(caminho_orig):
            return False
        logging.debug(f"Tentando carregar imagem: {caminho_orig}")
        imagem = cv2.imread(caminho_orig, cv2.IMREAD_COLOR)
        if imagem is None:
            logging.warning(f"cv2.imread falhou para {caminho_orig}. Tentando fallback.")
            temp_path = PASTA_TEMP / os.path.basename(caminho_orig)
            try:
                shutil.copy2(caminho_orig, temp_path)
                imagem = cv2.imread(str(temp_path), cv2.IMREAD_COLOR)
                if imagem is None:
                    logging.error(f"Falha ao carregar após cópia para {temp_path}")
                    try:
                        img_test = face_recognition.load_image_file(str(temp_path))
                        logging.info(f"Carregado com face_recognition: {temp_path}")
                        imagem = cv2.cvtColor(img_test, cv2.COLOR_RGB2BGR)
                    except Exception as e:
                        logging.error(f"Falha no fallback com face_recognition: {e}")
                        return False
                else:
                    logging.info(f"Imagem carregada após cópia para {temp_path}")
            except Exception as e:
                logging.error(f"Erro ao copiar para {temp_path}: {e}")
                return False
        altura, largura = imagem.shape[:2]
        proporcao = min(TAMANHO_MAXIMO[0] / largura, TAMANHO_MAXIMO[1] / altura)
        if proporcao < 1:
            nova_largura = int(largura * proporcao)
            nova_altura = int(altura * proporcao)
            imagem = cv2.resize(imagem, (nova_largura, nova_altura), interpolation=cv2.INTER_AREA)
        caminho_dest = normalize_path(caminho_dest)
        if not cv2.imwrite(caminho_dest, imagem):
            logging.error(f"Erro ao salvar imagem pré-processada em {caminho_dest}")
            return False
        logging.info(f"Imagem pré-processada salva em {caminho_dest}")
        return True
    except (cv2.error, ValueError) as e:
        logging.error(f"Erro de processamento de imagem {caminho_orig}: {e}")
        return False
    except PermissionError as e:
        logging.error(f"Permissão negada para {caminho_orig}: {e}")
        return False
    except Exception as e:
        logging.critical(f"Erro inesperado no pré-processamento de {caminho_orig}: {e}", exc_info=True)
        return False

def processar_imagem_pre(caminho, indice, total):
    global cancelado
    if cancelado:
        return None
    nome_arquivo = os.path.basename(caminho)
    caminho_dest = PASTA_TEMP / f"pre_{nome_arquivo}"
    if pre_processar_imagem(caminho, caminho_dest):
        logging.info(f"[{indice}/{total}] Imagem pré-processada: {nome_arquivo}")
        return str(caminho_dest)
    return None

def pre_processar_imagens_em_lote(arquivos_imagem):
    total = len(arquivos_imagem)
    logging.info(f"Iniciando pré-processamento de {total} imagens")
    with Pool(processes=cpu_count()) as pool:
        resultados = pool.starmap(
            processar_imagem_pre,
            [(caminho, i + 1, total) for i, caminho in enumerate(arquivos_imagem)]
        )
    caminhos_pre_processados = [r for r in resultados if r is not None]
    logging.info(f"Pré-processamento concluído: {len(caminhos_pre_processados)}/{total} imagens válidas")
    return caminhos_pre_processados

def carregar_rostos_conhecidos(pasta_referencia, arquivo_rostos_conhecidos):
    pasta_referencia = normalize_path(pasta_referencia)
    arquivo_rostos_conhecidos = normalize_path(arquivo_rostos_conhecidos)
    rostos = {}
    if os.path.exists(arquivo_rostos_conhecidos):
        try:
            with open(arquivo_rostos_conhecidos, 'r', encoding='utf-8') as f:
                dados = json.load(f)
                for nome, info in dados.items():
                    codificacoes = []
                    for caminho in info['imagens']:
                        caminho = normalize_path(caminho)
                        if not validar_arquivo(caminho):
                            continue
                        nome_arquivo = os.path.basename(caminho)
                        caminho_temp = PASTA_TEMP / f"ref_{nome_arquivo}"
                        if pre_processar_imagem(caminho, caminho_temp):
                            imagem = face_recognition.load_image_file(str(caminho_temp))
                            codificacao = face_recognition.face_encodings(imagem, model=modelo_reconhecimento)
                            if codificacao:
                                codificacoes.append(codificacao[0])
                            else:
                                logging.warning(f"Nenhum rosto detectado em {caminho}")
                    if codificacoes:
                        rostos[nome] = codificacoes
                    else:
                        logging.warning(f"Nenhuma codificação válida para {nome}")
                logging.info("Rostos conhecidos carregados com sucesso")
        except json.JSONDecodeError as e:
            logging.error(f"Erro ao ler rostos_conhecidos.json: {e}")
        except PermissionError as e:
            logging.error(f"Permissão negada para {arquivo_rostos_conhecidos}: {e}")
        except Exception as e:
            logging.critical(f"Erro inesperado ao carregar rostos conhecidos: {e}", exc_info=True)
    return rostos

def salvar_rostos_conhecidos(rostos_conhecidos, pasta_referencia, arquivo_rostos_conhecidos):
    pasta_referencia = normalize_path(pasta_referencia)
    arquivo_rostos_conhecidos = normalize_path(arquivo_rostos_conhecidos)
    dados = {}
    for nome, codificacoes in rostos_conhecidos.items():
        imagens = [f"{pasta_referencia}/{nome}_{i}.jpg" for i in range(len(codificacoes))]
        dados[nome] = {"imagens": imagens}
    try:
        with open(arquivo_rostos_conhecidos, 'w', encoding='utf-8') as f:
            json.dump(dados, f)
        logging.info("Rostos conhecidos salvos com sucesso")
    except PermissionError as e:
        logging.error(f"Permissão negada para salvar {arquivo_rostos_conhecidos}: {e}")
    except Exception as e:
        logging.critical(f"Erro ao salvar rostos conhecidos: {e}", exc_info=True)

def validar_imagem(caminho):
    try:
        caminho = normalize_path(caminho)
        if not validar_arquivo(caminho):
            return False
        imagem = face_recognition.load_image_file(caminho)
        return True
    except Exception as e:
        logging.error(f"Imagem inválida ou corrompida: {caminho} - Erro: {e}")
        return False

def processar_imagem(args):
    global cancelado
    caminho_imagem, rostos_conhecidos, pasta_saida, indice, total, caminho_original = args
    if cancelado:
        return
    while not processamento_event.is_set():
        if cancelado:
            return
        threading.Event().wait(0.1)
    if not validar_imagem(caminho_imagem):
        return
    try:
        imagem = face_recognition.load_image_file(caminho_imagem)
        codificacoes_rosto = face_recognition.face_encodings(imagem, model=modelo_reconhecimento)
        if len(codificacoes_rosto) == 0:
            logging.info(f"[{indice}/{total}] Nenhum rosto em {os.path.basename(caminho_imagem)}")
            return
        correspondencias_encontradas = False
        pessoas_identificadas = []
        for codificacao_rosto in codificacoes_rosto:
            for nome, codificacoes_conhecidas in rostos_conhecidos.items():
                resultados = face_recognition.compare_faces(codificacoes_conhecidas, codificacao_rosto, tolerance=tolerance)
                if any(resultados):
                    if nome not in pessoas_identificadas:
                        pessoas_identificadas.append(nome)
                    correspondencias_encontradas = True
        if correspondencias_encontradas:
            for nome in pessoas_identificadas:
                pasta_pessoa = Path(pasta_saida) / nome
                pasta_pessoa.mkdir(parents=True, exist_ok=True)
                shutil.copy(caminho_original, pasta_pessoa)
                logging.info(f"[{indice}/{total}] {os.path.basename(caminho_original)} copiada para {nome}")
        else:
            pasta_desconhecidos = Path(pasta_saida) / "desconhecidos"
            pasta_desconhecidos.mkdir(parents=True, exist_ok=True)
            shutil.copy(caminho_original, pasta_desconhecidos)
            logging.info(f"[{indice}/{total}] {os.path.basename(caminho_original)} copiada para 'desconhecidos'")
    except PermissionError as e:
        logging.error(f"Permissão negada ao processar {caminho_imagem}: {e}")
    except Exception as e:
        logging.critical(f"Erro ao processar imagem {caminho_imagem}: {e}", exc_info=True)

def gerar_relatorio(pasta_saida, erros):
    pasta_saida = normalize_path(pasta_saida)
    relatorio = {}
    try:
        for pasta in os.listdir(pasta_saida):
            caminho_pasta = os.path.join(pasta_saida, pasta)
            if os.path.isdir(caminho_pasta):
                qtd_fotos = len([f for f in os.listdir(caminho_pasta) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
                relatorio[pasta] = qtd_fotos
        with open("relatorio.txt", "w", encoding='utf-8') as f:
            f.write("Relatório de Separação\n")
            f.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            for pessoa, qtd in relatorio.items():
                f.write(f"{pessoa}: {qtd} fotos\n")
            if erros:
                f.write("\nErros Encontrados:\n")
                for erro in erros:
                    f.write(f"- {erro}\n")
        logging.info("Relatório gerado em 'relatorio.txt'")
    except PermissionError as e:
        logging.error(f"Permissão negada para gerar relatório: {e}")
        erros.append(f"Sem permissão para criar relatório: {e}")
    except Exception as e:
        logging.critical(f"Erro ao gerar relatório: {e}", exc_info=True)
        erros.append(f"Erro ao gerar relatório: {e}")

def listar_fotos_em_subpastas(pasta_entrada):
    pasta_entrada = normalize_path(pasta_entrada)
    arquivos_imagem = []
    try:
        for raiz, _, arquivos in os.walk(pasta_entrada):
            for arquivo in arquivos:
                if arquivo.lower().endswith(('.jpg', '.jpeg', '.png')):
                    caminho = os.path.join(raiz, arquivo)
                    caminho = normalize_path(caminho)
                    if validar_arquivo(caminho):
                        arquivos_imagem.append(caminho)
                    else:
                        logging.warning(f"Ignorando arquivo inválido: {caminho}")
        logging.info(f"Encontradas {len(arquivos_imagem)} fotos válidas em {pasta_entrada}")
        return arquivos_imagem
    except PermissionError as e:
        logging.error(f"Permissão negada para listar fotos em {pasta_entrada}: {e}")
    except Exception as e:
        logging.critical(f"Erro ao listar fotos em {pasta_entrada}: {e}", exc_info=True)
    return arquivos_imagem

def separar_fotos(pasta_referencia, pasta_entrada, pasta_saida):
    global cancelado
    cancelado = False
    erros = []
    arquivo_rostos_conhecidos = "rostos_conhecidos.json"
    pasta_referencia = normalize_path(pasta_referencia)
    pasta_entrada = normalize_path(pasta_entrada)
    pasta_saida = normalize_path(pasta_saida)
    logging.info(f"Iniciando separação: Ref={pasta_referencia}, In={pasta_entrada}, Out={pasta_saida}")
    try:
        Path(pasta_saida).mkdir(parents=True, exist_ok=True)
        Path(pasta_referencia).mkdir(parents=True, exist_ok=True)
        PASTA_TEMP.mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        logging.error(f"Permissão negada para criar pastas: {e}")
        erros.append(f"Sem permissão para criar pastas: {e}")
        return
    rostos_conhecidos = carregar_rostos_conhecidos(pasta_referencia, arquivo_rostos_conhecidos)
    if not rostos_conhecidos:
        logging.info(f"Nenhum rosto conhecido em rostos_conhecidos.json. Verificando {pasta_referencia}")
        try:
            arquivos_referencia = [f for f in os.listdir(pasta_referencia) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            if not arquivos_referencia:
                logging.warning(f"Nenhuma imagem em {pasta_referencia}")
            for arquivo_ref in arquivos_referencia:
                caminho_ref = os.path.join(pasta_referencia, arquivo_ref)
                caminho_ref = normalize_path(caminho_ref)
                if not validar_arquivo(caminho_ref):
                    continue
                nome_arquivo = os.path.basename(caminho_ref)
                caminho_temp = PASTA_TEMP / f"ref_{nome_arquivo}"
                if pre_processar_imagem(caminho_ref, caminho_temp):
                    try:
                        imagem_ref = face_recognition.load_image_file(str(caminho_temp))
                        codificacao = face_recognition.face_encodings(imagem_ref, model=modelo_reconhecimento)
                        if codificacao:
                            nome_base = os.path.splitext(arquivo_ref)[0].split('_')[0]
                            if nome_base not in rostos_conhecidos:
                                rostos_conhecidos[nome_base] = []
                            rostos_conhecidos[nome_base].append(codificacao[0])
                            logging.info(f"Rosto de {nome_base} adicionado: {arquivo_ref}")
                        else:
                            logging.warning(f"Nenhum rosto detectado em {caminho_ref}")
                    except Exception as e:
                        logging.error(f"Erro ao processar referência {caminho_ref}: {e}")
                        erros.append(f"Erro ao processar referência {caminho_ref}: {e}")
            salvar_rostos_conhecidos(rostos_conhecidos, pasta_referencia, arquivo_rostos_conhecidos)
        except PermissionError as e:
            logging.error(f"Permissão negada para pasta de referência: {e}")
            erros.append(f"Sem permissão para pasta de referência: {e}")
        except Exception as e:
            logging.critical(f"Erro ao verificar pasta de referência: {e}", exc_info=True)
            erros.append(f"Erro ao verificar pasta de referência: {e}")
    if not rostos_conhecidos:
        logging.warning("Nenhum rosto conhecido válido encontrado")
    arquivos_imagem = listar_fotos_em_subpastas(pasta_entrada)
    if not arquivos_imagem:
        logging.warning("Nenhuma imagem válida na pasta de entrada")
        erros.append("Nenhuma imagem válida encontrada na pasta de entrada")
        try:
            shutil.rmtree(PASTA_TEMP)
            logging.info("Pasta temporária removida")
        except Exception as e:
            logging.error(f"Erro ao remover pasta temporária: {e}")
            erros.append(f"Erro ao remover pasta temporária: {e}")
        gerar_relatorio(pasta_saida, erros)
        return
    arquivos_pre_processados = pre_processar_imagens_em_lote(arquivos_imagem)
    if not arquivos_pre_processados:
        logging.warning("Nenhuma imagem válida após pré-processamento")
        erros.append("Nenhuma imagem válida após pré-processamento")
        try:
            shutil.rmtree(PASTA_TEMP)
            logging.info("Pasta temporária removida")
        except Exception as e:
            logging.error(f"Erro ao remover pasta temporária: {e}")
            erros.append(f"Erro ao remover pasta temporária: {e}")
        gerar_relatorio(pasta_saida, erros)
        return
    total_fotos = len(arquivos_pre_processados)
    num_nucleos = cpu_count()
    num_processos = max(1, math.floor(num_nucleos * 0.75) if num_nucleos > 2 else num_nucleos // 2)
    logging.info(f"Usando {num_processos}/{num_nucleos} núcleos para {total_fotos} fotos")
    args = [
        (caminho, rostos_conhecidos, pasta_saida, i + 1, total_fotos, arquivos_imagem[i])
        for i, caminho in enumerate(arquivos_pre_processados)
    ]
    try:
        with Pool(processes=num_processos) as pool:
            pool.map(processar_imagem, args)
    except Exception as e:
        logging.critical(f"Erro no processamento paralelo: {e}", exc_info=True)
        erros.append(f"Erro no processamento paralelo: {e}")
    try:
        shutil.rmtree(PASTA_TEMP)
        logging.info("Pasta temporária removida com sucesso")
    except Exception as e:
        logging.error(f"Erro ao remover pasta temporária {PASTA_TEMP}: {e}")
        erros.append(f"Erro ao remover pasta temporária: {e}")
    if cancelado:
        logging.info("Processamento cancelado pelo usuário")
        erros.append("Processamento cancelado pelo usuário")
    else:
        logging.info(f"Separação concluída: {pasta_saida}")
    gerar_relatorio(pasta_saida, erros)