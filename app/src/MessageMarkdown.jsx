import React from 'react';
import {Code2} from 'lucide-react';
import {RichInline as Inline} from './RichContent.jsx';
import './message-readability.css';

export default function MessageMarkdown({
  text = '', files=[], onPreview, renderCopy
}) {
  const source = String(text);
  const barePython = !source.includes('```') && /^(?:from [\w.]+ import |import [\w.]|(?:async )?def \w+\(|class \w+[(:]|"""[^\n]*\n)/.test(source.trimStart());
  const chunks = (barePython ? '```python\n' + source + '\n```' : source).split(/```/);
  return <div className="markdown">{chunks.map((chunk, i) => {
      if (i % 2) {
        const newline = chunk.indexOf('\n');
        const lang = newline < 0 ? 'code' : chunk.slice(0, newline).trim();
        const code = newline < 0 ? chunk : chunk.slice(newline + 1);
        return <div className="code-block" key={i}><div className="code-head"><span><Code2 size={13} />{lang || 'code'}</span>{renderCopy?.(code)}</div><pre><code>{code.replace(/\n$/, '')}</code></pre></div>;
      }
      return <div key={i}>{chunk.split('\n').map((line, j) => {
          if (/^#{1,4} /.test(line)) {
            const level = line.match(/^#+/)[0].length;
            return React.createElement('h' + Math.min(level + 1, 5), {
              key: j
            }, <Inline files={files} onPreview={onPreview} text={line.replace(/^#+ /, '')} />);
          }
          if (/^\s*[-*] /.test(line)) return <div className="list-line" key={j}><span>•</span><span className="list-content"><Inline files={files} onPreview={onPreview} text={line.replace(/^\s*[-*] /, '')} /></span></div>;
          if (/^\d+\. /.test(line)) return <div className="list-line" key={j}><span>{line.match(/^\d+/)[0]}.</span><span className="list-content"><Inline files={files} onPreview={onPreview} text={line.replace(/^\d+\. /, '')} /></span></div>;
          if (/^> /.test(line)) return <blockquote key={j}><Inline files={files} onPreview={onPreview} text={line.slice(2)} /></blockquote>;
          if (/^\|.+\|$/.test(line)) return <div className="table-line" key={j}>{line.split('|').slice(1, -1).map((v, k) => <span key={k}><Inline files={files} onPreview={onPreview} text={v.trim()} /></span>)}</div>;
          return line.trim() ? <p key={j}><Inline files={files} onPreview={onPreview} text={line} /></p> : <div className="paragraph-gap" key={j} />;
        })}</div>;
    })}</div>;
}
