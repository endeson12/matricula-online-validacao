# Roteiro para apresentar ao professor

## 1. Escolha do formulário

“Escolhi uma matrícula em um curso de informática. O aluno informa nome, e-mail, nascimento e turma. Este é um exercício prático, não o sistema real de uma universidade.”

## 2. Os quatro níveis e suas falhas

1. Clique em **E-mail inválido**, depois em **Validar e matricular**: o formato `ana@` é rejeitado. É a validação sintática. Nada é gravado e os campos continuam preenchidos.
2. Clique em **Data futura** e valide: a data tem formato válido, mas não faz sentido como nascimento. É a validação semântica.
3. Clique em **Turma fechada** e valide: os dados podem estar corretos, mas a regra não permite a matrícula. Escolher outra turma é a saída.
4. Clique em **Dados válidos** e confirme. Depois reenvie os mesmos dados: a matrícula repetida é rejeitada por integridade. A vaga não é descontada novamente.

## 3. Mostre o pipeline

“Na implementação Python, o formulário envia à API. A API repete as verificações e inicia uma transação. Confere existência, duplicidade e regras atuais, cadastra o aluno se necessário, reduz a vaga e grava a matrícula. O comprovante só é emitido depois do commit. Se houver falha, o rollback desfaz as alterações.”

**Atenção:** a demonstração online roda no navegador com IndexedDB. Não diga que a Vercel está executando a API Python ou usando um SQLite compartilhado. A versão completa da API está na pasta `python/` e pode ser executada localmente.

## 4. Última vaga

A turma noturna começa com uma vaga. Abra duas abas na mesma origem e tente matricular dois alunos fictícios diferentes. Apenas uma matrícula é confirmada. As transações de escrita que abrangem os mesmos object stores são serializadas no IndexedDB. Dispositivos diferentes não compartilham o banco desta demonstração.

O teste automatizado `tests/browser_qa.py` também provoca essa disputa. A versão Python testa o mesmo cenário com conexões SQLite concorrentes.

## 5. Se pedirem para mostrar o código

- `public/store.mjs`: `validar()` contém os dois primeiros níveis; `matricular()` aplica regras, verifica integridade e realiza a transação online.
- `python/app.py`: `validar()` valida sem gravar; `matricular()` implementa a API com transação SQLite; `iniciar_banco()` define `FOREIGN KEY`, `UNIQUE` e `CHECK`.
- `python/test_app.py`: teste de rollback força falha depois de reduzir vaga e verifica que tudo voltou ao estado anterior.

## Frase final

“Formato correto não garante dado coerente. Dado coerente não garante permissão pela regra. E toda confirmação precisa manter os registros consistentes.”
