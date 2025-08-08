import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import jsPDF from 'jspdf';
import 'jspdf-autotable';
import { VariableSizeList as List } from 'react-window';




const components = {
  code({ node, inline, className, children, ...props }) {
    const match = /language-(\w+)/.exec(className || '');
    return !inline && match ? (
      <SyntaxHighlighter style={oneDark} language={match[1]} PreTag="div" {...props}>
        {String(children).replace(/\n$/, '')}
      </SyntaxHighlighter>
    ) : (
      <code className={className} {...props}>
        {children}
      </code>
    );
  },
  table({ node, ...props }) {
    return (
      <table
        style={{
          borderCollapse: 'collapse',
          width: '100%',
          marginTop: '10px',
          marginBottom: '10px',
        }}
        {...props}
      />
    );
  },
  th({ node, ...props }) {
    return (
      <th
        style={{
          border: '1px solid #ddd',
          padding: '8px',
          backgroundColor: '#0e639c',
          color: 'white',
          textAlign: 'left',
        }}
        {...props}
      />
    );
  },
  td({ node, ...props }) {
    return (
      <td
        style={{
          border: '1px solid #ddd',
          padding: '8px',
          textAlign: 'left',
        }}
        {...props}
      />
    );
  },
};

function isCodeRelated(text) {
  const keywords = [
    'code', 'bug', 'error', 'debug', 'function', 'class', 'script', 'compile',
    'syntax', 'program', 'javascript', 'python', 'java', 'c++', 'typescript',
    'debugging', 'algorithm', 'hello',
  ];
  const lowered = text.toLowerCase();
  return keywords.some((word) => lowered.includes(word));
}

export default function App() {
  const [messages, setMessages] = useState([
    {
      role: 'system',
      content: 'Hi! Ask me anything about Java or programming.',
    },
  ]);
  const [model, setModel] = useState('llama3.2:1b');
  const [interactionMode, setInteractionMode] = useState('direct'); // 'direct' or 'database'
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [copiedIndex, setCopiedIndex] = useState(null);
  const [excelData, setExcelData] = useState([]);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Utility to convert JSON array of objects to markdown table
  function jsonToMarkdownTable(jsonArray) {
    if (!Array.isArray(jsonArray) || jsonArray.length === 0) return '';

    const headers = Object.keys(jsonArray[0]);
    const headerRow = `| ${headers.join(' | ')} |`;
    const separatorRow = `| ${headers.map(() => '---').join(' | ')} |`;

    const rows = jsonArray
      .map((obj) =>
        headers
          .map((header) => {
            const val = obj[header];
            if (typeof val === 'object') return JSON.stringify(val);
            return String(val);
          })
          .join(' | ')
      )
      .map((row) => `| ${row} |`)
      .join('\n');

    return [headerRow, separatorRow, rows].join('\n');
  }

  async function sendMessage() {
    if (!input.trim()) return;

    if (!isCodeRelated(input.trim()) & interactionMode === 'direct') {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: "⚠️ Sorry, I can only assist with code generation and debugging questions.",
        },
      ]);
      setInput('');
      return;
    } 

    const userMessage = { role: 'user', content: input.trim() };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    let currentResponse = '';
    setMessages((prev) => [...prev, { role: 'assistant', content: '', model }]);

    const startTime = performance.now();

    try {
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model,
          prompt: userMessage.content,
          mode: interactionMode,
          stream: interactionMode === 'direct' || interactionMode === 'database' || interactionMode === 'langchain' || interactionMode === 'langchainprompt'|| interactionMode === 'restful'|| interactionMode === 'embedded',
        }),
      });

      if (!res.ok || !res.body) {
        throw new Error(`❌ Failed to fetch response: ${res.status} ${res.statusText}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');

      if ((interactionMode === 'database') ||(interactionMode === 'langchainprompt')||(interactionMode === 'restful')||(interactionMode === 'embedded')) {
        // Streaming NDJSON (newline-delimited JSON) from DB
        let buffer = '';
        let allData = [];

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop(); // Keep last partial line for next chunk

          for (const line of lines) {
            if (!line.trim()) continue;

            try {
              const json = JSON.parse(line);
              // Accumulate JSON objects (expecting an array of objects)
              if (Array.isArray(json)) {
                allData = allData.concat(json);
              } else if (typeof json === 'object') {
                allData.push(json);
              } else {
                // fallback: stringify
                allData.push({ data: json });
              }

              // Convert accumulated data to markdown table and update
              currentResponse = jsonToMarkdownTable(allData);
              setExcelData(allData);

              setMessages((prev) => {
                const allButLast = prev.slice(0, -1);
                const updatedLast = {
                  ...prev[prev.length - 1],
                  content: currentResponse.trim(),
                  model,
                };
                return [...allButLast, updatedLast];
              });
            } catch (err) {
              console.warn('⚠️ JSON parse error:', err, line);
            }
          }
        }
      } else {
        // Token streaming (e.g., LLM generation)
        let done = false;

        while (!done) {
          const { value, done: doneReading } = await reader.read();
          done = doneReading;

          if (value) {
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n').filter((line) => line.trim());

            for (const line of lines) {
              const clean = line.replace(/^data:\s*/, '').trim();
              if (clean === '[DONE]') continue;

              try {
                const data = JSON.parse(clean);
                const token = data.response;

                if (token) {
                  currentResponse += token;
                  setMessages((prev) => {
                    const allButLast = prev.slice(0, -1);
                    const updatedLast = { ...prev[prev.length - 1], content: currentResponse, model };
                    return [...allButLast, updatedLast];
                  });
                }
              } catch {
                // ignore invalid JSON chunks
              }
            }
          }
        }
      }

      const endTime = performance.now();
      const elapsed = ((endTime - startTime) / 1000).toFixed(2);

      setMessages((prev) => {
        const updated = [...prev];
        const lastMsg = updated[updated.length - 1] || {};
        updated[updated.length - 1] = {
          ...lastMsg,
          content: currentResponse,
          model,
          responseTime: elapsed,
        };
        return updated;
      });
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `⚠️ Error: ${err.message}`, model },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  const downloadFile = async (type) => {
  if (!excelData || excelData.length === 0) {
    alert('No data to download.');
    return;
  }

  const urlMap = {
    excel: '/api/download-excel',
    csv: '/api/download-csv',
    pdf: '/api/download-pdf',
  };

  const url = urlMap[type];

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ data: excelData }),
    });

    if (!res.ok) {
      throw new Error(`Failed to download ${type}`);
    }

    const blob = await res.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = `chatbot_data.${type === 'excel' ? 'xlsx' : type}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } catch (err) {
    console.error(`Download ${type} error:`, err);
    alert(`Failed to download ${type} file.`);
  }
};




  async function copyToClipboard(text, index) {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIndex(index);
      setTimeout(() => setCopiedIndex(null), 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
    }
  }


const listRef = useRef();
const rowHeights = useRef({});

const filteredMessages = useMemo(
  () => messages.filter((msg) => msg.role !== 'system'),
  [messages]
);

const getItemSize = (index) => rowHeights.current[index] || 100;

const setRowHeight = (index, size) => {
  if (rowHeights.current[index] !== size) {
    rowHeights.current = { ...rowHeights.current, [index]: size };
    if (listRef.current) {
      listRef.current.resetAfterIndex(index);
    }
  }
};

useEffect(() => {
  if (listRef.current) {
    listRef.current.scrollToItem(filteredMessages.length - 1, 'end');
  }
}, [filteredMessages]);




  return (
    <>
      <style>{`
        /* your existing styles here */
        * {
          box-sizing: border-box;
        }
        body, html, #root {
          margin: 0; padding: 0; height: 100%;
          background-color: #1e1e1e;
          color: #d4d4d4;
          font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
          overflow: hidden;
        }
        .app-container {
          display: flex;
          flex-direction: column;
          height: 100vh;
          max-width: 100vw;
          margin: 0 auto;
          background-color: #1e1e1e;
          border-radius: 8px;
          box-shadow: 0 0 20px rgba(0,0,0,0.7);
          overflow: hidden;
        }
        header {
          background-color: #0e639c;
          color: white;
          display: flex;
          align-items: center;
          padding: 12px 24px;
          gap: 24px;
          width: 100vw;
          position: fixed;
          top: 0;
          left: 0;
          box-sizing: border-box;
          z-index: 10;
        }
        header > div:first-child {
          font-weight: 700;
          font-size: 1.8rem;
          flex-shrink: 0;
          display: flex;
          align-items: center;
          gap: 12px;
        }
        header > div:last-child,
        header > div:nth-child(3) {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-left: auto;
          font-weight: 600;
          font-size: 1rem;
        }
        label {
          user-select: none;
        }
        select {
          padding: 6px 12px;
          font-size: 1rem;
          border-radius: 6px;
          background: #252526;
          color: #d4d4d4;
          border: 1px solid #444;
          min-width: 140px;
          cursor: pointer;
        }
        select:disabled {
          cursor: not-allowed;
          opacity: 0.7;
        }
        main {
          flex: 1;
          overflow-y: auto;
          padding: 80px 24px 120px;
          scrollbar-width: thin;
          scrollbar-color: #0e639c transparent;
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        main::-webkit-scrollbar {
          width: 8px;
        }
        main::-webkit-scrollbar-thumb {
          background-color: #0e639c;
          border-radius: 4px;
        }
        form {
          display: flex;
          gap: 12px;
          padding: 16px 24px;
          background-color: #0e639c;
          position: fixed;
          bottom: 0;
          left: 0;
          width: 100vw;
          box-sizing: border-box;
          border-top: 2px solid #084c75;
          border-bottom-left-radius: 8px;
          border-bottom-right-radius: 8px;
          max-height: 150px;
          z-index: 10;
        }
        textarea {
          flex: 1;
          resize: vertical;
          min-height: 80px;
          max-height: 150px;
          padding: 10px;
          font-size: 1rem;
          border-radius: 6px;
          border: none;
          background-color: #1e1e1e;
          color: #d4d4d4;
          font-family: monospace;
        }
        textarea:disabled {
          background-color: #2d2d2d;
          color: #777;
          cursor: not-allowed;
        }
        button {
          padding: 0 24px;
          font-size: 1rem;
          border-radius: 6px;
          border: none;
          background-color: #0e639c;
          color: white;
          cursor: pointer;
          user-select: none;
          min-width: 100px;
          transition: background-color 0.2s ease;
          flex-shrink: 0;
        }
        button:hover:not(:disabled) {
          background-color: #1177d1;
        }
        button:disabled {
          background-color: #3a3d41;
          cursor: not-allowed;
        }
        .message {
          padding: 12px 16px;
          border-radius: 20px;
          line-height: 1.4;
          white-space: pre-wrap;
          word-break: break-word;
          max-width: 90vw;
          flex-shrink: 0;
          position: relative;
        }
        .user {
          background-color: #0a5a0a;
          color: #c8ffc8;
          align-self: flex-end;
          border-bottom-right-radius: 4px;
          border-bottom-left-radius: 20px;
          border-top-left-radius: 20px;
          border-top-right-radius: 20px;
        }
        .assistant {
          background-color: #252526;
          color: #d4d4d4;
          align-self: flex-start;
          border-bottom-left-radius: 4px;
          border-bottom-right-radius: 20px;
          border-top-left-radius: 20px;
          border-top-right-radius: 20px;
          padding-top: 28px; /* for model label */
        }
        .copy-button {
          background: none;
          border: none;
          color: #0e639c;
          cursor: pointer;
          font-weight: 600;
          font-size: 0.9rem;
          padding: 0;
          position: absolute;
          bottom: 8px;
          right: 12px;
          user-select: none;
        }
        .copy-button:hover {
          text-decoration: underline;
        }
        .copy-button.copied {
          color: #6a9955;
          cursor: default;
        }
        .response-time {
          margin-top: 4px;
          font-size: 0.75rem;
          color: #888;
          font-style: italic;
        }
        .model-label {
          position: absolute;
          top: 8px;
          left: 16px;
          font-size: 0.75rem;
          font-weight: 600;
          color: #0e639c;
          user-select: none;
        }
      `}</style>
      <div className="app-container" role="main" aria-label="Chatbot interface">
        <header>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <img
              src="deutsche_bank_logo_2.jpeg"
              alt="Deutsche Bank Logo"
              style={{ height: '36px' }}
            />
            <div style={{ fontSize: '1.8rem', fontWeight: 'bold' }}>CodeNova</div>
          </div>

          <div>
            <label style={{ fontSize: '1rem', fontWeight: 'bold'}} htmlFor="model-select">AI Model:</label>
            <select
              id="model-select"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              disabled={loading}
              aria-label="Select AI model"
            >
              <option value="llama3.2:1b">LLaMA3.2:1b</option>
              <option value="codellama:7b-instruct">CodeLLaMA:7b-instruct</option>
              <option value="sqlcoder">SQLCoder:7b</option>
              <option value="gemma">Gemma</option>
              <option value="llama3">LLaMA3</option>
              <option value="mistral">Mistral</option>
              <option value="phi3">Phi-3</option>  
            </select>
          </div>

          <div>
            <label htmlFor="interaction-mode-select" style={{ marginLeft: '16px' }}>
              Agent:
            </label>
            <select
              id="interaction-mode-select"
              value={interactionMode}
              onChange={(e) => setInteractionMode(e.target.value)}
              disabled={loading}
              aria-label="Select interaction mode"
              style={{
                marginLeft: '8px',
                minWidth: '140px',
                padding: '6px 12px',
                fontSize: '1rem',
                borderRadius: '6px',
                background: '#252526',
                color: '#d4d4d4',
                border: '1px solid #444',
                cursor: 'pointer',
              }}
            >
              <option value="direct">Code Genie</option>
              <option value="database">Database - Direct Intent Routes</option>
              <option value="restful">RESTful - Prompt Engineered & Embedded</option>
              <option value="langchain">Database - Lang Chained</option>
              <option value="langchainprompt">Database - Lang Chained & Prompt Engineered</option>
              <option value="embedded">Database - Lang Chained - Prompt Engineered - Embedded Vectorisation</option>
            </select>
          </div>
        </header>

               <main aria-live="polite" aria-relevant="additions" tabIndex={-1} style={{ flex: 1, overflow: 'hidden' }}>
          <List
            height={600} // Or use window.innerHeight - toolbar height
            itemCount={filteredMessages.length}
            itemSize={200} // You can adjust this; or switch to VariableSizeList later
            width="100%"
            ref={listRef}
          >
            {({ index, style }) => {
              const msg = filteredMessages[index];
              const isUser = msg.role === 'user';

              return (
                <div style={{ ...style, padding: '12px 20px', boxSizing: 'border-box' }}>
                  <div
                    className={`message ${isUser ? 'user' : 'assistant'}`}
                    aria-label={isUser ? 'User message' : `Assistant response from model ${msg.model || ''}`}
                  >
                    {!isUser && msg.model && msg.content.length > 10 && (
                      <div className="model-label" aria-hidden="true">
                        Model: {msg.model}
                      </div>
                    )}
                    <ReactMarkdown
                      children={msg.content}
                      remarkPlugins={[remarkGfm]}
                      components={components}
                    />
                    {!isUser && (
                      <button
                        className={`copy-button ${copiedIndex === index ? 'copied' : ''}`}
                        onClick={() => copyToClipboard(msg.content, index)}
                        aria-label="Copy assistant response to clipboard"
                      >
                        {copiedIndex === index ? 'Copied!' : 'Copy'}
                      </button>
                    )}
                    {!isUser && msg.responseTime && (
                      <div className="response-time">
                        Response time: {msg.responseTime}s
                      </div>
                    )}
                  </div>
                </div>
              );
            }}
          </List>

          {/* Keep download buttons below */}
          {excelData.length > 0 && (
            <div className="button-row">
              <button onClick={() => downloadFile('excel')}>⬇️ Download Excel</button>
              <button onClick={() => downloadFile('csv')}>⬇️ Download CSV</button>
              <button onClick={() => downloadFile('pdf')}>⬇️ Download PDF</button>
            </div>
          )}
          <div ref={messagesEndRef} />
        </main>


        <form
          onSubmit={(e) => {
            e.preventDefault();
            sendMessage();
          }}
        >
          <textarea
            placeholder="Ask me........."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            rows={3}
          />
          <button type="submit" disabled={loading || !input.trim()}>
            {loading ? 'Loading...' : 'Send'}
          </button>
        </form>
      </div>
    </>
  );
}
