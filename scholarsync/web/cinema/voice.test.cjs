const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, 'app.js'), 'utf8').split('function field(')[0];

function setup(saved) {
  const nodes = new Map(), utterances = [], timers = [];
  const videos = ['intro', 'idle', 'thinking', 'speaking'].map(state => ({dataset:{state}, active:false, classList:{toggle(_, active){this.owner.active=active}}, play(){return Promise.resolve()}, pause(){}}));
  videos.forEach(v=>v.classList.owner=v);
  const engine = {cancel(){},resume(){},speak(u){utterances.push(u);u.onstart?.()}};
  const context = vm.createContext({document:{querySelector(s){if(!nodes.has(s))nodes.set(s,{textContent:'',setAttribute(){}});return nodes.get(s)},querySelectorAll(){return videos}},window:{speechSynthesis:engine,SpeechSynthesisUtterance:function(){}},SpeechSynthesisUtterance:function(text){this.text=text},matchMedia:()=>({matches:false}),localStorage:{getItem:()=>saved,setItem(){}},clearTimeout(){},setTimeout(fn,ms){timers.push({fn,ms})}});
  vm.runInContext(source,context);
  return {call:code=>vm.runInContext(code,context), utterances, videos, timers,nodes};
}

test('voice is on by default and speaking clip stays active until all speech ends',()=>{
  const s=setup();s.call(`speak('First sentence. '.repeat(45))`);
  assert.equal(s.call('state'),'speaking');assert.equal(s.timers.length,0);
  let i=0;while(i<s.utterances.length)s.utterances[i++].onend();
  assert.ok(i>1);assert.equal(s.call('state'),'idle');assert.equal(s.utterances.map(u=>u.text).join(' '),'First sentence. '.repeat(45).trim());
});
test('mute preference and disabling speech stop animation without stale callbacks',()=>{
  const s=setup('off');s.call(`speak('Hello')`);assert.equal(s.utterances.length,0);
  s.call(`setVoice(true); speak('Hello');`);const old=s.utterances[0];s.call(`setVoice(false); video('thinking','Thinking','')`);old.onend();assert.equal(s.call('state'),'thinking');
});
test('new response supersedes old speech and errors return to idle',()=>{
  const s=setup();s.call(`speak('Old'); speak('New')`);s.utterances[0].onend();assert.equal(s.call('state'),'speaking');s.utterances[1].onerror();assert.equal(s.call('state'),'idle');
});
