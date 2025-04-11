import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from separador import separar_fotos, pausar_processamento, retomar_processamento, cancelar_processamento, listar_fotos_em_subpastas, get_log_queue
import threading
import queue
import os
import logging

class InterfaceSeparador:
    def __init__(self, root):
        self.root = root
        self.root.title("Separador de Fotos")
        self.root.geometry("600x400")

        # Inicializar variáveis
        self.pasta_referencia = tk.StringVar(value="")
        self.pasta_entrada = tk.StringVar(value="")
        self.pasta_saida = tk.StringVar(value="")
        self.log_queue = get_log_queue()  # Usar a mesma fila do separador
        self.total_imagens = 0
        self.progresso = tk.DoubleVar(value=0)

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

        # Iniciar verificação de logs
        self.atualizar_logs()

    def selecionar_pasta_referencia(self):
        pasta = filedialog.askdirectory()
        if pasta:
            self.pasta_referencia.set(pasta)

    def selecionar_pasta_entrada(self):
        pasta = filedialog.askdirectory()
        if pasta:
            self.pasta_entrada.set(pasta)

    def selecionar_pasta_saida(self):
        pasta = filedialog.askdirectory()
        if pasta:
            self.pasta_saida.set(pasta)

    def iniciar_separacao(self):
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
        self.total_imagens = len(listar_fotos_em_subpastas(self.pasta_entrada.get()))

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

    def executar_separacao(self, pasta_referencia, pasta_entrada, pasta_saida):
        try:
            separar_fotos(pasta_referencia, pasta_entrada, pasta_saida)
        except PermissionError:
            self.log_queue.put("Erro: Sem permissão para acessar uma das pastas selecionadas.")
            logging.error("Permissão negada durante separação", exc_info=True)
        except FileNotFoundError:
            self.log_queue.put("Erro: Uma das pastas selecionadas não existe.")
            logging.error("Pasta não encontrada durante separação", exc_info=True)
        except Exception as e:
            self.log_queue.put("Erro inesperado durante a separação. Contate o suporte.")
            logging.critical(f"Erro inesperado na separação: {e}", exc_info=True)
        finally:
            self.root.after(0, self.finalizar_separacao)

    def pausar_separacao(self):
        if self.botao_pausar["text"] == "Pausar":
            pausar_processamento()
            self.botao_pausar.config(text="Retomar")
            self.log_queue.put("Processamento pausado.")
        else:
            retomar_processamento()
            self.botao_pausar.config(text="Pausar")
            self.log_queue.put("Processamento retomado.")

    def cancelar_separacao(self):
        cancelar_processamento()
        self.log_queue.put("Cancelando processamento...")
        self.finalizar_separacao()

    def finalizar_separacao(self):
        self.botao_iniciar.config(state=tk.NORMAL)
        self.botao_pausar.config(state=tk.DISABLED, text="Pausar")
        self.botao_cancelar.config(state=tk.DISABLED)
        self.progresso.set(0)

    def atualizar_logs(self):
        try:
            while True:
                mensagem = self.log_queue.get_nowait()
                self.log_texto.config(state=tk.NORMAL)
                self.log_texto.insert(tk.END, mensagem + "\n")
                self.log_texto.see(tk.END)
                self.log_texto.config(state=tk.DISABLED)
                # Atualizar progresso
                if "Imagem pré-processada" in mensagem and self.total_imagens > 0:
                    try:
                        indice = int(mensagem.split("[")[1].split("/")[0])
                        self.progresso.set((indice / self.total_imagens) * 100)
                    except (IndexError, ValueError):
                        pass  # Ignorar mensagens malformadas
        except queue.Empty:
            pass
        self.root.after(100, self.atualizar_logs)

if __name__ == "__main__":
    root = tk.Tk()
    app = InterfaceSeparador(root)
    root.mainloop()