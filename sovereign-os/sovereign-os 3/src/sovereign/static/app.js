"use strict";
const $=id=>document.getElementById(id);
const state={ records:[], claims:[], claimsCursor:null, selected:new Set(), providers:[], editId:null, plan:null, planKey:null};
function setStatus(message, bad=false){const p=$("capture-status");p.textContent=message;p.style.color=bad?"#e6a9a2":"#9ebda7"}
async function api(url, options={}){
  const r=await fetch(url,{...options,headers:{...(options.body?{"Content-Type":"application/json"}:{}),...(options.headers||{})}});
  const data=await r.json();
  if(!r.ok){const err=new Error(typeof data.detail==="string"?data.detail:`HTTP ${r.status}`);err.status=r.status;throw err}
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
const claimsPage=cursor=>api("/api/claims"+(cursor?`?cursor=${encodeURIComponent(cursor)}`:""));
async function refreshClaims(){
  // Reload as many pages as were already shown, so older claims stay visible after a decision.
  const want=Math.max(state.claims.length,1);let claims=[],cursor=null;
  do{const page=await claimsPage(cursor);claims=claims.concat(page.claims);cursor=page.next_cursor}while(cursor&&claims.length<want);
  state.claims=claims;state.claimsCursor=cursor;drawClaims();
}
async function loadOlderClaims(){
  const page=await claimsPage(state.claimsCursor);const seen=new Set(state.claims.map(c=>c.id));
  state.claims=state.claims.concat(page.claims.filter(c=>!seen.has(c.id)));state.claimsCursor=page.next_cursor;drawClaims();
}
async function claimAction(c,action){
  const body={confirm:true,expected_status:c.status};
  if(action==="approve"&&!confirm("Approve this claim as an accurate interpretation of its evidence?"))return;
  if(action==="reject"&&!confirm(c.status==="approved"?"Revoke your approval and reject this claim? Rejection is final.":"Reject this claim? Rejection is final."))return;
  if(action==="contest"){const note=prompt("Why is this claim contested?");if(note===null)return;body.note=note.slice(0,500)||null}
  if(action==="correct"){
    const text=prompt("Corrected claim (the old claim is kept as superseded history):",c.text);if(text===null||!text.trim())return;
    body.text=text;body.source_ids=selectedRecords().length?selectedRecords().map(x=>x.id):c.source_ids;action="supersede";
  }
  try{await api(`/api/claims/${encodeURIComponent(c.id)}/${action}`,{method:"POST",body:JSON.stringify(body)});await refreshClaims()}catch(e){alert(e.message)}
}
function drawClaims(){
  $("claim-count").textContent=`${state.claims.length}${state.claimsCursor?"+":""} claims`;$("more-claims").hidden=!state.claimsCursor;
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
    const del=el("button","","Delete");del.addEventListener("click",async()=>{if(!confirm("Delete this claim and its history? Its evidence is not affected."))return;try{await api(`/api/claims/${encodeURIComponent(c.id)}`,{method:"DELETE"});await refreshClaims()}catch(e){alert(e.message)}});
    const why=el("button","","Provenance");why.addEventListener("click",()=>openProvenance(c.id));
    actions.append(why,del);foot.append(el("span","",displayDate(c.created_at)),actions);wrapper.append(foot);container.append(wrapper)
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
    const remove=el("button","","Forget");remove.addEventListener("click",async()=>{
      try{
        // The server computes exactly what Forget will remove (same plan it executes); never estimate it here.
        const plan=await api(`/api/memories/${encodeURIComponent(record.id)}/forget-preview`);
        const older=plan.records_forgotten-1;
        const shown=plan.claims.slice(0,5).map(c=>`  • [${c.status}] ${c.text}`).join("\n");
        const rest=plan.claims_forgotten>5?`\n  …and ${plan.claims_forgotten-5} more`:"";
        if(!confirm(`Forget this record${older?` and its ${older} earlier revision(s)`:""}, and ${plan.claims_forgotten} claim(s) derived from them?${plan.claims_forgotten?"\n\n"+shown+rest:""}\n\nThey are removed from the active vault and will not return on import or restore. Backups may retain copies.`))return;
        const r=await api(`/api/memories/${encodeURIComponent(record.id)}?expected_impact=${plan.impact_token}`,{method:"DELETE"});
        state.selected.delete(record.id);state.plan=null;await refresh();invalidatePlan();
        renderAnswer("Forgotten content is no longer shown here. Preview the context again before asking.");
        setStatus(`Forgot ${r.records_forgotten} record revision(s) and ${r.claims_forgotten} derived claim(s). Backups not covered.`);
      }catch(e){setStatus(e.message,true)}
    });
    const why=el("button","","Provenance");why.addEventListener("click",()=>openProvenance(record.id));
    actions.append(why,edit,remove);foot.append(t,created,actions);wrapper.append(foot);container.append(wrapper)
  }
}
function selectedRecords(){return state.records.filter(r=>state.selected.has(r.id))}
function drawContext(){
  const chosen=selectedRecords();$("context-count").textContent=String(chosen.length);$("selected-count").textContent=`${chosen.length} selected for context`;$("claim-source-count").textContent=String(chosen.length);
  const preview=$("context-preview");preview.replaceChildren();invalidatePlan();
  if(!chosen.length){preview.append(el("p","empty","No records pinned. The Context Compiler still retrieves relevant approved memory and evidence."));return}
  for(const r of chosen){const item=el("div","context-item");item.append(el("small","",`${r.sensitivity.toUpperCase()} · ${r.id.slice(0,8)} · ${displayDate(r.created_at)}`),document.createTextNode(r.content));preview.append(item)}
}
function updateProvider(){
 const chosen=$("provider").value;const cloud=chosen!=="local";
 const provider=state.providers.find(x=>x.id===chosen);
 $("provider-note").textContent=!cloud?"No external connection.":provider?.ready?"Cloud model configured.":"Set the key and model in your local environment.";
 invalidatePlan();
}
// --- Ask: preview the compiled context, then ask with exactly that plan (ADR-0004) ---
function currentRequest(){return {question:$("question").value.trim(),provider:$("provider").value,source_ids:selectedRecords().map(x=>x.id)}}
function invalidatePlan(){
 if(state.plan&&JSON.stringify(currentRequest())===state.planKey)return;
 state.plan=null;state.planKey=null;$("plan").hidden=true;$("approval").hidden=true;
 const ask=$("ask");ask.disabled=true;ask.firstChild.textContent="Preview the context first ";
}
const REASON_LABEL={invalid_state:"record in an unrecognized state — never used",superseded:"superseded",rejected:"rejected",contested:"contested",not_authoritative:"not approved memory",stale:"evidence corrected",orphaned:"evidence missing or unverified",sensitive_cloud:"sensitive — stays on this device",not_relevant:"not relevant to the question",duplicate:"duplicate content",budget_exceeded:"context budget exceeded"};
function itemNode(x,label){
 const node=el("div","context-item"+(x.role?"":" excluded"));
 const meta=[x.label?`${label} [${x.label}]`:label,x.type==="claim"?`claim ${x.id.slice(0,8)} · ${x.status} · evidence ${x.source_ids.map(i=>i.slice(0,8)).join(", ")}`:`source ${x.id.slice(0,8)} · ${displayDate(x.created_at)}`,x.sensitivity.toUpperCase()];
 if(x.relevance.pinned)meta.push("PINNED");
 node.append(el("small","",meta.join(" · ")),document.createTextNode(x.content.length>280?x.content.slice(0,280)+"…":x.content));
 const why=el("button","text-button","Provenance ↗");why.type="button";why.addEventListener("click",()=>openProvenance(x.id));node.append(why);return node;
}
function renderPlan(plan){
 const memory=plan.included.filter(x=>x.role==="approved_memory"),evidence=plan.included.filter(x=>x.role==="evidence");
 const inc=$("plan-included");inc.replaceChildren(el("div","source-label",`APPROVED MEMORY (${memory.length})`));
 if(!memory.length)inc.append(el("p","empty","No approved, intact memory matched."));for(const x of memory)inc.append(itemNode(x,"◆ approved memory"));
 inc.append(el("div","source-label",`EVIDENCE (${evidence.length})`));if(!evidence.length)inc.append(el("p","empty","No source record matched."));for(const x of evidence)inc.append(itemNode(x,"▤ evidence"));
 const exc=$("plan-excluded");exc.replaceChildren(el("div","source-label",`EXCLUDED (${plan.excluded.length})`));
 if(!plan.excluded.length)exc.append(el("p","empty","Nothing relevant was excluded."));for(const x of plan.excluded)exc.append(itemNode(x,`✕ ${REASON_LABEL[x.reason]||x.reason}`));
 const dis=$("plan-disclosure");dis.replaceChildren(el("div","source-label","DISCLOSURE"));
 const ask=$("ask");ask.disabled=false;$("approval").hidden=plan.target.boundary!=="cloud";
 if(plan.target.boundary==="local"){dis.append(el("p","","Nothing leaves this device. No model is called."));ask.firstChild.textContent="Ask locally ";}
 else if(plan.disclosure.blocked){dis.append(el("p","blocked",`Blocked: ${plan.disclosure.blocked.detail}`));ask.disabled=true;ask.firstChild.textContent="Cannot send this context ";}
 else{
  dis.append(el("p","",`Leaves this device → ${plan.target.provider}: your question and ${plan.outbound.items.length} item(s), all ${plan.disclosure.outbound_sensitivities.join(", ")||"no records"}.`));
  for(const x of plan.included)dis.append(itemNode(x,x.role==="approved_memory"?"◆ sent as approved memory":"▤ sent as evidence"));
  const details=el("details","payload");details.append(el("summary","","Exact payload"),el("pre","",plan.outbound.messages.map(m=>`[${m.role}]\n${m.content}`).join("\n\n")));dis.append(details);
  ask.firstChild.textContent="Approve this context & ask ";
 }
 $("plan").hidden=false;
}
async function previewContext(){
 const request=currentRequest();if(!request.question){renderAnswer("Enter a question first.");return}
 $("preview").disabled=true;
 try{const plan=await api("/api/context/compile",{method:"POST",body:JSON.stringify(request)});state.plan=plan;state.planKey=JSON.stringify(request);renderPlan(plan)}
 catch(e){renderAnswer(`Could not compile context: ${e.message}`)}finally{$("preview").disabled=false}
}
async function askWithPlan(){
 const plan=state.plan;if(!plan||JSON.stringify(currentRequest())!==state.planKey){invalidatePlan();return}
 const cloud=plan.target.boundary==="cloud";$("ask").disabled=true;renderAnswer("Working...");
 try{const data=await api("/api/ask",{method:"POST",body:JSON.stringify({...currentRequest(),approve_cloud_disclosure:cloud,context_token:plan.context_token})});
   const used=data.receipt.included.length;
   const memories=data.context.included.filter(x=>x.role==="approved_memory");
   renderAnswer(data.answer,data.sources,data.cloud_disclosure?`Sent your question and the ${used} item(s) you approved to ${plan.target.provider}. Nothing else left this device.`:"No data sent to any model.",memories);
 }catch(e){
   if(e.status===409){renderAnswer(`409 — ${e.message} The updated context is shown above.`);await refresh();state.plan=null;await previewContext();return}
   renderAnswer(`Request denied or failed: ${e.message}`);
 }finally{if(state.plan)$("ask").disabled=!!state.plan.disclosure.blocked}
}
async function init(){
 $("today").textContent=new Date().toLocaleDateString(undefined,{month:"short",day:"numeric",year:"numeric"});
 const status=await api("/api/status");state.providers=status.providers;
 const select=$("provider");select.replaceChildren();
 for(const p of status.providers){const opt=el("option","",p.name+(p.ready?"":" (not configured)"));opt.value=p.id;select.append(opt)}
 $("provider").addEventListener("change",updateProvider);$("question").addEventListener("input",invalidatePlan);updateProvider();await refresh();
 for(const nav of document.querySelectorAll("[data-jump]"))nav.addEventListener("click",()=>{document.getElementById(nav.dataset.jump).scrollIntoView({behavior:"smooth"});document.querySelectorAll(".nav").forEach(n=>n.classList.remove("active"));nav.classList.add("active")});
 $("save").addEventListener("click",async()=>{const content=$("note").value.trim();if(!content){setStatus("Write a note first.",true);return}$("save").disabled=true;try{await api("/api/memories",{method:"POST",body:JSON.stringify({content,sensitivity:$("sensitivity").value})});$("note").value="";$("search").value="";await refresh();setStatus("Source record saved locally. No model was contacted.")}catch(e){setStatus(e.message,true)}finally{$("save").disabled=false}});
 $("more-claims").addEventListener("click",()=>loadOlderClaims().catch(e=>alert(e.message)));
 $("add-claim").addEventListener("click",async()=>{const text=$("claim-text").value.trim();const source_ids=selectedRecords().map(x=>x.id);if(!text||!source_ids.length){alert("Select at least one source record and write the claim.");return}try{await api("/api/claims",{method:"POST",body:JSON.stringify({text,source_ids})});$("claim-text").value="";await refreshClaims()}catch(e){alert(e.message)}});
 $("refresh").addEventListener("click",()=>refresh().catch(e=>alert(e.message)));
 $("search").addEventListener("keydown",e=>{if(e.key==="Enter")refresh().catch(err=>alert(err.message))});
 $("edit-form").addEventListener("submit",async e=>{e.preventDefault();try{const original=state.records.find(r=>r.id===state.editId);await api(`/api/memories/${encodeURIComponent(state.editId)}/correct`,{method:"POST",body:JSON.stringify({content:$("edit-text").value,sensitivity:original.sensitivity})});state.selected.delete(state.editId);$("edit-dialog").close();$("search").value="";await refresh();setStatus("Correction saved as new active revision.")}catch(err){alert(err.message)}});
 $("cancel-edit").addEventListener("click",()=>$("edit-dialog").close());
 $("prov-close").addEventListener("click",()=>$("prov-dialog").close());
 $("prov-hops").addEventListener("change",()=>{if(state.provFocus)openProvenance(state.provFocus)});
 $("export").addEventListener("click",()=>{window.location.href="/api/export"});
 const loadFile=async(trusted)=>{const file=$("import-file").files[0];if(!file){alert("Choose an export file first.");return}
  try{const payload=JSON.parse(await file.text());
   if(trusted&&!confirm("Trusted restore: only for your own Sovereign backup. It restores prior approvals and applies its deletions to this vault. Continue?"))return;
   const r=trusted?await api("/api/restore",{method:"POST",body:JSON.stringify({confirm_trusted_restore:true,backup:payload})}):await api("/api/import",{method:"POST",body:JSON.stringify(payload)});
   const skipped=r.records_skipped?` ${r.records_skipped} records were skipped because they would replace, resurrect or re-support existing evidence.`:"";
   await refresh();setStatus((trusted?`Restored ${r.imported} records and ${r.claims_restored} claims (${r.approved_claims_restored} approved).`:`Imported ${r.imported} records; ${r.claims_imported_as_proposed} claims arrived as unverified proposals.`)+skipped)}
  catch(e){setStatus(e.message,true)}};
 $("import").addEventListener("click",()=>loadFile(false));$("restore").addEventListener("click",()=>loadFile(true));
 $("preview").addEventListener("click",()=>previewContext());
 $("ask").addEventListener("click",()=>askWithPlan());
}
function renderAnswer(message,sources=[],disclosure="",memories=[]){
 const container=$("answer");container.replaceChildren(el("span","eyebrow","OUTPUT"),el("p","",message));
 if(disclosure)container.append(el("div","source-label",disclosure));
 if(memories.length){container.append(el("div","source-label",`APPROVED MEMORY (${memories.length})`));for(const m of memories)container.append(el("div","context-item",`${m.id.slice(0,8)} · ${m.content}`))}
 if(sources?.length){container.append(el("div","source-label",`SOURCE RECORDS (${sources.length})`));for(const s of sources)container.append(el("div","context-item",`${s.id.slice(0,8)} · ${s.content}`))}
}
// --- SB-2a provenance navigation (read-only; never changes what a model may see) ---
const EDGE_STATE={active:"evidence intact",superseded:"evidence since corrected",unverified:"evidence changed since the claim was made"};
function claimStatusLabel(c){return c.authoritative?"APPROVED MEMORY":c.status==="approved"?"APPROVED · NO LONGER AUTHORITATIVE":c.status.toUpperCase()+" · NOT AUTHORITATIVE"}
function provItem(graph,node,note){
 const row=el("div","prov-item");const body=el("div","prov-text");
 const kind=node.kind==="claim"?`claim · ${claimStatusLabel(node)} · ${SUPPORT_LABEL[node.support]}`:`source record · ${node.status.toUpperCase()} · ${node.sensitivity.toUpperCase()}`;
 body.append(el("small","",[kind,displayDate(node.created_at),note].filter(Boolean).join(" · ")),document.createTextNode(node.text.length>400?node.text.slice(0,400)+"…":node.text));
 const actions=el("div","record-actions");
 if(node.id!==graph.focus.id){const go=el("button","","Open");go.type="button";go.addEventListener("click",()=>openProvenance(node.id));actions.append(go)}
 if(node.kind==="record"&&node.status==="active"){const pin=el("button","",state.selected.has(node.id)?"Pinned":"Pin for context");pin.type="button";pin.addEventListener("click",()=>pinFromProvenance(node.id,pin));actions.append(pin)}
 row.append(body,actions);return row;
}
function provSection(container,title,items){container.append(el("div","source-label",title));if(!items.length){container.append(el("p","empty","None stored."));return}for(const i of items)container.append(i)}
function renderProvenance(graph){
 const body=$("prov-body");body.replaceChildren();
 const byId=new Map(graph.nodes.map(n=>[n.id,n]));const focus=byId.get(graph.focus.id);
 const out=type=>graph.edges.filter(e=>e.type===type&&e.from===focus.id);const into=type=>graph.edges.filter(e=>e.type===type&&e.to===focus.id);
 const near=new Set([focus.id]);const item=(id,note)=>{near.add(id);return provItem(graph,byId.get(id),note)};
 const head=el("div","prov-focus");head.append(provItem(graph,focus,"selected"));body.append(head);
 if(focus.kind==="claim"){
  const why=focus.authoritative?"Approved by you, and every piece of evidence it cites is present and unchanged.":focus.status!=="approved"?`Not approved memory: its status is ${focus.status}.`:{stale:"You approved it, but evidence it cites has since been corrected; it no longer counts as approved memory.",orphaned:"You approved it, but evidence it cites is missing or has changed; it no longer counts as approved memory."}[focus.support];
  body.append(el("p","micro",why));
  provSection(body,"SUPPORTED BY (evidence this claim cites)",out("SUPPORTED_BY").map(e=>item(e.to,EDGE_STATE[e.evidence_state]||e.evidence_state)));
  provSection(body,"SUPERSEDES (the earlier claim it replaced)",out("SUPERSEDES").map(e=>item(e.to)));
  provSection(body,"SUPERSEDED BY (the claim that replaced it)",into("SUPERSEDES").map(e=>item(e.from)));
  provSection(body,"DECISION HISTORY",focus.history.map(h=>el("p","",`${displayDate(h.at)} · ${h.from_status?h.from_status+" → ":""}${h.to_status} · by ${h.actor}${h.note?` · “${h.note}”`:""}`)));
 }else{
  provSection(body,"CITED BY (claims resting on this record)",into("SUPPORTED_BY").map(e=>item(e.from,EDGE_STATE[e.evidence_state]||e.evidence_state)));
  provSection(body,"CORRECTS (the earlier revision)",out("CORRECTS").map(e=>item(e.to)));
  provSection(body,"CORRECTED BY (the newer revision)",into("CORRECTS").map(e=>item(e.from)));
 }
 const further=graph.nodes.filter(n=>!near.has(n.id));
 if(graph.hops>1)provSection(body,"FURTHER LINKS (two steps away)",further.map(n=>provItem(graph,n,"")));
 if(graph.truncated)body.append(el("p","micro","More linked items exist than this view shows; open one of them to continue."));
}
async function openProvenance(id){
 state.provFocus=id;const dialog=$("prov-dialog");
 try{const graph=await api(`/api/provenance/${encodeURIComponent(id)}?hops=${$("prov-hops").value}`);renderProvenance(graph)}
 catch(e){$("prov-body").replaceChildren(el("p","empty",e.status===404?"This item is no longer in your vault.":`Could not load provenance: ${e.message}`))}
 if(!dialog.open)dialog.showModal();
}
function pinFromProvenance(id,button){
 if(!state.records.some(r=>r.id===id)){button.textContent="Not in the current library view";return}
 if(!state.selected.has(id)&&state.selected.size>=8){button.textContent="Up to eight sources";return}
 state.selected.add(id);drawRecords();drawContext();button.textContent="Pinned";
}
init().catch(err=>renderAnswer("Initialization failed: "+err.message));
