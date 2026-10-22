// Static source/catalogue audit; does not launch the app or contact the network.
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'..'),src=path.join(root,'frontend/src');
const store=path.join(root,'frontend/node_modules/.pnpm');
const dep=name=>require(path.join(store,fs.readdirSync(store).find(n=>n.startsWith(name.replace('/','+')+'@')),'node_modules',name));
const {parse}=dep('@vue/compiler-sfc'),{parse:template}=dep('@vue/compiler-dom'),ts=dep('typescript');
const catalogue={...JSON.parse(fs.readFileSync(path.join(src,'studio/locales/en.json'))),...JSON.parse(fs.readFileSync(path.join(src,'locales/en.json')))};
const keys=new Set(),missing=new Set(),raw=[];
function expression(code){const tree=ts.createSourceFile('audit.ts',code,ts.ScriptTarget.Latest,true);function walk(n){if(ts.isCallExpression(n)&&n.expression.getText(tree)==='t'&&n.arguments[0]&&ts.isStringLiteral(n.arguments[0])){const key=n.arguments[0].text;keys.add(key);if(!catalogue[key])missing.add(key)}ts.forEachChild(n,walk)}walk(tree)}
for(const file of fs.readdirSync(src).filter(f=>f.endsWith('.vue'))){const {descriptor}=parse(fs.readFileSync(path.join(src,file),'utf8'));if(descriptor.scriptSetup)expression(descriptor.scriptSetup.content);if(descriptor.template){const tree=template(descriptor.template.content);function walk(n){if(n.type===2&&/[\u3400-\u9fff]/.test(n.content)&&n.content!=='简体中文')raw.push({file,text:n.content});if(n.type===5)expression(n.content.content);for(const p of n.props||[])if(p.exp)expression(p.exp.content);for(const c of n.children||[])walk(c)}walk(tree)}}
const result={literalKeys:keys.size,missing:[...missing],rawText:raw};
fs.writeFileSync(path.join(root,'artifacts/localization-audit.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify(result));if(missing.size||raw.length)process.exitCode=1;
