import path from 'node:path';
import fs from 'node:fs/promises';

export function browserCandidates(platform,env={},bundled=''){
 const values=[];
 if(platform==='win32'){
  const roots=[env['PROGRAMFILES(X86)']||'C:\\Program Files (x86)',env.PROGRAMFILES||'C:\\Program Files'];
  for(const root of roots)values.push(path.win32.join(root,'Microsoft/Edge/Application/msedge.exe'));
  for(const root of roots)values.push(path.win32.join(root,'Google/Chrome/Application/chrome.exe'));
  if(env.LOCALAPPDATA)values.push(path.win32.join(env.LOCALAPPDATA,'Google/Chrome/Application/chrome.exe'));
 }else if(platform==='darwin')values.push('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge','/Applications/Chromium.app/Contents/MacOS/Chromium');
 else values.push('/usr/bin/chromium','/usr/bin/chromium-browser','/usr/bin/google-chrome','/usr/bin/microsoft-edge');
 if(bundled)values.push(bundled);
 return [...new Set(values)];
}

export async function installedBrowser(chromium){
 for(const candidate of browserCandidates(process.platform,process.env,chromium.executablePath())){
  try{await fs.access(candidate);return candidate}catch{}
 }
 throw Error('Для просмотра установите Microsoft Edge, Google Chrome или Chromium.');
}
