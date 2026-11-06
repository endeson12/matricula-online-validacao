# Matrícula online

Exercício prático de validação de dados usando um formulário de matrícula em um curso de informática.

**Demonstração:** https://matricula-online-validacao.vercel.app

## Funcionalidades

- Informar nome, e-mail, nascimento e turma.
- Validar os dados antes de gravar.
- Conferir inscrições abertas e vagas.
- Impedir matrícula repetida na mesma turma.
- Mostrar confirmação ou motivo do erro.
- Listar matrículas realizadas e limpar os dados de teste.

## Quatro níveis de validação

| Nível | Exemplo | Tratamento |
|---|---|---|
| Sintático | E-mail incompleto ou data inválida | Indicar o campo, sem gravar. |
| Semântico | Nascimento no futuro | Pedir correção, sem gravar. |
| Negócio | Turma lotada ou inscrições encerradas | Recusar e orientar outra turma. |
| Integridade | Turma inexistente ou matrícula repetida | Recusar conflito e desfazer a transação. |

## Organização

- `public/`: formulário online com HTML, CSS e JavaScript. Os dados são guardados no **IndexedDB deste navegador**, sem API e sem banco compartilhado entre visitantes.
- `python/`: versão com **API Python e banco SQLite**, para executar localmente.
- `tests/`: testes JavaScript e teste opcional no navegador.
- `docs/`: roteiro de apresentação e instruções da versão Python.

## Executar a versão Python

Com Python 3.10 ou superior:

```sh
cd python
python app.py
```

No Windows, também pode usar `py app.py`. Abra **http://127.0.0.1:8000** e mantenha o terminal aberto. Não é necessário instalar bibliotecas adicionais.

### Fluxo até o banco

Formulário → API → validações → BEGIN IMMEDIATE → conferir vaga e integridade → gravar aluno/matrícula e reduzir vaga → COMMIT → comprovante.

Se ocorrer falha durante a transação: **ROLLBACK**, sem gravação parcial. SQLite serializa a escrita no banco inteiro, não apenas uma turma. A versão online usa uma transação IndexedDB e só confirma depois da conclusão.

## Testar

Na raiz do repositório:

```sh
python -m unittest discover -s python -v
npm test
```

O primeiro comando executa os 18 testes da API/SQLite; o segundo, os 11 testes JavaScript (Node.js 20+). Há também `tests/browser_qa.py`, opcional, que usa Playwright.

## Observações

Use somente dados fictícios, como `ana@example.com`. A versão online não envia os dados para uma API; limpar o armazenamento do navegador remove os registros. É um exercício acadêmico, sem autenticação e não pronto para produção.

O exemplo foi inspirado no domínio de matrícula do SIGAA/UFRN, sem vínculo institucional nem uso do código da universidade.
