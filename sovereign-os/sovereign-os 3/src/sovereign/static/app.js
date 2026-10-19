"use strict";
const $=id=>document.getElementById(id);
const state={ records:[], claims:[], selected:new Set(), providers:[], editId:null};
function setStatus(message, bad=false){const p=$("capture-status");p.textContent=message;p.style.color=bad?"#e6a9a2":"#9ebda7"}
async function api(url, options={}){
  const r=await fetch(url,{...options,headers:{...(options.body?{"Content-Type":"application/json"}:{}),...(options.headers||{})}});
  const data=await r.json();
  if(!r.ok)throw new Error(typeof data.detail==="string"?data.detail:`HTTP ${r.status}`);
  return data;
}
function displayDate(date){return (date||"").slice(0,16).replace("T"," ")}
function el(type,className,text){const node=document.createElement(type);if(className)node.className=className;if(text!==undefined)node.textContent=text;return node}
function visibleRecords(){return state.records}
async function refresh(){
  const q=$("search").value.trim();
  const data=await api("/api/memories"+(q?"?q="+encodeURIComponent(q):""));
  state.records=data.records;
  const available=new Set(data.records.map(x=>x.id));
  // Keep selected items across searches? No: if a record isn't visible, clear it.
  state.selected=new Set([...state.selected].filter(x=>available.has(x)));
  drawRecords();drawContext();await refreshClaims();
}
const SUPPORT_LABEL={supported:"EVIDENCE INTACT",stale:"EVIDENCE CORRECTED — RE-CHECK",orphaned:"EVIDENCE MISSING OR UNVERIFIED — UNSUPPORTED"};
const CLAIM_ACTIONS={proposed:["approve","reject","contest","correct"],approved:["contest","reject","correct"],contested:["approve","reject","correct"],rejected:[],superseded:[]};
async function refreshClaims(){state.claims=(await api("/api/claims")).claims;drawClaims()}
async function claimAction(c,action){
  const body={confirm:true,expected_status:c.status};
  if(action==="approve"&&!confirm("Approve this claim as an accurate interpretation of its evidence?"))return;
  if(action==="reject"&&!confirm(c.status==="approved"?"Revoke your approval and reject this claim? Rejection is final.":"Reject this claim? Rejection is final."))return;
  if(action==="contest"){const note=prompt("Why is this claim contested?");if(note===null)return;body.note=note.slice(0,500)||null}
  if(action==="correct"){
    const text=prompt("Corrected claim (the old claim is kept as superseded history):",c.text);if(text===null||!text.trim())return;
    body.text=text;body.source_ids=selectedRecords().length?selectedRecords().map(x=>x.id):c.source_ids;action="supersede";
  }
  try{await api(`/api/claims/${c.id}/${action}`,{method:"POST",body:JSON.stringify(body)});await refreshClaims()}catch(e){alert(e.message)}
}
function drawClaims(){
  $("claim-count").textContent=`${state.claims.length} claims`;
  const container=$("claims-list");container.replaceChildren();
  if(!state.claims.length){container.append(el("p","empty","No claims yet. Select evidence above and propose an interpretation."));return}
  for(const c of state.claims){
    const wrapper=el("div","record claim "+(c.authoritative?"authoritative":"not-authoritative"));
    const statusLabel=c.authoritative?"APPROVED MEMORY":c.status==="approved"?"APPROVED · NO LONGER AUTHORITATIVE":c.status.toUpperCase()+" · NOT AUTHORITATIVE";
    const tags=el("div","record-actions");
    tags.append(el("span","tag claim-"+(c.authoritative?"approved":c.status==="approved"?"stale":c.status),statusLabel),el("span","tag claim-"+c.support,SUPPORT_LABEL[c.support]),el("span","tag",{model:"MODEL-PROPOSED",human:"HUMAN-WRITTEN",imported:"IMPORTED · UNVERIFIED"}[c.origin]));
    wrapper.append(tags,el("div","record-main",c.text));
    const evidence=el("div","claim-sources");
    for(const s of c.sources)evidence.append(el("div","",`Evidence ${s.id.slice(0,8)} [${s.state}]: ${s.content??"(not in this vault)"}`));
    const history=c.history.map(e=>`${e.to_status} by ${e.actor} ${displayDate(e.at)}${e.note?` (“${e.note}”)`:""}`).join(" → ");
    evidence.append(el("div","",`History: ${history}`+(c.supersedes_id?` · replaces ${c.supersedes_id.slice(0,8)}`:"")+(c.superseded_by?` · replaced by ${c.superseded_by.slice(0,8)}`:"")));
    wrapper.append(evidence);
    const foot=el("div","record-foot");const actions=el("div","record-actions");
    for(const action of CLAIM_ACTIONS[c.status]){const btn=el("button","",action[0].toUpperCase()+action.slice(1));btn.addEventListener("click",()=>claimAction(c,action));actions.append(btn)}
    const del=el("button","","Delete");del.addEventListener("click",async()=>{if(!confirm("Delete this claim and its history? Its evidence is not affected."))return;try{await api(`/api/claims/${c.id}`,{method:"DELETE"});await refreshClaims()}catch(e){alert(e.message)}});
    actions.append(del);foot.append(el("span","",displayDate(c.created_at)),actions);wrapper.append(foot);container.append(wrapper)
  }
}
function drawRecords(){
  $("count").textContent=`${state.records.length} shown`;
  const container=$("records");container.replaceChildren();
  if(!state.records.length){container.append(el("p","empty","No records found. Capture a thought, or search a different phrase."));return}
  for(const record of visibleRecords()){
    const wrapper=el("div","record");const top=el("div","record-top");
    const ck=el("input");ck.type="checkbox";ck.checked=state.selected.has(record.id);
    ck.setAttribute("aria-label","Include record in context");ck.addEventListener("change",()=>{if(ck.checked){if(state.selected.size>=8){ck.checked=false;alert("Select up to eight sources.");return}state.selected.add(record.id)}else state.selected.delete(record.id);drawContext()});
    const txt=el("div","record-main",record.content);top.append(ck,txt);wrapper.append(top);
    const foot=el("div","record-foot");const t=el("span","tag"+(record.sensitivity==="sensitive"?" sensitive":""),record.sensitivity.toUpperCase());
    const created=el("span","",displayDate(record.created_at));const actions=el("div","record-actions");
    const edit=el("button","","Correct");edit.addEventListener("click",()=>{$("edit-text").value=record.content;state.editId=record.id;$("edit-dialog").showModal()});
    const remove=el("button","","Forget");remove.addEventListener("click",async()=>{const dependent=state.claims.filter(c=>c.source_ids.includes(record.id)).length;if(!confirm(`Forget this record, its prior revisions and ${dependent} claim(s) derived from them? They are removed from the active vault and will not return on import or restore. Backups may retain copies.`))return;try{const r=await api(`/api/memories/${record.id}`,{method:"DELETE"});state.selected.delete(record.id);await refresh();setStatus(`Forgot ${r.records_forgotten} record revision(s) and ${r.claims_forgotten} derived claim(s). Backups not covered.`)}catch(e){setStatus(e.message,true)}});
    actions.append(edit,remove);foot.append(t,created,actions);wrapper.append(foot);container.append(wrapper)
  }
}
function selectedRecords(){return state.records.filter(r=>state.selected.has(r.id))}
function drawContext(){
  const chosen=selectedRecords();$("context-count").textContent=String(chosen.length);$("selected-count").textContent=`${chosen.length} selected for context`;$("claim-source-count").textContent=String(chosen.length);
  const preview=$("context-preview");preview.replaceChildren();
  if(!chosen.length){preview.append(el("p","empty","No records selected. Your question can still be sent without a memory context."));return}
  for(const r of chosen){const item=el("div","context-item");item.append(el("small","",`${r.sensitivity.toUpperCase()} · ${r.id.slice(0,8)} · ${displayDate(r.created_at)}`),document.createTextNode(r.content));preview.append(item)}
}
function updateProvider(){
 const chosen=$("provider").value;const cloud=chosen!=="local";
 $("approval").hidden=!cloud;$("allow-cloud").checked=false;
 const provider=state.providers.find(x=>x.id===chosen);
 $("provider-note").textContent=!cloud?"No external connection.":provider?.ready?"Cloud model configured.":"Set the key and model in your local environment.";
}
async function init(){
 $("today").textContent=new Date().toLocaleDateString(undefined,{month:"short",day:"numeric",year:"numeric"});
 const status=await api("/api/status");state.providers=status.providers;
 const select=$("provider");select.replaceChildren();
 for(const p of status.providers){const opt=el("option","",p.name+(p.ready?"":" (not configured)"));opt.value=p.id;select.append(opt)}
 $("provider").addEventListener("change",updateProvider);updateProvider();await refresh();
 for(const nav of document.querySelectorAll("[data-jump]"))nav.addEventListener("click",()=>{document.getElementById(nav.dataset.jump).scrollIntoView({behavior:"smooth"});document.querySelectorAll(".nav").forEach(n=>n.classList.remove("active"));nav.classList.add("active")});
 $("save").addEventListener("click",async()=>{const content=$("note").value.trim();if(!content){setStatus("Write a note first.",true);return}$("save").disabled=true;try{await api("/api/memories",{method:"POST",body:JSON.stringify({content,sensitivity:$("sensitivity").value})});$("note").value="";$("search").value="";await refresh();setStatus("Source record saved locally. No model was contacted.")}catch(e){setStatus(e.message,true)}finally{$("save").disabled=false}});
 $("add-claim").addEventListener("click",async()=>{const text=$("claim-text").value.trim();const source_ids=selectedRecords().map(x=>x.id);if(!text||!source_ids.length){alert("Select at least one source record and write the claim.");return}try{await api("/api/claims",{method:"POST",body:JSON.stringify({text,source_ids})});$("claim-text").value="";await refreshClaims()}catch(e){alert(e.message)}});
 $("refresh").addEventListener("click",()=>refresh().catch(e=>alert(e.message)));
 $("search").addEventListener("keydown",e=>{if(e.key==="Enter")refresh().catch(err=>alert(err.message))});
 $("edit-form").addEventListener("submit",async e=>{e.preventDefault();try{const original=state.records.find(r=>r.id===state.editId);await api(`/api/memories/${state.editId}/correct`,{method:"POST",body:JSON.stringify({content:$("edit-text").value,sensitivity:original.sensitivity})});state.selected.delete(state.editId);$("edit-dialog").close();$("search").value="";await refresh();setStatus("Correction saved as new active revision.")}catch(err){alert(err.message)}});
 $("cancel-edit").addEventListener("click",()=>$("edit-dialog").close());
 $("export").addEventListener("click",()=>{window.location.href="/api/export"});
 const loadFile=async(trusted)=>{const file=$("import-file").files[0];if(!file){alert("Choose an export file first.");return}
  try{const payload=JSON.parse(await file.text());
   if(trusted&&!confirm("Trusted restore: only for your own Sovereign backup. It restores prior approvals and applies its deletions to this vault. Continue?"))return;
   const r=trusted?await api("/api/restore",{method:"POST",body:JSON.stringify({confirm_trusted_restore:true,backup:payload})}):await api("/api/import",{method:"POST",body:JSON.stringify(payload)});
   const skipped=r.records_skipped?` ${r.records_skipped} records were skipped because they would replace, resurrect or re-support existing evidence.`:"";
   await refresh();setStatus((trusted?`Restored ${r.imported} records and ${r.claims_restored} claims (${r.approved_claims_restored} approved).`:`Imported ${r.imported} records; ${r.claims_imported_as_proposed} claims arrived as unverified proposals.`)+skipped)}
  catch(e){setStatus(e.message,true)}};
 $("import").addEventListener("click",()=>loadFile(false));$("restore").addEventListener("click",()=>loadFile(true));
 $("ask").addEventListener("click",async()=>{
  const question=$("question").value.trim();if(!question){renderAnswer("Enter a question first.");return}
  const provider=$("provider").value;
  $("ask").disabled=true;renderAnswer("Working...");
  try{const data=await api("/api/ask",{method:"POST",body:JSON.stringify({question,provider,source_ids:selectedRecords().map(x=>x.id),approve_cloud_disclosure:$("allow-cloud").checked})});
    renderAnswer(data.answer,data.sources,data.cloud_disclosure?`Sent your question and ${data.sources.length} selected sources to ${provider}.`:"No data sent to any model.");
    $("allow-cloud").checked=false;
  }catch(e){renderAnswer(`Request denied or failed: ${e.message}`)}finally{$("ask").disabled=false}
 });
}
function renderAnswer(message,sources=[],disclosure=""){
 const container=$("answer");container.replaceChildren(el("span","eyebrow","OUTPUT"),el("p","",message));
 if(disclosure)container.append(el("div","source-label",disclosure));
 if(sources?.length){container.append(el("div","source-label",`SOURCE RECORDS (${sources.length})`));for(const s of sources)container.append(el("div","context-item",`${s.id.slice(0,8)} · ${s.content}`))}
}
init().catch(err=>renderAnswer("Initialization failed: "+err.message));
