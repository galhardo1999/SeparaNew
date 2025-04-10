import tkinter as tk
from tkinter import filedialog, ttk
import threading
from PIL import Image, ImageTk
import os
from separador import separar_fotos, pausar_processamento, retomar_processamento, cancelar_processamento
from multiprocessing import Queue

class InterfaceSeparador:
    def __init__(self, root):
        self.root = root
        self.root.title("Separador de Fotos")
        self.root.geometry("700x550")
        self.root.minsize(550, 450)

        # Permitir que a janela seja redimensionável
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Aplicar um tema moderno
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TLabel", font=("Helvetica", 10), background="#f0f0f0")
        self.style.configure("TButton", font=("Helvetica", 10, "bold"), padding=5, background="#4a90e2", foreground="white")
        self.style.configure("TEntry", font=("Helvetica", 10), padding=5)
        self.style.configure("TLabelframe", background="#f0f0f0")
        self.style.configure("TLabelframe.Label", background="#f0f0f0", font=("Helvetica", 11, "bold"))

        # Frame principal
        self.frame_principal = ttk.Frame(self.root, padding=15, style="Custom.TFrame")
        self.frame_principal.grid(row=0, column=0, sticky="nsew")
        self.style.configure("Custom.TFrame", background="#f0f0f0")

        # Configurar responsividade
        self.frame_principal.columnconfigure(0, weight=1)
        self.frame_principal.rowconfigure(3, weight=1)

        # Variáveis
        self.pasta_referencia = tk.StringVar()
        self.pasta_entrada = tk.StringVar()
        self.pasta_saida = tk.StringVar()
        self.processando = False
        self.progresso = 0
        self.total_fotos = 0
        self.queue = Queue()
        self.running = True

        # Frame para seleção de pastas
        frame_pastas = ttk.LabelFrame(self.frame_principal, text="Seleção de Pastas", padding=10)
        frame_pastas.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
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
        frame_botoes = ttk.Frame(self.frame_principal, style="Custom.TFrame")
        frame_botoes.grid(row=1, column=0, sticky="ew", padx=5, pady=10)
        frame_botoes.columnconfigure(0, weight=1)
        frame_botoes.columnconfigure(1, weight=1)
        frame_botoes.columnconfigure(2, weight=1)

        # Carregar ícones (opcional)
        try:
            self.icon_play = ImageTk.PhotoImage(Image.open("play.png").resize((20, 20)))
            self.icon_pause = ImageTk.PhotoImage(Image.open("pause.png").resize((20, 20)))
            self.icon_stop = ImageTk.PhotoImage(Image.open("stop.png").resize((20, 20)))
        except Exception:
            self.icon_play = None
            self.icon_pause = None
            self.icon_stop = None

        self.botao_iniciar = ttk.Button(frame_botoes, text="Iniciar", image=self.icon_play, compound="left", command=self.iniciar_processamento)
        self.botao_iniciar.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

        self.botao_pausar = ttk.Button(frame_botoes, text="Pausar", image=self.icon_pause, compound="left", command=self.pausar_processamento, state="disabled")
        self.botao_pausar.grid(row=0, column=1, padx=10, pady=5, sticky="ew")

        self.botao_cancelar = ttk.Button(frame_botoes, text="Cancelar", image=self.icon_stop, compound="left", command=self.cancelar_processamento, state="disabled")
        self.botao_cancelar.grid(row=0, column=2, padx=10, pady=5, sticky="ew")

        # Frame para barra de progresso
        frame_progresso = ttk.Frame(self.frame_principal, style="Custom.TFrame")
        frame_progresso.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        frame_progresso.columnconfigure(0, weight=1)

        self.barra_progresso = ttk.Progressbar(frame_progresso, orient="horizontal", mode="determinate")
        self.barra_progresso.grid(row=0, column=0, sticky="ew", padx=5, pady=5)

        # Frame para o log
        frame_log = ttk.LabelFrame(self.frame_principal, text="Log", padding=10)
        frame_log.grid(row=3, column=0, sticky="nsew", padx=5, pady=5)
        frame_log.columnconfigure(0, weight=1)
        frame_log.rowconfigure(0, weight=1)

        self.texto_log = tk.Text(frame_log, height=10, font=("Helvetica", 10), bg="#ffffff", fg="#333333", bd=0, relief="flat")
        self.texto_log.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(frame_log, orient="vertical", command=self.texto_log.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.texto_log.config(yscrollcommand=scrollbar.set, state="disabled")

        # Variável para controle do thread
        self.thread_processamento = None

        # Iniciar thread para ler mensagens da queue
        self.thread_log = threading.Thread(target=self.ler_log_queue, daemon=True)
        self.thread_log.start()

    def ler_log_queue(self):
        while self.running:
            try:
                mensagem = self.queue.get_nowait()
                self.root.after(0, self.enviar_log, mensagem)
            except:
                threading.Event().wait(0.1)

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

        # Atualizar progresso se a mensagem contiver informações de progresso
        if "fotos para processar" in mensagem:
            try:
                self.total_fotos = int(mensagem.split()[1])
                self.progresso = 0
                self.barra_progresso["maximum"] = self.total_fotos
            except:
                pass
        elif f"/{self.total_fotos}]" in mensagem:
            try:
                self.progresso += 1
                self.barra_progresso["value"] = self.progresso
            except:
                pass

    def iniciar_processamento(self):
        if not self.pasta_referencia.get() or not self.pasta_entrada.get() or not self.pasta_saida.get():
            self.enviar_log("Erro: Selecione todas as pastas antes de iniciar.")
            return

        self.processando = True
        self.progresso = 0
        self.barra_progresso["value"] = 0

        self.botao_iniciar.config(state="disabled")
        self.botao_pausar.config(state="normal")
        self.botao_cancelar.config(state="normal")

        self.thread_processamento = threading.Thread(target=self.executar_separacao)
        self.thread_processamento.start()

    def executar_separacao(self):
        separar_fotos(
            self.pasta_referencia.get(),
            self.pasta_entrada.get(),
            self.pasta_saida.get(),
            self.queue
        )

        self.processando = False
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
        self.processando = False
        self.botao_iniciar.config(state="normal")
        self.botao_pausar.config(state="disabled")
        self.botao_cancelar.config(state="disabled")
        self.botao_pausar.config(text="Pausar")
        self.enviar_log("Cancelando processamento...")

    def fechar(self):
        self.running = False
        self.root.destroy()

if __name__ == '__main__':
    root = tk.Tk()
    app = InterfaceSeparador(root)
    root.protocol("WM_DELETE_WINDOW", app.fechar)
    root.mainloop()