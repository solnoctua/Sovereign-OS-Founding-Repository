"use strict";
// Sovereign browser UI. Conversations (ADR-0008, PROPOSED) live only in this tab's memory: this file uses no
// browser storage and the server stores no conversation. Every model-bound byte is compiled by the server's
// Context Compiler, and a cloud message is sent only after its exact preview is approved (ADR-0004).
const $=id=>document.getElementById(id);
const state={records:[],claims:[],claimsCursor:null,selected:new Set(),providers:[],editId:null,
  chats:[],activeId:null,query:"",forgotten:new Set(),
  conversation:{max_message_chars:16000,max_request_messages:64}};
const PROVIDER_NAME={local:"Local · your vault only",kimi:"Kimi",openai:"OpenAI"};
const providerName=id=>PROVIDER_NAME[id]||id;
const s=n=>n===1?"":"s";
function setStatus(message, bad=false){const p=$("capture-status");p.textContent=message;p.style.color=bad?"#e6a9a2":"#9ebda7"}
async function api(url, options={}){
  const r=await fetch(url,{...options,headers:{...(options.body?{"Content-Type":"application/json"}:{}),...(options.headers||{})}});
  let data=null;try{data=await r.json()}catch{data=null}
  if(!r.ok){const err=new Error(typeof data?.detail==="string"?data.detail:`HTTP ${r.status}`);err.status=r.status;throw err}
  return data;
}
function displayDate(date){return (date||"").slice(0,16).replace("T"," ")}
function el(type,className,text){const node=document.createElement(type);if(className)node.className=className;if(text!==undefined)node.textContent=text;return node}
function button(label,onClick,className="text-button"){const b=el("button",className,label);b.type="button";b.addEventListener("click",onClick);return b}
function listJoin(parts){return parts.length<2?parts.join(""):parts.slice(0,-1).join(", ")+" and "+parts[parts.length-1]}
function uid(){return globalThis.crypto?.randomUUID?crypto.randomUUID():Date.now().toString(36)+Math.random().toString(36).slice(2)}

// --- Conversations: held in this tab only (ADR-0008 §6) --------------------------------------------------
const PENDING=["preparing","review","blocked","sending"];
function activeChat(){return state.chats.find(c=>c.id===state.activeId)||null}
function pendingTurn(chat){return chat?.turns.find(t=>PENDING.includes(t.status))||null}
function titleOf(text){const line=text.replace(/\s+/g," ").trim();return line.length>60?line.slice(0,59)+"…":line}
function newChat(){
  const chat={id:uid(),title:"New conversation",turns:[],updated:Date.now()};
  state.chats.unshift(chat);state.activeId=chat.id;showView("chat");drawChatList();drawChat();$("message").focus();return chat;
}
function touch(chat){chat.updated=Date.now();state.chats.sort((a,b)=>b.updated-a.updated)}
function draw(chat){if(chat.id===state.activeId)drawChat();drawChatList()}

// Asynchronous results are fenced (ADR-0008 §6). Every preview, reply and local search a turn starts carries the
// turn's sequence number; it is accepted only while that conversation still exists, still holds that turn, and the
// number is unchanged. Clearing, cancelling, editing, deleting and any newer preparation move the number on, so a
// completion that arrives late (after a Forget, a deletion or a newer request) is dropped, never shown or reused.
function begin(turn){turn.seq=(turn.seq||0)+1;return turn.seq}
function current(chat,turn,seq){return state.chats.includes(chat)&&chat.turns.includes(turn)&&turn.seq===seq}
function retire(turn){turn.seq=(turn.seq||0)+1}

// Unicode-safe, bounded head-and-tail clipping (ADR-0008 §2, F-2): lengths are counted in code points as the server
// counts them, cuts fall on grapheme-cluster boundaries where the browser can segment text (never inside a surrogate
// pair), a visible marker says how much was left out, and text already within the bound is returned unchanged.
const GRAPHEMES=typeof Intl!=="undefined"&&Intl.Segmenter?new Intl.Segmenter(undefined,{granularity:"grapheme"}):null;
const omission=n=>`\n…[${n} characters omitted by Sovereign]…\n`;
function wellFormed(text){
  return typeof text.toWellFormed==="function"?text.toWellFormed():
    text.replace(/[\ud800-\udbff](?![\udc00-\udfff])|(?<![\ud800-\udbff])[\udc00-\udfff]/g,"�");
}
function clip(text,limit){
  text=wellFormed(text);
  const total=Array.from(text).length;
  if(total<=limit)return text;
  const pieces=GRAPHEMES?Array.from(GRAPHEMES.segment(text),g=>g.segment):Array.from(text);
  const budget=limit-Array.from(omission(total)).length,headBudget=Math.ceil(budget/2),tailBudget=budget-headBudget;
  let headEnd=0,head=0,tailStart=pieces.length,tail=0;
  while(headEnd<pieces.length){const n=Array.from(pieces[headEnd]).length;if(head+n>headBudget)break;head+=n;headEnd++}
  while(tailStart>headEnd){const n=Array.from(pieces[tailStart-1]).length;if(tail+n>tailBudget)break;tail+=n;tailStart--}
  return pieces.slice(0,headEnd).join("")+omission(total-head-tail)+pieces.slice(tailStart).join("");
}
// The earlier complete cloud exchanges a turn carries, oldest first, and how many eligible earlier messages this
// browser left out (its request limit) or shortened. Local, failed, pending and cleared turns never travel, and
// neither does any turn's compiled context: memory is compiled afresh for every message.
function historyBefore(chat,turn){
  const stop=chat.turns.findIndex(t=>t.id===(turn.replaces||turn.id));
  const limit=state.conversation.max_message_chars,cap=Math.floor(state.conversation.max_request_messages/2)*2;
  const eligible=chat.turns.slice(0,stop<0?chat.turns.length:stop).filter(t=>t.status==="done"&&t.provider!=="local"&&t.reply)
    .flatMap(t=>[{role:"user",content:t.message},{role:"assistant",content:t.reply,provider:t.provider}]);
  const kept=eligible.slice(-cap);let clipped=0;
  const history=kept.map(m=>{const content=clip(m.content,limit);if(content!==m.content)clipped++;return {...m,content}});
  return {history,trimmed:eligible.length-kept.length,clipped};
}
function cloudRequest(chat,turn){
  const {history,trimmed,clipped}=historyBefore(chat,turn);
  return {request:{question:turn.message,provider:turn.provider,source_ids:turn.pins,conversation:{history}},trimmed,clipped};
}
// Which vault items a turn used (included) and listed (included or excluded), as kind-qualified keys kept apart
// from its displayed context: a record and a claim can share an id, and an earlier Forget may drop the display.
const itemKey=x=>`${x.type==="claim"?"claim":"record"}:${x.id}`;
function remember(turn){
  const ctx=turn.context||turn.plan;
  turn.used=(ctx?.included||[]).map(itemKey);turn.listed=[...turn.used,...(ctx?.excluded||[]).map(itemKey)];
}
const usesForgotten=turn=>(turn.used||[]).some(k=>state.forgotten.has(k));
const listsForgotten=turn=>(turn.listed||[]).some(k=>state.forgotten.has(k));
const REASONS={forget:"the first of them used memory you have since forgotten",
  claim:"the first of them used a claim you have since deleted",
  restore:"a trusted restore can delete records, and this tab cannot tell which messages used them"};
// Conservative suffix invalidation (ADR-0008 §6): Sovereign cannot trace every way later text repeats earlier text,
// so it clears the first affected turn and every turn after it: your messages, replies, previews and pending
// requests. Earlier turns stay. One content-free notice takes their place.
function invalidateFrom(chat,index,reason){
  const removed=chat.turns.slice(index);if(!removed.length)return;
  for(const t of removed)retire(t);
  const count=removed.reduce((n,t)=>n+(t.status==="cleared"?t.count:1),0);
  chat.turns=[...chat.turns.slice(0,index),{id:uid(),status:"cleared",count,reason,seq:0}];
}
function finish(chat,turn){
  if(usesForgotten(turn))return invalidateFrom(chat,chat.turns.indexOf(turn),"forget");  // a Forget committed meanwhile
  if(turn.replaces){chat.turns=chat.turns.filter(t=>t.id!==turn.replaces);turn.replaces=null}
  touch(chat);
}
async function send(){
  const text=$("message").value.trim();if(!text)return;
  const chat=activeChat()||newChat();
  if(pendingTurn(chat)){updateComposer();return}
  const turn={id:uid(),message:text,provider:$("provider").value,pins:selectedRecords().map(r=>r.id),status:"preparing"};
  chat.turns.push(turn);if(chat.turns.length===1)chat.title=titleOf(text);touch(chat);
  $("message").value="";autosize();draw(chat);
  await run(chat,turn);
}
function run(chat,turn,notice=null){return turn.provider==="local"?runLocal(chat,turn):prepare(chat,turn,notice)}
async function runLocal(chat,turn){
  // Local turns call no model and are never part of a cloud conversation (ADR-0008 §1).
  const seq=begin(turn);turn.status="sending";turn.error=null;draw(chat);const started=performance.now();
  try{
    const data=await api("/api/ask",{method:"POST",body:JSON.stringify({question:turn.message,provider:"local",source_ids:turn.pins})});
    if(!current(chat,turn,seq))return;
    Object.assign(turn,{context:data.context,receipt:data.receipt,ms:performance.now()-started,status:"local"});remember(turn);finish(chat,turn);
  }catch(e){if(!current(chat,turn,seq))return;turn.status="error";turn.error=`Could not search your vault: ${e.message}`}
  draw(chat);
}
async function prepare(chat,turn,notice=null){
  // Compile and show exactly what this message would send; nothing leaves the device until it is approved.
  const seq=begin(turn);
  Object.assign(turn,{status:"preparing",notice,error:null,plan:null,request:null});draw(chat);
  const {request,trimmed,clipped}=cloudRequest(chat,turn);
  try{
    const plan=await api("/api/context/compile",{method:"POST",body:JSON.stringify(request)});
    if(!current(chat,turn,seq))return;
    Object.assign(turn,{request,plan,trimmed,clipped,status:plan.disclosure.blocked?"blocked":"review"});remember(turn);
    if(listsForgotten(turn))return prepare(chat,turn,notice);   // compiled before a Forget committed: compile again
  }catch(e){if(!current(chat,turn,seq))return;turn.status="error";turn.error=`Could not prepare this message: ${e.message}`}
  draw(chat);
}
async function approve(chat,turn){
  if(turn.status!=="review")return;
  const seq=begin(turn);turn.status="sending";draw(chat);const started=performance.now();
  try{
    // Exactly the previewed request plus the approval of its token; the server recompiles and verifies it.
    const data=await api("/api/ask",{method:"POST",body:JSON.stringify({...turn.request,approve_cloud_disclosure:true,context_token:turn.plan.context_token})});
    if(!current(chat,turn,seq))return;   // cleared, cancelled or deleted while in flight: the reply is dropped
    Object.assign(turn,{reply:data.answer,context:data.context,receipt:data.receipt,ms:performance.now()-started,status:"done",plan:null});
    remember(turn);finish(chat,turn);
  }catch(e){
    if(!current(chat,turn,seq))return;
    if(e.status===409)return prepare(chat,turn,"Your memory or this conversation changed since the preview. Review the updated context before sending.");
    turn.status="error";
    turn.error=e.status===503?`${providerName(turn.provider)} is not configured on this computer. Set its API key and model in the environment and restart Sovereign.`:`The request was refused or failed: ${e.message}`;
  }
  draw(chat);
}
function cancel(chat,turn){
  retire(turn);chat.turns=chat.turns.filter(t=>t!==turn);
  if(!turn.replaces&&!$("message").value.trim()){$("message").value=turn.message;autosize()}
  if(!chat.turns.length)chat.title="New conversation";
  draw(chat);$("message").focus();
}
function regenerate(chat,turn){
  if(pendingTurn(chat))return;
  const again={id:uid(),message:turn.message,provider:$("provider").value,pins:turn.pins,status:"preparing",replaces:turn.id};
  chat.turns.push(again);draw(chat);run(chat,again);
}
function editLast(chat,turn){
  if(turn.status==="done"&&!confirm("Edit this message? Its reply is removed from this conversation."))return;
  retire(turn);chat.turns=chat.turns.filter(t=>t!==turn);if(!chat.turns.length)chat.title="New conversation";
  $("message").value=turn.message;autosize();draw(chat);$("message").focus();
}
function deleteChat(chat){
  if(!confirm("Delete this conversation from this tab? Copies already sent to a provider are outside Sovereign's control."))return;
  for(const t of chat.turns)retire(t);
  state.chats=state.chats.filter(c=>c!==chat);if(state.activeId===chat.id)state.activeId=state.chats[0]?.id||null;
  drawChatList();drawChat();
}
// A Forget or claim deletion through this tab (keys like "record:<id>") reaches every conversation it holds: the
// suffix from the earliest turn that used a forgotten item is cleared, a turn that only listed one loses its stored
// preview, and every remaining pending review is compiled again.
function purgeForgotten(keys,reason="forget"){
  for(const k of keys)state.forgotten.add(k);
  for(const chat of state.chats){
    const index=chat.turns.findIndex(t=>t.status!=="cleared"&&usesForgotten(t));
    if(index>=0)invalidateFrom(chat,index,reason);
    for(const turn of chat.turns)if(listsForgotten(turn)){turn.context=null;turn.plan=null}
  }
  invalidateReviews("Your memory changed since this preview. Review the updated context before sending.");
}
function clearAllConversations(reason){
  for(const chat of state.chats)if(chat.turns.some(t=>t.status!=="cleared"))invalidateFrom(chat,0,reason);
  drawChat();drawChatList();
}
function invalidateReviews(notice){
  for(const chat of state.chats)for(const turn of chat.turns)
    if(turn.provider!=="local"&&["review","blocked","preparing"].includes(turn.status))prepare(chat,turn,notice);
  drawChat();drawChatList();
}

// --- Conversation rendering ----------------------------------------------------------------------------------
function drawChatList(){
  const list=$("chat-list");list.replaceChildren();const q=state.query.toLowerCase();
  const shown=state.chats.filter(c=>!q||c.title.toLowerCase().includes(q)||c.turns.some(t=>(t.message||"").toLowerCase().includes(q)||(t.reply||"").toLowerCase().includes(q)));
  if(!shown.length){list.append(el("p","empty",state.chats.length?"No conversation matches.":"No conversations yet."));return}
  for(const chat of shown){
    const row=el("div","chat-item"+(chat.id===state.activeId?" active":""));
    const open=button("",()=>{state.activeId=chat.id;showView("chat");drawChatList();drawChat();closeSidebar()},"chat-open");
    open.append(el("span","chat-name",chat.title));open.title=chat.title;
    if(chat.id===state.activeId)open.setAttribute("aria-current","true");
    if(pendingTurn(chat)?.status==="review")open.append(el("span","chat-flag","review"));
    const del=button("×",()=>deleteChat(chat),"chat-delete");del.setAttribute("aria-label",`Delete conversation: ${chat.title}`);
    row.append(open,del);list.append(row);
  }
}
function drawChat(){
  const chat=activeChat();const box=$("messages");box.replaceChildren();
  $("chat-title").textContent=chat?.title||"New conversation";
  if(!chat||!chat.turns.length)box.append(emptyState());
  else{const last=chat.turns[chat.turns.length-1];for(const turn of chat.turns)turn.status==="cleared"?box.append(clearedNotice(turn)):box.append(userMessage(chat,turn,turn===last),turnView(chat,turn,turn===last))}
  updateComposer();box.scrollTop=box.scrollHeight;
}
function emptyState(){
  const box=el("div","empty-state");
  box.append(el("div","emblem big","S"),el("h2","","What are we thinking about?"),
    el("p","","Sovereign brings relevant approved memory and records from your vault into each message, and shows you exactly what would leave this device before anything is sent."));
  const ideas=el("div","suggestions");
  for(const [label,text] of [["What have I recorded about…","What have I recorded about "],["Stress-test an idea","Stress-test this idea: "],["Brainstorm directions","Brainstorm directions for "]])
    ideas.append(button(label,()=>{$("message").value=text;autosize();$("message").focus()},"suggestion"));
  box.append(ideas,el("p","micro","Prototype: synthetic or non-sensitive data only. Conversations live only in this tab; reloading clears them."));
  return box;
}
function userMessage(chat,turn,isLast){
  const row=el("div","msg user");row.append(el("div","bubble",turn.message));
  const meta=el("div","msg-meta");
  if(turn.pins?.length)meta.append(el("span","",`${turn.pins.length} pinned record${s(turn.pins.length)}`));
  if(turn.replaces)meta.append(el("span","","Regenerating the reply above"));
  if(isLast&&["done","local","error"].includes(turn.status))meta.append(button("Edit",()=>editLast(chat,turn)));
  if(meta.childNodes.length)row.append(meta);
  return row;
}
function turnView(chat,turn,isLast){
  const local=turn.provider==="local";
  if(turn.status==="preparing")return pendingLine(local?"Searching your vault…":"Compiling the context for this message…");
  if(turn.status==="sending")return pendingLine(local?"Searching your vault…":`Waiting for ${providerName(turn.provider)}…`);
  if(turn.status==="review"||turn.status==="blocked")return reviewCard(chat,turn);
  if(turn.status==="done")return replyView(chat,turn,isLast);
  if(turn.status==="local")return localView(chat,turn,isLast);
  const wrap=el("div","msg assistant failed");wrap.append(el("p","",turn.error||"Something went wrong."));
  const actions=el("div","review-actions");actions.append(button("Try again",()=>run(chat,turn),"secondary"),button("Remove",()=>cancel(chat,turn),"secondary"));
  wrap.append(actions);return wrap;
}
function clearedNotice(turn){
  const box=el("div","msg cleared");box.setAttribute("role","status");
  box.append(el("p","",`${turn.count} message${s(turn.count)} from here on ${turn.count===1?"was":"were"} cleared from this conversation, with ${turn.count===1?"its reply and preview":"their replies and previews"}, because ${REASONS[turn.reason]||REASONS.forget}.`),
    el("p","micro","Earlier messages are kept. Sovereign cannot trace every way later text repeats earlier text, so it clears everything after the first message that used it, and none of it is sent again. Copies already sent to a provider are outside Sovereign's control."));
  return box;
}
function pendingLine(text){const line=el("div","msg assistant pending");line.append(el("span","pulse"),document.createTextNode(text));return line}
function reviewCard(chat,turn){
  const plan=turn.plan,provider=providerName(turn.provider),ready=!!state.providers.find(p=>p.id===turn.provider)?.ready;
  const card=el("div","msg review");card.setAttribute("role","group");card.setAttribute("aria-label",`Review before sending to ${provider}`);
  card.append(el("div","review-title",`Review what leaves this device → ${provider}`));
  if(turn.notice)card.append(el("p","notice",turn.notice));
  if(plan.disclosure.blocked)card.append(el("p","blocked",`Blocked: ${plan.disclosure.blocked.detail}`));
  else{
    const conv=plan.conversation||{sent_messages:0,omitted_messages:0,carryover:[]};
    const memory=plan.included.filter(x=>x.role==="approved_memory").length,evidence=plan.included.length-memory;
    const parts=["your message"];
    if(conv.sent_messages)parts.push(`${conv.sent_messages} earlier message${s(conv.sent_messages)} of this conversation`);
    parts.push(plan.included.length?`${plan.included.length} item${s(plan.included.length)} from your memory (${memory} approved memory, ${evidence} evidence; all ${plan.disclosure.outbound_sensitivities.join(", ")})`:"nothing from your memory");
    card.append(el("p","review-summary",`Leaves this device: ${listJoin(parts)}.`));
    for(const c of conv.carryover)card.append(el("p","warn",`Includes ${c.replies} earlier ${c.replies===1?"reply":"replies"} written by ${providerName(c.from)}: approving sends ${c.replies===1?"it":"them"} to ${provider}.`));
    // Omissions in full (F-3): this browser's request limit, counted here, plus Sovereign's budget, reported by the
    // server. The exact payload below stays the authority on what is sent.
    const byBrowser=turn.trimmed||0,byServer=conv.omitted_messages||0,total=byBrowser+byServer,notes=[];
    if(total)notes.push(`${total} older message${s(total)} of this conversation ${total===1?"is":"are"} not sent: ${byBrowser} left out by this browser before the request (counted here, not verified by Sovereign) and ${byServer} by Sovereign's conversation budget.`);
    if(turn.clipped)notes.push(`${turn.clipped} earlier message${s(turn.clipped)} ${turn.clipped===1?"was":"were"} shortened to the per-message limit; the payload marks where.`);
    if(notes.length)card.append(el("p","micro omitted",notes.join(" ")));
    if(!ready)card.append(el("p","warn",`${provider} is not configured on this computer: set its API key and model in the environment and restart Sovereign. You can still inspect what would be sent.`));
  }
  card.append(itemsDetails(`Memory and evidence to send (${plan.included.length})`,plan.included,plan.included.length>0&&plan.included.length<=3));
  if(plan.excluded.length)card.append(itemsDetails(`Considered but not used (${plan.excluded.length})`,plan.excluded,false));
  if(plan.outbound){const d=el("details","payload");d.append(el("summary","","Exact payload"),el("pre","",plan.outbound.messages.map(m=>`[${m.role}]\n${m.content}`).join("\n\n")));card.append(d)}
  const actions=el("div","review-actions");const go=button("Approve & send",()=>approve(chat,turn),"primary");go.disabled=!!plan.disclosure.blocked||!ready;
  actions.append(go,button("Cancel",()=>cancel(chat,turn),"secondary"));card.append(actions);
  card.append(el("p","micro","Approving sends exactly this payload, for this message only. Sensitive items never leave this device. The provider's retention policy applies."));
  return card;
}
function itemsDetails(title,items,open){
  const d=el("details","items");d.open=open;d.append(el("summary","",title));
  if(!items.length)d.append(el("p","empty","None."));
  for(const x of items)d.append(itemNode(x));
  return d;
}
function replyView(chat,turn,isLast){
  const wrap=el("div","msg assistant");const labels=new Map((turn.context?.included||[]).map(x=>[x.label,x]));
  const cite=label=>{
    const x=labels.get(label);if(!x)return el("span","cite unknown",`[${label}]`);
    const chip=button(label,()=>openProvenance(x.type==="claim"?"claim":"record",x.id),"cite");
    chip.title=`${x.role==="approved_memory"?"Approved memory":"Evidence"}: ${x.content.length>200?x.content.slice(0,200)+"…":x.content}`;return chip;
  };
  wrap.append(renderMarkdown(turn.reply,cite));
  const used=turn.context?.included.length,earlier=turn.receipt?.conversation?.sent_messages||0;
  const meta=el("div","msg-meta");
  meta.append(el("span","",[providerName(turn.provider),turn.ms?`${(turn.ms/1000).toFixed(1)} s`:"",
    used===undefined?"":`sent ${used} memory item${s(used)}${earlier?` and ${earlier} earlier message${s(earlier)}`:""}`].filter(Boolean).join(" · ")));
  meta.append(button("Copy",e=>copy(turn.reply,e.currentTarget)));
  if(isLast){const target=$("provider").value;meta.append(button(target===turn.provider?"Regenerate":`Regenerate with ${providerName(target)}`,()=>regenerate(chat,turn)))}
  wrap.append(meta);
  if(turn.context)wrap.append(itemsDetails(`Memory used (${turn.context.included.length})`,turn.context.included,false));
  else wrap.append(el("p","micro","Memory details for this reply were removed from this tab after a Forget."));
  return wrap;
}
function localView(chat,turn,isLast){
  const wrap=el("div","msg assistant local");const ctx=turn.context;
  wrap.append(el("p","local-head","From your vault: no model was called and nothing left this device."));
  const memory=ctx.included.filter(x=>x.role==="approved_memory"),evidence=ctx.included.filter(x=>x.role==="evidence");
  if(!ctx.included.length)wrap.append(el("p","empty","No eligible record matched this message's words. A record phrased differently, or one that cannot be used here, can still exist: try other words, or pin records in Memory."));
  if(memory.length){wrap.append(el("div","source-label",`APPROVED MEMORY (${memory.length})`));for(const x of memory)wrap.append(itemNode(x))}
  if(evidence.length){wrap.append(el("div","source-label",`EVIDENCE (${evidence.length})`));for(const x of evidence)wrap.append(itemNode(x))}
  if(ctx.excluded.length)wrap.append(itemsDetails(`Considered but not used (${ctx.excluded.length})`,ctx.excluded,false));
  const meta=el("div","msg-meta");meta.append(el("span","",[providerName("local"),turn.ms?`${(turn.ms/1000).toFixed(1)} s`:""].filter(Boolean).join(" · ")));
  if(isLast){const target=$("provider").value;meta.append(button(target==="local"?"Search again":`Ask ${providerName(target)}`,()=>regenerate(chat,turn)))}
  wrap.append(meta);return wrap;
}
async function copy(text,btn){try{await navigator.clipboard.writeText(text);btn.textContent="Copied"}catch{btn.textContent="Copy failed"}setTimeout(()=>{btn.textContent="Copy"},1500)}

// Model output is untrusted text: a small Markdown subset is rendered by building DOM nodes with textContent only,
// never innerHTML, and links stay plain text. [M1] / [E2] citations become chips for this turn's items.
const INLINE=/(`[^`\n]+`)|(\*\*[^*\n]+?\*\*)|(\[[ME]\d{1,3}(?:\s*[,;]\s*[ME]\d{1,3})*\])|(\*[^*\s][^*\n]*?\*)/g;
function inline(parent,text,cite){
  let last=0;
  for(const m of text.matchAll(INLINE)){
    if(m.index>last)parent.append(document.createTextNode(text.slice(last,m.index)));
    if(m[1])parent.append(el("code","md-inline",m[0].slice(1,-1)));
    else if(m[2]){const b=el("strong");inline(b,m[0].slice(2,-2),cite);parent.append(b)}
    else if(m[3])for(const label of m[0].slice(1,-1).split(/[,;]/))parent.append(cite(label.trim()));
    else{const i=el("em");inline(i,m[0].slice(1,-1),cite);parent.append(i)}
    last=m.index+m[0].length;
  }
  if(last<text.length)parent.append(document.createTextNode(text.slice(last)));
}
function renderMarkdown(text,cite){
  const root=el("div","md");const lines=String(text).replace(/\r\n?/g,"\n").split("\n");
  const fence=l=>/^\s*(```|~~~)/.test(l),heading=l=>/^\s{0,3}#{1,6}\s+\S/.test(l),item=l=>/^\s*([-*+•]|\d{1,3}[.)])\s+/.test(l),
    quote=l=>/^\s*>/.test(l),rule=l=>/^\s*([-*_])(\s*\1){2,}\s*$/.test(l),row=l=>/^\s*\|.*\|\s*$/.test(l),
    separator=l=>/^\s*\|?[\s:|-]*-[\s:|-]*\|?\s*$/.test(l)&&l.includes("-");
  const cells=l=>l.trim().replace(/^\|/,"").replace(/\|$/,"").split("|").map(c=>c.trim());
  let i=0;
  while(i<lines.length){
    const line=lines[i];
    if(!line.trim()){i++;continue}
    if(fence(line)){
      const mark=line.trim().slice(0,3),code=[];i++;
      while(i<lines.length&&!lines[i].trim().startsWith(mark)){code.push(lines[i]);i++}
      i++;const pre=el("pre","md-code");pre.append(el("code","",code.join("\n")));root.append(pre);continue;
    }
    if(heading(line)){const m=line.match(/^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$/);const h=el(`h${Math.min(m[1].length+2,6)}`,"md-h");inline(h,m[2],cite);root.append(h);i++;continue}
    if(rule(line)){root.append(el("hr"));i++;continue}
    if(row(line)&&i+1<lines.length&&separator(lines[i+1])){
      const table=el("table","md-table"),head=el("tr");for(const c of cells(line)){const th=el("th");inline(th,c,cite);head.append(th)}
      const thead=el("thead");thead.append(head);table.append(thead);const body=el("tbody");i+=2;
      while(i<lines.length&&row(lines[i])){const tr=el("tr");for(const c of cells(lines[i])){const td=el("td");inline(td,c,cite);tr.append(td)}body.append(tr);i++}
      table.append(body);const scroll=el("div","md-table-wrap");scroll.append(table);root.append(scroll);continue;
    }
    if(quote(line)){const q=[];while(i<lines.length&&quote(lines[i])){q.push(lines[i].replace(/^\s*>\s?/,""));i++}const bq=el("blockquote","md-quote");bq.append(renderMarkdown(q.join("\n"),cite));root.append(bq);continue}
    if(item(line)){
      const first=line.match(/^\s*(\d{1,3})[.)]\s+/);const list=el(first?"ol":"ul","md-list");if(first&&first[1]!=="1")list.start=Number(first[1]);
      while(i<lines.length&&(item(lines[i])||(lines[i].trim()&&/^\s{2,}\S/.test(lines[i])&&list.lastElementChild))){
        if(item(lines[i])){const li=el("li");inline(li,lines[i].replace(/^\s*([-*+•]|\d{1,3}[.)])\s+/,""),cite);list.append(li)}
        else{const li=list.lastElementChild;li.append(document.createTextNode(" "));inline(li,lines[i].trim(),cite)}
        i++;
      }
      root.append(list);continue;
    }
    const p=el("p","md-p");let n=0;
    while(i<lines.length&&lines[i].trim()&&!fence(lines[i])&&!heading(lines[i])&&!item(lines[i])&&!quote(lines[i])&&!rule(lines[i])&&!(row(lines[i])&&i+1<lines.length&&separator(lines[i+1]))){
      if(n++)p.append(el("br"));inline(p,lines[i].trim(),cite);i++;
    }
    root.append(p);
  }
  return root;
}

// --- Composer, pins and views ----------------------------------------------------------------------------------
function updateComposer(){
  const pending=pendingTurn(activeChat()),id=$("provider").value,p=state.providers.find(x=>x.id===id);
  $("send").disabled=!!pending;
  $("composer-note").textContent=pending?"Approve or cancel the message above first.":
    id==="local"?"Local: searches your vault. No model is called and nothing leaves this device.":
    p?.ready?`${providerName(id)}: before each message is sent you review exactly what leaves this device.`:
    `${providerName(id)} is not configured: set its API key and model, then restart Sovereign. You can still preview what would be sent.`;
}
function autosize(){const t=$("message");t.style.height="auto";t.style.height=Math.min(t.scrollHeight,220)+"px"}
function showView(view){
  $("chat-view").hidden=view!=="chat";$("memory-view").hidden=view!=="memory";
  for(const n of document.querySelectorAll("[data-view]"))n.classList.toggle("active",n.dataset.view===view);
  closeSidebar();
  if(view==="memory")refresh().catch(e=>setStatus(e.message,true));   // always show the vault as it is now
}
function closeSidebar(){$("shell").classList.remove("sidebar-open")}

// --- Memory: records, claims, revalidation and provenance --------------------------------------------------------
async function refresh(){
  const q=$("search").value.trim();
  const data=await api("/api/memories"+(q?"?q="+encodeURIComponent(q):""));
  state.records=data.records;
  const available=new Set(data.records.map(x=>x.id));
  // A pinned record that is no longer listed is unpinned, so a pin is always visible where it was chosen.
  state.selected=new Set([...state.selected].filter(x=>available.has(x)));
  drawRecords();drawContext();await refreshClaims();
}
const SUPPORT_LABEL={supported:"EVIDENCE INTACT",stale:"EVIDENCE CORRECTED — RE-CHECK",orphaned:"EVIDENCE MISSING OR UNVERIFIED — UNSUPPORTED"};
// Evidence-set integrity (ADR-0006, D-A): shown only when the complete evidence set is not committed.
const INTEGRITY_LABEL={unconfirmed:"MADE BEFORE SCHEMA 5 — REVALIDATION REQUIRED",mismatch:"EVIDENCE LINKS CHANGED — NOT AUTHORITATIVE"};
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
    if(c.integrity!=="committed")tags.append(el("span","tag claim-"+(c.integrity==="unconfirmed"?"stale":"orphaned"),INTEGRITY_LABEL[c.integrity]||"EVIDENCE SET UNKNOWN"));
    wrapper.append(tags,el("div","record-main",c.text));
    const evidence=el("div","claim-sources");
    for(const src of c.sources)evidence.append(el("div","",`Evidence ${src.id.slice(0,8)} [${src.state}]: ${src.content??"(not in this vault)"}`));
    const history=c.history.map(e=>`${e.to_status} by ${e.actor} ${displayDate(e.at)}${e.note?` (“${e.note}”)`:""}`).join(" → ");
    evidence.append(el("div","",`History: ${history}`+(c.supersedes_id?` · replaces ${c.supersedes_id.slice(0,8)}`:"")+(c.superseded_by?` · replaced by ${c.superseded_by.slice(0,8)}`:"")));
    wrapper.append(evidence);
    const foot=el("div","record-foot");const actions=el("div","record-actions");
    for(const action of CLAIM_ACTIONS[c.status]){const btn=el("button","",action[0].toUpperCase()+action.slice(1));btn.addEventListener("click",()=>claimAction(c,action));actions.append(btn)}
    if(c.integrity==="unconfirmed"&&CLAIM_ACTIONS[c.status].length){const btn=el("button","","Revalidate");btn.addEventListener("click",()=>openRevalidation(c));actions.append(btn)}
    const del=el("button","","Delete");del.addEventListener("click",async()=>{if(!confirm("Delete this claim and its history? Its evidence is not affected."))return;try{await api(`/api/claims/${encodeURIComponent(c.id)}`,{method:"DELETE"});purgeForgotten(["claim:"+c.id],"claim");await refreshClaims()}catch(e){alert(e.message)}});
    const why=el("button","","Provenance");why.addEventListener("click",()=>openProvenance("claim",c.id));
    actions.append(why,del);foot.append(el("span","",displayDate(c.created_at)),actions);wrapper.append(foot);container.append(wrapper)
  }
}
// Governed revalidation of a claim made before schema 5 (ADR-0006, D-A): every surviving source is shown in full and
// must be ticked before confirming; the request names exactly the links shown, so it never covers unseen evidence.
function openRevalidation(c){
 state.reval=c;$("reval-claim").replaceChildren(el("small","",`claim · ${c.status.toUpperCase()} · ${SUPPORT_LABEL[c.support]}`),document.createTextNode(c.text));
 const list=$("reval-evidence");list.replaceChildren();const boxes=[];
 for(const src of c.sources){
  const row=el("label","reval-source");const box=document.createElement("input");box.type="checkbox";box.disabled=src.state!=="active";
  const body=el("div","record-main");body.append(el("small","",`source ${src.id.slice(0,8)} · ${src.state}${src.sensitivity?" · "+src.sensitivity.toUpperCase():""}`),document.createTextNode(src.content??"(not in this vault)"));
  row.append(box,body);boxes.push(box);list.append(row);
 }
 const ok=c.support==="supported";
 $("reval-blocked").hidden=ok;$("reval-blocked").textContent=ok?"":`Its surviving evidence is ${c.support}, so it cannot be confirmed as it stands. Reconstruct it with evidence you choose.`;
 const sync=()=>{$("reval-confirm").disabled=!ok||!boxes.every(b=>b.checked)};for(const b of boxes)b.addEventListener("change",sync);sync();
 $("reval-note").value="";$("reval-dialog").showModal();
}
async function confirmRevalidation(){
 const c=state.reval;
 const body={confirm:true,expected_status:c.status,note:$("reval-note").value.trim().slice(0,500)||null,
  evidence:c.sources.map(src=>({id:src.id,evidence_sha256:c.source_hashes[src.id]}))};
 try{await api(`/api/claims/${encodeURIComponent(c.id)}/revalidate`,{method:"POST",body:JSON.stringify(body)});$("reval-dialog").close();await refreshClaims()}catch(e){alert(e.message)}
}
function drawRecords(){
  $("count").textContent=`${state.records.length} shown`;
  const container=$("records");container.replaceChildren();
  if(!state.records.length){container.append(el("p","empty","No records found. Capture a thought, or search a different phrase."));return}
  for(const record of state.records){
    const wrapper=el("div","record");const top=el("div","record-top");
    const ck=el("input");ck.type="checkbox";ck.checked=state.selected.has(record.id);
    ck.setAttribute("aria-label","Pin record for conversations");ck.addEventListener("change",()=>{if(ck.checked){if(state.selected.size>=8){ck.checked=false;alert("Pin up to eight sources.");return}state.selected.add(record.id)}else state.selected.delete(record.id);drawContext()});
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
        if(!confirm(`Forget this record${older?` and its ${older} earlier revision(s)`:""}, and ${plan.claims_forgotten} claim(s) derived from them?${plan.claims_forgotten?"\n\n"+shown+rest:""}\n\nThey are removed from the active vault and will not return on import or restore. In this tab's conversations, everything from the first message that used them onward is cleared. Backups and copies already sent to a provider may retain them.`))return;
        const r=await api(`/api/memories/${encodeURIComponent(record.id)}?expected_impact=${plan.impact_token}`,{method:"DELETE"});
        state.selected.delete(record.id);purgeForgotten([...r.record_ids.map(i=>"record:"+i),...r.claim_ids.map(i=>"claim:"+i)]);await refresh();
        setStatus(`Forgot ${r.records_forgotten} record revision(s) and ${r.claims_forgotten} derived claim(s); conversations in this tab no longer show them. Backups and provider copies are not covered.`);
      }catch(e){setStatus(e.message,true)}
    });
    const why=el("button","","Provenance");why.addEventListener("click",()=>openProvenance("record",record.id));
    actions.append(why,edit,remove);foot.append(t,created,actions);wrapper.append(foot);container.append(wrapper)
  }
}
function selectedRecords(){return state.records.filter(r=>state.selected.has(r.id))}
function drawContext(){
  // Pinned records are considered first for the next messages, but still pass every authority and disclosure rule.
  const chosen=selectedRecords();$("selected-count").textContent=`${chosen.length} pinned for conversations`;$("claim-source-count").textContent=String(chosen.length);
  const pins=$("pins");pins.replaceChildren();pins.hidden=!chosen.length;if(!chosen.length)return;
  pins.append(el("span","pins-label","Pinned for your next messages:"));
  for(const r of chosen){
    const chip=el("span","pin"+(r.sensitivity==="sensitive"?" sensitive":""),r.content.length>40?r.content.slice(0,40)+"…":r.content);chip.title=r.content;
    const x=button("×",()=>{state.selected.delete(r.id);drawRecords();drawContext()},"pin-remove");x.setAttribute("aria-label","Unpin");chip.append(x);pins.append(chip);
  }
  pins.append(button("Clear",()=>{state.selected.clear();drawRecords();drawContext()}));
}
const REASON_LABEL={invalid_state:"record in an unrecognized state — never used",superseded:"superseded",rejected:"rejected",contested:"contested",not_authoritative:"not approved memory",stale:"evidence corrected",orphaned:"evidence missing or unverified",revalidation_required:"made before schema 5 — awaits your revalidation",evidence_set_mismatch:"evidence links differ from their commitment — never used",sensitive_cloud:"sensitive — stays on this device",not_relevant:"not relevant to the message",duplicate:"duplicate content",budget_exceeded:"context budget exceeded"};
function itemNode(x){
 const node=el("div","context-item"+(x.role?"":" excluded"));
 const kind=x.role==="approved_memory"?"◆ approved memory":x.role==="evidence"?"▤ evidence":`✕ ${REASON_LABEL[x.reason]||x.reason}`;
 const meta=[x.label?`${kind} [${x.label}]`:kind,x.type==="claim"?`claim ${x.id.slice(0,8)} · ${x.status} · recorded ${displayDate(x.created_at)} · evidence ${x.source_ids.map(i=>i.slice(0,8)).join(", ")}`:`source ${x.id.slice(0,8)} · ${displayDate(x.created_at)}`,x.sensitivity.toUpperCase()];
 if(x.relevance.pinned)meta.push("PINNED");
 node.append(el("small","",meta.join(" · ")),document.createTextNode(x.content.length>280?x.content.slice(0,280)+"…":x.content));
 const why=el("button","text-button","Provenance ↗");why.type="button";why.addEventListener("click",()=>openProvenance(x.type==="claim"?"claim":"record",x.id));node.append(why);return node;
}
// --- SB-2a provenance navigation (read-only; never changes what a model may see) ---
// Identity is (kind, id): a record and a claim may share an id, so nodes and edge endpoints are keyed by both.
const EDGE_STATE={active:"evidence intact",superseded:"evidence since corrected"};
const provKey=x=>`${x.kind}:${x.id}`;
function claimStatusLabel(c){return c.authoritative?"APPROVED MEMORY":c.status==="approved"?"APPROVED · NO LONGER AUTHORITATIVE":c.status.toUpperCase()+" · NOT AUTHORITATIVE"}
function provItem(graph,node,note){
 const row=el("div","prov-item");const body=el("div","prov-text");
 const kind=node.kind==="claim"?[`claim · ${claimStatusLabel(node)} · ${SUPPORT_LABEL[node.support]}`,node.integrity!=="committed"?INTEGRITY_LABEL[node.integrity]||"EVIDENCE SET UNKNOWN":""].filter(Boolean).join(" · "):`source record · ${node.status.toUpperCase()} · ${node.sensitivity.toUpperCase()}`;
 body.append(el("small","",[kind,displayDate(node.created_at),note].filter(Boolean).join(" · ")),document.createTextNode(node.text_truncated?node.text+"…":node.text));
 const actions=el("div","record-actions");
 if(provKey(node)!==provKey(graph.focus)){const go=el("button","","Open");go.type="button";go.addEventListener("click",()=>openProvenance(node.kind,node.id));actions.append(go)}
 if(node.kind==="record"&&node.status==="active"){const pin=el("button","",state.selected.has(node.id)?"Pinned":"Pin for conversations");pin.type="button";pin.addEventListener("click",()=>pinFromProvenance(node.id,pin));actions.append(pin)}
 row.append(body,actions);return row;
}
function provSection(container,title,items,empty="None stored."){container.append(el("div","source-label",title));if(!items.length){container.append(el("p","empty",empty));return}for(const i of items)container.append(i)}
function renderProvenance(graph){
 const body=$("prov-body");body.replaceChildren();
 const byKey=new Map(graph.nodes.map(n=>[provKey(n),n]));const focusKey=provKey(graph.focus);const focus=byKey.get(focusKey);
 const out=type=>graph.edges.filter(e=>e.type===type&&provKey(e.from)===focusKey);const into=type=>graph.edges.filter(e=>e.type===type&&provKey(e.to)===focusKey);
 const near=new Set([focusKey]);const item=(end,note)=>{near.add(provKey(end));return provItem(graph,byKey.get(provKey(end)),note)};
 const head=el("div","prov-focus");head.append(provItem(graph,focus,"selected"));body.append(head);
 if(focus.kind==="claim"){
  const why=focus.authoritative?"Approved by you, and every piece of evidence it cites is present and unchanged.":focus.status!=="approved"?`Not approved memory: its status is ${focus.status}.`:focus.support!=="supported"?{stale:"You approved it, but evidence it cites has since been corrected; it no longer counts as approved memory.",orphaned:"You approved it, but evidence it cites is missing or has changed; it no longer counts as approved memory."}[focus.support]:{unconfirmed:"You approved it before schema 5, and Sovereign cannot prove its evidence set is complete; it counts as approved memory again once you revalidate it in the claims list.",mismatch:"You approved it, but its evidence links no longer match the set committed when it was made; it no longer counts as approved memory."}[focus.integrity]||"It does not count as approved memory.";
  body.append(el("p","micro",why));
  provSection(body,"SUPPORTED BY (evidence this claim cites)",out("SUPPORTED_BY").map(e=>item(e.to,EDGE_STATE[e.evidence_state])),focus.support==="orphaned"?"No verified evidence: what it cited is missing or has changed since the claim was made.":"None stored.");
  provSection(body,"SUPERSEDES (the earlier claim it replaced)",out("SUPERSEDES").map(e=>item(e.to)));
  provSection(body,"SUPERSEDED BY (the claim that replaced it)",into("SUPERSEDES").map(e=>item(e.from)));
  provSection(body,"DECISION HISTORY",focus.history.map(h=>el("p","",`${displayDate(h.at)} · ${h.from_status?h.from_status+" → ":""}${h.to_status} · by ${h.actor}${h.note?` · “${h.note}”`:""}`)));
  if(!focus.history_complete)body.append(el("p","micro",`Showing the ${focus.history.length} most recent decisions. The full history is kept in your vault and in exports.`));
 }else{
  provSection(body,"CITED BY (claims resting on this record)",into("SUPPORTED_BY").map(e=>item(e.from,EDGE_STATE[e.evidence_state])));
  provSection(body,"CORRECTS (the earlier revision)",out("CORRECTS").map(e=>item(e.to)));
  provSection(body,"CORRECTED BY (the newer revision)",into("CORRECTS").map(e=>item(e.from)));
 }
 const further=graph.nodes.filter(n=>!near.has(provKey(n)));
 if(graph.hops>1)provSection(body,"FURTHER LINKS (two steps away)",further.map(n=>provItem(graph,n,"")));
 if(graph.truncated)body.append(el("p","micro","More linked items exist than this view shows; open one of them to continue."));
}
async function openProvenance(kind,id){
 state.provFocus={kind,id};const dialog=$("prov-dialog");
 try{const graph=await api(`/api/provenance/${encodeURIComponent(kind)}/${encodeURIComponent(id)}?hops=${$("prov-hops").value}`);renderProvenance(graph)}
 catch(e){$("prov-body").replaceChildren(el("p","empty",e.status===404?"This item is no longer in your vault.":`Could not load provenance: ${e.message}`))}
 if(!dialog.open)dialog.showModal();
}
function pinFromProvenance(id,button){
 if(!state.records.some(r=>r.id===id)){button.textContent="Not in the current library view";return}
 if(!state.selected.has(id)&&state.selected.size>=8){button.textContent="Up to eight sources";return}
 state.selected.add(id);drawRecords();drawContext();button.textContent="Pinned";
}

// --- Start ------------------------------------------------------------------------------------------------------
async function init(){
 const status=await api("/api/status");state.providers=status.providers;
 if(status.conversation)state.conversation=status.conversation;
 const select=$("provider");select.replaceChildren();
 for(const p of status.providers){const opt=el("option","",providerName(p.id)+(p.cloud&&!p.ready?" (not configured)":""));opt.value=p.id;select.append(opt)}
 select.value=(status.providers.find(p=>p.cloud&&p.ready)||{id:"local"}).id;
 select.addEventListener("change",()=>{updateComposer();drawChat()});
 $("composer").addEventListener("submit",e=>{e.preventDefault();send()});
 $("message").addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey&&!e.isComposing){e.preventDefault();send()}});
 $("message").addEventListener("input",autosize);
 $("new-chat").addEventListener("click",()=>{const chat=activeChat();if(chat&&!chat.turns.length){showView("chat");$("message").focus();return}newChat()});
 $("chat-search").addEventListener("input",e=>{state.query=e.target.value.trim();drawChatList()});
 $("toggle-sidebar").addEventListener("click",e=>{e.stopPropagation();$("shell").classList.toggle("sidebar-open")});
 document.querySelector("main").addEventListener("click",closeSidebar);   // tapping outside the drawer closes it
 for(const nav of document.querySelectorAll("[data-view]"))nav.addEventListener("click",()=>showView(nav.dataset.view));
 $("save").addEventListener("click",async()=>{const content=$("note").value.trim();if(!content){setStatus("Write a note first.",true);return}$("save").disabled=true;try{await api("/api/memories",{method:"POST",body:JSON.stringify({content,sensitivity:$("sensitivity").value})});$("note").value="";$("search").value="";await refresh();setStatus("Source record saved locally. No model was contacted.")}catch(e){setStatus(e.message,true)}finally{$("save").disabled=false}});
 $("more-claims").addEventListener("click",()=>loadOlderClaims().catch(e=>alert(e.message)));
 $("add-claim").addEventListener("click",async()=>{const text=$("claim-text").value.trim();const source_ids=selectedRecords().map(x=>x.id);if(!text||!source_ids.length){alert("Select at least one source record and write the claim.");return}try{await api("/api/claims",{method:"POST",body:JSON.stringify({text,source_ids})});$("claim-text").value="";await refreshClaims()}catch(e){alert(e.message)}});
 $("refresh").addEventListener("click",()=>refresh().catch(e=>alert(e.message)));
 $("search").addEventListener("keydown",e=>{if(e.key==="Enter")refresh().catch(err=>alert(err.message))});
 $("edit-form").addEventListener("submit",async e=>{e.preventDefault();try{const original=state.records.find(r=>r.id===state.editId);await api(`/api/memories/${encodeURIComponent(state.editId)}/correct`,{method:"POST",body:JSON.stringify({content:$("edit-text").value,sensitivity:original.sensitivity})});state.selected.delete(state.editId);$("edit-dialog").close();$("search").value="";await refresh();setStatus("Correction saved as new active revision.")}catch(err){alert(err.message)}});
 $("cancel-edit").addEventListener("click",()=>$("edit-dialog").close());
 $("prov-close").addEventListener("click",()=>$("prov-dialog").close());
 $("prov-hops").addEventListener("change",()=>{if(state.provFocus)openProvenance(state.provFocus.kind,state.provFocus.id)});
 $("reval-cancel").addEventListener("click",()=>$("reval-dialog").close());
 $("reval-confirm").addEventListener("click",confirmRevalidation);
 $("reval-reconstruct").addEventListener("click",()=>{const c=state.reval;$("reval-dialog").close();claimAction(c,"correct")});
 $("export").addEventListener("click",()=>{window.location.href="/api/export"});
 const loadFile=async(trusted)=>{const file=$("import-file").files[0];if(!file){alert("Choose an export file first.");return}
  try{const payload=JSON.parse(await file.text());
   if(trusted&&!confirm("Trusted restore: only for your own Sovereign backup. It restores prior approvals and applies its deletions to this vault. Continue?"))return;
   const r=trusted?await api("/api/restore",{method:"POST",body:JSON.stringify({confirm_trusted_restore:true,backup:payload})}):await api("/api/import",{method:"POST",body:JSON.stringify(payload)});
   const skipped=r.records_skipped?` ${r.records_skipped} records were skipped because they would replace, resurrect or re-support existing evidence.`:"";
   await refresh();
   if(trusted&&((payload.tombstones||[]).length||(payload.claim_tombstones||[]).length||r.claims_forgotten))clearAllConversations("restore");
   invalidateReviews("Your vault changed since this preview. Review the updated context before sending.");
   setStatus((trusted?`Restored ${r.imported} records and ${r.claims_restored} claims (${r.approved_claims_restored} approved). Conversations in this tab that could depend on the backup's deletions were cleared.`:`Imported ${r.imported} records; ${r.claims_imported_as_proposed} claims arrived as unverified proposals.`)+skipped)}
  catch(e){setStatus(e.message,true)}};
 $("import").addEventListener("click",()=>loadFile(false));$("restore").addEventListener("click",()=>loadFile(true));
 drawChatList();drawChat();autosize();
 await refresh();
}
init().catch(err=>{$("composer-note").textContent="Initialization failed: "+err.message});
