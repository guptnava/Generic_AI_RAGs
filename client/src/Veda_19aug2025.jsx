import React, { useState, useRef, useEffect, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { PanelLeft, X, Settings } from 'lucide-react';
import * as htmlToImage from 'html-to-image';


// Define a custom markdown component for rendering tables
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
      <div className="table-container">
        <table
          style={{
            borderCollapse: 'collapse',
            width: '100%',
            minWidth: '600px',
          }}
          {...props}
        />
      </div>
    );
  },
  th({ node, ...props }) {
    return (
      <th
        style={{
          border: '1px solid #ddd',
          padding: '5px',
          backgroundColor: '#0e639c',
          color: 'white',
          textAlign: 'left',
          whiteSpace: 'nowrap',
          fontSize: '0.8rem',
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
          padding: '5px',
          textAlign: 'left',
          whiteSpace: 'nowrap',
          fontSize: '0.8rem',
        }}
        {...props}
      />
    );
  },
};

const LeftPanel = ({
  isPanelOpen,
  temperature,
  setTemperature,
  topK,
  setTopK,
  topP,
  setTopP,
  commandHistory,
  onHistoryClick
}) => {
  const resetSliders = () => {
    setTemperature(0.7);
    setTopK(50);
    setTopP(0.9);
  };
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        padding: isPanelOpen ? '16px' : '0',
        backgroundColor: '#252526',
        color: '#d4d4d4',
        transition: 'width 0.3s ease-in-out',
        width: isPanelOpen ? '288px' : '0',
        overflow: 'hidden',
        flexShrink: 0,
        borderRight: isPanelOpen ? '1px solid #444' : 'none',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 'bold' }}>Settings</h2>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', overflowY: 'auto' }}>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <label htmlFor="temperature" style={{ fontSize: '0.875rem', fontWeight: 'semibold', marginBottom: '4px' }}>
            Temperature: {temperature}
          </label>
          <input
            type="range"
            id="temperature"
            min="0"
            max="1"
            step="0.1"
            value={temperature}
            onChange={(e) => setTemperature(parseFloat(e.target.value))}
            style={{ width: '100%' }}
          />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <label htmlFor="topK" style={{ fontSize: '0.875rem', fontWeight: 'semibold', marginBottom: '4px' }}>
            Top K: {topK}
          </label>
          <input
            type="range"
            id="topK"
            min="1"
            max="100"
            step="1"
            value={topK}
            onChange={(e) => setTopK(parseInt(e.target.value))}
            style={{ width: '100%' }}
          />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <label htmlFor="topP" style={{ fontSize: '0.875rem', fontWeight: 'semibold', marginBottom: '4px' }}>
            Top P: {topP}
          </label>
          <input
            type="range"
            id="topP"
            min="0"
            max="1"
            step="0.1"
            value={topP}
            onChange={(e) => setTopP(parseFloat(e.target.value))}
            style={{ width: '100%' }}
          />
        </div>
        <button
          onClick={resetSliders}
          style={{
            backgroundColor: '#06445eff',
            color: '#d4d4d4',
            padding: '8px 16px',
            borderRadius: '6px',
            border: 'none',
            cursor: 'pointer',
            marginTop: '8px'
          }}
        >
          Reset Sliders
        </button>
        <hr style={{ borderTop: '1px solid #444', margin: '16px 0' }} />
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 'bold', marginBottom: '8px' }}>Command History</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {commandHistory.length > 0 ? (
              commandHistory.map((historyItem, index) => (
                <button
                  key={index}
                  onClick={() => onHistoryClick(historyItem)}
                  style={{
                    backgroundColor: '#3d3d3d',
                    color: '#d4d4d4',
                    padding: '8px',
                    borderRadius: '6px',
                    border: '1px solid #555',
                    textAlign: 'left',
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    transition: 'background-color 0.2s',
                  }}
                >
                  {historyItem.command}
                </button>
              ))
            ) : (
              <span style={{ fontStyle: 'italic', color: '#999' }}>No history yet.</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// Component for rendering a custom bar graph
const BarGraphComponent = React.forwardRef(({ labels, data, title, yAxisLabel, xAxisLabel }, ref) => {
  const maxValue = Math.max(...data);
  const formattedData = data.map(value => (typeof value === 'number' ? value.toFixed(2) : value));

  return (
    <div ref={ref} style={{
      width: '100%',
      backgroundColor: '#2d2d2d',
      padding: '20px',
      borderRadius: '8px',
      boxShadow: '0 4px 8px rgba(0,0,0,0.3)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
    }}>
      <h3 style={{ color: '#d4d4d4', marginBottom: '20px' }}>{title}</h3>
      <div style={{ display: 'flex', flexDirection: 'row', width: '100%', height: '300px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', marginRight: '10px', alignItems: 'flex-end', fontSize: '0.75rem', color: '#aaa' }}>
          <span>{maxValue.toFixed(2)}</span>
          <span>{(maxValue / 2).toFixed(2)}</span>
          <span>0.00</span>
        </div>
        <div style={{
          display: 'flex',
          justifyContent: 'space-around',
          alignItems: 'flex-end',
          width: '100%',
          borderLeft: '1px solid #555',
          borderBottom: '1px solid #555',
        }}>
          {data.map((value, index) => (
            <div key={index} style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              width: '40px',
              height: `${(value / maxValue) * 100}%`,
              backgroundColor: 'rgba(75, 192, 192, 0.6)',
              position: 'relative',
              transition: 'height 0.5s ease-in-out',
              borderRadius: '4px 4px 0 0',
              marginBottom: '-1px',
              margin: '0 5px'
            }}>
              <span style={{
                position: 'absolute',
                top: '-20px',
                fontSize: '0.75rem',
                color: '#ddd',
                whiteSpace: 'nowrap'
              }}>
                {formattedData[index]}
              </span>
            </div>
          ))}
        </div>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-around', width: '100%', marginTop: '5px', color: '#d4d4d4', fontSize: '0.8rem' }}>
        {labels.map((label, index) => (
          <span key={index} style={{ width: '50px', textAlign: 'center', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{label}</span>
        ))}
      </div>
      <div style={{ marginTop: '10px', textAlign: 'center', fontSize: '0.8rem', color: '#888' }}>
        <p>This graph was generated from the fetched data.</p>
      </div>
    </div>
  );
});


// Component for rendering a custom line graph
const LineGraphComponent = React.forwardRef(({ labels, data, title }, ref) => {
  const maxValue = Math.max(...data);
  const totalPoints = labels.length;
  const formattedData = data.map(value => (typeof value === 'number' ? value.toFixed(2) : value));

  return (
    <div ref={ref} style={{
      width: '100%',
      backgroundColor: '#2d2d2d',
      padding: '20px',
      borderRadius: '8px',
      boxShadow: '0 4px 8px rgba(0,0,0,0.3)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
    }}>
      <h3 style={{ color: '#d4d4d4', marginBottom: '20px' }}>{title}</h3>
      <div style={{ display: 'flex', flexDirection: 'row', width: '100%', height: '300px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', marginRight: '10px', alignItems: 'flex-end', fontSize: '0.75rem', color: '#aaa' }}>
          <span>{maxValue.toFixed(2)}</span>
          <span>{(maxValue / 2).toFixed(2)}</span>
          <span>0.00</span>
        </div>
        <div style={{
          position: 'relative',
          width: '100%',
          borderLeft: '1px solid #555',
          borderBottom: '1px solid #555',
        }}>
          {/* Path for the line */}
          <svg
            viewBox={`0 0 100 100`}
            preserveAspectRatio="none"
            style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%' }}
          >
            <path
              d={
                `M 0 100 ` +
                data
                  .map((value, index) => {
                    const x = (index / (totalPoints - 1)) * 100;
                    const y = 100 - (value / maxValue) * 100;
                    return `L ${x} ${y}`;
                  })
                  .join(' ')
              }
              fill="none"
              stroke="rgba(75, 192, 192, 1)"
              strokeWidth="2"
            />
          </svg>
          {/* Points on the line */}
          {data.map((value, index) => {
            const x = (index / (totalPoints - 1)) * 100;
            const y = 100 - (value / maxValue) * 100;
            return (
              <React.Fragment key={index}>
                <div
                  style={{
                    position: 'absolute',
                    left: `calc(${x}% - 5px)`,
                    top: `calc(${y}% - 5px)`,
                    width: '10px',
                    height: '10px',
                    borderRadius: '50%',
                    backgroundColor: 'rgba(75, 192, 192, 1)',
                    boxShadow: '0 0 5px #000',
                  }}
                />
                 <div
                  style={{
                    position: 'absolute',
                    left: `calc(${x}% - 20px)`,
                    top: `calc(${y}% - 30px)`,
                    fontSize: '0.75rem',
                    color: '#ddd',
                    whiteSpace: 'nowrap',
                    pointerEvents: 'none',
                    textAlign: 'center'
                  }}
                >
                  {formattedData[index]}
                </div>
              </React.Fragment>
            );
          })}
        </div>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-around', width: '100%', marginTop: '5px', color: '#d4d4d4', fontSize: '0.8rem' }}>
        {labels.map((label, index) => (
          <span key={index} style={{ width: '50px', textAlign: 'center', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{label}</span>
        ))}
      </div>
      <div style={{ marginTop: '10px', textAlign: 'center', fontSize: '0.8rem', color: '#888' }}>
        <p>This graph was generated from the fetched data.</p>
      </div>
    </div>
  );
});


// Component to handle graph and table options for a single message
const TableAndGraphOptions = ({ message, onUpdateMessage, onDownloadFile }) => {
  const graphRef = useRef(null);

  // Use state hooks for this specific message's data and options
  const [viewMode, setViewMode] = useState(message.viewMode || 'table');
  const [selectedGraphType, setSelectedGraphType] = useState(message.selectedGraphType || 'bar');
  const [selectedXAxis, setSelectedXAxis] = useState(message.selectedXAxis || '');
  const [selectedYAxis, setSelectedYAxis] = useState(message.selectedYAxis || '');
  const [selectedAggregation, setSelectedAggregation] = useState(message.selectedAggregation || 'count');
  const [currentGraphData, setCurrentGraphData] = useState(message.currentGraphData || null);

  const excelData = message.tableData;
  const hasTableData = excelData && excelData.length > 0;
  const availableColumns = hasTableData ? Object.keys(excelData[0]) : [];
  
  // Set initial dropdown values when data is received
  useEffect(() => {
    if (hasTableData) {
      const keys = Object.keys(excelData[0]);
      if (keys.length > 0) {
        setSelectedXAxis(keys[0]);
        // Find the first numeric column for the y-axis
        const firstNumericKey = keys.find(key => typeof excelData[0][key] === 'number');
        setSelectedYAxis(firstNumericKey || keys[0]);
        // If first numeric key is found, default to 'sum' aggregation
        setSelectedAggregation(firstNumericKey ? 'sum' : 'count');
      }
    }
  }, [excelData]);


  // New function to aggregate data before graphing
  const aggregateData = (data, xAxisKey, yAxisKey, aggregationType) => {
    const aggregatedMap = new Map();
    data.forEach(item => {
      const xValue = item[xAxisKey];
      const yValue = typeof item[yAxisKey] === 'number' ? item[yAxisKey] : 0;

      if (!aggregatedMap.has(xValue)) {
        switch (aggregationType) {
          case 'count':
            aggregatedMap.set(xValue, 0);
            break;
          case 'sum':
            aggregatedMap.set(xValue, 0);
            break;
          case 'average':
            aggregatedMap.set(xValue, { sum: 0, count: 0 });
            break;
          case 'minimum':
            aggregatedMap.set(xValue, Infinity);
            break;
          case 'maximum':
            aggregatedMap.set(xValue, -Infinity);
            break;
          default:
            aggregatedMap.set(xValue, 0);
        }
      }

      switch (aggregationType) {
        case 'count':
          aggregatedMap.set(xValue, aggregatedMap.get(xValue) + 1);
          break;
        case 'sum':
          aggregatedMap.set(xValue, aggregatedMap.get(xValue) + yValue);
          break;
        case 'average':
          const avgData = aggregatedMap.get(xValue);
          avgData.sum += yValue;
          avgData.count += 1;
          aggregatedMap.set(xValue, avgData);
          break;
        case 'minimum':
          aggregatedMap.set(xValue, Math.min(aggregatedMap.get(xValue), yValue));
          break;
        case 'maximum':
          aggregatedMap.set(xValue, Math.max(aggregatedMap.get(xValue), yValue));
          break;
      }
    });

    const labels = Array.from(aggregatedMap.keys());
    const values = labels.map(label => {
      const val = aggregatedMap.get(label);
      if (aggregationType === 'average') {
        return val.count > 0 ? val.sum / val.count : 0;
      }
      return val;
    });

    return { labels, data: values };
  };

  const handleGenerateGraph = () => {
    if (!selectedXAxis || !selectedYAxis) {
      alert('Please select both X and Y axis columns.');
      return;
    }

    const { labels, data } = aggregateData(excelData, selectedXAxis, selectedYAxis, selectedAggregation);

    const newGraphData = {
      type: selectedGraphType,
      labels: labels,
      data: data,
      title: `${selectedAggregation.charAt(0).toUpperCase() + selectedAggregation.slice(1)} of ${selectedYAxis} by ${selectedXAxis}`,
    };

    setCurrentGraphData(newGraphData);
    setViewMode('graph');
    
    onUpdateMessage({
      ...message,
      selectedGraphType,
      selectedXAxis,
      selectedYAxis,
      selectedAggregation,
      currentGraphData: newGraphData,
      viewMode: 'graph'
    });
  };

  const handleSaveGraph = () => {
    if (graphRef.current) {
      const graphElement = graphRef.current;
      const graphType = currentGraphData?.type;
      
      if (graphType === 'line') {
        const svgElement = graphElement.querySelector('svg');
        if (svgElement) {
          htmlToImage.toSvg(svgElement)
            .then(function (dataUrl) {
              const link = document.createElement('a');
              link.href = dataUrl;
              link.download = 'line-graph.svg';
              document.body.appendChild(link);
              link.click();
              document.body.removeChild(link);
            })
            .catch(function (error) {
              console.error('oops, something went wrong!', error);
            });
        }
      } else if (graphType === 'bar') {
        htmlToImage.toPng(graphElement)
          .then(function (dataUrl) {
            const link = document.createElement('a');
            link.href = dataUrl;
            link.download = 'bar-chart.png';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(a);
          })
          .catch(function (error) {
              console.error('oops, something went wrong!', error);
            });
      }
    }
  };

  const handleToggleView = () => {
    const newViewMode = viewMode === 'graph' ? 'table' : 'graph';
    setViewMode(newViewMode);
    onUpdateMessage({ ...message, viewMode: newViewMode });
  };
  
  const handleDropdownChange = (setter, value) => {
    setter(value);
    onUpdateMessage({
      ...message,
      selectedGraphType,
      selectedXAxis,
      selectedYAxis,
      selectedAggregation
    });
  };


  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '20px', padding: '16px', backgroundColor: '#252526', borderRadius: '8px' }}>
      <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 'bold' }}>Graph & View Options for this table</h4>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'center' }}>
        <label htmlFor={`graph-type-select-${message.id}`}>Type:</label>
        <select id={`graph-type-select-${message.id}`} value={selectedGraphType} onChange={(e) => handleDropdownChange(setSelectedGraphType, e.target.value)}>
          <option value="bar">Bar Chart</option>
          <option value="line">Line Graph</option>
        </select>

        <label htmlFor={`x-axis-select-${message.id}`}>X-Axis (Group By):</label>
        <select id={`x-axis-select-${message.id}`} value={selectedXAxis} onChange={(e) => handleDropdownChange(setSelectedXAxis, e.target.value)}>
          {availableColumns.map(col => (
            <option key={col} value={col}>{col}</option>
          ))}
        </select>

        <label htmlFor={`y-axis-select-${message.id}`}>Y-Axis (Aggregate):</label>
        <select id={`y-axis-select-${message.id}`} value={selectedYAxis} onChange={(e) => handleDropdownChange(setSelectedYAxis, e.target.value)}>
          {availableColumns.map(col => (
            <option key={col} value={col}>{col}</option>
          ))}
        </select>

        <label htmlFor={`agg-select-${message.id}`}>Aggregation:</label>
        <select id={`agg-select-${message.id}`} value={selectedAggregation} onChange={(e) => handleDropdownChange(setSelectedAggregation, e.target.value)}>
          <option value="count">Count</option>
          <option value="sum">Sum</option>
          <option value="average">Average</option>
          <option value="minimum">Minimum</option>
          <option value="maximum">Maximum</option>
        </select>

        <button onClick={handleGenerateGraph} style={{ minWidth: '150px' }}>Generate Graph</button>
        {currentGraphData && (
          <>
            <button onClick={handleToggleView} style={{ minWidth: '150px' }}>
              {viewMode === 'graph' ? 'Show Table' : 'Show Graph'}
            </button>
            {viewMode === 'graph' && (
              <button
                onClick={handleSaveGraph}
                style={{
                  minWidth: '150px',
                  backgroundColor: '#1177d1',
                  color: '#fff',
                  padding: '8px 16px',
                  borderRadius: '6px',
                  border: 'none',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}
              >
                ⬇️ Save Graph
              </button>
            )}
          </>
        )}
      </div>
      <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
       <button 
            onClick={() => onDownloadFile('excel', excelData)} 
            style={{ fontSize: "15px", fontFamily: "Arial, sans-serif" }}
            >
            {/* <img 
                src="client/src/icons/excel_1.jpeg" 
                alt="Excel icon" 
                style={{ width: "20px", height: "20px", marginRight: "8px" }} 
            /> */}
            ⬇️ Download Excel
        </button>
        <button onClick={() => onDownloadFile('csv', excelData)}>⬇️ Download CSV</button>
        <button onClick={() => onDownloadFile('pdf', excelData)}>⬇️ Download PDF</button>
      </div>
      {viewMode === 'graph' && currentGraphData && (
        <div ref={graphRef}>
          {currentGraphData.type === 'bar' ? (
            <BarGraphComponent labels={currentGraphData.labels} data={currentGraphData.data} title={currentGraphData.title} />
          ) : (
            <LineGraphComponent labels={currentGraphData.labels} data={currentGraphData.data} title={currentGraphData.title} />
          )}
        </div>
      )}
    </div>
  );
};

export default function App() {
  const os = navigator.platform;
  console.log(`Hello! Welcome from your ${os} device 🤖`);

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) {
      return 'Good morning! What can I help you with today?';
    } else if (hour < 18) {
      return 'Good afternoon! How can I assist you?';
    } else {
      return 'Good evening! How can I help?';
    }
  };

  const [messages, setMessages] = useState([
    {
      id: 0,
      role: 'system',
      content: getGreeting(),
    },
  ]);
  const [model, setModel] = useState('llama3.2:1b');
  const [interactionMode, setInteractionMode] = useState('direct');
  const inputRef = useRef(null); // Use a ref for the input element
  const [loading, setLoading] = useState(false);
  const [copiedIndex, setCopiedIndex] = useState(null);
  const messagesEndRef = useRef(null);

  const [isPanelOpen, setIsPanelOpen] = useState(true);
  const [temperature, setTemperature] = useState(0.7);
  const [topK, setTopK] = useState(50);
  const [topP, setTopP] = useState(0.9);
  const [commandHistory, setCommandHistory] = useState([]);
  
  // New state to hold the in-progress streaming message
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentStreamingMessage]);

  const jsonToMarkdownTable = useMemo(() => {
    return (jsonArray, limit = 10) => {
      if (!Array.isArray(jsonArray) || jsonArray.length === 0) return '';

      const headers = Object.keys(jsonArray[0]);
      const headerRow = `| ${headers.join(' | ')} |`;
      const separatorRow = `| ${headers.map(() => '---').join(' | ')} |`;

      const rows = jsonArray
        .slice(0, limit)
        .map((obj) =>
          headers
            .map((header) => {
              const val = obj[header];
              return typeof val === 'object' ? JSON.stringify(val) : String(val);
            })
            .join(' | ')
        )
        .map((row) => `| ${row} |`)
        .join('\n');

      return [headerRow, separatorRow, rows].join('\n');
    };
  }, []);

  async function sendMessage() {
    const input = inputRef.current.value.trim();
    if (!input) return;

    setCommandHistory(prev => {
      const newHistory = [...prev, { command: input, model, mode: interactionMode }];
      return newHistory.slice(-10);
    });

    const userMessage = { id: messages.length, role: 'user', content: input };
    setMessages((prev) => [...prev, userMessage]);
    inputRef.current.value = ''; // Clear the input using the ref
    setLoading(true);
    
    // Initialize the new streaming message state
    setCurrentStreamingMessage({ id: messages.length + 1, role: 'assistant', content: '', model, tableData: null });

    let currentResponseContent = '';
    let tableData = [];
    
    const startTime = performance.now();

    try {
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model,
          prompt: userMessage.content,
          mode: interactionMode,
          stream: ['direct', 'database', 'langchain', 'langchainprompt', 'restful', 'embedded', 'embedded_narrated', 'generic_rag'].includes(interactionMode),
        }),
      });

      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(`❌ Failed to fetch response: ${res.status} ${res.statusText}. Server response: ${errorText}`);
      }
      
      if (!res.body) {
         throw new Error('❌ Failed to fetch response: The response body is empty.');
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      
      if (['database', 'langchainprompt', 'restful', 'embedded', 'embedded_narrated', 'generic_rag'].includes(interactionMode)) {
        let buffer = '';
        let allData = [];
        let narrationText = null;

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop();

          for (const line of lines) {
            if (!line.trim()) continue;

            try {
              const json = JSON.parse(line);

              if (json._narration) {
                narrationText = json._narration;
              } else {
                if (Array.isArray(json)) {
                  allData = allData.concat(json);
                } else if (typeof json === 'object') {
                  allData.push(json);
                } else {
                  allData.push({ data: json });
                }
                tableData = allData;
              }

              currentResponseContent = jsonToMarkdownTable(allData, 10);
              if (narrationText) {
                currentResponseContent += `\n\n📝 ${narrationText}`;
              }

            } catch (err) {
              console.warn('⚠️ JSON parse error:', err, line);
              currentResponseContent = `⚠️ Error parsing response: ${err.message}`;
              break;
            }
          }
          setCurrentStreamingMessage(prev => ({ ...prev, content: currentResponseContent, tableData: tableData.length > 0 ? tableData : null }));
        }

        const endTime = performance.now();
        const elapsed = ((endTime - startTime) / 1000).toFixed(2);
        
        setMessages(prev => [...prev, {
          ...currentStreamingMessage,
          content: currentResponseContent,
          tableData: tableData.length > 0 ? tableData : null,
          responseTime: elapsed
        }]);
        setCurrentStreamingMessage(null);
        
      } else {
        while (true) {
          const { value, done: doneReading } = await reader.read();
          if (doneReading) break;
          
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
                  currentResponseContent += token;
                  setCurrentStreamingMessage(prev => ({ ...prev, content: currentResponseContent }));
                }
              } catch {
              }
            }
          }
        }
        
        const endTime = performance.now();
        const elapsed = ((endTime - startTime) / 1000).toFixed(2);
        
        setMessages(prev => [...prev, {
          ...currentStreamingMessage,
          content: currentResponseContent,
          responseTime: elapsed
        }]);
        setCurrentStreamingMessage(null);
      }

    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { id: prev.length, role: 'assistant', content: `⚠️ Error: ${err.message}`, model },
      ]);
      setCurrentStreamingMessage(null);
    } finally {
      setLoading(false);
    }
  }

  const handleUpdateMessage = (updatedMessage) => {
    setMessages(prev =>
      prev.map(msg => (msg.id === updatedMessage.id ? updatedMessage : msg))
    );
  };

  const downloadFile = async (type, data) => {
    if (!data || data.length === 0) {
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
        body: JSON.stringify({ data }),
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
      document.body.removeChild(a);
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

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  const handleHistoryClick = (historyItem) => {
    if (inputRef.current) {
        inputRef.current.value = historyItem.command;
    }
    setModel(historyItem.model);
    setInteractionMode(historyItem.mode);
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      backgroundColor: '#1e1e1e',
      color: '#d4d4d4',
      fontFamily: 'Inter, sans-serif'
    }}>
      <style>{`
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
        
        .chat-scroll-area {
          flex: 1;
          overflow-y: auto;
          overflow-x: hidden;
          padding: 24px;
          padding-top: 80px;
          padding-bottom: 120px;
          scrollbar-width: thin;
          scrollbar-color: #0e639c transparent;
          display: flex;
          flex-direction: column;
        }
        .chat-scroll-area::-webkit-scrollbar {
          width: 8px;
        }
        .chat-scroll-area::-webkit-scrollbar-thumb {
          background-color: #0e639c;
          border-radius: 4px;
        }
        
        /* Table Scrollbar Styles */
        .table-container {
          overflow-x: auto;
          margin-top: 10px;
          margin-bottom: 10px;
          scrollbar-width: thin; /* For Firefox */
          scrollbar-color: #0e639c transparent; /* For Firefox */
        }
        .table-container::-webkit-scrollbar {
          height: 8px; /* For horizontal scrollbar in Chrome/Safari */
        }
        .table-container::-webkit-scrollbar-thumb {
          background-color: #0e639c;
          border-radius: 4px;
        }
        .table-container::-webkit-scrollbar-track {
          background-color: transparent;
        }


        header {
          background-color: #0e639c;
          color: white;
          display: flex;
          align-items: center;
          padding: 12px 24px;
          gap: 24px;
          width: 100%;
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
        form {
          display: flex;
          gap: 12px;
          padding: 16px 24px;
          background-color: #0e639c;
          position: fixed;
          bottom: 0;
          left: 0;
          width: 100%;
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
          width: 100%; /* Fixed width for uniform bubbles */
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
          padding-top: 28px;
        }
        .assistant.greeting {
          max-width: 100%;
          white-space: nowrap;
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

        input[type="range"] {
          -webkit-appearance: none;
          appearance: none;
          width: 100%;
          height: 8px;
          background: #4a4a4a;
          border-radius: 4px;
          outline: none;
          transition: background 0.2s ease-in-out;
        }
        input[type="range"]:hover {
          background: #5a5a5a;
        }

        input[type="range"]::-webkit-slider-thumb {
          -webkit-appearance: none;
          appearance: none;
          width: 20px;
          height: 20px;
          background: #0e639c;
          border-radius: 50%;
          cursor: pointer;
          transition: background 0.2s ease-in-out, transform 0.2s ease-in-out;
          border: 2px solid #0e639c;
          box-shadow: 0 0 2px rgba(0,0,0,0.5);
          margin-top: -6px;
        }
        input[type="range"]::-moz-range-thumb {
          width: 20px;
          height: 20px;
          background: #0e639c;
          border-radius: 50%;
          cursor: pointer;
          transition: background 0.2s ease-in-out, transform 0.2s ease-in-out;
          border: 2px solid #0e639c;
          box-shadow: 0 0 2px rgba(0,0,0,0.5);
        }
        input[type="range"]::-webkit-slider-thumb:hover {
          background: #1177d1;
          transform: scale(1.1);
        }
        input[type="range"]::-moz-range-thumb:hover {
          background: #1177d1;
          transform: scale(1.1);
        }

        /* Hamburger Menu Icon */
        .hamburger-menu {
          width: 24px;
          height: 24px;
          display: flex;
          flex-direction: column;
          justify-content: space-around;
          cursor: pointer;
          padding: 4px;
        }
        .hamburger-menu span {
          display: block;
          height: 2px;
          width: 100%;
          background-color: white;
          transition: all 0.2s ease-in-out;
        }
        .hamburger-menu.open span:first-child {
          transform: translateY(8px) rotate(45deg);
        }
        .hamburger-menu.open span:nth-child(2) {
          opacity: 0;
        }
        .hamburger-menu.open span:last-child {
          transform: translateY(-8px) rotate(-45deg);
        }
      `}</style>
      <header>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={() => setIsPanelOpen(prev => !prev)}
            style={{ 
              background: 'transparent', 
              border: 'none', 
              cursor: 'pointer', 
              padding: '0', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center', 
              transition: 'transform 0.2s' 
            }}
            onMouseOver={(e) => e.currentTarget.style.transform = 'scale(1.1)'}
            onMouseOut={(e) => e.currentTarget.style.transform = 'scale(1)'}
            aria-label="Toggle settings panel"
          >
            <div className={`hamburger-menu ${isPanelOpen ? 'open' : ''}`}>
              <span></span>
              <span></span>
              <span></span>
            </div>
          </button>
          <img
            src="https://placehold.co/36x36/ffffff/0e639c?text=DB"
            alt="Deutsche Bank Logo"
            style={{ height: '36px' }}
          />
          <div style={{ fontSize: '1.8rem', fontWeight: 'bold' }}>AI-Nova</div>
        </div>

        <div>
          <label style={{ fontSize: '1rem', fontWeight: 'bold' }} htmlFor="model-select">Model:</label>
          <select
            id="model-select"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            disabled={loading}
            aria-label="Select AI model"
          >
            <option value="dbLLM">Deutsche Bank - dbLLM</option>
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
            <option value="direct">Developer Assitant</option>
            <option value="database">Database - Direct Intent Routes</option>
            <option value="restful">API Assistant (Trained)</option>
            <option value="langchain">Database Assistant (Un-Trained)</option>
            <option value="langchainprompt">Database Assistant (Partially Trained)</option>
            <option value="embedded">Database Assistant (Fully Trained)</option>
            <option value="webscrape">Documentation Assistant</option>
            <option value="riskdata">Data Analysis Assistant</option>
            <option value="embedded_narrated">Database Assistant with Narration</option>
            <option value="generic_rag">Database Assistant - Generic RAG</option>
          </select>
        </div>
      </header>

      <div style={{ flexGrow: 1, display: 'flex', position: 'relative', overflow: 'hidden' }}>
        <LeftPanel
          isPanelOpen={isPanelOpen}
          temperature={temperature}
          setTemperature={setTemperature}
          topK={topK}
          setTopK={setTopK}
          topP={topP}
          setTopP={setTopP}
          commandHistory={commandHistory}
          onHistoryClick={handleHistoryClick}
        />
        <main className="chat-scroll-area" aria-live="polite" aria-relevant="additions" tabIndex={-1}>
          {messages
            .map((msg, index) => {
              const isUser = msg.role === 'user';
              const isTableMessage = msg.tableData && msg.tableData.length > 0;
              const isGreeting = index === 0 && !isUser; // Added condition to identify the greeting
              return (
                <div
                  key={index}
                  className={`message ${isUser ? 'user' : 'assistant'} ${isGreeting ? 'greeting' : ''}`}
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

                  {!isUser && !isTableMessage && (
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
                  {isTableMessage && (
                    <div style={{ fontSize: '0.8rem', color: '#aaa', marginTop: '6px' }}>
                      Showing only first 10 rows. Full data available in downloads below.
                    </div>
                  )}
                  {isTableMessage && (
                    <TableAndGraphOptions
                      message={msg}
                      onUpdateMessage={handleUpdateMessage}
                      onDownloadFile={downloadFile}
                    />
                  )}
                </div>
              );
            })}
          
          {/* Render the streaming message separately for better performance */}
          {currentStreamingMessage && (
            <div
              key="streaming"
              className="message assistant"
              aria-label={`Assistant response from model ${currentStreamingMessage.model || ''}`}
            >
              <div className="model-label" aria-hidden="true">
                Model: {currentStreamingMessage.model}
              </div>
              <ReactMarkdown
                children={currentStreamingMessage.content}
                remarkPlugins={[remarkGfm]}
                components={components}
              />
              {currentStreamingMessage.tableData && currentStreamingMessage.tableData.length > 0 && (
                <div style={{ fontSize: '0.8rem', color: '#aaa', marginTop: '6px' }}>
                  Showing only first 10 rows. Full data available in downloads below.
                </div>
              )}
            </div>
          )}
          <div ref={messagesEndRef} />
        </main>
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleKeyDown({ key: 'Enter', shiftKey: false, preventDefault: () => {} });
        }}
      >
        <textarea
          ref={inputRef} // Attach the ref to the textarea
          placeholder="Ask me........."
          onKeyDown={handleKeyDown}
          disabled={loading}
          rows={3}
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Loading...' : 'Send'}
        </button>
      </form>
    </div>
  );
}
