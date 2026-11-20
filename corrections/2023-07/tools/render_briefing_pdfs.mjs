#!/usr/bin/env node
// Build A4 briefing PDFs from the July 2023 retrospective source components.
// Usage: node render_briefing_pdfs.mjs COMPONENTS_DIRECTORY OUTPUT_DIRECTORY [YYYY-MM-DD ...]
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

function briefingPDF(nonretail, retail, region = {}) {
  const date = nonretail.date;
  if (date !== retail.date || !date) throw Error("Edition date mismatch");
  const boxes = [
    ["geo", "Geographic Macro Overview"], ["sectors","Sector Deep Dive"],
    ["earnings_pattern","Earnings Pattern"], ["underowned","Underowned Themes"],
    ["crypto","Crypto"], ["flows","Capital Flows & Liquidity"],
    ["anticipatory","Anticipatory Positioning"], ["catalysts","Stock Catalysts"],
    ["retail","What Retail Is Playing"]
  ];
  const pageW=595.28, pageH=841.89, left=54, right=541, bottom=67;
  const ink="0.10 0.14 0.17", navy="0.07 0.13 0.19", muted="0.29 0.36 0.39", teal="0.06 0.35 0.39", rule="0.81 0.84 0.83";
  const glyph = {"€":128,"’":146,"‘":145,"“":147,"”":148,"…":133,"•":149,"–":150,"—":151,"−":22,"ł":23,"Ł":24,"ę":25,"ś":26,"ń":27,"ą":28,"ż":29,"ź":30,"Ś":31,"œ":156};
  const extra = {22:"minus",23:"lslash",24:"Lslash",25:"eogonek",26:"sacute",27:"nacute",28:"aogonek",29:"zdotaccent",30:"zacute",31:"Sacute"};
  const normalize=s=>String(s??"").normalize("NFC").replace(/[\u00a0\u202f]/g," ").replace(/[\u200b\ufe0f]/g,"").replace(/\s*[⚡✓⚠]+\s*/gu," ").replace(/[\u2009\t]/g," ").trim();
  const codeOf=ch=>glyph[ch]??(ch.charCodeAt(0)<=255?ch.charCodeAt(0):null);
  const bytes=(str)=>Array.from(str,ch=>{
    const n=codeOf(ch);
    if(n!==null)return n;
    const basic=ch.normalize("NFD").replace(/\p{M}/gu,"");
    if(basic.length===1&&basic.charCodeAt(0)<127)return basic.charCodeAt(0);
    throw Error("Font cannot encode "+ch+" U+"+ch.codePointAt(0).toString(16));
  });
  const literal=str=>"("+bytes(str).map(c=>(c<32||c>126?"\\"+c.toString(8).padStart(3,"0"):[40,41,92].includes(c)?"\\"+String.fromCharCode(c):String.fromCharCode(c))).join("")+")";
  const urlLiteral=s=>literal(String(s).replace(/[^\x20-\x7e]/gu,ch=>encodeURIComponent(ch)));
  const digits=(x)=>Number(x.toFixed(2)).toString();
  const roman=[250,333,408,500,500,833,778,180,333,333,500,564,250,333,250,278,500,500,500,500,500,500,500,500,500,500,278,278,564,564,564,444,921,722,667,667,722,611,556,722,722,333,389,722,611,889,722,722,556,722,667,556,611,722,722,944,722,722,611,333,278,333,469,500,333,444,500,444,500,444,333,500,500,278,278,500,278,778,500,500,500,500,333,389,278,500,500,722,500,500,444,480,200,480,541];
  const helv=[278,278,355,556,556,889,667,191,333,333,389,584,278,333,278,278,556,556,556,556,556,556,556,556,556,556,278,278,584,584,584,556,1015,667,667,722,722,667,611,778,722,278,500,667,556,833,722,778,667,778,722,667,611,722,667,944,667,667,611,278,278,278,469,556,333,556,556,500,556,556,278,556,556,222,222,500,222,833,556,556,556,556,333,500,278,556,500,722,500,500,500,334,260,334,584];
  function width(str,font,size) {
    const widths=font==="F1"?roman:helv;
    let w=0;
    for(const ch of str) {
      const normalized=ch.normalize("NFD").replace(/\p{M}/gu,"");
      const c=normalized.charCodeAt(0);
      w+=c>=32&&c<=126?widths[c-32]:(ch==="—"?1000:ch==="–"?500:"‘’".includes(ch)?333:"“”".includes(ch)?444:ch==="·"?250:ch==="ł"?278:550);
    }
    return w*size/1000*(font==="F3"?1.08:1);
  }
  let pages=[],p,section="",y,major=[];
  const sourceList=[],sourceByUrl=new Map(),explicitLinks=new Map(), unknownRefs=new Set();
  function register(source) {
    if(!source || !/^https?:\/\//i.test(source.url||""))return null;
    if(sourceByUrl.has(source.url))return sourceByUrl.get(source.url);
    const entry={title:normalize(source.title||source.url),url:source.url,date:source.date||"",n:sourceList.length+1};
    sourceList.push(entry);sourceByUrl.set(source.url,entry);return entry;
  }
  const registry=list=>new Map((list||[]).map(s=>[String(s.id),s]));
  const nr=registry(nonretail.sources), rr=registry(retail.sources), gr=registry(region.sources);
  function textAt(page,x,base,s,font,size,color=ink) {
    if(!s)return;
    page.ops.push(`BT /${font} ${digits(size)} Tf ${color} rg 1 0 0 1 ${digits(x)} ${digits(base)} Tm ${literal(s)} Tj ET`);
  }
  function lineAt(page,x1,y1,x2,y2,color=rule) {page.ops.push(`${color} RG 0.6 w ${digits(x1)} ${digits(y1)} m ${digits(x2)} ${digits(y2)} l S`);}
  function newPage(){p={ops:[],links:[],section};pages.push(p);y=754;}
  function need(h){if(y-h<bottom)newPage();}
  function wrapLine(tokens,font,size,max) {
    const output=[];let line=[],advance=0,space=width(" ",font,size);
    for(const tok of tokens) {
      const f=tok.ref?"F2":font, fs=tok.ref?size*0.75:size;
      const w=width(tok.s,f,fs);
      if(w>max && !tok.ref) {
        if(line.length){output.push(line);line=[];advance=0;}
        let seg="";
        for(const c of tok.s){if(seg&&width(seg+c,font,size)>max){output.push([{...tok,s:seg,w:width(seg,font,size)}]);seg="";}seg+=c;}
        if(seg){line=[{...tok,s:seg,w:width(seg,font,size)}];advance=line[0].w;}
        continue;
      }
      if(line.length&&advance+space+w>max){output.push(line);line=[];advance=0;}
      if(line.length)advance+=space;
      line.push({...tok,w});advance+=w;
    }
    if(line.length)output.push(line);
    return output;
  }
  function parseParagraph(input,map) {
    let t=normalize(input).replace(/\*\*([^*]+)\*\*/g,"$1").replace(/\[\[([\w.:-]+)\]\]/g,"[$1]");
    t=t.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,(_,label,url)=>{
      let e=register({title:label,url});let key="url"+e.n;explicitLinks.set(key,e);return `${label} [${key}]`;});
    const out=[];
    for(const m of t.matchAll(/\[([\w.:-]+)\]|[^\s[\]]+|\[|\]/g)){
      if(m[1]){
        const src=map.get(m[1]);const e=explicitLinks.get(m[1])||register(src);
        if(e){out.push({s:`[${e.n}]`,ref:e});continue;}
        unknownRefs.add(m[1]);
      }
      out.push({s:m[0]});
    }
    return out;
  }
  function prose(s,map,{size=11.4,font="F1",color=ink,leading=15.45,post=8.5,link=null}={}) {
    const groups=String(s??"").split(/\n\s*\n/).filter(t=>t.trim());
    for(const g of groups) {
      const tokens=parseParagraph(g,map);
      const rows=wrapLine(tokens,font,size,right-left);
      if(rows.length>1)need(2*leading+2);
      for(let i=0;i<rows.length;i++){
        if(rows.length-i===2&&y-leading<bottom+5)newPage();
        need(2);
        let xx=left,run=[],start=left,ws=width(" ",font,size);
        const flush=()=>{if(run.length){textAt(p,start,y,run.join(" "),font,size,color);run=[];}};
        for(const tok of rows[i]){
          if(tok.ref) {
            flush();textAt(p,xx,y+2,tok.s,"F2",size*0.75,teal);
            p.links.push({box:[xx-1,y,xx+tok.w+1,y+size+2],url:tok.ref.url});
          } else {if(!run.length)start=xx;run.push(tok.s);}
          xx+=tok.w+ws;
        }
        flush();
        if(link)p.links.push({box:[left,y-2,xx-ws+1,y+size],url:link});
        y-=leading;
      }
      y-=post;
    }
  }
  function heading(s,level) {
    let title=normalize(s);
    if(!title)return;
    const font=level===1?"F3":"F3", sz=level===1?19:level===2?14.4:10.15;
    const rows=wrapLine(title.split(/\s+/).map(s=>({s})),font,sz,right-left);
    need((rows.length-1)*(sz+3)+(level===1?86:level===2?62:42));
    if(level===1){y-=4;lineAt(p,left,y+7,right,y+7);y-=19;major.push({title,page:pages.length-1,y:y+22});}
    if(level===2)y-=7;
    if(level===3)y-=1;
    for(const row of rows){textAt(p,left,y,row.map(t=>t.s).join(" "),font,sz,level===3?teal:navy);y-=sz+4;}
    if(level<3)y-=3;
  }
  const fmtd = new Date(date+"T00:00:00Z").toLocaleDateString("en-GB",{timeZone:"UTC",day:"numeric",month:"long",year:"numeric",weekday:"long"});
  newPage();
  textAt(p,left,744,"Market Intelligence Briefing","F3",27,navy);
  textAt(p,left,715,fmtd,"F2",14,teal);textAt(p,left,695,"As of 00:00 UTC","F2",9,muted);y=668;
  if(nonretail.standfirst)prose(nonretail.standfirst,nr,{size:12.2,leading:17});
  for(const [key,title] of boxes) {
    section=title;
    heading(title,1);
    if(key==="retail")prose(retail.intro,rr,{size:12,leading:16});
    const collection=key==="retail"?retail.plays:nonretail[key];
    if(!collection)throw Error(`Missing ${date} ${key}`);
    for(const item of Array.isArray(collection)?collection:[collection]){
      let headingText=normalize(item.title||item.key);
      const sym=String(item.key??"");
      if(["sectors","catalysts"].includes(key)&&/^[A-Z][A-Z0-9.^-]{0,8}$/.test(sym)&&!headingText.includes(sym))headingText+=`  /  ${sym}`;
      if(item.stance&&!headingText.toLowerCase().includes(item.stance.toLowerCase()))headingText+=`  ·  ${item.stance}`;
      if(headingText && headingText.toLowerCase()!==title.toLowerCase())heading(headingText,2);
      for(const [l,t] of item.parts||[]){heading(l,3);prose(t,key==="retail"?rr:nr);}
      if(key==="geo" && region[item.key])for(const [l,t]of region[item.key]){heading(l,3);prose(t,gr);}
      y-=3;
    }
  }
  section="Sources";heading("Sources",1);
  for(const e of [...sourceList]){
    const sourceLine=`${e.n}. ${e.date?e.date+"  ·  ":""}${e.title}`;
    prose(sourceLine,new Map(),{font:"F2",size:9.2,leading:12.5,post:4.5,color:teal,link:e.url});
  }
  if(unknownRefs.size)throw Error("Unresolved citations "+[...unknownRefs].join(", "));
  const objects=[null],reserve=()=>{objects.push(null);return objects.length-1;},put=(id,txt)=>{objects[id]=txt;};
  const catalog=reserve(), pageTree=reserve(), info=reserve(), enc=reserve(),uni=reserve();
  const fonts=["Times-Roman","Helvetica","Helvetica-Bold"].map(()=>reserve());
  const ids=pages.map(()=>reserve()), outlines=reserve(), marks=major.map(()=>reserve());
  const stream=s=>`<< /Length ${s.length} >>\nstream\n${s}endstream`;
  put(enc,`<< /Type /Encoding /BaseEncoding /WinAnsiEncoding /Differences [22 ${Object.values(extra).map(g=>"/"+g).join(" ")}] >>`);
  let hex4=n=>n.toString(16).padStart(4,"0"),toUni=new Map;
  for(let i=32;i<256;i++)toUni.set(i,i);
  for(const [ch,b]of Object.entries(glyph))toUni.set(b,ch.codePointAt(0));
  const mapPairs=[...toUni].sort((a,b)=>a[0]-b[0]);let cm="/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n/CMapName /BriefingUnicode def /CMapType 2 def\n1 begincodespacerange\n<00> <FF>\nendcodespacerange\n";
  for(let i=0;i<mapPairs.length;i+=90){let part=mapPairs.slice(i,i+90);cm+=`${part.length} beginbfchar\n`+part.map(([b,u])=>`<${b.toString(16).padStart(2,"0")}> <${hex4(u)}>`).join("\n")+"\nendbfchar\n";}
  cm+="endcmap CMapName currentdict /CMap defineresource pop end end\n";put(uni,stream(cm));
  fonts.forEach((f,i)=>put(f,`<< /Type /Font /Subtype /Type1 /BaseFont /${["Times-Roman","Helvetica","Helvetica-Bold"][i]} /Encoding ${enc} 0 R /ToUnicode ${uni} 0 R >>`));
  const linkCount=pages.reduce((v,p)=>v+p.links.length,0);
  pages.forEach((page,i)=>{
    textAt(page,left,799,"ZEMBIHF   /   MARKET INTELLIGENCE","F3",8.2,teal);
    textAt(page,right-width(date,"F2",8.2),799,date,"F2",8.2,muted);
    lineAt(page,left,787,right,787);lineAt(page,left,49,right,49);
    textAt(page,left,32,page.section||"Market Intelligence Briefing","F2",8,muted);
    const counter=`${i+1} / ${pages.length}`;textAt(page,right-width(counter,"F2",8),32,counter,"F2",8,muted);
    const anns=page.links.map(({box,url})=>{let id=reserve();put(id,`<< /Type /Annot /Subtype /Link /Rect [${box.map(digits).join(" ")}] /Border [0 0 0] /A << /S /URI /URI ${urlLiteral(url)} >> >>`);return id;});
    let sc=reserve();put(sc,stream(page.ops.join("\n")+"\n"));
    put(ids[i],`<< /Type /Page /Parent ${pageTree} 0 R /MediaBox [0 0 ${pageW} ${pageH}] /Resources << /Font << ${fonts.map((n,i)=>`/F${i+1} ${n} 0 R`).join(" ")} >> >> /Contents ${sc} 0 R${anns.length?" /Annots ["+anns.map(a=>`${a} 0 R`).join(" ")+"]":""} >>`);
  });
  put(pageTree,`<< /Type /Pages /Count ${ids.length} /Kids [${ids.map(a=>`${a} 0 R`).join(" ")}] >>`);
  marks.forEach((id,i)=>{let m=major[i];put(id,`<< /Title ${literal(m.title)} /Parent ${outlines} 0 R${i?" /Prev "+marks[i-1]+" 0 R":""}${i<marks.length-1?" /Next "+marks[i+1]+" 0 R":""} /Dest [${ids[m.page]} 0 R /XYZ null ${digits(m.y)} null] >>`);});
  put(outlines,`<< /Type /Outlines /Count ${marks.length} /First ${marks[0]} 0 R /Last ${marks[marks.length-1]} 0 R >>`);
  put(catalog,`<< /Type /Catalog /Pages ${pageTree} 0 R /Outlines ${outlines} 0 R /PageMode /UseNone /Lang (en-GB) >>`);
  put(info,`<< /Title ${literal("Market Intelligence Briefing - "+date)} /Subject (Point-in-time market retrospective) >>`);
  let data="%PDF-1.4\n", offsets=[0];
  for(let i=1;i<objects.length;i++){if(!objects[i])throw Error("Missing PDF object "+i);offsets.push(data.length);data+=`${i} 0 obj\n${objects[i]}\nendobj\n`;}
  let xref=data.length;
  data+=`xref\n0 ${objects.length}\n0000000000 65535 f \n`+offsets.slice(1).map(n=>n.toString().padStart(10,"0")+" 00000 n \n").join("")+`trailer\n<< /Size ${objects.length} /Root ${catalog} 0 R /Info ${info} 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  if(/[^\x00-\x7f]/.test(data)||!offsets.slice(1).every((v,j)=>data.startsWith(`${j+1} 0 obj`,v))||!data.startsWith("xref",xref))throw Error("PDF cross-reference verification failed");
  return {data,pages:pages.length,links:linkCount,sources:sourceList.length,sections:major.length};
}

const [, , componentRoot, outRoot, ...selected] = process.argv;
if (!componentRoot || !outRoot) {
  throw Error("Usage: node render_briefing_pdfs.mjs COMPONENTS_DIRECTORY OUTPUT_DIRECTORY [YYYY-MM-DD ...]");
}
const readJSON = path => JSON.parse(readFileSync(path, "utf8"));
const dates = selected.length ? selected : readdirSync(join(componentRoot, "retail"))
  .filter(name => /^\d{4}-\d\d-\d\d\.json$/.test(name))
  .map(name => name.slice(0, 10)).sort();
const regionMap = readJSON(join(componentRoot, "regions", "july-03-11.json"));
mkdirSync(outRoot, { recursive: true });
for (const date of dates) {
  if (!/^\d{4}-\d\d-\d\d$/.test(date)) throw Error("Invalid edition date: "+date);
  const draft = readJSON(join(componentRoot, "nonretail", date+".json"));
  const retail = readJSON(join(componentRoot, "retail", date+".json"));
  const result = briefingPDF(draft, retail, regionMap[date]);
  const path = join(outRoot, "report_"+date+".pdf");
  writeFileSync(path, result.data, "ascii");
  process.stdout.write(`${date}  ${result.pages} pages  ${result.links} citation links  ${path}\n`);
}
