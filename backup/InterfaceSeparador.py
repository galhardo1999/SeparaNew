import tkinter as tk
from tkinter import filedialog, ttk
import threading
from separador import separar_fotos, pausar_processamento, retomar_processamento, cancelar_processamento

class InterfaceSeparador:
    def __init__(self, root):
        self.root = root
        self.root.title("Separador de Fotos")
        self.root.geometry("600x500")
        self.root.minsize(500, 400)  # Tamanho mínimo da janela

        # Permitir que a janela seja redimensionável
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Frame principal para conter todos os widgets
        self.frame_principal = ttk.Frame(self.root, padding=10)
        self.frame_principal.grid(row=0, column=0, sticky="nsew")

        # Configurar o frame principal para ser responsivo
        self.frame_principal.columnconfigure(0, weight=1)
        self.frame_principal.rowconfigure(2, weight=1)  # A linha do log deve expandir mais

        # Variáveis para os caminhos
        self.pasta_referencia = tk.StringVar()
        self.pasta_entrada = tk.StringVar()
        self.pasta_saida = tk.StringVar()

        # Frame para seleção de pastas
        frame_pastas = ttk.LabelFrame(self.frame_principal, text="Seleção de Pastas", padding=10)
        frame_pastas.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Configurar o frame de pastas para ser responsivo
        frame_pastas.columnconfigure(1, weight=1)

        # Pasta de referência
        ttk.Label(frame_pastas, text="Pasta de Referência:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frame_pastas, textvariable=self.pasta_referencia).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(frame_pastas, text="Selecionar", command=self.selecionar_pasta_referencia).grid(row=0, column=2, padx=5, pady=5)

        # Pasta de entrada
        ttk.Label(frame_pastas, text="Pasta de Entrada:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frame_pastas, textvariable=self.pasta_entrada).grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(frame_pastas, text="Selecionar", command=self.selecionar_pasta_entrada).grid(row=1, column=2, padx=5, pady=5)

        # Pasta de saída
        ttk.Label(frame_pastas, text="Pasta de Saída:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frame_pastas, textvariable=self.pasta_saida).grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(frame_pastas, text="Selecionar", command=self.selecionar_pasta_saida).grid(row=2, column=2, padx=5, pady=5)

        # Frame para botões de controle
        frame_botoes = ttk.Frame(self.frame_principal)
        frame_botoes.grid(row=1, column=0, sticky="ew", padx=5, pady=5)

        

        # Frame para o log
        frame_log = ttk.LabelFrame(self.frame_principal, text="Log", padding=10)
        frame_log.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)

        # Configurar o frame de log para ser responsivo
        frame_log.columnconfigure(0, weight=1)
        frame_log.rowconfigure(0, weight=1)

        self.texto_log = tk.Text(frame_log, height=10, state="disabled")
        self.texto_log.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(frame_log, orient="vertical", command=self.texto_log.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.texto_log.config(yscrollcommand=scrollbar.set)

        # Variável para controle do thread
        self.thread_processamento = None

        # Configurar o frame de botões para ser responsivo
        frame_botoes.columnconfigure(0, weight=1)
        frame_botoes.columnconfigure(1, weight=1)
        frame_botoes.columnconfigure(2, weight=1)

        self.botao_iniciar = ttk.Button(frame_botoes, text="Iniciar", command=self.iniciar_processamento)
        self.botao_iniciar.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        self.botao_pausar = ttk.Button(frame_botoes, text="Pausar", command=self.pausar_processamento, state="disabled")
        self.botao_pausar.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.botao_cancelar = ttk.Button(frame_botoes, text="Cancelar", command=self.cancelar_processamento, state="disabled")
        self.botao_cancelar.grid(row=0, column=2, padx=5, pady=5, sticky="ew")

    def selecionar_pasta_referencia(self):
        pasta = filedialog.askdirectory(title="Selecionar Pasta de Referência")
        if pasta:
            self.pasta_referencia.set(pasta)

    def selecionar_pasta_entrada(self):
        pasta = filedialog.askdirectory(title="Selecionar Pasta de Entrada")
        if pasta:
            self.pasta_entrada.set(pasta)

    def selecionar_pasta_saida(self):
        pasta = filedialog.askdirectory(title="Selecionar Pasta de Saída")
        if pasta:
            self.pasta_saida.set(pasta)

    def enviar_log(self, mensagem):
        self.texto_log.config(state="normal")
        self.texto_log.insert(tk.END, mensagem + "\n")
        self.texto_log.see(tk.END)
        self.texto_log.config(state="disabled")

    def iniciar_processamento(self):
        # Verificar se os caminhos foram preenchidos
        if not self.pasta_referencia.get() or not self.pasta_entrada.get() or not self.pasta_saida.get():
            self.enviar_log("Erro: Selecione todas as pastas antes de iniciar.")
            return

        # Desativar botão de iniciar e ativar os outros
        self.botao_iniciar.config(state="disabled")
        self.botao_pausar.config(state="normal")
        self.botao_cancelar.config(state="normal")

        # Iniciar o processamento em um thread separado
        self.thread_processamento = threading.Thread(target=self.executar_separacao)
        self.thread_processamento.start()

    def executar_separacao(self):
        # Chamar a função de separação
        separar_fotos(
            self.pasta_referencia.get(),
            self.pasta_entrada.get(),
            self.pasta_saida.get(),
            self.enviar_log
        )

        # Reativar botão de iniciar e desativar os outros
        self.root.after(0, lambda: self.botao_iniciar.config(state="normal"))
        self.root.after(0, lambda: self.botao_pausar.config(state="disabled"))
        self.root.after(0, lambda: self.botao_cancelar.config(state="disabled"))

    def pausar_processamento(self):
        if self.botao_pausar["text"] == "Pausar":
            pausar_processamento()
            self.botao_pausar.config(text="Retomar")
            self.enviar_log("Processamento pausado.")
        else:
            retomar_processamento()
            self.botao_pausar.config(text="Pausar")
            self.enviar_log("Processamento retomado.")

    def cancelar_processamento(self):
        cancelar_processamento()
        self.botao_iniciar.config(state="normal")
        self.botao_pausar.config(state="disabled")
        self.botao_cancelar.config(state="disabled")
        self.botao_pausar.config(text="Pausar")
        self.enviar_log("Cancelando processamento...")

if __name__ == '__main__':
    root = tk.Tk()
    app = InterfaceSeparador(root)
    root.mainloop()