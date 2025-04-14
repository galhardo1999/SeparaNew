import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from separador_fotos import SeparadorFotos
import threading
import queue
import os
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class InterfaceSeparadorFotos:
    def __init__(self, janela: tk.Tk):
        """Inicializa a interface gráfica do separador de fotos."""
        self.janela = janela
        self.janela.title("Separador de Fotos")
        self.janela.geometry("600x400")
        self.janela.minsize(400, 300)  # Tamanho mínimo para responsividade
        self.separador = SeparadorFotos()
        self.fila_logs = self.separador.obter_fila_logs()
        self.fila_progresso = self.separador.obter_fila_progresso()
        self.contador_processadas = self.separador.obter_contador_processadas()

        # Configurar pesos para responsividade
        self.janela.grid_columnconfigure(1, weight=1)  # Coluna das entradas expande
        self.janela.grid_columnconfigure(0, weight=0)  # Coluna dos labels fixa
        self.janela.grid_columnconfigure(2, weight=0)  # Coluna dos botões "Selecionar" fixa
        self.janela.grid_rowconfigure(3, weight=1)     # Linha dos logs expande verticalmente
        self.janela.grid_rowconfigure(4, weight=0)     # Barra de progresso não expande
        self.janela.grid_rowconfigure(5, weight=0)     # Botões não expandem
        self.janela.grid_rowconfigure(6, weight=0)     # Status não expande

        # Variáveis da interface
        self.pasta_referencia = tk.StringVar(value="")
        self.pasta_entrada = tk.StringVar(value="")
        self.pasta_saida = tk.StringVar(value="")
        self.progresso = tk.DoubleVar(value=0)
        self.total_imagens = 0
        self.ultima_foto_logada = 0  # Rastrear última foto exibida no log

        # Configuração da interface
        tk.Label(janela, text="Pasta de Referência:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        tk.Entry(janela, textvariable=self.pasta_referencia).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        tk.Button(janela, text="Selecionar", command=self.selecionar_pasta_referencia).grid(row=0, column=2, padx=5, pady=5)

        tk.Label(janela, text="Pasta de Entrada:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        tk.Entry(janela, textvariable=self.pasta_entrada).grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        tk.Button(janela, text="Selecionar", command=self.selecionar_pasta_entrada).grid(row=1, column=2, padx=5, pady=5)

        tk.Label(janela, text="Pasta de Saída:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        tk.Entry(janela, textvariable=self.pasta_saida).grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        tk.Button(janela, text="Selecionar", command=self.selecionar_pasta_saida).grid(row=2, column=2, padx=5, pady=5)

        self.texto_logs = tk.Text(janela, height=10, state=tk.DISABLED)
        self.texto_logs.grid(row=3, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")

        self.barra_progresso = ttk.Progressbar(janela, variable=self.progresso, maximum=100)
        self.barra_progresso.grid(row=4, column=0, columnspan=3, padx=5, pady=5, sticky="ew")

        # Frame para botões, permitindo alinhamento centralizado
        frame_botoes = tk.Frame(janela)
        frame_botoes.grid(row=5, column=0, columnspan=3, pady=5)
        frame_botoes.grid_columnconfigure(0, weight=1)
        frame_botoes.grid_columnconfigure(1, weight=1)
        frame_botoes.grid_columnconfigure(2, weight=1)

        self.botao_iniciar = tk.Button(frame_botoes, text="Iniciar", command=self.iniciar_separacao)
        self.botao_iniciar.grid(row=0, column=0, padx=5)

        self.botao_pausar = tk.Button(frame_botoes, text="Pausar", command=self.pausar_separacao, state=tk.DISABLED)
        self.botao_pausar.grid(row=0, column=1, padx=5)

        self.botao_cancelar = tk.Button(frame_botoes, text="Cancelar", command=self.cancelar_separacao, state=tk.DISABLED)
        self.botao_cancelar.grid(row=0, column=2, padx=5)

        self.label_status = tk.Label(janela, text="Pronto")
        self.label_status.grid(row=6, column=0, columnspan=3, pady=5, sticky="ew")

        # Carregar configurações salvas
        self.carregar_configuracoes()
        self.janela.protocol("WM_DELETE_WINDOW", self.ao_fechar)

        # Iniciar atualizações periódicas
        self.atualizar_logs()
        self.atualizar_progresso()

    def selecionar_pasta_referencia(self) -> None:
        """Abre um diálogo para selecionar a pasta de referência."""
        pasta = filedialog.askdirectory()
        if pasta:
            self.pasta_referencia.set(pasta)
            self.salvar_configuracoes()

    def selecionar_pasta_entrada(self) -> None:
        """Abre um diálogo para selecionar a pasta de entrada."""
        pasta = filedialog.askdirectory()
        if pasta:
            self.pasta_entrada.set(pasta)
            self.salvar_configuracoes()

    def selecionar_pasta_saida(self) -> None:
        """Abre um diálogo para selecionar a pasta de saída."""
        pasta = filedialog.askdirectory()
        if pasta:
            self.pasta_saida.set(pasta)
            self.salvar_configuracoes()

    def carregar_configuracoes(self) -> None:
        """Carrega configurações salvas do arquivo configuracoes.json."""
        try:
            if Path("configuracoes.json").exists():
                with Path("configuracoes.json").open("r", encoding="utf-8") as f:
                    configuracoes = json.load(f)
                self.pasta_referencia.set(configuracoes.get("pasta_referencia", ""))
                self.pasta_entrada.set(configuracoes.get("pasta_entrada", ""))
                self.pasta_saida.set(configuracoes.get("pasta_saida", ""))
        except Exception as e:
            logger.error(f"Erro ao carregar configurações: {e}")

    def salvar_configuracoes(self) -> None:
        """Salva as configurações atuais no arquivo configuracoes.json."""
        try:
            configuracoes = {
                "pasta_referencia": self.pasta_referencia.get(),
                "pasta_entrada": self.pasta_entrada.get(),
                "pasta_saida": self.pasta_saida.get()
            }
            with Path("configuracoes.json").open("w", encoding="utf-8") as f:
                json.dump(configuracoes, f, indent=2)
        except Exception as e:
            logger.error(f"Erro ao salvar configurações: {e}")

    def iniciar_separacao(self) -> None:
        """Inicia o processo de separação de fotos após validar as pastas."""
        for pasta, nome in [
            (self.pasta_referencia.get(), "referência"),
            (self.pasta_entrada.get(), "entrada"),
            (self.pasta_saida.get(), "saída")
        ]:
            if not pasta:
                messagebox.showerror("Erro", f"Selecione a pasta de {nome}.")
                return
            if not os.path.exists(pasta):
                messagebox.showerror("Erro", f"A pasta de {nome} não existe.")
                return
            if not os.access(pasta, os.R_OK):
                messagebox.showerror("Erro", f"Sem permissão de leitura na pasta de {nome}.")
                return
            if nome == "saída" and not os.access(pasta, os.W_OK):
                messagebox.showerror("Erro", f"Sem permissão de escrita na pasta de saída.")
                return

        self.botao_iniciar.config(state=tk.DISABLED)
        self.botao_pausar.config(state=tk.NORMAL)
        self.botao_cancelar.config(state=tk.NORMAL)
        self.progresso.set(0)
        self.ultima_foto_logada = 0  # Resetar log
        self.label_status.config(text="Processando...")
        from utilitarios_arquivos import listar_imagens
        self.total_imagens = len(listar_imagens(Path(self.pasta_entrada.get())))

        self.thread = threading.Thread(
            target=self.executar_separacao,
            args=(
                self.pasta_referencia.get(),
                self.pasta_entrada.get(),
                self.pasta_saida.get(),
            ),
        )
        self.thread.daemon = True
        self.thread.start()

    def executar_separacao(self, pasta_referencia: str, pasta_entrada: str, pasta_saida: str) -> None:
        """Executa a separação de fotos em uma thread separada."""
        try:
            self.separador.separar_fotos(pasta_referencia, pasta_entrada, pasta_saida)
        except (PermissionError, OSError) as e:
            self.fila_logs.put(f"Erro: Sem permissão para acessar uma das pastas: {e}")
            self.janela.after(0, lambda: messagebox.showerror("Erro", str(e)))
        except Exception as e:
            self.fila_logs.put(f"Erro inesperado: {e}")
            self.janela.after(0, lambda: messagebox.showerror("Erro", "Erro inesperado durante a separação."))
            logger.error(f"Erro na separação: {e}", exc_info=True)
        finally:
            self.janela.after(0, self.finalizar_separacao)

    def pausar_separacao(self) -> None:
        """Pausa ou retoma o processo de separação."""
        if self.botao_pausar["text"] == "Pausar":
            self.separador.pausar_processamento()
            self.botao_pausar.config(text="Retomar")
            self.label_status.config(text="Pausado")
        else:
            self.separador.retomar_processamento()
            self.botao_pausar.config(text="Pausar")
            self.label_status.config(text="Processando...")

    def cancelar_separacao(self) -> None:
        """Cancela o processo de separação."""
        self.separador.cancelar_processamento()
        self.label_status.config(text="Cancelado")
        self.finalizar_separacao()

    def finalizar_separacao(self) -> None:
        """Finaliza o processo de separação, redefinindo a interface."""
        self.botao_iniciar.config(state=tk.NORMAL)
        self.botao_pausar.config(state=tk.DISABLED, text="Pausar")
        self.botao_cancelar.config(state=tk.DISABLED)
        self.progresso.set(0)
        self.label_status.config(text="Concluído")
        self.salvar_configuracoes()

    def atualizar_logs(self) -> None:
        """Atualiza a área de logs com mensagens da fila."""
        try:
            while True:
                mensagem = self.fila_logs.get_nowait()
                # Trata objetos LogRecord do QueueHandler
                if isinstance(mensagem, logging.LogRecord):
                    texto = mensagem.getMessage()
                else:
                    texto = str(mensagem)
                self.texto_logs.config(state=tk.NORMAL)
                self.texto_logs.insert(tk.END, texto + "\n")
                self.texto_logs.see(tk.END)
                # Limitar o número de linhas para evitar sobrecarga
                linhas = int(self.texto_logs.index('end-1c').split('.')[0])
                if linhas > 1000:
                    self.texto_logs.delete(1.0, f"{linhas-1000}.0")
                self.texto_logs.config(state=tk.DISABLED)
                self.janela.update_idletasks()
        except queue.Empty:
            pass
        self.janela.after(100, self.atualizar_logs)

    def atualizar_progresso(self) -> None:
        """Atualiza a barra de progresso e os logs de fotos processadas."""
        try:
            while True:
                self.fila_progresso.get_nowait()
                if self.total_imagens > 0:
                    self.progresso.set((self.progresso.get() + (1 / self.total_imagens) * 100))
        except queue.Empty:
            pass
        # Atualizar logs com base no contador_processadas
        with self.contador_processadas.get_lock():  # Sincronizar acesso
            fotos_processadas = self.contador_processadas.value
        while self.ultima_foto_logada < fotos_processadas and self.total_imagens > 0:
            self.ultima_foto_logada += 1
            self.texto_logs.config(state=tk.NORMAL)
            self.texto_logs.insert(tk.END, f"Fotos processadas: {self.ultima_foto_logada}/{self.total_imagens} fotos\n")
            self.texto_logs.see(tk.END)
            # Limitar o número de linhas
            linhas = int(self.texto_logs.index('end-1c').split('.')[0])
            if linhas > 1000:
                self.texto_logs.delete(1.0, f"{linhas-1000}.0")
            self.texto_logs.config(state=tk.DISABLED)
            self.janela.update_idletasks()
        self.janela.after(100, self.atualizar_progresso)

    def ao_fechar(self) -> None:
        """Executa ações ao fechar a janela."""
        self.separador.cancelar_processamento()
        self.salvar_configuracoes()
        self.janela.destroy()

if __name__ == "__main__":
    janela = tk.Tk()
    aplicativo = InterfaceSeparadorFotos(janela)
    janela.mainloop()