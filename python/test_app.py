import json
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

from app import Falha, conectar, criar_handler, iniciar_banco, matricular


class TestMatricula(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'teste.db'
        iniciar_banco(self.db)
        self.dados = {'nome': 'Ana Teste', 'email': 'ana@example.com',
                      'nascimento': '2000-01-15', 'turma_id': 1}

    def tearDown(self):
        self.tmp.cleanup()

    def consultar(self, sql, args=()):
        con = conectar(self.db)
        try:
            return [tuple(r) for r in con.execute(sql, args).fetchall()]
        finally:
            con.close()

    def falha(self, nivel, status, **mudancas):
        with self.assertRaises(Falha) as cm:
            matricular(self.db, dict(self.dados, **mudancas))
        self.assertEqual(cm.exception.dados['nivel'], nivel)
        self.assertEqual(cm.exception.status, status)
        return cm.exception

    def test_sucesso_com_commit_e_comprovante(self):
        resultado = matricular(self.db, self.dados)
        self.assertTrue(resultado['sucesso'])
        self.assertEqual(resultado['comprovante']['vagas_restantes'], 1)
        self.assertEqual(self.consultar('SELECT count(*) FROM matriculas'), [(1,)])
        self.assertEqual(self.consultar('SELECT count(*) FROM alunos'), [(1,)])

    def test_email_incompleto_sintatico_sem_gravacao(self):
        self.falha('sintatico', 422, email='ana@')
        self.assertEqual(self.consultar('SELECT count(*) FROM alunos'), [(0,)])
        self.assertEqual(self.consultar('SELECT vagas FROM turmas WHERE id=1'), [(2,)])

    def test_tipo_incorreto(self):
        self.falha('sintatico', 422, turma_id=True)
        self.falha('sintatico', 422, nome=123)

    def test_data_impossivel(self):
        self.falha('sintatico', 422, nascimento='2026-02-30')

    def test_data_futura_semantica(self):
        self.falha('semantico', 422, nascimento=(date.today()+timedelta(days=1)).isoformat())

    def test_nome_sem_sentido(self):
        self.falha('semantico', 422, nome='A')

    def test_inscricoes_encerradas(self):
        self.falha('negocio', 409, turma_id=2)
        self.assertEqual(self.consultar('SELECT count(*) FROM alunos'), [(0,)])

    def test_turma_lotada(self):
        matricular(self.db, dict(self.dados, turma_id=3))
        self.falha('negocio', 409, turma_id=3, email='bruno@example.com', nome='Bruno Teste')
        self.assertEqual(self.consultar('SELECT count(*) FROM alunos'), [(1,)])

    def test_turma_inexistente(self):
        self.falha('integridade', 404, turma_id=999)

    def test_matricula_duplicada_nao_reduz_vagas(self):
        matricular(self.db, self.dados)
        self.falha('integridade', 409)
        self.assertEqual(self.consultar('SELECT vagas FROM turmas WHERE id=1'), [(1,)])
        self.assertEqual(self.consultar('SELECT count(*) FROM matriculas'), [(1,)])

    def test_email_com_caixa_diferente_nao_duplica(self):
        matricular(self.db, self.dados)
        self.falha('integridade', 409, email='ANA@EXAMPLE.COM')

    def test_nao_sobrescreve_aluno_existente(self):
        matricular(self.db, self.dados)
        self.falha('integridade', 409, nome='Outra Pessoa', turma_id=3)
        self.assertEqual(self.consultar('SELECT nome FROM alunos'), [('Ana Teste',)])

    def test_rollback_real_apos_reduzir_vaga(self):
        # Força falha NO BANCO após criar aluno e reduzir vaga.
        con = conectar(self.db)
        try:
            con.execute("CREATE TRIGGER falha_teste BEFORE INSERT ON matriculas "
                        "BEGIN SELECT RAISE(ABORT, 'falha de teste'); END")
        finally:
            con.close()
        self.falha('integridade', 409)
        self.assertEqual(self.consultar('SELECT count(*) FROM alunos'), [(0,)])
        self.assertEqual(self.consultar('SELECT count(*) FROM matriculas'), [(0,)])
        self.assertEqual(self.consultar('SELECT vagas FROM turmas WHERE id=1'), [(2,)])

    def test_fk_real_no_banco(self):
        con = conectar(self.db)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute('INSERT INTO matriculas(aluno_id,turma_id) VALUES (999,1)')
        finally:
            con.close()

    def test_unique_real_no_banco(self):
        matricular(self.db, self.dados)
        con = conectar(self.db)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute('INSERT INTO matriculas(aluno_id,turma_id) VALUES (1,1)')
        finally:
            con.close()

    def test_check_impede_vagas_negativas(self):
        con = conectar(self.db)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute('UPDATE turmas SET vagas=-1 WHERE id=1')
        finally:
            con.close()

    def test_duas_pessoas_ultima_vaga_concorrente(self):
        barreira = threading.Barrier(2)
        def tentar(nome):
            dados = dict(self.dados, nome=nome, email=nome.lower()+'@example.com', turma_id=3)
            barreira.wait(timeout=5)
            try:
                matricular(self.db, dados)
                return 201
            except Falha as erro:
                self.assertEqual(erro.dados['nivel'], 'negocio')
                return erro.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(tentar, 'Ana')
            b = pool.submit(tentar, 'Bruno')
            self.assertEqual(sorted([a.result(), b.result()]), [201, 409])
        self.assertEqual(self.consultar('SELECT vagas FROM turmas WHERE id=3'), [(0,)])
        self.assertEqual(self.consultar('SELECT count(*) FROM matriculas WHERE turma_id=3'), [(1,)])
        self.assertEqual(self.consultar('SELECT count(*) FROM alunos'), [(1,)])

    def test_http_formulario_api_json_e_persistencia(self):
        servidor = ThreadingHTTPServer(('127.0.0.1', 0), criar_handler(self.db))
        thread = threading.Thread(target=servidor.serve_forever, daemon=True)
        thread.start()
        cliente = HTTPConnection('127.0.0.1', servidor.server_port, timeout=5)
        try:
            cliente.request('GET', '/')
            r = cliente.getresponse()
            self.assertEqual(r.status, 200)
            self.assertIn('Matrícula'.encode(), r.read())
            cliente.request('GET', '/api/turmas')
            r = cliente.getresponse()
            self.assertEqual(r.status, 200)
            self.assertEqual(len(json.loads(r.read())['turmas']), 3)
            cliente.request('POST', '/api/matriculas', '{malformado',
                            {'Content-Type': 'application/json'})
            r = cliente.getresponse()
            self.assertEqual(r.status, 400)
            r.read()
            cliente.request('POST', '/api/matriculas', json.dumps(self.dados),
                            {'Content-Type': 'application/json'})
            r = cliente.getresponse()
            self.assertEqual(r.status, 201)
            self.assertTrue(json.loads(r.read())['sucesso'])
            self.assertEqual(self.consultar('SELECT count(*) FROM matriculas'), [(1,)])
            cliente.request('POST', '/api/matriculas', json.dumps(self.dados),
                            {'Content-Type': 'application/json'})
            r = cliente.getresponse()
            self.assertEqual(r.status, 409)
            self.assertEqual(json.loads(r.read())['nivel'], 'integridade')
        finally:
            cliente.close()
            servidor.shutdown()
            servidor.server_close()
            thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main(verbosity=2)
