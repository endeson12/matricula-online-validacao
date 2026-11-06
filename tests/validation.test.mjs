import test from 'node:test';
import assert from 'node:assert/strict';
import {validar,Falha} from '../public/store.mjs';
const hoje=new Date(2026,10,6);
const aluno={nome:'Ana Teste',email:'ana@example.com',nascimento:'2000-01-15',turma_id:1};
function rejeita(dados,nivel,campo){assert.throws(()=>validar(dados,hoje),e=>e instanceof Falha&&e.nivel===nivel&&(!campo||campo in e.campos));}
test('normaliza espaços e e-mail',()=>assert.deepEqual(validar({...aluno,nome:' Ana Teste ',email:' ANA@EXAMPLE.COM '},hoje),aluno));
test('rejeita e-mail incompleto',()=>rejeita({...aluno,email:'ana@'},'sintatico','email'));
test('rejeita campos ausentes',()=>rejeita({},'sintatico','nome'));
test('rejeita tipo incorreto de turma',()=>rejeita({...aluno,turma_id:'1'},'sintatico','turma_id'));
test('rejeita booleano como turma',()=>rejeita({...aluno,turma_id:true},'sintatico','turma_id'));
test('rejeita data impossível',()=>rejeita({...aluno,nascimento:'2026-02-30'},'sintatico','nascimento'));
test('rejeita formato de data errado',()=>rejeita({...aluno,nascimento:'15/01/2000'},'sintatico','nascimento'));
test('rejeita nascimento futuro',()=>rejeita({...aluno,nascimento:'2099-01-01'},'semantico','nascimento'));
test('rejeita nome de uma letra',()=>rejeita({...aluno,nome:'A'},'semantico','nome'));
test('aceita ano bissexto válido',()=>assert.equal(validar({...aluno,nascimento:'2000-02-29'},hoje).nascimento,'2000-02-29'));
test('rejeita entrada não objeto',()=>rejeita(null,'sintatico'));
