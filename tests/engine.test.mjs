import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {SAMPLE,DEMO_PROFILE,MODES,normalizeRows,rankPeople,parseCsv,safeUrl} from '../dist/engine.js';
test('the same room produces meaningfully different shortlists for different intentions',()=>{
 const winners=Object.keys(MODES).map(mode=>rankPeople(SAMPLE,DEMO_PROFILE,mode,MODES[mode].goal).filter(p=>p.eligible)[0].id);
 assert.equal(new Set(winners).size,5);
 assert.equal(winners[0],'d1');assert.equal(winners[1],'d3');assert.equal(winners[2],'d4');
});
test('hiring does not confuse recruiters seeking candidates with people seeking jobs',()=>{
 const results=rankPeople(SAMPLE,DEMO_PROFILE,'hiring',MODES.hiring.goal);
 assert.equal(results.find(p=>p.id==='d7').eligible,false);
 assert.deepEqual(results.filter(p=>p.eligible).map(p=>p.id).sort(),['d10','d9']);
});
test('editing an intention changes the ranking',()=>{
 const ai=rankPeople(SAMPLE,DEMO_PROFILE,'collaborate',MODES.collaborate.goal);
 const energy=rankPeople(SAMPLE,DEMO_PROFILE,'collaborate','Energy grid and infrastructure partnerships');
 assert.notEqual(ai[0].id,energy[0].id);assert.equal(energy[0].id,'d6');
});
test('editing interests changes social recommendations without using professional titles',()=>{
 const music=rankPeople(SAMPLE,{...DEMO_PROFILE,interests:'Jazz and music'},'social','Meet people who like jazz');
 assert.ok(music.filter(p=>p.eligible).every(p=>/jazz|music|guitar/i.test(p.interests)));
 const noInterests=rankPeople(SAMPLE.map(p=>({...p,interests:''})),DEMO_PROFILE,'social','Art and travel');
 assert.equal(noInterests.filter(p=>p.eligible).length,0);
});
test('uploaded workbook aliases import all ten attendees without inventing biographies',()=>{
 const data=JSON.parse(fs.readFileSync(new URL('../dist/imported.json',import.meta.url)));
 const {people}=normalizeRows(data);assert.equal(people.length,10);
 assert.ok(people.every(p=>!p.bio&&!p.skills&&!p.hiring&&!p.interests&&!p.fictional));
 const social=rankPeople(people,DEMO_PROFILE,'social',MODES.social.goal);assert.ok(social.every(p=>p.score===null));
});
test('deduplication uses a complete profile identity, while preserving different domains',()=>{
 const rows=[{Name:'A',Linkedin:'https://www.linkedin.com/in/a/'},{Name:'A',Linkedin:'https://linkedin.com/in/a'},{Name:'B',Linkedin:'https://example.org/in/a'}];
 const r=normalizeRows(rows);assert.equal(r.people.length,2);assert.equal(r.duplicates,1);
});
test('CSV supports quoted commas, escaped quotes, newlines, BOM, and empty cells',()=>{
 const r=parseCsv('\uFEFFName,Job Title,Bio\r\n"Jane, Doe",Designer,"Works with ""AI""\nand products"\r\nSam,,\r\n');
 assert.equal(r.length,2);assert.equal(r[0].Name,'Jane, Doe');assert.equal(r[0].Bio,'Works with "AI"\nand products');assert.equal(r[1]['Job Title'],'');
 assert.throws(()=>parseCsv('Name\n"unclosed'),/unclosed/);
});
test('unsafe URL schemes never become profile links',()=>{
 for(const u of ['javascript:alert(1)','data:text/html,test','file:///tmp/a','not a url'])assert.equal(safeUrl(u),'');
 assert.ok(safeUrl('https://linkedin.com/in/a').startsWith('https://'));
});
test('unknown input fails usefully and sparse evidence never produces invented intent',()=>{
 assert.throws(()=>normalizeRows([]),/No attendees/);
 assert.throws(()=>normalizeRows([{Company:'Example'}]),/Row 2/);
 assert.throws(()=>normalizeRows(Array(501).fill({Name:'A'})),/500/);
 const people=normalizeRows([{Name:'A','Job Title':'AI product founder',Company:'Example'}]).people;
 const r=rankPeople(people,DEMO_PROFILE,'career',MODES.career.goal)[0];assert.equal(r.breakdown[2].value,0);assert.ok(r.gaps.some(s=>s.includes('No current hiring')));
});
test('scores stay within the defined scale and irrelevant profiles stay unranked',()=>{
 for(const mode of Object.keys(MODES)){const ranked=rankPeople(SAMPLE,DEMO_PROFILE,mode,MODES[mode].goal);for(const p of ranked){assert.ok(p.score===null||p.score>=0&&p.score<=10);assert.equal(p.eligible,p.score!==null);if(p.score!==null)assert.ok(Math.abs(p.breakdown.reduce((s,b)=>s+b.value,0)-p.score)<.051);}}
});
