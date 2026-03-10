#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SIMULADOR ELEITORAL ES — SaaS
Backend Flask com autenticação, multi-usuário e persistência SQLite
"""

from flask import (Flask, render_template, request, redirect, url_for,
                   session, jsonify, flash, abort)
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, json, math, os, datetime, hmac, hashlib, requests
from functools import wraps

# ─── Configuração de Planos ────────────────────────────────────────────────────
PLANOS = {
    "mensal": {
        "nome":      "Plano Mensal",
        "preco":     99.90,
        "tipo":      "recorrente",
        "descricao": "Acesso completo com renovação mensal automática",
        "mp_id":     None,   # preenchido via variável de ambiente MP_PLAN_ID_MENSAL
    },
    "vitalicio": {
        "nome":      "Plano Vitalício",
        "preco":     999.90,
        "tipo":      "unico",
        "descricao": "Acesso completo e permanente, pague uma vez",
        "mp_id":     None,
    },
}

MP_ACCESS_TOKEN  = os.environ.get("MP_ACCESS_TOKEN", "")
MP_WEBHOOK_SECRET= os.environ.get("MP_WEBHOOK_SECRET", "")
MP_PLAN_MENSAL   = os.environ.get("MP_PLAN_ID_MENSAL", "")
BASE_URL         = os.environ.get("BASE_URL", "http://localhost:5000")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "simulador-eleitoral-es-2026-secret")

DB_PATH = os.path.join(os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", os.path.dirname(__file__)), "database.db")

# ─────────────────────────────────────────────────────────────────────────────
# BANCO DE DADOS
# ─────────────────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            nome      TEXT NOT NULL,
            email     TEXT UNIQUE NOT NULL,
            senha     TEXT NOT NULL,
            papel     TEXT NOT NULL DEFAULT 'usuario',
            criado_em TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS simulacoes (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id   INTEGER NOT NULL REFERENCES usuarios(id),
            nome         TEXT NOT NULL,
            descricao    TEXT,
            cargo        TEXT NOT NULL,
            eleitores    INTEGER NOT NULL,
            votos_brancos INTEGER NOT NULL DEFAULT 0,
            votos_nulos   INTEGER NOT NULL DEFAULT 0,
            dados_json   TEXT NOT NULL,
            resultado_json TEXT,
            criado_em    TEXT NOT NULL,
            atualizado_em TEXT NOT NULL,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS assinaturas (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id        INTEGER NOT NULL REFERENCES usuarios(id),
            plano             TEXT NOT NULL,          -- 'mensal' | 'vitalicio'
            status            TEXT NOT NULL DEFAULT 'pendente',
            -- 'pendente' | 'ativa' | 'cancelada' | 'expirada' | 'suspensa'
            mp_payment_id     TEXT,                   -- ID do pagamento no MP
            mp_subscription_id TEXT,                  -- ID da assinatura recorrente no MP
            valor_pago        REAL,
            data_inicio       TEXT,
            data_expiracao    TEXT,                   -- NULL = vitalício
            criado_em         TEXT NOT NULL,
            atualizado_em     TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS pagamentos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id      INTEGER NOT NULL REFERENCES usuarios(id),
            assinatura_id   INTEGER REFERENCES assinaturas(id),
            mp_payment_id   TEXT NOT NULL,
            status          TEXT NOT NULL,
            valor           REAL NOT NULL,
            plano           TEXT NOT NULL,
            metodo          TEXT,
            criado_em       TEXT NOT NULL
        );

        -- Migração: adicionar coluna ativo se não existir
        """)
        try:
            db.execute("ALTER TABLE usuarios ADD COLUMN ativo INTEGER NOT NULL DEFAULT 1")
        except Exception:
            pass
        try:
            db.execute("ALTER TABLE usuarios ADD COLUMN plano TEXT")
        except Exception:
            pass
        try:
            db.execute("ALTER TABLE usuarios ADD COLUMN plano_expira TEXT")
        except Exception:
            pass
        # Admin padrão
        adm = db.execute("SELECT id FROM usuarios WHERE email='admin@simulador.es'").fetchone()
        if not adm:
            db.execute("""INSERT INTO usuarios (nome,email,senha,papel,criado_em)
                          VALUES (?,?,?,?,?)""",
                       ("Administrador", "admin@simulador.es",
                        generate_password_hash("admin123"),
                        "admin", _agora()))

def _agora():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

init_db()

# ─────────────────────────────────────────────────────────────────────────────
# AUTENTICAÇÃO
# ─────────────────────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("papel") != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated

def assinatura_ativa(uid):
    """Retorna True se o usuário tem assinatura ativa ou é admin."""
    with get_db() as db:
        u = db.execute("SELECT papel FROM usuarios WHERE id=?", (uid,)).fetchone()
        if u and u["papel"] == "admin":
            return True
        a = db.execute("""SELECT * FROM assinaturas
                          WHERE usuario_id=? AND status='ativa'
                          ORDER BY id DESC LIMIT 1""", (uid,)).fetchone()
        if not a:
            return False
        if a["plano"] == "vitalicio":
            return True
        # Mensal: verificar expiração
        if a["data_expiracao"]:
            exp = datetime.datetime.fromisoformat(a["data_expiracao"])
            return datetime.datetime.now() < exp
        return True

def plano_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if not assinatura_ativa(session["user_id"]):
            return redirect(url_for("planos"))
        return f(*args, **kwargs)
    return decorated

def usuario_atual():
    if "user_id" not in session:
        return None
    with get_db() as db:
        return db.execute("SELECT * FROM usuarios WHERE id=?",
                          (session["user_id"],)).fetchone()

# ─────────────────────────────────────────────────────────────────────────────
# MOTOR ELEITORAL
# ─────────────────────────────────────────────────────────────────────────────
VAGAS = {"Deputado Federal": 10, "Deputado Estadual": 30}
ELEITORES_ES = 2_921_506

def calcular_eleicao(dados_partidos: dict, vagas: int,
                     brancos: int, nulos: int, eleitores: int) -> dict:
    partidos = []
    for sigla, d in dados_partidos.items():
        total = sum(c["votos"] for c in d["candidatos"]) + d.get("votos_legenda", 0)
        partidos.append({
            "sigla": sigla,
            "candidatos": sorted(d["candidatos"], key=lambda c: c["votos"], reverse=True),
            "votos_legenda": d.get("votos_legenda", 0),
            "total_votos": total,
        })

    total_validos = sum(p["total_votos"] for p in partidos)
    comparecimento = total_validos + brancos + nulos
    abstencao = max(0, eleitores - comparecimento)

    # QE
    qe_raw = total_validos / vagas if vagas > 0 else 0
    fracao = qe_raw - math.floor(qe_raw)
    qe = math.ceil(qe_raw) if fracao > 0.5 else math.floor(qe_raw)
    qe = max(1, qe)

    # QP
    for p in partidos:
        p["atingiu_qe"]    = p["total_votos"] >= qe
        p["atingiu_80_qe"] = p["total_votos"] >= 0.8 * qe
        p["vagas_qp"]      = math.floor(p["total_votos"] / qe) if p["atingiu_qe"] and qe else 0
        p["vagas_sobra"]   = 0

    # Sobras — Regras para 2026 (pós-STF ADIs 7228, 7263 e 7325)
    # TODOS os partidos participam das sobras (STF derrubou o filtro de 80% QE)
    # Exigência individual permanece: candidato precisa de >= 20% QE para assumir vaga de sobra
    vagas_usadas = sum(p["vagas_qp"] for p in partidos)
    sobras = vagas - vagas_usadas

    minimo_20_qe = math.ceil(0.2 * qe) if qe else 0  # exigência individual nas sobras

    for _ in range(sobras):
        # Todos os partidos participam do cálculo de médias (sem filtro de 80%)
        for p in partidos:
            p["media"] = p["total_votos"] / (p["vagas_qp"] + p["vagas_sobra"] + 1)

        # Ordenar por média decrescente
        partidos_por_media = sorted(partidos, key=lambda p: p["media"], reverse=True)

        # Atribuir vaga ao primeiro partido com maior média que tenha
        # ao menos um candidato AINDA NÃO ELEITO com >= 20% QE individual.
        # (candidatos já consumidos pelas vagas QP + sobras anteriores não contam)
        vaga_atribuida = False
        for p in partidos_por_media:
            ja_eleitos = p["vagas_qp"] + p["vagas_sobra"]
            proximos = p["candidatos"][ja_eleitos:]  # candidatos ainda disponíveis
            if any(c["votos"] >= minimo_20_qe for c in proximos):
                p["vagas_sobra"] += 1
                vaga_atribuida = True
                break

        # Se nenhum partido tiver candidato disponível com 20% QE,
        # atribui ao de maior média (garante distribuição integral)
        if not vaga_atribuida and partidos_por_media:
            partidos_por_media[0]["vagas_sobra"] += 1

    # Vagas totais e eleitos
    minimo = math.ceil(0.1 * qe) if qe else 0
    resultado_cands = []
    for p in partidos:
        p["vagas_total"] = p["vagas_qp"] + p["vagas_sobra"]
        vagas_p = p["vagas_total"]
        eleitos_cnt = 0
        for i, c in enumerate(p["candidatos"]):
            c = dict(c, partido=p["sigla"], posicao=i+1)
            if vagas_p > 0 and eleitos_cnt < vagas_p:
                # 1ª fase (QP): mínimo 10% do QE
                # 2ª fase (SOBRA): mínimo 20% do QE
                eh_sobra = eleitos_cnt >= p["vagas_qp"]
                minimo_vaga = minimo_20_qe if eh_sobra else minimo
                if c["votos"] >= minimo_vaga:
                    c["status"] = "ELEITO"
                    c["eleito_por"] = "QP" if not eh_sobra else "SOBRA"
                    eleitos_cnt += 1
                else:
                    c["status"] = "NÃO ELEITO"
                    c["eleito_por"] = f"< mín {minimo_vaga:,}"
            else:
                c["status"] = "SUPLENTE" if p["vagas_total"] > 0 else "NÃO ELEITO"
                c["eleito_por"] = ""
            resultado_cands.append(c)

    return {
        "qe": qe, "qe_raw": round(qe_raw, 4),
        "total_validos": total_validos,
        "total_brancos": brancos, "total_nulos": nulos,
        "comparecimento": comparecimento, "abstencao": abstencao,
        "eleitores": eleitores, "vagas": vagas,
        "vagas_qp_total": vagas_usadas, "vagas_sobras": sobras,
        "minimo_individual": minimo,
        "minimo_80_qe": math.ceil(0.8 * qe) if qe else 0,
        "minimo_20_qe": math.ceil(0.2 * qe) if qe else 0,
        "total_eleitos": sum(1 for c in resultado_cands if c["status"] == "ELEITO"),
        "partidos": partidos,
        "candidatos": resultado_cands,
    }

# ─────────────────────────────────────────────────────────────────────────────
# ROTAS — AUTH
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        senha = request.form.get("senha","")
        with get_db() as db:
            u = db.execute("SELECT * FROM usuarios WHERE email=?", (email,)).fetchone()
        if u and check_password_hash(u["senha"], senha):
            session["user_id"] = u["id"]
            session["nome"]    = u["nome"]
            session["papel"]   = u["papel"]
            return redirect(url_for("dashboard"))
        flash("E-mail ou senha incorretos.", "erro")
    return render_template("login.html")

@app.route("/cadastro", methods=["GET","POST"])
def cadastro():
    if request.method == "POST":
        nome  = request.form.get("nome","").strip()
        email = request.form.get("email","").strip().lower()
        senha = request.form.get("senha","")
        conf  = request.form.get("confirmar","")
        if not nome or not email or not senha:
            flash("Preencha todos os campos.", "erro")
        elif senha != conf:
            flash("As senhas não coincidem.", "erro")
        elif len(senha) < 6:
            flash("A senha deve ter ao menos 6 caracteres.", "erro")
        else:
            try:
                with get_db() as db:
                    db.execute("""INSERT INTO usuarios (nome,email,senha,papel,criado_em)
                                  VALUES (?,?,?,?,?)""",
                               (nome, email, generate_password_hash(senha), "usuario", _agora()))
                flash("Conta criada com sucesso! Faça login.", "ok")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Este e-mail já está cadastrado.", "erro")
    return render_template("cadastro.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ─────────────────────────────────────────────────────────────────────────────
# ROTAS — DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/dashboard")
@plano_required
def dashboard():
    with get_db() as db:
        sims = db.execute("""SELECT * FROM simulacoes WHERE usuario_id=?
                             ORDER BY atualizado_em DESC""",
                          (session["user_id"],)).fetchall()
    return render_template("dashboard.html", simulacoes=sims, usuario=usuario_atual())

# ─────────────────────────────────────────────────────────────────────────────
# ROTAS — SIMULAÇÕES
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/simulacao/nova")
@plano_required
def nova_simulacao():
    return render_template("simulador.html", simulacao=None, usuario=usuario_atual())

@app.route("/simulacao/<int:sid>")
@plano_required
def editar_simulacao(sid):
    with get_db() as db:
        sim = db.execute("SELECT * FROM simulacoes WHERE id=? AND usuario_id=?",
                         (sid, session["user_id"])).fetchone()
    if not sim:
        abort(404)
    return render_template("simulador.html", simulacao=sim, usuario=usuario_atual())

@app.route("/api/simulacao/salvar", methods=["POST"])
@plano_required
def api_salvar():
    body = request.get_json()
    nome         = body.get("nome","").strip() or "Sem título"
    descricao    = body.get("descricao","").strip()
    cargo        = body.get("cargo","Deputado Federal")
    eleitores    = int(body.get("eleitores", ELEITORES_ES))
    brancos      = int(body.get("votos_brancos", 0))
    nulos        = int(body.get("votos_nulos", 0))
    dados        = body.get("dados_partidos", {})
    resultado    = body.get("resultado", None)
    sim_id       = body.get("id")
    agora        = _agora()

    dados_json   = json.dumps(dados, ensure_ascii=False)
    res_json     = json.dumps(resultado, ensure_ascii=False) if resultado else None

    with get_db() as db:
        if sim_id:
            existing = db.execute("SELECT id FROM simulacoes WHERE id=? AND usuario_id=?",
                                  (sim_id, session["user_id"])).fetchone()
            if existing:
                db.execute("""UPDATE simulacoes SET nome=?,descricao=?,cargo=?,eleitores=?,
                              votos_brancos=?,votos_nulos=?,dados_json=?,resultado_json=?,
                              atualizado_em=? WHERE id=?""",
                           (nome,descricao,cargo,eleitores,brancos,nulos,
                            dados_json,res_json,agora,sim_id))
                return jsonify({"ok": True, "id": sim_id, "msg": "Salvo com sucesso!"})
        cur = db.execute("""INSERT INTO simulacoes
                            (usuario_id,nome,descricao,cargo,eleitores,votos_brancos,
                             votos_nulos,dados_json,resultado_json,criado_em,atualizado_em)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                         (session["user_id"],nome,descricao,cargo,eleitores,brancos,
                          nulos,dados_json,res_json,agora,agora))
        return jsonify({"ok": True, "id": cur.lastrowid, "msg": "Simulação criada!"})

@app.route("/api/simulacao/<int:sid>", methods=["GET"])
@plano_required
def api_carregar(sid):
    with get_db() as db:
        sim = db.execute("SELECT * FROM simulacoes WHERE id=? AND usuario_id=?",
                         (sid, session["user_id"])).fetchone()
    if not sim:
        return jsonify({"ok": False, "msg": "Não encontrado"}), 404
    return jsonify({
        "ok": True,
        "id": sim["id"],
        "nome": sim["nome"],
        "descricao": sim["descricao"] or "",
        "cargo": sim["cargo"],
        "eleitores": sim["eleitores"],
        "votos_brancos": sim["votos_brancos"],
        "votos_nulos": sim["votos_nulos"],
        "dados_partidos": json.loads(sim["dados_json"]),
        "resultado": json.loads(sim["resultado_json"]) if sim["resultado_json"] else None,
        "atualizado_em": sim["atualizado_em"],
    })

@app.route("/api/simulacao/<int:sid>", methods=["DELETE"])
@plano_required
def api_deletar(sid):
    with get_db() as db:
        db.execute("DELETE FROM simulacoes WHERE id=? AND usuario_id=?",
                   (sid, session["user_id"]))
    return jsonify({"ok": True})

@app.route("/api/calcular", methods=["POST"])
@plano_required
def api_calcular():
    body    = request.get_json()
    cargo   = body.get("cargo","Deputado Federal")
    vagas   = VAGAS.get(cargo, 10)
    dados   = body.get("dados_partidos", {})
    brancos = int(body.get("votos_brancos", 0))
    nulos   = int(body.get("votos_nulos", 0))
    eleit   = int(body.get("eleitores", ELEITORES_ES))

    if not dados:
        return jsonify({"ok": False, "msg": "Nenhum dado informado"}), 400

    res = calcular_eleicao(dados, vagas, brancos, nulos, eleit)
    return jsonify({"ok": True, "resultado": res})

# ─────────────────────────────────────────────────────────────────────────────
# ROTAS — ADMIN
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# ROTAS — PLANOS E PAGAMENTO (MERCADO PAGO)
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/planos")
@login_required
def planos():
    uid = session["user_id"]
    ativa = assinatura_ativa(uid)
    with get_db() as db:
        assinatura = db.execute(
            "SELECT * FROM assinaturas WHERE usuario_id=? AND status='ativa' ORDER BY id DESC LIMIT 1",
            (uid,)).fetchone()
    return render_template("planos.html", planos=PLANOS, ativa=ativa,
                           assinatura=assinatura, usuario=usuario_atual())

@app.route("/assinar/<plano>", methods=["POST"])
@login_required
def assinar(plano):
    if plano not in PLANOS:
        abort(404)
    uid   = session["user_id"]
    u     = usuario_atual()
    dados_plano = PLANOS[plano]

    if not MP_ACCESS_TOKEN:
        # Modo demonstração — ativa direto (para testes sem credenciais MP)
        with get_db() as db:
            agora = _agora()
            exp   = None
            if plano == "mensal":
                exp = (datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
            db.execute("""INSERT INTO assinaturas
                (usuario_id,plano,status,valor_pago,data_inicio,data_expiracao,criado_em,atualizado_em)
                VALUES (?,?,?,?,?,?,?,?)""",
                (uid, plano, "ativa", dados_plano["preco"], agora, exp, agora, agora))
            db.execute("UPDATE usuarios SET plano=?, plano_expira=? WHERE id=?",
                       (plano, exp, uid))
        flash(f"Plano {dados_plano['nome']} ativado em modo demonstração!", "ok")
        return redirect(url_for("dashboard"))

    # ── Criar preferência no Mercado Pago ─────────────────────────────────────
    headers = {"Authorization": f"Bearer {MP_ACCESS_TOKEN}",
               "Content-Type": "application/json"}

    if plano == "vitalicio":
        # Pagamento único
        payload = {
            "items": [{
                "title":      dados_plano["nome"],
                "description":dados_plano["descricao"],
                "quantity":   1,
                "unit_price": dados_plano["preco"],
                "currency_id":"BRL",
            }],
            "payer":             {"email": u["email"]},
            "back_urls":         {
                "success": f"{BASE_URL}/pagamento/sucesso/{plano}",
                "failure": f"{BASE_URL}/pagamento/falha/{plano}",
                "pending": f"{BASE_URL}/pagamento/pendente/{plano}",
            },
            "auto_return":       "approved",
            "external_reference":f"{uid}:{plano}",
            "notification_url":  f"{BASE_URL}/webhook/mp",
        }
        r = requests.post("https://api.mercadopago.com/checkout/preferences",
                          headers=headers, json=payload, timeout=10)
        if r.status_code != 201:
            flash("Erro ao conectar com Mercado Pago. Tente novamente.", "erro")
            return redirect(url_for("planos"))
        init_point = r.json().get("init_point")
        return redirect(init_point)

    else:
        # Assinatura recorrente — redirecionar para checkout de assinatura
        if not MP_PLAN_MENSAL:
            flash("Plano mensal não configurado ainda. Entre em contato.", "erro")
            return redirect(url_for("planos"))
        payload = {
            "preapproval_plan_id": MP_PLAN_MENSAL,
            "reason":              dados_plano["nome"],
            "payer_email":         u["email"],
            "back_url":            f"{BASE_URL}/pagamento/sucesso/mensal",
            "external_reference":  f"{uid}:mensal",
            "auto_recurring": {
                "frequency":       1,
                "frequency_type":  "months",
                "transaction_amount": dados_plano["preco"],
                "currency_id":     "BRL",
            },
        }
        r = requests.post("https://api.mercadopago.com/preapproval",
                          headers=headers, json=payload, timeout=10)
        if r.status_code not in (200, 201):
            flash("Erro ao criar assinatura. Tente novamente.", "erro")
            return redirect(url_for("planos"))
        init_point = r.json().get("init_point") or r.json().get("sandbox_init_point")
        return redirect(init_point)

@app.route("/pagamento/sucesso/<plano>")
@login_required
def pagamento_sucesso(plano):
    payment_id = request.args.get("payment_id") or request.args.get("preapproval_id")
    uid = session["user_id"]
    with get_db() as db:
        agora = _agora()
        exp   = None
        if plano == "mensal":
            exp = (datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        # Verificar se já existe (idempotente)
        existe = db.execute(
            "SELECT id FROM assinaturas WHERE usuario_id=? AND plano=? AND status='ativa'",
            (uid, plano)).fetchone()
        if not existe:
            db.execute("""INSERT INTO assinaturas
                (usuario_id,plano,status,mp_payment_id,valor_pago,data_inicio,data_expiracao,criado_em,atualizado_em)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (uid, plano, "ativa", payment_id,
                 PLANOS[plano]["preco"], agora, exp, agora, agora))
            db.execute("UPDATE usuarios SET plano=?, plano_expira=? WHERE id=?",
                       (plano, exp, uid))
            if payment_id:
                db.execute("""INSERT INTO pagamentos
                    (usuario_id,mp_payment_id,status,valor,plano,criado_em)
                    VALUES (?,?,?,?,?,?)""",
                    (uid, payment_id, "approved", PLANOS[plano]["preco"], plano, agora))
    flash(f"✅ Pagamento confirmado! Bem-vindo ao {PLANOS[plano]['nome']}.", "ok")
    return redirect(url_for("dashboard"))

@app.route("/pagamento/falha/<plano>")
@login_required
def pagamento_falha(plano):
    flash("Pagamento não aprovado. Tente novamente ou escolha outro método.", "erro")
    return redirect(url_for("planos"))

@app.route("/pagamento/pendente/<plano>")
@login_required
def pagamento_pendente(plano):
    flash("Pagamento em análise. Você receberá acesso assim que for confirmado.", "info")
    return redirect(url_for("planos"))

@app.route("/webhook/mp", methods=["POST"])
def webhook_mp():
    """Webhook do Mercado Pago — atualiza status de pagamentos/assinaturas."""
    data = request.get_json(silent=True) or {}
    topic = data.get("type") or request.args.get("topic", "")

    if topic == "payment":
        pid = data.get("data", {}).get("id") or request.args.get("id")
        if pid and MP_ACCESS_TOKEN:
            r = requests.get(f"https://api.mercadopago.com/v1/payments/{pid}",
                             headers={"Authorization": f"Bearer {MP_ACCESS_TOKEN}"}, timeout=10)
            if r.status_code == 200:
                p = r.json()
                status = p.get("status")
                ext_ref = p.get("external_reference", "")
                if ":" in ext_ref:
                    uid, plano = ext_ref.split(":", 1)
                    uid = int(uid)
                    with get_db() as db:
                        agora = _agora()
                        if status == "approved":
                            exp = None
                            if plano == "mensal":
                                exp = (datetime.datetime.now() + datetime.timedelta(days=30)
                                       ).strftime("%Y-%m-%d %H:%M:%S")
                            existe = db.execute(
                                "SELECT id FROM assinaturas WHERE mp_payment_id=?",
                                (str(pid),)).fetchone()
                            if not existe:
                                db.execute("""INSERT INTO assinaturas
                                    (usuario_id,plano,status,mp_payment_id,valor_pago,
                                     data_inicio,data_expiracao,criado_em,atualizado_em)
                                    VALUES (?,?,?,?,?,?,?,?,?)""",
                                    (uid, plano, "ativa", str(pid),
                                     PLANOS.get(plano, {}).get("preco", 0),
                                     agora, exp, agora, agora))
                                db.execute("UPDATE usuarios SET plano=?, plano_expira=? WHERE id=?",
                                           (plano, exp, uid))
                                db.execute("""INSERT INTO pagamentos
                                    (usuario_id,mp_payment_id,status,valor,plano,criado_em)
                                    VALUES (?,?,?,?,?,?)""",
                                    (uid, str(pid), status,
                                     PLANOS.get(plano, {}).get("preco", 0), plano, agora))
                        elif status in ("cancelled", "rejected", "refunded"):
                            db.execute("""UPDATE assinaturas SET status='cancelada', atualizado_em=?
                                         WHERE usuario_id=? AND plano=? AND status='ativa'""",
                                       (agora, uid, plano))
                            db.execute("UPDATE usuarios SET plano=NULL WHERE id=?", (uid,))

    elif topic == "subscription_preapproval":
        sid = data.get("data", {}).get("id") or request.args.get("id")
        if sid and MP_ACCESS_TOKEN:
            r = requests.get(f"https://api.mercadopago.com/preapproval/{sid}",
                             headers={"Authorization": f"Bearer {MP_ACCESS_TOKEN}"}, timeout=10)
            if r.status_code == 200:
                s = r.json()
                status = s.get("status")
                ext_ref = s.get("external_reference", "")
                if ":" in ext_ref:
                    uid, plano = ext_ref.split(":", 1)
                    uid = int(uid)
                    agora = _agora()
                    with get_db() as db:
                        if status == "authorized":
                            exp = (datetime.datetime.now() + datetime.timedelta(days=30)
                                   ).strftime("%Y-%m-%d %H:%M:%S")
                            db.execute("""UPDATE assinaturas
                                SET status='ativa', mp_subscription_id=?, data_expiracao=?, atualizado_em=?
                                WHERE usuario_id=? AND plano='mensal'""",
                                (sid, exp, agora, uid))
                            db.execute("UPDATE usuarios SET plano='mensal', plano_expira=? WHERE id=?",
                                       (exp, uid))
                        elif status in ("cancelled", "paused"):
                            db.execute("""UPDATE assinaturas SET status=?, atualizado_em=?
                                WHERE usuario_id=? AND plano='mensal' AND status='ativa'""",
                                ("cancelada" if status=="cancelled" else "suspensa", agora, uid))
                            if status == "cancelled":
                                db.execute("UPDATE usuarios SET plano=NULL WHERE id=?", (uid,))
    return jsonify({"ok": True}), 200

@app.route("/minha-assinatura")
@login_required
def minha_assinatura():
    uid = session["user_id"]
    with get_db() as db:
        assinatura = db.execute(
            "SELECT * FROM assinaturas WHERE usuario_id=? ORDER BY id DESC LIMIT 1",
            (uid,)).fetchone()
        pagamentos = db.execute(
            "SELECT * FROM pagamentos WHERE usuario_id=? ORDER BY criado_em DESC LIMIT 12",
            (uid,)).fetchall()
    return render_template("minha_assinatura.html", assinatura=assinatura,
                           pagamentos=pagamentos, planos=PLANOS, usuario=usuario_atual())

@app.route("/cancelar-assinatura", methods=["POST"])
@login_required
def cancelar_assinatura():
    uid = session["user_id"]
    with get_db() as db:
        a = db.execute(
            "SELECT * FROM assinaturas WHERE usuario_id=? AND status='ativa'",
            (uid,)).fetchone()
        if a and a["mp_subscription_id"] and MP_ACCESS_TOKEN:
            requests.patch(
                f"https://api.mercadopago.com/preapproval/{a['mp_subscription_id']}",
                headers={"Authorization": f"Bearer {MP_ACCESS_TOKEN}"},
                json={"status": "cancelled"}, timeout=10)
        agora = _agora()
        db.execute("UPDATE assinaturas SET status='cancelada', atualizado_em=? WHERE usuario_id=? AND status='ativa'",
                   (agora, uid))
        db.execute("UPDATE usuarios SET plano=NULL WHERE id=?", (uid,))
    flash("Assinatura cancelada. Seu acesso permanece até o fim do período pago.", "info")
    return redirect(url_for("minha_assinatura"))


@app.route("/admin")
@admin_required
def admin():
    with get_db() as db:
        usuarios   = db.execute("""
            SELECT u.*,
                   a.plano      AS plano_ativo,
                   a.status     AS assinatura_status,
                   a.data_expiracao,
                   (SELECT COUNT(*) FROM simulacoes WHERE usuario_id=u.id) AS total_sims
            FROM usuarios u
            LEFT JOIN assinaturas a ON a.usuario_id=u.id AND a.status='ativa'
            ORDER BY u.criado_em DESC""").fetchall()

        total_usuarios   = db.execute("SELECT COUNT(*) as c FROM usuarios WHERE papel!='admin'").fetchone()["c"]
        total_sims       = db.execute("SELECT COUNT(*) as c FROM simulacoes").fetchone()["c"]
        assinaturas_ativas = db.execute("SELECT COUNT(*) as c FROM assinaturas WHERE status='ativa'").fetchone()["c"]
        mensais_ativos   = db.execute("SELECT COUNT(*) as c FROM assinaturas WHERE status='ativa' AND plano='mensal'").fetchone()["c"]
        vitalicios_ativos= db.execute("SELECT COUNT(*) as c FROM assinaturas WHERE status='ativa' AND plano='vitalicio'").fetchone()["c"]
        receita_mensal   = db.execute("""SELECT COALESCE(SUM(valor),0) as v FROM pagamentos
                                         WHERE criado_em >= date('now','start of month')""").fetchone()["v"]
        receita_total    = db.execute("SELECT COALESCE(SUM(valor),0) as v FROM pagamentos WHERE status='approved'").fetchone()["v"]
        mrr              = mensais_ativos * 99.90
        ultimos_pagamentos = db.execute("""
            SELECT p.*, u.nome, u.email FROM pagamentos p
            JOIN usuarios u ON u.id=p.usuario_id
            ORDER BY p.criado_em DESC LIMIT 20""").fetchall()
        sims_por_dia     = db.execute("""
            SELECT DATE(criado_em) as dia, COUNT(*) as total
            FROM simulacoes WHERE criado_em >= date('now','-30 days')
            GROUP BY dia ORDER BY dia""").fetchall()

    metricas = {
        "total_usuarios": total_usuarios,
        "total_sims": total_sims,
        "assinaturas_ativas": assinaturas_ativas,
        "mensais_ativos": mensais_ativos,
        "vitalicios_ativos": vitalicios_ativos,
        "receita_mensal": receita_mensal,
        "receita_total": receita_total,
        "mrr": mrr,
    }
    return render_template("admin.html", usuarios=usuarios, metricas=metricas,
                           ultimos_pagamentos=ultimos_pagamentos,
                           sims_por_dia=sims_por_dia, usuario=usuario_atual())

@app.route("/admin/assinatura/<int:uid>/ativar", methods=["POST"])
@admin_required
def admin_ativar_plano(uid):
    plano = request.form.get("plano", "mensal")
    with get_db() as db:
        agora = _agora()
        exp   = None
        if plano == "mensal":
            exp = (datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        db.execute("UPDATE assinaturas SET status='cancelada', atualizado_em=? WHERE usuario_id=? AND status='ativa'",
                   (agora, uid))
        db.execute("""INSERT INTO assinaturas
            (usuario_id,plano,status,valor_pago,data_inicio,data_expiracao,criado_em,atualizado_em)
            VALUES (?,?,?,?,?,?,?,?)""",
            (uid, plano, "ativa", 0.0, agora, exp, agora, agora))
        db.execute("UPDATE usuarios SET plano=?, plano_expira=? WHERE id=?", (plano, exp, uid))
    flash(f"Plano ativado manualmente para usuário #{uid}.", "ok")
    return redirect(url_for("admin"))

@app.route("/admin/assinatura/<int:uid>/revogar", methods=["POST"])
@admin_required
def admin_revogar_plano(uid):
    with get_db() as db:
        agora = _agora()
        db.execute("UPDATE assinaturas SET status='cancelada', atualizado_em=? WHERE usuario_id=? AND status='ativa'",
                   (agora, uid))
        db.execute("UPDATE usuarios SET plano=NULL WHERE id=?", (uid,))
    flash(f"Acesso revogado para usuário #{uid}.", "info")
    return redirect(url_for("admin"))

@app.route("/admin/usuario/<int:uid>/toggle", methods=["POST"])
@admin_required
def admin_toggle_papel(uid):
    with get_db() as db:
        u = db.execute("SELECT papel FROM usuarios WHERE id=?", (uid,)).fetchone()
        if u:
            novo = "admin" if u["papel"] == "usuario" else "usuario"
            db.execute("UPDATE usuarios SET papel=? WHERE id=?", (novo, uid))
    return redirect(url_for("admin"))

@app.route("/admin/usuario/<int:uid>/excluir", methods=["POST"])
@admin_required
def admin_excluir_usuario(uid):
    if uid == session["user_id"]:
        flash("Não pode excluir sua própria conta.", "erro")
        return redirect(url_for("admin"))
    with get_db() as db:
        db.execute("DELETE FROM simulacoes WHERE usuario_id=?", (uid,))
        db.execute("DELETE FROM usuarios WHERE id=?", (uid,))
    return redirect(url_for("admin"))

# ─────────────────────────────────────────────────────────────────────────────
# ROTAS — PERFIL
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/perfil", methods=["GET","POST"])
@login_required
def perfil():
    u = usuario_atual()
    if request.method == "POST":
        novo_nome = request.form.get("nome","").strip()
        nova_senha = request.form.get("nova_senha","")
        conf_senha = request.form.get("confirmar","")
        atual_senha = request.form.get("senha_atual","")
        with get_db() as db:
            user = db.execute("SELECT * FROM usuarios WHERE id=?",
                              (session["user_id"],)).fetchone()
            if not check_password_hash(user["senha"], atual_senha):
                flash("Senha atual incorreta.", "erro")
            else:
                if nova_senha:
                    if nova_senha != conf_senha:
                        flash("As senhas novas não coincidem.", "erro")
                        return render_template("perfil.html", usuario=u)
                    if len(nova_senha) < 6:
                        flash("Senha deve ter ao menos 6 caracteres.", "erro")
                        return render_template("perfil.html", usuario=u)
                    db.execute("UPDATE usuarios SET nome=?,senha=? WHERE id=?",
                               (novo_nome, generate_password_hash(nova_senha), session["user_id"]))
                else:
                    db.execute("UPDATE usuarios SET nome=? WHERE id=?",
                               (novo_nome, session["user_id"]))
                session["nome"] = novo_nome
                flash("Perfil atualizado!", "ok")
    return render_template("perfil.html", usuario=usuario_atual())

if __name__ == "__main__":
    print("\n" + "═"*52)
    print("  SIMULADOR ELEITORAL ES — SaaS")
    print("  Acesse: http://localhost:5000")
    print("  Admin:  admin@simulador.es / admin123")
    print("═"*52 + "\n")
    app.run(debug=True, port=5000)
