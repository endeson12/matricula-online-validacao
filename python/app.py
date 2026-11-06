"""Matrícula didática: Python 3.10+, biblioteca padrão e SQLite.
Execute: python app.py | Teste: python -m unittest -v
"""
import argparse
import json
import re
import sqlite3
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent


class Falha(Exception):
    def __init__(self, status, nivel, mensagem, campos=None):
        self.status = status
        self.dados = {"sucesso": False, "nivel": nivel, "mensagem": mensagem,
                      "campos": campos or {}}
        super().__init__(mensagem)


def conectar(db):
    con = sqlite3.connect(str(db), timeout=3, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def iniciar_banco(db):
    con = conectar(db)
    try:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS alunos (
            id INTEGER PRIMARY KEY,
            nome TEXT NOT NULL CHECK(length(trim(nome)) >= 2),
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            nascimento TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS turmas (
            id INTEGER PRIMARY KEY,
            nome TEXT NOT NULL,
            capacidade INTEGER NOT NULL CHECK(capacidade > 0),
            vagas INTEGER NOT NULL CHECK(vagas >= 0 AND vagas <= capacidade),
            inscricoes_abertas INTEGER NOT NULL CHECK(inscricoes_abertas IN (0, 1))
        );
        CREATE TABLE IF NOT EXISTS matriculas (
            id INTEGER PRIMARY KEY,
            aluno_id INTEGER NOT NULL REFERENCES alunos(id),
            turma_id INTEGER NOT NULL REFERENCES turmas(id),
            criada_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(aluno_id, turma_id)
        );
        ''')
        con.executemany('''INSERT OR IGNORE INTO turmas
            (id,nome,capacidade,vagas,inscricoes_abertas) VALUES (?,?,?,?,?)''', [
            (1, 'Informática básica — manhã', 2, 2, 1),
            (2, 'Informática básica — tarde (inscrições encerradas)', 2, 2, 0),
            (3, 'Informática básica — noite (última vaga)', 1, 1, 1),
        ])
    finally:
        con.close()


def validar(entrada):
    """Níveis 1 e 2: sem abrir transação e sem gravar dados."""
    if not isinstance(entrada, dict):
        raise Falha(422, 'sintatico', 'Envie um objeto JSON com os campos do formulário.')
    campos = {}
    for campo in ('nome', 'email', 'nascimento'):
        if not isinstance(entrada.get(campo), str) or not entrada[campo].strip():
            campos[campo] = 'Informe um texto não vazio.'
    if type(entrada.get('turma_id')) is not int or entrada['turma_id'] <= 0:
        campos['turma_id'] = 'Informe um identificador inteiro positivo.'
    if not campos.get('email') and (
        len(entrada['email'].strip()) > 254 or
        not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', entrada['email'].strip())
    ):
        campos['email'] = 'E-mail incompleto ou com formato inválido.'
    nascimento = None
    if not campos.get('nascimento'):
        valor = entrada['nascimento'].strip()
        try:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', valor):
                raise ValueError()
            nascimento = date.fromisoformat(valor)
        except ValueError:
            campos['nascimento'] = 'Informe uma data válida no formato AAAA-MM-DD.'
    if not campos.get('nome') and len(entrada['nome'].strip()) > 120:
        campos['nome'] = 'Use no máximo 120 caracteres.'
    if campos:
        raise Falha(422, 'sintatico', 'Corrija os campos indicados. Nada foi gravado.', campos)

    # Nível 2: formato válido não significa valor com sentido.
    if nascimento > date.today():
        campos['nascimento'] = 'O nascimento não pode estar no futuro.'
    if len(entrada['nome'].strip()) < 2:
        campos['nome'] = 'Informe um nome com pelo menos dois caracteres.'
    if campos:
        raise Falha(422, 'semantico', 'Confira o sentido dos dados. Nada foi gravado.', campos)
    return {'nome': entrada['nome'].strip(), 'email': entrada['email'].strip().lower(),
            'nascimento': nascimento.isoformat(), 'turma_id': entrada['turma_id']}


def matricular(db, entrada):
    dados = validar(entrada)
    con = conectar(db)
    try:
        # Serializa escritores ANTES de consultar vagas. Em PostgreSQL, pode-se
        # usar BEGIN + SELECT da turma FOR UPDATE (bloqueio por linha).
        con.execute('BEGIN IMMEDIATE')
        turma = con.execute('SELECT * FROM turmas WHERE id=?', (dados['turma_id'],)).fetchone()
        if turma is None:
            raise Falha(404, 'integridade', 'A turma informada não existe.',
                        {'turma_id': 'Selecione uma turma existente.'})
        aluno = con.execute('SELECT * FROM alunos WHERE email=?', (dados['email'],)).fetchone()
        if aluno is not None:
            if aluno['nome'] != dados['nome'] or aluno['nascimento'] != dados['nascimento']:
                raise Falha(409, 'integridade', 'Este e-mail já possui dados diferentes. '
                            'Confira os dados; o cadastro existente não será alterado.')
            if con.execute('SELECT 1 FROM matriculas WHERE aluno_id=? AND turma_id=?',
                           (aluno['id'], turma['id'])).fetchone():
                raise Falha(409, 'integridade', 'Este aluno já está matriculado nesta turma.')

        # Nível 3: regras atuais, verificadas dentro da transação.
        if not turma['inscricoes_abertas']:
            raise Falha(409, 'negocio', 'Inscrições encerradas. Selecione outra turma.')
        if turma['vagas'] <= 0:
            raise Falha(409, 'negocio', 'Turma lotada. Selecione outra turma.')

        # O formulário também cadastra o aluno. Esse cadastro participa da mesma
        # transação: uma falha não deixa aluno ou vaga parcialmente gravados.
        if aluno is None:
            aluno_id = con.execute('INSERT INTO alunos(nome,email,nascimento) VALUES (?,?,?)',
                (dados['nome'], dados['email'], dados['nascimento'])).lastrowid
        else:
            aluno_id = aluno['id']
        con.execute('UPDATE turmas SET vagas=vagas-1 WHERE id=?', (turma['id'],))
        # Nível 4: FOREIGN KEY, UNIQUE e CHECK são defesas reais no banco.
        matricula_id = con.execute('INSERT INTO matriculas(aluno_id,turma_id) VALUES (?,?)',
                                  (aluno_id, turma['id'])).lastrowid
        con.commit()
        # Comprovante somente DEPOIS do commit.
        return {'sucesso': True, 'mensagem': 'Matrícula confirmada.',
                'comprovante': {'matricula_id': matricula_id, 'aluno': dados['nome'],
                               'turma': turma['nome'], 'vagas_restantes': turma['vagas'] - 1}}
    except Falha:
        con.rollback()
        raise
    except sqlite3.IntegrityError:
        con.rollback()
        raise Falha(409, 'integridade', 'Conflito na gravação. A operação foi desfeita.') from None
    except sqlite3.OperationalError as erro:
        con.rollback()
        if 'locked' in str(erro).lower() or 'busy' in str(erro).lower():
            raise Falha(503, 'persistencia', 'Banco ocupado. Tente novamente em instantes.') from None
        raise Falha(500, 'persistencia', 'Não foi possível gravar. A operação foi desfeita.') from None
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def criar_handler(db):
    class Handler(BaseHTTPRequestHandler):
        def json(self, status, dados):
            corpo = json.dumps(dados, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(corpo)))
            self.send_header('Cache-Control', 'no-store')
            if status == 503:
                self.send_header('Retry-After', '1')
            self.end_headers()
            self.wfile.write(corpo)

        def do_GET(self):
            caminho = urlsplit(self.path).path
            if caminho == '/':
                corpo = (ROOT / 'index.html').read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)
            elif caminho == '/api/turmas':
                con = conectar(db)
                try:
                    turmas = [dict(r) for r in con.execute('SELECT * FROM turmas ORDER BY id')]
                finally:
                    con.close()
                self.json(200, {'turmas': turmas})
            else:
                self.json(404, {'sucesso': False, 'mensagem': 'Rota não encontrada.'})

        def do_POST(self):
            if urlsplit(self.path).path != '/api/matriculas':
                self.json(404, {'sucesso': False, 'mensagem': 'Rota não encontrada.'})
                return
            try:
                if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
                    raise Falha(415, 'sintatico', 'Use Content-Type: application/json.')
                try:
                    tamanho = int(self.headers.get('Content-Length', '0'))
                except ValueError:
                    raise Falha(400, 'sintatico', 'Tamanho da requisição inválido.') from None
                if tamanho <= 0 or tamanho > 16384:
                    raise Falha(413 if tamanho > 16384 else 400, 'sintatico', 'Corpo ausente ou muito grande.')
                try:
                    dados = json.loads(self.rfile.read(tamanho).decode('utf-8'))
                except (ValueError, UnicodeDecodeError):
                    raise Falha(400, 'sintatico', 'JSON inválido. Nada foi gravado.') from None
                self.json(201, matricular(db, dados))
            except Falha as erro:
                self.json(erro.status, erro.dados)
            except Exception:
                # Não expor SQL, caminhos ou detalhes internos ao formulário.
                self.json(500, {'sucesso': False, 'nivel': 'persistencia',
                                'mensagem': 'Falha interna. Matrícula não confirmada.'})

    return Handler


def main():
    parser = argparse.ArgumentParser(description='Demonstração local de matrícula online')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--db', type=Path, default=ROOT / 'matriculas.db')
    args = parser.parse_args()
    iniciar_banco(args.db)
    servidor = ThreadingHTTPServer((args.host, args.port), criar_handler(args.db))
    print(f'Abra http://{args.host}:{args.port} — Ctrl+C para encerrar.', flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()


if __name__ == '__main__':
    main()
