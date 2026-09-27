"""
Bella Pele Cosméticos — Backend (Flask + SQLite)
--------------------------------------------------
Como rodar:
    pip install -r requirements.txt
    python app.py
Depois abra http://127.0.0.1:5000 no navegador.

O banco de dados fica salvo no arquivo bella_pele.db (criado automaticamente
na primeira execução). Você pode abrir esse arquivo com o "DB Browser for
SQLite" para visualizar e editar os dados manualmente.
"""

import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, g, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "bella_pele.db")

MAX_TENTATIVAS = 3
BLOQUEIO_SEGUNDOS = 60

app = Flask(__name__, template_folder=".")
# Em produção, troque por uma chave secreta forte e mantida fora do código
# (ex.: variável de ambiente). Para uso local isso já é suficiente.
app.secret_key = os.environ.get("BELLA_PELE_SECRET", "troque-esta-chave-em-producao")


# ---------------------------------------------------------------------------
# Banco de dados
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL,
            tentativas_falhas INTEGER NOT NULL DEFAULT 0,
            bloqueado_ate TEXT,
            criado_em TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            telefone TEXT,
            email TEXT,
            cpf TEXT,
            endereco TEXT,
            nascimento TEXT
        );

        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            categoria TEXT,
            marca TEXT,
            preco REAL NOT NULL DEFAULT 0,
            estoque INTEGER NOT NULL DEFAULT 0,
            validade TEXT
        );

        CREATE TABLE IF NOT EXISTS funcionarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            cpf TEXT,
            telefone TEXT,
            email TEXT,
            nascimento TEXT,
            funcao TEXT,
            salario REAL NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS vendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT,
            cliente TEXT NOT NULL,
            funcionario TEXT,
            produto TEXT NOT NULL,
            quantidade REAL NOT NULL DEFAULT 0,
            preco REAL NOT NULL DEFAULT 0,
            total REAL NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS financeiro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            categoria TEXT,
            descricao TEXT,
            data TEXT,
            vencimento TEXT,
            status TEXT NOT NULL DEFAULT 'Pendente',
            forma TEXT,
            valor REAL NOT NULL DEFAULT 0,
            origem TEXT NOT NULL DEFAULT 'manual',
            venda_id INTEGER REFERENCES vendas(id)
        );
        """
    )
    db.execute(
        """INSERT OR IGNORE INTO usuarios
           (nome, email, senha_hash, criado_em)
           VALUES (?, ?, ?, ?)""",
        (
            "Usuário de Teste",
            "teste@bellapele.com",
            generate_password_hash("Teste@123"),
            datetime.utcnow().isoformat(),
        ),
    )
    db.commit()
    db.close()


def row_to_dict(row):
    return dict(row) if row is not None else None


def rows_to_list(rows):
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return jsonify(ok=False, message="Sessão expirada. Faça login novamente."), 401
        return view(*args, **kwargs)
    return wrapped


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/cadastro", methods=["POST"])
def cadastro():
    dados = request.get_json(force=True, silent=True) or {}
    nome = (dados.get("nome") or "").strip()
    email = (dados.get("email") or "").strip().lower()
    senha = dados.get("senha") or ""

    if not nome or not email or not senha:
        return jsonify(ok=False, message="Preencha todos os campos."), 400
    if "@" not in email or "." not in email:
        return jsonify(ok=False, message="Informe um email válido."), 400
    if len(senha) < 6:
        return jsonify(ok=False, message="A senha deve ter pelo menos 6 caracteres."), 400

    db = get_db()
    existente = db.execute("SELECT id FROM usuarios WHERE email = ?", (email,)).fetchone()
    if existente:
        return jsonify(ok=False, message="Já existe uma conta com esse email."), 400

    db.execute(
        "INSERT INTO usuarios (nome, email, senha_hash, criado_em) VALUES (?, ?, ?, ?)",
        (nome, email, generate_password_hash(senha), datetime.utcnow().isoformat()),
    )
    db.commit()
    return jsonify(ok=True, message="Conta criada com sucesso!")


@app.route("/api/login", methods=["POST"])
def login():
    dados = request.get_json(force=True, silent=True) or {}
    email = (dados.get("email") or "").strip().lower()
    senha = dados.get("senha") or ""

    if not email or not senha:
        return jsonify(ok=False, message="Preencha email e senha."), 400

    db = get_db()
    usuario = db.execute("SELECT * FROM usuarios WHERE email = ?", (email,)).fetchone()

    # Mensagem genérica para não revelar se o email existe ou não
    if not usuario:
        return jsonify(ok=False, message="Email ou senha incorretos."), 401

    agora = datetime.utcnow()

    # Verifica se a conta está bloqueada por tentativas incorretas
    if usuario["bloqueado_ate"]:
        bloqueado_ate = datetime.fromisoformat(usuario["bloqueado_ate"])
        if agora < bloqueado_ate:
            segundos = int((bloqueado_ate - agora).total_seconds()) + 1
            return (
                jsonify(
                    ok=False,
                    message=f"Muitas tentativas incorretas. Aguarde {segundos}s para tentar novamente.",
                    bloqueado_segundos=segundos,
                ),
                429,
            )
        # O tempo de bloqueio já passou: libera novamente
        db.execute(
            "UPDATE usuarios SET bloqueado_ate = NULL, tentativas_falhas = 0 WHERE id = ?",
            (usuario["id"],),
        )
        db.commit()
        usuario = db.execute("SELECT * FROM usuarios WHERE id = ?", (usuario["id"],)).fetchone()

    if check_password_hash(usuario["senha_hash"], senha):
        db.execute(
            "UPDATE usuarios SET tentativas_falhas = 0, bloqueado_ate = NULL WHERE id = ?",
            (usuario["id"],),
        )
        db.commit()
        session.clear()
        session["user_id"] = usuario["id"]
        return jsonify(
            ok=True,
            usuario={"id": usuario["id"], "nome": usuario["nome"], "email": usuario["email"]},
        )

    # Senha incorreta: registra a tentativa
    tentativas = usuario["tentativas_falhas"] + 1
    if tentativas >= MAX_TENTATIVAS:
        bloqueado_ate = (agora + timedelta(seconds=BLOQUEIO_SEGUNDOS)).isoformat()
        db.execute(
            "UPDATE usuarios SET tentativas_falhas = 0, bloqueado_ate = ? WHERE id = ?",
            (bloqueado_ate, usuario["id"]),
        )
        db.commit()
        return (
            jsonify(
                ok=False,
                message=f"Muitas tentativas incorretas. Aguarde {BLOQUEIO_SEGUNDOS}s para tentar novamente.",
                bloqueado_segundos=BLOQUEIO_SEGUNDOS,
            ),
            429,
        )

    db.execute("UPDATE usuarios SET tentativas_falhas = ? WHERE id = ?", (tentativas, usuario["id"]))
    db.commit()
    restantes = MAX_TENTATIVAS - tentativas
    return (
        jsonify(ok=False, message=f"Senha incorreta. Você tem mais {restantes} tentativa(s) antes do bloqueio."),
        401,
    )


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify(ok=True)


@app.route("/api/me")
def me():
    if "user_id" not in session:
        return jsonify(ok=False), 401
    db = get_db()
    usuario = db.execute(
        "SELECT id, nome, email FROM usuarios WHERE id = ?", (session["user_id"],)
    ).fetchone()
    if not usuario:
        session.clear()
        return jsonify(ok=False), 401
    return jsonify(ok=True, usuario=row_to_dict(usuario))


# ---------------------------------------------------------------------------
# Clientes
# ---------------------------------------------------------------------------
@app.route("/api/clientes", methods=["GET", "POST"])
@login_required
def clientes():
    db = get_db()
    if request.method == "POST":
        d = request.get_json(force=True, silent=True) or {}
        nome = (d.get("nome") or "").strip()
        if not nome:
            return jsonify(ok=False, message="Informe o nome do cliente."), 400
        cur = db.execute(
            "INSERT INTO clientes (nome, telefone, email, cpf, endereco, nascimento) VALUES (?, ?, ?, ?, ?, ?)",
            (nome, d.get("telefone", ""), d.get("email", ""), d.get("cpf", ""), d.get("endereco", ""), d.get("nascimento", "")),
        )
        db.commit()
        novo = db.execute("SELECT * FROM clientes WHERE id = ?", (cur.lastrowid,)).fetchone()
        return jsonify(ok=True, cliente=row_to_dict(novo))

    q = (request.args.get("q") or "").strip().lower()
    if q:
        rows = db.execute(
            "SELECT * FROM clientes WHERE lower(nome) LIKE ? OR lower(cpf) LIKE ? OR CAST(id AS TEXT) = ? ORDER BY id DESC",
            (f"%{q}%", f"%{q}%", q),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM clientes ORDER BY id DESC").fetchall()
    return jsonify(ok=True, clientes=rows_to_list(rows))


# ---------------------------------------------------------------------------
# Produtos
# ---------------------------------------------------------------------------
@app.route("/api/produtos", methods=["GET", "POST"])
@login_required
def produtos():
    db = get_db()
    if request.method == "POST":
        d = request.get_json(force=True, silent=True) or {}
        nome = (d.get("nome") or "").strip()
        if not nome:
            return jsonify(ok=False, message="Informe o nome do produto."), 400
        try:
            preco = float(d.get("preco") or 0)
            estoque = int(d.get("estoque") or 0)
        except (TypeError, ValueError):
            return jsonify(ok=False, message="Preço/estoque inválidos."), 400
        cur = db.execute(
            "INSERT INTO produtos (nome, categoria, marca, preco, estoque, validade) VALUES (?, ?, ?, ?, ?, ?)",
            (nome, d.get("categoria", ""), d.get("marca", ""), preco, estoque, d.get("validade", "")),
        )
        db.commit()
        novo = db.execute("SELECT * FROM produtos WHERE id = ?", (cur.lastrowid,)).fetchone()
        return jsonify(ok=True, produto=row_to_dict(novo))

    q = (request.args.get("q") or "").strip().lower()
    if q:
        rows = db.execute(
            "SELECT * FROM produtos WHERE lower(nome) LIKE ? OR lower(marca) LIKE ? OR CAST(id AS TEXT) = ? ORDER BY id DESC",
            (f"%{q}%", f"%{q}%", q),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM produtos ORDER BY id DESC").fetchall()
    return jsonify(ok=True, produtos=rows_to_list(rows))


# ---------------------------------------------------------------------------
# Funcionários
# ---------------------------------------------------------------------------
@app.route("/api/funcionarios", methods=["GET", "POST"])
@login_required
def funcionarios():
    db = get_db()
    if request.method == "POST":
        d = request.get_json(force=True, silent=True) or {}
        nome = (d.get("nome") or "").strip()
        if not nome:
            return jsonify(ok=False, message="Informe o nome do funcionário."), 400
        try:
            salario = float(d.get("salario") or 0)
        except (TypeError, ValueError):
            return jsonify(ok=False, message="Salário inválido."), 400
        cur = db.execute(
            "INSERT INTO funcionarios (nome, cpf, telefone, email, nascimento, funcao, salario) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (nome, d.get("cpf", ""), d.get("telefone", ""), d.get("email", ""), d.get("nascimento", ""), d.get("funcao", ""), salario),
        )
        db.commit()
        novo = db.execute("SELECT * FROM funcionarios WHERE id = ?", (cur.lastrowid,)).fetchone()
        return jsonify(ok=True, funcionario=row_to_dict(novo))

    rows = db.execute("SELECT * FROM funcionarios ORDER BY id DESC").fetchall()
    return jsonify(ok=True, funcionarios=rows_to_list(rows))


# ---------------------------------------------------------------------------
# Vendas (gera automaticamente um lançamento de Entrada no Financeiro)
# ---------------------------------------------------------------------------
@app.route("/api/vendas", methods=["GET", "POST"])
@login_required
def vendas():
    db = get_db()
    if request.method == "POST":
        d = request.get_json(force=True, silent=True) or {}
        cliente = (d.get("cliente") or "").strip()
        produto = (d.get("produto") or "").strip()
        if not cliente or not produto:
            return jsonify(ok=False, message="Informe cliente e produto."), 400
        try:
            quantidade = float(d.get("quantidade") or 0)
            preco = float(d.get("preco") or 0)
        except (TypeError, ValueError):
            return jsonify(ok=False, message="Quantidade/preço inválidos."), 400
        total = quantidade * preco
        data_venda = d.get("data", "")
        funcionario = d.get("funcionario", "")

        cur = db.execute(
            "INSERT INTO vendas (data, cliente, funcionario, produto, quantidade, preco, total) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (data_venda, cliente, funcionario, produto, quantidade, preco, total),
        )
        venda_id = cur.lastrowid

        # lançamento automático no financeiro
        db.execute(
            """INSERT INTO financeiro (tipo, categoria, descricao, data, vencimento, status, forma, valor, origem, venda_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "Entrada",
                "Venda de Produto",
                f"Venda #{venda_id} — {produto} ({cliente})",
                data_venda,
                data_venda,
                "Pago",
                "—",
                total,
                "venda",
                venda_id,
            ),
        )
        db.commit()
        nova = db.execute("SELECT * FROM vendas WHERE id = ?", (venda_id,)).fetchone()
        return jsonify(ok=True, venda=row_to_dict(nova))

    rows = db.execute("SELECT * FROM vendas ORDER BY id DESC").fetchall()
    return jsonify(ok=True, vendas=rows_to_list(rows))


# ---------------------------------------------------------------------------
# Financeiro
# ---------------------------------------------------------------------------
@app.route("/api/financeiro", methods=["GET", "POST"])
@login_required
def financeiro():
    db = get_db()
    if request.method == "POST":
        d = request.get_json(force=True, silent=True) or {}
        tipo = d.get("tipo")
        try:
            valor = float(d.get("valor") or 0)
        except (TypeError, ValueError):
            return jsonify(ok=False, message="Valor inválido."), 400
        if tipo not in ("Entrada", "Saída") or not valor:
            return jsonify(ok=False, message="Informe tipo e valor do lançamento."), 400
        cur = db.execute(
            """INSERT INTO financeiro (tipo, categoria, descricao, data, vencimento, status, forma, valor, origem)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'manual')""",
            (
                tipo,
                d.get("categoria", ""),
                d.get("descricao", ""),
                d.get("data", ""),
                d.get("vencimento", ""),
                d.get("status") or "Pendente",
                d.get("forma", ""),
                valor,
            ),
        )
        db.commit()
        novo = db.execute("SELECT * FROM financeiro WHERE id = ?", (cur.lastrowid,)).fetchone()
        return jsonify(ok=True, lancamento=row_to_dict(novo))

    rows = db.execute("SELECT * FROM financeiro ORDER BY id DESC").fetchall()
    return jsonify(ok=True, financeiro=rows_to_list(rows))


@app.route("/api/financeiro/<int:lanc_id>/status", methods=["POST"])
@login_required
def atualizar_status_financeiro(lanc_id):
    d = request.get_json(force=True, silent=True) or {}
    status = d.get("status")
    if status not in ("Pago", "Pendente"):
        return jsonify(ok=False, message="Status inválido."), 400
    db = get_db()
    db.execute("UPDATE financeiro SET status = ? WHERE id = ?", (status, lanc_id))
    db.commit()
    atualizado = db.execute("SELECT * FROM financeiro WHERE id = ?", (lanc_id,)).fetchone()
    if not atualizado:
        return jsonify(ok=False, message="Lançamento não encontrado."), 404
    return jsonify(ok=True, lancamento=row_to_dict(atualizado))


if __name__ == "__main__":
    init_db()
    app.run(
        host=os.environ.get("FLASK_HOST", "127.0.0.1"),
        port=int(os.environ.get("FLASK_PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )
