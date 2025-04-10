import cv2
import face_recognition
import os
import shutil
from pathlib import Path
import json
from datetime import datetime
from multiprocessing import Pool, cpu_count, Queue
import math
import numpy as np
import threading

# Variável global para controle de pausa e cancelamento
pausado = False
cancelado = False

# Função para atualizar o estado de pausa
def pausar_processamento():
    global pausado
    pausado = True

# Função para retomar o processamento
def retomar_processamento():
    global pausado
    pausado = False

# Função para cancelar o processamento
def cancelar_processamento():
    global cancelado
    cancelado = True

# Configurações iniciais
tolerance = 0.4
modelo_reconhecimento = "cnn"

# Função para carregar rostos conhecidos (suporte a múltiplas imagens por pessoa)
def carregar_rostos_conhecidos(pasta_referencia, arquivo_rostos_conhecidos, queue):
    if os.path.exists(arquivo_rostos_conhecidos):
        try:
            with open(arquivo_rostos_conhecidos, 'r') as f:
                dados = json.load(f)
                rostos = {}
                for nome, info in dados.items():
                    codificacoes = []
                    for caminho in info['imagens']:
                        imagem = face_recognition.load_image_file(caminho)
                        codificacao = face_recognition.face_encodings(imagem, model=modelo_reconhecimento)
                        if codificacao:
                            codificacoes.append(codificacao[0])
                    if codificacoes:
                        rostos[nome] = codificacoes
                queue.put("Rostos conhecidos carregados com sucesso.")
                return rostos
        except Exception as e:
            queue.put(f"Erro ao carregar rostos conhecidos: {e}")
            return {}
    return {}

# Função para salvar rostos conhecidos
def salvar_rostos_conhecidos(rostos_conhecidos, pasta_referencia, arquivo_rostos_conhecidos, queue):
    dados = {}
    for nome, codificacoes in rostos_conhecidos.items():
        imagens = [f"{pasta_referencia}/{nome}_{i}.jpg" for i in range(len(codificacoes))]
        dados[nome] = {"imagens": imagens}
    try:
        with open(arquivo_rostos_conhecidos, 'w') as f:
            json.dump(dados, f)
        queue.put("Rostos conhecidos salvos com sucesso.")
    except Exception as e:
        queue.put(f"Erro ao salvar rostos conhecidos: {e}")

# Função para validar imagem
def validar_imagem(caminho, queue):
    try:
        imagem = face_recognition.load_image_file(caminho)
        return True
    except Exception as e:
        queue.put(f"Imagem inválida ou corrompida: {caminho} - Erro: {e}")
        return False

# Função para processar uma única imagem
def processar_imagem(args):
    global pausado, cancelado
    caminho_imagem, rostos_conhecidos, pasta_saida, indice, total, queue = args
    if cancelado:
        return

    # Pausar se necessário
    while pausado:
        if cancelado:
            return
        threading.Event().wait(0.1)

    if not validar_imagem(caminho_imagem, queue):
        return
    
    imagem = face_recognition.load_image_file(caminho_imagem)
    codificacoes_rosto = face_recognition.face_encodings(imagem, model=modelo_reconhecimento)

    if len(codificacoes_rosto) == 0:
        queue.put(f"[{indice}/{total}] Nenhum rosto em {os.path.basename(caminho_imagem)}")
        return

    correspondencias_encontradas = False
    pessoas_identificadas = []

    # Verificar cada rosto na imagem
    for codificacao_rosto in codificacoes_rosto:
        for nome, codificacoes_conhecidas in rostos_conhecidos.items():
            resultados = face_recognition.compare_faces(codificacoes_conhecidas, codificacao_rosto, tolerance=tolerance)
            if any(resultados):
                if nome not in pessoas_identificadas:
                    pessoas_identificadas.append(nome)
                correspondencias_encontradas = True

    # Copiar a foto para as pastas de todas as pessoas identificadas
    if correspondencias_encontradas:
        for nome in pessoas_identificadas:
            pasta_pessoa = os.path.join(pasta_saida, nome)
            Path(pasta_pessoa).mkdir(parents=True, exist_ok=True)
            shutil.copy(caminho_imagem, pasta_pessoa)
            queue.put(f"[{indice}/{total}] {os.path.basename(caminho_imagem)} copiada para {nome}")
    else:
        pasta_desconhecidos = os.path.join(pasta_saida, "desconhecidos")
        Path(pasta_desconhecidos).mkdir(parents=True, exist_ok=True)
        shutil.copy(caminho_imagem, pasta_desconhecidos)
        queue.put(f"[{indice}/{total}] {os.path.basename(caminho_imagem)} copiada para 'desconhecidos'")

# Função para gerar relatório
def gerar_relatorio(pasta_saida, queue):
    relatorio = {}
    for pasta in os.listdir(pasta_saida):
        caminho_pasta = os.path.join(pasta_saida, pasta)
        if os.path.isdir(caminho_pasta):
            qtd_fotos = len([f for f in os.listdir(caminho_pasta) if f.endswith(('.jpg', '.jpeg', '.png'))])
            relatorio[pasta] = qtd_fotos
    with open("relatorio.txt", "w", encoding='utf-8') as f:
        for pessoa, qtd in relatorio.items():
            f.write(f"{pessoa}: {qtd} fotos\n")
    queue.put("Relatório gerado em 'relatorio.txt'.")

# Função para listar todas as fotos em subpastas
def listar_fotos_em_subpastas(pasta_entrada, queue):
    arquivos_imagem = []
    for raiz, _, arquivos in os.walk(pasta_entrada):
        for arquivo in arquivos:
            if arquivo.endswith(('.jpg', '.jpeg', '.png')):
                arquivos_imagem.append(os.path.join(raiz, arquivo))
    queue.put(f"Encontradas {len(arquivos_imagem)} fotos para processar.")
    return arquivos_imagem

# Função principal de separação
def separar_fotos(pasta_referencia, pasta_entrada, pasta_saida, queue):
    global pausado, cancelado
    pausado = False
    cancelado = False
    arquivo_rostos_conhecidos = "rostos_conhecidos.json"

    # Criar pastas se não existirem
    Path(pasta_saida).mkdir(parents=True, exist_ok=True)
    Path(pasta_referencia).mkdir(parents=True, exist_ok=True)

    # Carregar rostos conhecidos
    rostos_conhecidos = carregar_rostos_conhecidos(pasta_referencia, arquivo_rostos_conhecidos, queue)
    if not rostos_conhecidos:
        queue.put(f"Nenhum rosto conhecido encontrado. Adicione fotos de referência em '{pasta_referencia}'.")
        arquivos_referencia = [f for f in os.listdir(pasta_referencia) if f.endswith(('.jpg', '.jpeg', '.png'))]
        for arquivo_ref in arquivos_referencia:
            caminho_ref = os.path.join(pasta_referencia, arquivo_ref)
            if validar_imagem(caminho_ref, queue):
                imagem_ref = face_recognition.load_image_file(caminho_ref)
                codificacao = face_recognition.face_encodings(imagem_ref, model=modelo_reconhecimento)
                if codificacao:
                    nome_base = os.path.splitext(arquivo_ref)[0].split('_')[0]
                    if nome_base not in rostos_conhecidos:
                        rostos_conhecidos[nome_base] = []
                    rostos_conhecidos[nome_base].append(codificacao[0])
                    queue.put(f"Rosto de {nome_base} adicionado ao banco (imagem: {arquivo_ref}).")
        salvar_rostos_conhecidos(rostos_conhecidos, pasta_referencia, arquivo_rostos_conhecidos, queue)

    # Listar fotos e preparar para multiprocessing
    arquivos_imagem = listar_fotos_em_subpastas(pasta_entrada, queue)
    total_fotos = len(arquivos_imagem)

    # Identificar número de núcleos e calcular processos
    num_nucleos = cpu_count()
    if num_nucleos <= 2:
        num_processos = max(1, math.floor(num_nucleos * 0.5))
    else:
        num_processos = max(1, math.floor(num_nucleos * 0.75))

    queue.put(f"Detectados {num_nucleos} núcleos. Usando {num_processos} processos para processar {total_fotos} fotos...")

    # Preparar argumentos para o multiprocessing
    args = [(caminho, rostos_conhecidos, pasta_saida, i+1, total_fotos, queue) for i, caminho in enumerate(arquivos_imagem)]

    # Usar Pool para processar em paralelo
    with Pool(processes=num_processos) as pool:
        pool.map(processar_imagem, args)

    if cancelado:
        queue.put("Processamento cancelado pelo usuário.")
    else:
        # Gerar relatório
        gerar_relatorio(pasta_saida, queue)
        queue.put(f"Separação concluída! As fotos foram copiadas para {pasta_saida}.")