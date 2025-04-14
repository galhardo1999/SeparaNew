from flask import Flask, render_template, request, redirect, url_for, flash, session
from database import init_db, register_user, authenticate_user, get_user_name, is_admin, get_all_users

app = Flask(__name__)
app.secret_key = "sua_chave_secreta_aqui"  # Substitua por uma chave segura

# Inicializa o banco de dados
init_db()

# Planos de assinatura
PLANOS = [
    {"nome": "Básico", "preco": "R$ 19,90/mês", "recursos": ["100 fotos/mês", "Suporte básico", "1 usuário"]},
    {"nome": "Pro", "preco": "R$ 49,90/mês", "recursos": ["500 fotos/mês", "Suporte prioritário", "3 usuários"]},
    {"nome": "Premium", "preco": "R$ 99,90/mês", "recursos": ["Fotos ilimitadas", "Suporte 24/7", "10 usuários"]}
]

@app.route('/')
def index():
    if 'user_email' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if authenticate_user(email, password):
            session['user_email'] = email
            flash('Login bem-sucedido!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('E-mail ou senha incorretos.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        if register_user(name, email, password):
            flash('Registro bem-sucedido! Faça login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('E-mail já registrado.', 'danger')
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_email' not in session:
        flash('Faça login para acessar o dashboard.', 'warning')
        return redirect(url_for('login'))
    if is_admin(session['user_email']):
        return redirect(url_for('admin_dashboard'))
    user_name = get_user_name(session['user_email'])
    return render_template('dashboard.html', user_name=user_name, planos=PLANOS)

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user_email' not in session:
        flash('Faça login para acessar o dashboard.', 'warning')
        return redirect(url_for('login'))
    if not is_admin(session['user_email']):
        flash('Acesso restrito a administradores.', 'danger')
        return redirect(url_for('dashboard'))
    user_name = get_user_name(session['user_email'])
    users = get_all_users()
    return render_template('admin/admin_dashboard.html', user_name=user_name, users=users)

@app.route('/logout')
def logout():
    session.pop('user_email', None)
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)