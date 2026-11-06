import { listar, matricular, reiniciar, Falha } from './store.mjs';

const form = document.getElementById('form');
const botao = document.getElementById('enviar');
const mensagem = document.getElementById('resultado');
const nomes = { sintatico: 'Sintático', semantico: 'Semântico', negocio: 'Negócio', integridade: 'Integridade', persistencia: 'Persistência' };
const canal = window.BroadcastChannel ? new BroadcastChannel('matricula-lab') : null;

function mostrar(texto, tipo = '') {
  mensagem.textContent = texto;
  mensagem.className = 'result ' + tipo;
}

function limparErros() {
  document.querySelectorAll('.field-error').forEach(campo => campo.textContent = '');
  form.querySelectorAll('input, select').forEach(campo => campo.removeAttribute('aria-invalid'));
}

async function atualizar() {
  const dados = await listar();
  const select = document.getElementById('turma_id');
  const selecionada = select.value;
  select.replaceChildren(new Option('Selecione uma turma', ''));
  const tabela = document.getElementById('turmas');
  tabela.replaceChildren();

  for (const turma of dados.turmas) {
    select.add(new Option(turma.nome + ' — ' + turma.periodo.split(' · ')[0], turma.id));
    const linha = document.createElement('tr');
    linha.className = 'course';
    const nome = document.createElement('td');
    nome.textContent = turma.nome;
    const periodo = document.createElement('small');
    periodo.textContent = turma.periodo;
    nome.append(periodo);
    const situacao = document.createElement('td');
    situacao.textContent = turma.inscricoes_abertas ? turma.vagas + ' vaga(s)' : 'Inscrições encerradas';
    linha.append(nome, situacao);
    tabela.append(linha);
  }
  select.value = selecionada;
  document.getElementById('total').textContent = dados.matriculas.length;
  const historico = document.getElementById('historico');
  historico.replaceChildren();
  if (!dados.matriculas.length) historico.textContent = 'Nenhuma matrícula realizada.';
  for (const matricula of dados.matriculas) {
    const item = document.createElement('div');
    item.className = 'enrollment';
    item.textContent = '#' + matricula.id + ' — ' + matricula.aluno;
    const turma = document.createElement('small');
    turma.textContent = matricula.turma;
    item.append(turma);
    historico.append(item);
  }
}

form.addEventListener('submit', async evento => {
  evento.preventDefault();
  limparErros();
  botao.disabled = true;
  const dados = {
    nome: form.elements.nome.value,
    email: form.elements.email.value,
    nascimento: form.elements.nascimento.value,
    turma_id: Number(form.elements.turma_id.value)
  };
  try {
    const resposta = await matricular(dados);
    const comprovante = resposta.comprovante;
    mostrar('Matrícula confirmada.\nNúmero: ' + comprovante.id + '\nAluno: ' + comprovante.aluno + '\nTurma: ' + comprovante.turma, 'success');
    canal?.postMessage('atualizar');
  } catch (erro) {
    const falha = erro instanceof Falha ? erro : new Falha('persistencia', 'Não foi possível acessar o banco deste navegador.');
    mostrar(nomes[falha.nivel] + ': ' + falha.message, 'failure');
    for (const [campo, texto] of Object.entries(falha.campos)) {
      const aviso = document.getElementById('erro-' + campo);
      if (aviso) aviso.textContent = texto;
      form.elements[campo]?.setAttribute('aria-invalid', 'true');
    }
  } finally {
    botao.disabled = false;
    try { await atualizar(); } catch { mostrar('Não foi possível carregar os dados.', 'failure'); }
  }
});

// Atalhos opcionais para demonstrar os erros em sala.
document.querySelectorAll('[data-cenario]').forEach(botao => {
  botao.addEventListener('click', () => {
    const cenario = botao.dataset.cenario;
    form.elements.nome.value = 'Ana Teste';
    form.elements.email.value = cenario === 'email' ? 'ana@' : 'ana@example.com';
    const amanha = new Date();
    amanha.setDate(amanha.getDate() + 1);
    const dataFutura = amanha.getFullYear() + '-' + String(amanha.getMonth() + 1).padStart(2, '0') + '-' + String(amanha.getDate()).padStart(2, '0');
    form.elements.nascimento.value = cenario === 'futuro' ? dataFutura : '2000-01-15';
    form.elements.turma_id.value = cenario === 'fechada' ? '2' : '1';
    limparErros();
    mostrar('Exemplo preenchido. Clique em Matricular.');
  });
});

document.getElementById('reiniciar').addEventListener('click', async () => {
  if (!confirm('Limpar as matrículas de teste e repor as vagas neste navegador?')) return;
  try {
    await reiniciar();
    form.reset();
    limparErros();
    await atualizar();
    mostrar('Dados de teste removidos. As vagas foram repostas.');
    canal?.postMessage('atualizar');
  } catch { mostrar('Não foi possível limpar os dados.', 'failure'); }
});

canal?.addEventListener('message', () => atualizar().catch(() => {}));
atualizar().catch(() => mostrar('O navegador não permitiu acessar o IndexedDB.', 'failure'));
