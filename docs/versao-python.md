# Matrícula online — validação de dados

Implementação didática baseada em `Roteiro_Didatico.docx` e `Slides_Didaticos.pdf` do ZIP enviado. Referência de domínio: matrícula do SIGAA/UFRN, adaptada a um curso livre. Não é código do SIGAA nem integração com a universidade.

## Executar

Requisito: **Python 3.10 ou superior**, sem bibliotecas externas.

1. Extraia este ZIP em uma pasta.
2. Abra o terminal nessa pasta.
3. Execute `python app.py` (no Windows, também pode ser `py app.py`; no Linux, `python3 app.py`).
4. Abra **http://127.0.0.1:8000** no navegador.
5. Para parar, pressione Ctrl+C no terminal.

O SQLite cria `matriculas.db` automaticamente. Não precisa instalar servidor de banco. Reiniciar o programa **não repõe vagas** nem apaga matrículas.

Para uma nova demonstração sem apagar o banco anterior:

```sh
python app.py --db outra_demonstracao.db --port 8001
```

Abra então http://127.0.0.1:8001. Não reutilize o mesmo arquivo se quiser um cenário vazio.

## Os quatro requisitos do exercício

### 1. Formulário/API escolhido

Matrícula em curso de informática: nome, e-mail, nascimento e turma. O formulário cria ou reutiliza o cadastro do aluno e efetua sua matrícula, tudo na mesma transação.

### 2 e 3. Validação por nível e estratégia de falha

| Nível | Verificação implementada | Estratégia de falha |
|---|---|---|
| Sintático (formato) | Campos obrigatórios e tipos; e-mail completo; data válida AAAA-MM-DD; turma inteira positiva | HTTP 422 com indicação dos campos; JSON malformado retorna 400. Não abre transação nem grava. |
| Semântico (sentido) | Nascimento não pode estar no futuro; nome deve ter ao menos dois caracteres | HTTP 422 com explicação. Não grava; formulário mantém os dados. |
| Negócio (regra) | Inscrições abertas e pelo menos uma vaga, conferidas dentro da transação | HTTP 409 e indicação para escolher outra turma; rollback. |
| Integridade (registro) | Turma existente, aluno identificado por e-mail, matrícula sem repetição; FOREIGN KEY, UNIQUE e CHECK reais no banco | Turma ausente: 404. Conflito: 409. Rollback integral, sem aluno órfão, vaga perdida ou matrícula duplicada. |

Também há tratamento de banco ocupado (503, para tentar depois) e erro de persistência (500, sem expor SQL). O front-end ajuda a validar, mas a API repete as verificações porque o navegador pode ser contornado.

### 4. Pipeline até o banco

```text
FORMULÁRIO (preserva dados em caso de erro)
    ↓ POST /api/matriculas
API: sintaxe → semântica
    ├─ falhou → 400/422 + campos; nada gravado
    ↓
BEGIN IMMEDIATE (bloqueio de escrita)
    ↓
Existência da turma/aluno + duplicidade
    ↓
Inscrições abertas + vagas atuais
    ↓
Cadastrar aluno se necessário
    ↓
Reduzir vaga + inserir matrícula (FK, UNIQUE e CHECK)
    ├─ falhou → ROLLBACK de TODAS as alterações
    ↓
COMMIT
    ↓
201 + COMPROVANTE
```

**Diferença em relação ao PostgreSQL dos slides:** este código usa SQLite para facilitar a execução. `BEGIN IMMEDIATE` serializa os escritores no banco inteiro; não equivale a bloqueio por linha. Em PostgreSQL, o padrão correspondente pode usar `BEGIN` e `SELECT ... FOR UPDATE` para bloquear a turma. Não execute `FOR UPDATE` no SQLite.

## Demonstração para o professor

Use somente dados fictícios, por exemplo Ana Teste, `ana@example.com`, 2000-01-15.

1. **Sucesso:** escolha a turma 1 (manhã). Mostre o comprovante e a redução da vaga.
2. **Sintático:** tente e-mail `ana@`. O navegador aponta o erro; a API também o rejeita se chamada diretamente (teste automatizado).
3. **Semântico:** informe um nascimento futuro. A API explica e nada é gravado.
4. **Negócio:** selecione a turma 2, com inscrições encerradas. Recebe recusa e orientação para outra turma.
5. **Integridade:** reenvie exatamente os mesmos dados para a mesma turma. Recebe conflito de matrícula duplicada; não perde outra vaga.
6. **Última vaga:** a turma 3 tem uma única vaga. Dois alunos diferentes não conseguem ocupá-la juntos; o teste concorrente automatizado demonstra isso.

Um mesmo aluno pode cursar turmas diferentes, mas não repetir a mesma turma. Não se proíbem nomes iguais: pessoas diferentes podem ter o mesmo nome. O e-mail é o identificador didático do cadastro; dados divergentes nesse e-mail são recusados, não sobrescritos.

## Testes

```sh
python -m unittest -v
```

Os testes usam bancos temporários isolados, não alteram o banco da demonstração. Incluem validações, constraints reais, rollback provocado depois de reduzir vaga, concorrência na última vaga e requisições HTTP reais ao formulário/API.

## Arquivos

- `app.py`: API HTTP, validações, transação, criação do banco e servidor.
- `index.html`: formulário e desenho do pipeline.
- `test_app.py`: testes automatizados.
- `README.md`: requisitos, execução e roteiro de apresentação.
- `resultado-testes.txt`: saída real dos testes realizados na entrega.

## Limites

Exemplo local acadêmico, **não pronto para produção**: sem autenticação, autorização, verificação de propriedade do e-mail, recuperação de cadastro ou controles completos de privacidade. A verificação de e-mail é de formato, não de existência da caixa postal. Não use dados pessoais reais ou exponha o servidor publicamente. Não há idade mínima inventada, pois o material não exige uma.
