// Transparent, deterministic demo ranking. No live profile enrichment or LLM calls.
export const THEMES = {
  'AI & data': ['ai','artificial intelligence','machine learning','ml','data','model','llm','alignment','deepmind'],
  'Product & design': ['product','design','ux','prototype','prototyping','discovery'],
  'Strategy & growth': ['strategy','growth','gtm','go-to-market','market','business','partnership','expansion'],
  'Engineering': ['engineer','engineering','developer','software','infrastructure','coding','systems'],
  'Research': ['research','researcher','phd','science','scientific','university','alignment'],
  'Industrial & energy': ['energy','industrial','manufacturing','grid','rail','robotics','data center'],
  'Community': ['community','mentor','mentoring','events','workshop'],
  'Art & creativity': ['art','painting','museum','museums','photography','creative'],
  'Outdoors & travel': ['hiking','travel','outdoors','climbing'],
  'Motorsport': ['f1','formula 1','karting','motorsport'],
  'Music': ['music','jazz','guitar','concert']
};
const SOCIAL = ['Art & creativity','Outdoors & travel','Motorsport','Music'];
const escapeRx=s=>s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
export function themes(text='') {return Object.entries(THEMES).filter(([,ws])=>ws.some(w=>new RegExp('\\b'+escapeRx(w)+'(?:s)?\\b','i').test(text))).map(([k])=>k);}
export const MODES = {
  collaborate: {label:'Collaborate',goal:'Meet AI product builders and potential design partners.',icon:'spark'},
  career: {label:'Career',goal:'Meet people hiring for AI product and strategy roles.',icon:'briefcase'},
  learn: {label:'Learn',goal:'Learn how AI research becomes useful products.',icon:'book'},
  hiring: {label:'Hire',goal:'Find AI engineers and product designers for my team.',icon:'users'},
  social: {label:'Make friends',goal:'Meet people who enjoy art, travel, and F1.',icon:'coffee'}
};
export const DEMO_PROFILE={name:'Manisha Sharma',title:'Product builder · Strategy & AI',background:'Seven years building industrial software at GE, spanning product design, engineering, and strategy. MBA in AI and Business Analytics. Building AI agents and data-center site-selection tools.',interests:'Art, painting, museums, travel, F1 and go-karting.'};
export const SAMPLE = [
 {id:'d1',name:'Maya Chen',role:'Co-founder & Head of Product',company:'Forma AI',bio:'Building AI assistants for manufacturing teams. Looking for product design partners to test a new workflow product.',skills:'AI, product design, industrial software, user discovery',interests:'Art, museums, hiking',seeking:'Design partners and pilot collaborators',hiring:'Product designer',color:'#dfe8cb'},
 {id:'d2',name:'Arjun Mehta',role:'AI Platform Engineer',company:'Northstar Compute',bio:'Building developer infrastructure for AI inference. Interested in collaborating on practical agent systems.',skills:'AI, engineering, infrastructure, systems',interests:'F1, karting, travel',seeking:'Agent builders and technical collaborators',hiring:'',color:'#d5e4ec'},
 {id:'d3',name:'Sofia Laurent',role:'Director of Product',company:'Circuit Works',bio:'Leads an industrial software product team. Hiring a product strategist with manufacturing and AI experience.',skills:'Product, strategy, AI, manufacturing, design',interests:'Painting, museums, jazz',seeking:'Product strategists for the team',hiring:'AI product strategist',color:'#edd6cb'},
 {id:'d4',name:'Daniel Park',role:'Research Scientist',company:'Lattice Lab',bio:'Researches machine learning alignment and model evaluation. Exploring how research moves into useful products.',skills:'AI, research, alignment, product evaluation',interests:'Photography, hiking',seeking:'Applied research conversations',hiring:'',color:'#dfd8ec'},
 {id:'d5',name:'Nina Rao',role:'Founder',company:'Fieldnote',bio:'Creates product discovery tools for enterprise teams. Looking for collaborators to prototype AI workflows.',skills:'Product design, AI, software, user discovery',interests:'Art, travel, music',seeking:'Product builders and design partners',hiring:'',color:'#f0e2b9'},
 {id:'d6',name:'Leo Fischer',role:'Partnerships Lead',company:'Gridline',bio:'Develops energy and data-center partnerships across APAC. Interested in strategy and market intelligence collaboration.',skills:'Energy, strategy, market research, infrastructure',interests:'F1, travel, photography',seeking:'Market intelligence collaborators',hiring:'',color:'#d3e6d9'},
 {id:'d7',name:'Elena Brooks',role:'Technical Recruiter',company:'Tandem Talent',bio:'Recruits AI engineers and product leaders for enterprise software teams. Open to meeting experienced product and strategy candidates.',skills:'Recruiting, talent acquisition',interests:'Hiking, jazz',seeking:'AI and product candidates',hiring:'Product leader, AI engineer',color:'#e7d7d5'},
 {id:'d8',name:'Owen Williams',role:'Community Lead',company:'Builders Table',bio:'Runs workshops for product builders and facilitates cross-functional AI projects.',skills:'Community, product, AI, workshop',interests:'Art, F1, travel, guitar',seeking:'Workshop collaborators',hiring:'',color:'#cfe3e3'},
 {id:'d9',name:'Yuki Tanaka',role:'Machine Learning Engineer',company:'Everyday Robotics',bio:'Builds machine learning systems for manufacturing robots. Open to new engineering opportunities.',skills:'AI, engineering, robotics, manufacturing',interests:'Climbing, photography',seeking:'Engineering roles and technical peers',openToWork:'Yes',hiring:'',color:'#e6dfcc'},
 {id:'d10',name:'Amara Okafor',role:'Product Designer',company:'Studio Common',bio:'Designs enterprise software and AI interfaces. Open to a product design role or collaborative prototype.',skills:'Product, design, AI, prototyping',interests:'Painting, museums, travel',seeking:'Product design opportunities',openToWork:'Yes',hiring:'',color:'#dce2ef'},
 {id:'d11',name:'Tomás Silva',role:'PhD Researcher',company:'Meridian University',bio:'Studies AI model reliability and interpretable machine learning. Looking for research discussions.',skills:'AI, research, machine learning, model evaluation',interests:'Jazz, guitar',seeking:'Research peers',hiring:'',color:'#dce4ca'},
 {id:'d12',name:'Grace Kim',role:'Founder & Curator',company:'Sunday Club',bio:'Builds a creative community around museum visits, painting sessions, and travel.',skills:'Community, art, events',interests:'Art, painting, museums, travel, F1',seeking:'Friends and creative collaborators',hiring:'',color:'#eadad0'}
].map(p=>({...p,source:'Illustrative demo bio',fictional:true,linkedin:''}));
const aliases={'name':'name','attendee name':'name','job title':'role','role':'role','title':'role','current company / school':'company','current company':'company','company':'company','linkedin':'linkedin','linkedin url':'linkedin','bio':'bio','about':'bio','summary':'bio','skills':'skills','interests':'interests','hobbies':'interests','seeking':'seeking','looking for':'seeking','hiring for':'hiring','hiring':'hiring','event':'event','source url':'sourceUrl','open to work':'openToWork'};
export function safeUrl(url){try{const u=new URL(url);return ['http:','https:'].includes(u.protocol)?u.href:'';}catch{return '';}}
export function normalizeRows(rows){
 if(!Array.isArray(rows)||rows.length>500)throw Error('Use a list with 1–500 attendees.');
 const seen=new Set(),people=[];let duplicates=0;
 rows.forEach((row,i)=>{
  const p={id:'u'+i,name:'',role:'',company:'',bio:'',skills:'',interests:'',seeking:'',hiring:'',linkedin:'',source:'Your attendee file',fictional:false,color:['#dfe8cb','#d5e4ec','#edd6cb','#dfd8ec','#f0e2b9'][i%5]};
  Object.entries(row).forEach(([k,v])=>{const key=aliases[k.trim().toLowerCase()];if(key)p[key]=String(v??'').trim().slice(0,12000);});
  if(!p.name){if(Object.values(row).some(v=>String(v??'').trim()))throw Error(`Row ${i+2} needs a Name or Attendee Name.`);return;}
  p.linkedin=safeUrl(p.linkedin);p.sourceUrl=safeUrl(p.sourceUrl);
  const key=p.linkedin?new URL(p.linkedin).hostname.toLowerCase().replace(/^www\./,'')+new URL(p.linkedin).pathname.toLowerCase().replace(/\/$/,''):p.name.toLowerCase()+'|'+p.company.toLowerCase();
  if(seen.has(key)){duplicates++;return;}seen.add(key);people.push(p);
 });
 if(!people.length)throw Error('No attendees found. Include a header row with Name, Job Title, and Company.');
 return {people,duplicates};
}
export function rankPeople(people,profile,mode,goal){
 if(!MODES[mode])throw Error('Choose a matching intention.');
 const social=mode==='social';
 const desired=themes(goal).filter(t=>social?SOCIAL.includes(t):!SOCIAL.includes(t));
 const background=themes(social?profile.interests:profile.background).filter(t=>social?SOCIAL.includes(t):!SOCIAL.includes(t));
 return people.map(p=>{
  const text=social?p.interests:mode==='hiring'?[p.role,p.skills].join(' '):[p.role,p.company,p.bio,p.skills].join(' ');
  const available=themes(text),goalOverlap=desired.filter(t=>available.includes(t)),shared=background.filter(t=>available.includes(t));
  const goalPoints=desired.length?5*goalOverlap.length/desired.length:0;
  const backgroundPoints=background.length?3*shared.length/background.length:0;
  let intent=0,signal='';
  if(social&&shared.length){intent=2;signal='Shared interests supplied';}
  else if(mode==='career'&&p.hiring){intent=2;signal='Hiring roles supplied';}
  else if(mode==='hiring'&&/^(yes|true|open|open to work)$/i.test(p.openToWork||'')){intent=2;signal='Openness to roles supplied';}
  else if(mode==='collaborate'&&/collaborat|partner|pilot/i.test(p.seeking)){intent=2;signal='Collaboration interest supplied';}
  else if(mode==='learn'&&/research|workshop|mentor|discussion|peers/i.test(p.seeking)){intent=2;signal='Learning or research interest supplied';}
  const relevant=(goalOverlap.length||shared.length)>0;
  const eligible=relevant&&(social?!!p.interests:mode==='hiring'?intent>0:true);
  const points=eligible?Math.round((goalPoints+backgroundPoints+intent)*10)/10:null;
  const supportedFields=[p.role,p.company,p.bio,p.skills,p.interests,p.seeking,p.hiring].filter(Boolean).length;
  const evidence=social?[{label:'Interests',value:p.interests}]:[{label:'Role',value:p.role},{label:'Organization',value:p.company},{label:'Bio',value:p.bio},{label:'Skills',value:p.skills},{label:'Looking for',value:p.seeking},{label:'Hiring for',value:p.hiring},{label:'Open to work',value:p.openToWork}];
  let why=eligible?`${goalOverlap.length?goalOverlap.join(' and '):shared.join(' and ')} connects to ${goalOverlap.length?'your event goal':'your background'}.`:(social?'No shared interests are supplied for this person.':mode==='hiring'&&relevant?'Professional themes overlap, but openness to a role is not supplied.':'No matching work themes found in the supplied information.');
  if(signal)why+=' '+signal+'.';
  const topic=(goalOverlap[0]||shared[0]||'your work').toLowerCase();
  let opener=social?`I’m also into ${topic}. What have you been enjoying lately?`:`What are you working on at ${p.company||'the moment'} related to ${topic}?`;
  if(mode==='career'&&p.hiring)opener=`I saw ${p.hiring} in your hiring notes. What experience would be most useful for that team?`;
  if(mode==='collaborate'&&intent)opener=`What would make a collaboration around ${topic} useful for your team right now?`;
  if(mode==='hiring'&&intent)opener=`What kind of ${topic} work would you like to take on next?`;
  const gaps=[];
  if(supportedFields<=2)gaps.push('Basic profile information only. Add a bio or skills for a more useful comparison.');
  if(mode==='career'&&!p.hiring)gaps.push('No current hiring information supplied.');
  if(mode==='hiring'&&!intent)gaps.push('Openness to a new role is unknown.');
  if(!p.fictional)gaps.push('Imported details have not been independently verified.');
  return {...p,score:points,eligible,goalOverlap,shared,signal,why,opener,gaps,evidence:evidence.filter(e=>e.value),coverage:supportedFields>2?'Detailed bio':'Basic details',breakdown:[{label:'Your goal',value:goalPoints,max:5},{label:social?'Shared interests':'Your background',value:backgroundPoints,max:3},{label:'Stated intent',value:intent,max:2}]};
 }).sort((a,b)=>(b.score??-1)-(a.score??-1)||a.name.localeCompare(b.name));
}
export function parseCsv(text){
 const rows=[];let row=[],cell='',quoted=false;
 for(let i=0;i<text.length;i++){const c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){cell+='"';i++;}else quoted=!quoted;}else if(c===','&&!quoted){row.push(cell);cell='';}else if((c==='\n'||c==='\r')&&!quoted){if(c==='\r'&&text[i+1]==='\n')i++;row.push(cell);if(row.some(x=>x.trim()))rows.push(row);row=[];cell='';}else cell+=c;}
 if(quoted)throw Error('The CSV has an unclosed quote. Save it again from your spreadsheet app.');
 row.push(cell);if(row.some(x=>x.trim()))rows.push(row);
 const headers=(rows.shift()||[]).map(s=>s.replace(/^\uFEFF/,''));
 return rows.map(r=>Object.fromEntries(headers.map((h,i)=>[h,r[i]||''])));
}
