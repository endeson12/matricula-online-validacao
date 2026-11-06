import { listar, matricular, reiniciar, Falha } from "./store.mjs";
const $ = (s) => document.querySelector(s),
  form = $("#form"),
  botao = $("#enviar");
const nomes = {
  sintatico: "Sintático",
  semantico: "Semântico",
  negocio: "Negócio",
  integridade: "Integridade",
  persistencia: "Persistência",
};
const canal = globalThis.BroadcastChannel
  ? new BroadcastChannel("matricula-lab")
  : null;
function el(tag, texto, classe) {
  const e = document.createElement(tag);
  if (texto !== undefined) e.textContent = texto;
  if (classe) e.className = classe;
  return e;
}
function resultado(titulo, texto, tipo = "") {
  const caixa = $("#resultado");
  caixa.className = "result " + tipo;
  caixa.replaceChildren(el("strong", titulo), el("p", texto));
}
function niveis(falha = null, sucesso = false) {
  // Não afirmar que um nível passou se o fluxo parou antes de verificá-lo.
  const anteriores =
    falha === "semantico"
      ? ["sintatico"]
      : falha === "negocio" || falha === "integridade"
        ? ["sintatico", "semantico"]
        : [];
  document.querySelectorAll("[data-nivel]").forEach((item) => {
    const n = item.dataset.nivel;
    item.className =
      sucesso || anteriores.includes(n) ? "ok" : n === falha ? "fail" : "";
    item.querySelector(".state").textContent =
      sucesso || anteriores.includes(n)
        ? "Validado"
        : n === falha
          ? "Rejeitado"
          : "Aguardando";
  });
}
async function atualizar() {
  const { turmas, matriculas } = await listar(),
    selecao = $("#turma_id"),
    atual = selecao.value;
  selecao.replaceChildren(new Option("Selecione uma turma", ""));
  const lista = $("#turmas");
  lista.replaceChildren();
  for (const t of turmas) {
    selecao.add(new Option(`${t.nome} · ${t.periodo.split(" · ")[0]}`, t.id));
    const item = el("div", undefined, "course"),
      info = el("div");
    info.append(el("strong", t.nome), el("small", t.periodo));
    let texto = t.inscricoes_abertas
      ? `${t.vagas} vaga${t.vagas === 1 ? "" : "s"}`
      : "Encerrada";
    const pill = el(
      "span",
      texto,
      "pill" +
        (!t.inscricoes_abertas || t.vagas === 0
          ? " closed"
          : t.vagas === 1
            ? " last"
            : ""),
    );
    item.append(info, pill);
    lista.append(item);
  }
  selecao.value = atual;
  $("#total").textContent = String(matriculas.length);
  const historico = $("#historico");
  historico.replaceChildren();
  historico.className = matriculas.length ? "" : "empty";
  if (!matriculas.length)
    historico.textContent =
      "As matrículas aparecem aqui somente depois da confirmação da transação.";
  for (const m of [...matriculas].reverse()) {
    const linha = el("div", undefined, "enrollment"),
      info = el("div");
    info.append(el("strong", m.aluno), el("small", m.turma));
    linha.append(
      info,
      el("span", `CONFIRMADA · #${String(m.id).padStart(3, "0")}`),
    );
    historico.append(linha);
  }
}
canal?.addEventListener("message", () => atualizar().catch(() => {}));
form.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  botao.disabled = true;
  document
    .querySelectorAll(".field-error")
    .forEach((e) => (e.textContent = ""));
  form
    .querySelectorAll("input,select")
    .forEach((e) => e.removeAttribute("aria-invalid"));
  const entrada = {
    nome: form.elements.nome.value,
    email: form.elements.email.value,
    nascimento: form.elements.nascimento.value,
    turma_id: Number(form.elements.turma_id.value),
  };
  try {
    const resposta = await matricular(entrada);
    niveis(null, true);
    const c = resposta.comprovante;
    resultado(
      "Matrícula confirmada.",
      `Comprovante #${String(c.id).padStart(3, "0")} · ${c.aluno}\n${c.turma}\n${c.vagas_restantes} vaga(s) restante(s). Transação confirmada.`,
      "success",
    );
    $("#resposta-json").textContent = JSON.stringify(resposta, null, 2);
    canal?.postMessage("atualizar");
  } catch (erro) {
    const falha =
      erro instanceof Falha
        ? erro
        : new Falha(
            "persistencia",
            "Não foi possível acessar o armazenamento local. Nenhuma confirmação foi emitida.",
          );
    niveis(falha.nivel);
    resultado(
      `Não confirmada · ${nomes[falha.nivel] || falha.nivel}`,
      falha.message,
      "failure",
    );
    for (const [campo, mensagem] of Object.entries(falha.campos)) {
      const e = $("#erro-" + campo);
      if (e) e.textContent = mensagem;
      form.elements[campo]?.setAttribute("aria-invalid", "true");
    }
    $("#resposta-json").textContent = JSON.stringify(
      {
        sucesso: false,
        nivel: falha.nivel,
        mensagem: falha.message,
        campos: falha.campos,
      },
      null,
      2,
    );
  } finally {
    botao.disabled = false;
    try {
      await atualizar();
    } catch {
      resultado(
        "Armazenamento indisponível.",
        "Verifique se o navegador permite usar IndexedDB.",
        "failure",
      );
    }
  }
});
document.querySelectorAll("[data-cenario]").forEach((button) =>
  button.addEventListener("click", () => {
    const c = button.dataset.cenario;
    form.elements.nome.value = "Ana Teste";
    form.elements.email.value = c === "email" ? "ana@" : "ana@example.com";
    const amanha = new Date();
    amanha.setDate(amanha.getDate() + 1);
    const futura = `${amanha.getFullYear()}-${String(amanha.getMonth() + 1).padStart(2, "0")}-${String(amanha.getDate()).padStart(2, "0")}`;
    form.elements.nascimento.value = c === "futuro" ? futura : "2000-01-15";
    form.elements.turma_id.value = c === "fechada" ? "2" : "1";
    resultado(
      "Cenário preenchido.",
      "Clique em “Validar e matricular” para executar as verificações.",
    );
    niveis();
    document
      .querySelectorAll(".field-error")
      .forEach((e) => (e.textContent = ""));
    form
      .querySelectorAll("input,select")
      .forEach((e) => e.removeAttribute("aria-invalid"));
  }),
);
$("#reiniciar").addEventListener("click", async () => {
  if (
    !confirm(
      "Apagar os dados fictícios desta demonstração neste navegador e repor as vagas?",
    )
  )
    return;
  try {
    await reiniciar();
    form.reset();
    niveis();
    document
      .querySelectorAll(".field-error")
      .forEach((e) => (e.textContent = ""));
    form
      .querySelectorAll("input,select")
      .forEach((e) => e.removeAttribute("aria-invalid"));
    $("#resposta-json").textContent = "Nenhuma operação realizada.";
    resultado(
      "Demonstração reiniciada.",
      "As vagas foram repostas e as matrículas locais removidas.",
    );
    await atualizar();
    canal?.postMessage("atualizar");
  } catch {
    resultado(
      "Não foi possível reiniciar.",
      "O navegador não permitiu alterar o banco local.",
      "failure",
    );
  }
});
atualizar().catch(() =>
  resultado(
    "Armazenamento indisponível.",
    "Abra em um navegador com IndexedDB habilitado.",
    "failure",
  ),
);
