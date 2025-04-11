import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from separador import Separador
import threading
import queue
import os
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class InterfaceSeparador:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Separador de Fotos")
        self.root.geometry("600x400")
        self.separador = Separador()
        self.log_queue = self.separador.get_log_queue()
        self.progresso_queue = self.separador.get_progresso_queue()

        # Variáveis
        self.pasta_referencia = tk.StringVar(value="")
        self.pasta_entrada = tk.StringVar(value="")
        self.pasta_saida = tk.StringVar(value="")
        self.progresso = tk.DoubleVar(value=0)
        self.total_imagens = 0

        # Interface
        tk.Label(root, text="Pasta de Referência:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        tk.Entry(root, textvariable=self.pasta_referencia, width=50).grid(row=0, column=1, padx=5, pady=5)
        tk.Button(root, text="Selecionar", command=self.selecionar_pasta_referencia).grid(row=0, column=2, padx=5, pady=5)

        tk.Label(root, text="Pasta de Entrada:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        tk.Entry(root, textvariable=self.pasta_entrada, width=50).grid(row=1, column=1, padx=5, pady=5)
        tk.Button(root, text="Selecionar", command=self.selecionar_pasta_entrada).grid(row=1, column=2, padx=5, pady=5)

        tk.Label(root, text="Pasta de Saída:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        tk.Entry(root, textvariable=self.pasta_saida, width=50).grid(row=2, column=1, padx=5, pady=5)
        tk.Button(root, text="Selecionar", command=self.selecionar_pasta_saida).grid(row=2, column=2, padx=5, pady=5)

        self.botao_iniciar = tk.Button(root, text="Iniciar", command=self.iniciar_separacao)
        self.botao_iniciar.grid(row=3, column=0, columnspan=3, pady=10)

        self.botao_pausar = tk.Button(root, text="Pausar", command=self.pausar_separacao, state=tk.DISABLED)
        self.botao_pausar.grid(row=4, column=0, columnspan=3, pady=5)

        self.botao_cancelar = tk.Button(root, text="Cancelar", command=self.cancelar_separacao, state=tk.DISABLED)
        self.botao_cancelar.grid(row=5, column=0, columnspan=3, pady=5)

        self.log_texto = tk.Text(root, height=10, width=70, state=tk.DISABLED)
        self.log_texto.grid(row=6, column=0, columnspan=3, padx=5, pady=5)

        self.barra_progresso = ttk.Progressbar(root, variable=self.progresso, maximum=100)
        self.barra_progresso.grid(row=7, column=0, columnspan=3, padx=5, pady=5)

        self.status_label = tk.Label(root, text="Pronto")
        self.status_label.grid(row=8, column=0, columnspan=3, pady=5)

        # Carregar configurações
        self.load_settings()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Iniciar verificações
        self.atualizar_logs()
        self.atualizar_progresso()

    def selecionar_pasta_referencia(self) -> None:
        pasta = filedialog.askdirectory()
        if pasta:
            self.pasta_referencia.set(pasta)
            self.save_settings()

    def selecionar_pasta_entrada(self) -> None:
        pasta = filedialog.askdirectory()
        if pasta:
            self.pasta_entrada.set(pasta)
            self.save_settings()

    def selecionar_pasta_saida(self) -> None:
        pasta = filedialog.askdirectory()
        if pasta:
            self.pasta_saida.set(pasta)
            self.save_settings()

    def load_settings(self) -> None:
        """Carrega configurações salvas."""
        try:
            if Path("settings.json").exists():
                with Path("settings.json").open("r", encoding="utf-8") as f:
                    settings = json.load(f)
                self.pasta_referencia.set(settings.get("pasta_referencia", ""))
                self.pasta_entrada.set(settings.get("pasta_entrada", ""))
                self.pasta_saida.set(settings.get("pasta_saida", ""))
        except Exception as e:
            logger.error(f"Erro ao carregar configurações: {e}")

    def save_settings(self) -> None:
        """Salva configurações atuais."""
        try:
            settings = {
                "pasta_referencia": self.pasta_referencia.get(),
                "pasta_entrada": self.pasta_entrada.get(),
                "pasta_saida": self.pasta_saida.get()
            }
            with Path("settings.json").open("w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            logger.error(f"Erro ao salvar configurações: {e}")

    def iniciar_separacao(self) -> None:
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
        self.status_label.config(text="Processando...")
        from file_utils import list_images
        self.total_imagens = len(list_images(Path(self.pasta_entrada.get())))

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
        try:
            self.separador.separar_fotos(pasta_referencia, pasta_entrada, pasta_saida)
        except (PermissionError, OSError) as e:
            self.log_queue.put(f"Erro: Sem permissão para acessar uma das pastas: {e}")
            self.root.after(0, lambda: messagebox.showerror("Erro", str(e)))
        except Exception as e:
            self.log_queue.put("Erro inesperado. Contate o suporte.")
            self.root.after(0, lambda: messagebox.showerror("Erro", "Erro inesperado durante a separação."))
            logger.error(f"Erro na separação: {e}", exc_info=True)
        finally:
            self.root.after(0, self.finalizar_separacao)

    def pausar_separacao(self) -> None:
        if self.botao_pausar["text"] == "Pausar":
            self.separador.pausar_processamento()
            self.botao_pausar.config(text="Retomar")
            self.status_label.config(text="Pausado")
        else:
            self.separador.retomar_processamento()
            self.botao_pausar.config(text="Pausar")
            self.status_label.config(text="Processando...")

    def cancelar_separacao(self) -> None:
        self.separador.cancelar_processamento()
        self.status_label.config(text="Cancelado")
        self.finalizar_separacao()

    def finalizar_separacao(self) -> None:
        self.botao_iniciar.config(state=tk.NORMAL)
        self.botao_pausar.config(state=tk.DISABLED, text="Pausar")
        self.botao_cancelar.config(state=tk.DISABLED)
        self.progresso.set(0)
        self.status_label.config(text="Concluído")
        self.save_settings()

    def atualizar_logs(self) -> None:
        try:
            while True:
                mensagem = self.log_queue.get_nowait()
                self.log_texto.config(state=tk.NORMAL)
                self.log_texto.insert(tk.END, mensagem + "\n")
                self.log_texto.see(tk.END)
                self.log_texto.config(state=tk.DISABLED)
        except queue.Empty:
            pass
        self.root.update()
        self.root.after(100, self.atualizar_logs)

    def atualizar_progresso(self) -> None:
        try:
            while True:
                self.progresso_queue.get_nowait()
                if self.total_imagens > 0:
                    self.progresso.set((self.progresso.get() + (1 / self.total_imagens) * 100))
        except queue.Empty:
            pass
        self.root.after(100, self.atualizar_progresso)

    def on_closing(self) -> None:
        self.separador.cancelar_processamento()
        self.save_settings()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = InterfaceSeparador(root)
    root.mainloop()