// Camada de domínio + persistência da demonstração online.
// Nenhuma chamada de rede: os dados ficam no IndexedDB deste navegador.
export class Falha extends Error {
  constructor(nivel, mensagem, campos = {}) {
    super(mensagem);
    this.nivel = nivel;
    this.campos = campos;
  }
}
export function validar(entrada, hoje = new Date()) {
  if (!entrada || typeof entrada !== "object" || Array.isArray(entrada))
    throw new Falha("sintatico", "Informe os campos do formulário.");
  const campos = {};
  for (const key of ["nome", "email", "nascimento"])
    if (typeof entrada[key] !== "string" || !entrada[key].trim())
      campos[key] = "Preencha este campo.";
  if (!Number.isInteger(entrada.turma_id) || entrada.turma_id <= 0)
    campos.turma_id = "Selecione uma turma.";
  if (!campos.nome && entrada.nome.trim().length > 120)
    campos.nome = "Use no máximo 120 caracteres.";
  if (
    !campos.email &&
    (entrada.email.trim().length > 254 ||
      !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(entrada.email.trim()))
  )
    campos.email = "Informe um e-mail completo, como ana@example.com.";
  let nascimento;
  if (!campos.nascimento) {
    const valor = entrada.nascimento.trim();
    nascimento = new Date(valor + "T12:00:00Z");
    if (
      !/^\d{4}-\d{2}-\d{2}$/.test(valor) ||
      Number.isNaN(nascimento.valueOf()) ||
      nascimento.toISOString().slice(0, 10) !== valor
    )
      campos.nascimento = "Informe uma data válida no formato AAAA-MM-DD.";
  }
  if (Object.keys(campos).length)
    throw new Falha(
      "sintatico",
      "Confira o formato dos campos. Nada foi gravado.",
      campos,
    );
  const hojeISO = `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, "0")}-${String(hoje.getDate()).padStart(2, "0")}`;
  if (entrada.nascimento.trim() > hojeISO)
    campos.nascimento = "O nascimento não pode estar no futuro.";
  if (entrada.nome.trim().length < 2)
    campos.nome = "Informe pelo menos dois caracteres.";
  if (Object.keys(campos).length)
    throw new Falha(
      "semantico",
      "O formato passou, mas o valor precisa fazer sentido.",
      campos,
    );
  return {
    nome: entrada.nome.trim(),
    email: entrada.email.trim().toLowerCase(),
    nascimento: entrada.nascimento.trim(),
    turma_id: entrada.turma_id,
  };
}

const iniciais = [
  {
    id: 1,
    nome: "Informática básica",
    periodo: "Manhã · 08h às 10h",
    capacidade: 3,
    vagas: 3,
    inscricoes_abertas: true,
  },
  {
    id: 2,
    nome: "Planilhas na prática",
    periodo: "Tarde · 14h às 16h",
    capacidade: 2,
    vagas: 2,
    inscricoes_abertas: false,
  },
  {
    id: 3,
    nome: "Introdução à programação",
    periodo: "Noite · 19h às 21h",
    capacidade: 1,
    vagas: 1,
    inscricoes_abertas: true,
  },
];
let conexao;
const requisicao = (req) =>
  new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
const concluida = (tx) =>
  new Promise((resolve, reject) => {
    tx.oncomplete = resolve;
    tx.onabort = () => reject(tx.error || new Error("Transação cancelada."));
    tx.onerror = () => {};
  });
export function abrirBanco() {
  if (conexao) return conexao;
  conexao = new Promise((resolve, reject) => {
    if (!globalThis.indexedDB) {
      reject(
        new Falha(
          "persistencia",
          "Seu navegador não disponibiliza armazenamento IndexedDB.",
        ),
      );
      return;
    }
    const req = indexedDB.open("matricula-exercicio-v1", 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      const alunos = db.createObjectStore("alunos", {
        keyPath: "id",
        autoIncrement: true,
      });
      alunos.createIndex("email", "email", { unique: true });
      const turmas = db.createObjectStore("turmas", { keyPath: "id" });
      iniciais.forEach((t) => turmas.put({ ...t }));
      const matriculas = db.createObjectStore("matriculas", {
        keyPath: "id",
        autoIncrement: true,
      });
      matriculas.createIndex("aluno_turma", ["aluno_id", "turma_id"], {
        unique: true,
      });
    };
    req.onsuccess = () => {
      const db = req.result;
      db.onversionchange = () => db.close();
      resolve(db);
    };
    req.onerror = () => {
      conexao = null;
      reject(
        new Falha("persistencia", "Não foi possível abrir o banco local."),
      );
    };
  });
  return conexao;
}
export async function listar() {
  const db = await abrirBanco(),
    tx = db.transaction(["turmas", "matriculas"], "readonly"),
    fim = concluida(tx);
  const turmas = await requisicao(tx.objectStore("turmas").getAll());
  const matriculas = await requisicao(tx.objectStore("matriculas").getAll());
  await fim;
  return { turmas, matriculas };
}
export async function matricular(entrada) {
  const dados = validar(entrada),
    db = await abrirBanco();
  // Transações readwrite que usam os mesmos stores são serializadas, inclusive
  // entre abas da mesma origem. Uma só operação pode ocupar a última vaga.
  const tx = db.transaction(["alunos", "turmas", "matriculas"], "readwrite");
  const fim = concluida(tx);
  fim.catch(() => {});
  try {
    const alunos = tx.objectStore("alunos"),
      turmas = tx.objectStore("turmas"),
      matriculas = tx.objectStore("matriculas");
    const turma = await requisicao(turmas.get(dados.turma_id));
    if (!turma)
      throw new Falha(
        "integridade",
        "A turma não existe. Selecione uma turma válida.",
        { turma_id: "Turma não encontrada." },
      );
    let aluno = await requisicao(alunos.index("email").get(dados.email));
    if (aluno) {
      if (aluno.nome !== dados.nome || aluno.nascimento !== dados.nascimento)
        throw new Falha(
          "integridade",
          "Este e-mail já tem dados diferentes. O cadastro não será sobrescrito.",
        );
      if (
        await requisicao(
          matriculas.index("aluno_turma").get([aluno.id, turma.id]),
        )
      )
        throw new Falha(
          "integridade",
          "Este aluno já está matriculado nesta turma. Nenhuma vaga foi descontada.",
        );
    }
    if (!turma.inscricoes_abertas)
      throw new Falha(
        "negocio",
        "As inscrições desta turma estão encerradas. Escolha outra turma.",
      );
    if (turma.vagas <= 0)
      throw new Falha(
        "negocio",
        "Esta turma está lotada. Escolha outra turma.",
      );
    if (!aluno) {
      const id = await requisicao(
        alunos.add({
          nome: dados.nome,
          email: dados.email,
          nascimento: dados.nascimento,
        }),
      );
      aluno = { id, ...dados };
    }
    // Mantemos os três registros na MESMA transação: falha aborta tudo.
    await requisicao(turmas.put({ ...turma, vagas: turma.vagas - 1 }));
    const comprovante = {
      aluno_id: aluno.id,
      turma_id: turma.id,
      aluno: dados.nome,
      turma: turma.nome,
      criada_em: new Date().toISOString(),
    };
    const id = await requisicao(matriculas.add(comprovante));
    await fim; // Só emitir comprovante após oncomplete (confirmação real).
    return {
      sucesso: true,
      mensagem: "Matrícula confirmada.",
      comprovante: { id, ...comprovante, vagas_restantes: turma.vagas - 1 },
    };
  } catch (erro) {
    try {
      tx.abort();
    } catch {}
    await fim.catch(() => {});
    if (erro instanceof Falha) throw erro;
    throw new Falha(
      "integridade",
      "A gravação apresentou um conflito. Toda a operação foi desfeita.",
    );
  }
}
export async function reiniciar() {
  const db = await abrirBanco(),
    tx = db.transaction(["alunos", "turmas", "matriculas"], "readwrite"),
    fim = concluida(tx);
  tx.objectStore("alunos").clear();
  tx.objectStore("matriculas").clear();
  tx.objectStore("turmas").clear();
  iniciais.forEach((t) => tx.objectStore("turmas").put({ ...t }));
  await fim;
}
