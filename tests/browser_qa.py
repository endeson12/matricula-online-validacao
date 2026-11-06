"""QA opcional: pip install playwright; playwright install chromium.
Executar da raiz: python tests/browser_qa.py
Usa somente alunos fictícios e banco isolado do navegador de teste.
"""
import functools
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright
import shutil

ROOT=Path(__file__).resolve().parents[1]
server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(SimpleHTTPRequestHandler,directory=str(ROOT/'public')))
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
checks=[]
try:
 with sync_playwright() as p:
  executable=shutil.which('chromium') or shutil.which('google-chrome')
  browser=p.chromium.launch(headless=True,**({'executable_path':executable} if executable else {}),args=['--no-sandbox'])
  context=browser.new_context(viewport={'width':1440,'height':1050})
  page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  base=f'http://127.0.0.1:{server.server_port}'
  page.goto(base,wait_until='networkidle');page.locator('#turmas .course').first.wait_for()
  checks.append('Página e IndexedDB inicializam')
  page.locator('details').evaluate('(e)=>e.open=true')
  page.locator('[data-cenario=email]').click();page.locator('#enviar').click()
  page.wait_for_function("document.querySelector('#resultado').textContent.includes('Sintático')")
  assert page.locator('#email').input_value()=='ana@';checks.append('Sintático recusa e preserva campos')
  page.locator('[data-cenario=futuro]').click();page.locator('#enviar').click()
  page.wait_for_function("document.querySelector('#resultado').textContent.includes('Semântico')");checks.append('Semântico recusa futuro')
  page.locator('[data-cenario=fechada]').click();page.locator('#enviar').click()
  page.wait_for_function("document.querySelector('#resultado').textContent.includes('Negócio')");checks.append('Negócio recusa turma fechada')
  page.locator('details').evaluate('(e)=>e.open=true');page.locator('[data-cenario=valido]').click();page.locator('#enviar').click()
  page.wait_for_function("document.querySelector('#resultado').classList.contains('success')")
  assert page.locator('#total').inner_text()=='1';checks.append('Matrícula confirmada com comprovante')
  page.reload(wait_until='networkidle');page.wait_for_function("document.querySelector('#total').textContent==='1'");checks.append('Persistência após recarregar')
  page.locator('details').evaluate('(e)=>e.open=true');page.locator('[data-cenario=valido]').click();page.locator('#enviar').click()
  page.wait_for_function("document.querySelector('#resultado').textContent.includes('Integridade')");checks.append('Duplicidade recusada')
  page.once('dialog',lambda d:d.accept());page.locator('#reiniciar').click()
  page.wait_for_function("document.querySelector('#total').textContent==='0'");checks.append('Reset só após confirmação')
  result=page.evaluate('''async()=>{
   const s=await import('/store.mjs');await s.reiniciar();
   const original=IDBObjectStore.prototype.add;
   IDBObjectStore.prototype.add=function(...args){if(this.name==='matriculas')throw new DOMException('Falha de teste','ConstraintError');return original.apply(this,args);};
   let falhou=false;
   try{await s.matricular({nome:'Ana Teste',email:'ana@example.com',nascimento:'2000-01-15',turma_id:1});}catch(e){falhou=e.nivel==='integridade';}finally{IDBObjectStore.prototype.add=original;}
   const estado=await s.listar();const db=await s.abrirBanco();const alunos=await new Promise((resolve,reject)=>{const r=db.transaction('alunos').objectStore('alunos').count();r.onsuccess=()=>resolve(r.result);r.onerror=reject;});
   return {falhou,vagas:estado.turmas.find(t=>t.id===1).vagas,matriculas:estado.matriculas.length,alunos};
  }''')
  assert result=={'falhou':True,'vagas':3,'matriculas':0,'alunos':0},result
  checks.append('Abort real desfaz aluno, matrícula e redução da vaga')
  other=context.new_page();other.goto(base,wait_until='networkidle')
  # Disparar duas operações sem esperar o primeiro resultado, em abas diferentes.
  run='''nome=>{window.tentativa=import('/store.mjs').then(s=>s.matricular({nome,email:nome.toLowerCase()+'@example.com',nascimento:'2000-01-15',turma_id:3})).then(()=>({ok:true})).catch(e=>({ok:false,nivel:e.nivel}));}'''
  page.evaluate(run,'Ana');other.evaluate(run,'Bruno')
  results=[page.evaluate('window.tentativa'),other.evaluate('window.tentativa')]
  assert sum(r['ok'] for r in results)==1,results
  assert [r for r in results if not r['ok']][0]['nivel']=='negocio'
  state=page.evaluate("async()=> (await import('/store.mjs')).listar()")
  assert len(state['matriculas'])==1 and next(t for t in state['turmas'] if t['id']==3)['vagas']==0
  checks.append('Duas abas: uma única confirmação para a última vaga')
  page.evaluate("async()=> (await import('/store.mjs')).reiniciar()")
  page.reload(wait_until='networkidle');page.locator('details').evaluate('(e)=>e.open=true');page.locator('[data-cenario=valido]').click();page.locator('#enviar').click()
  page.wait_for_function("document.querySelector('#resultado').classList.contains('success')")
  page.screenshot(path=str(ROOT/'docs/preview-desktop.png'),full_page=True)
  page.set_viewport_size({'width':390,'height':844});page.reload(wait_until='networkidle')
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Overflow mobile'
  page.screenshot(path=str(ROOT/'docs/preview-mobile.png'),full_page=True)
  checks.append('Layout móvel sem rolagem horizontal')
  assert not errors,errors;checks.append('Sem exceções JavaScript')
  browser.close()
 print(json.dumps({'status':'PASS','checks':checks},ensure_ascii=False,indent=2))
finally:
 server.shutdown();server.server_close();thread.join()
