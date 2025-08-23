import React, { useState, useRef, useEffect, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { PanelLeft, X, Settings } from 'lucide-react';
import * as htmlToImage from 'html-to-image';


// Define a custom markdown component for rendering code blocks
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
};

// New custom component for rendering the data table
const TableComponent = React.memo(({ data }) => {
  if (!data || data.length === 0) {
    return <div style={{ color: '#aaa', padding: '10px' }}>No data to display.</div>;
  }

  const headers = Object.keys(data[0]);

  return (
    <div className="table-container">
      <table
        style={{
          borderCollapse: 'collapse',
          width: '100%',
          minWidth: '600px',
        }}
      >
        <thead>
          <tr>
            {headers.map((header) => (
              <th
                key={header}
                style={{
                  border: '1px solid #ddd',
                  padding: '5px',
                  backgroundColor: '#0e639c',
                  color: 'white',
                  textAlign: 'left',
                  whiteSpace: 'nowrap',
                  fontSize: '0.8rem',
                }}
              >
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.slice(0, 10).map((row, rowIndex) => (
            <tr key={rowIndex}>
              {headers.map((header) => (
                <td
                  key={`${rowIndex}-${header}`}
                  style={{
                    border: '1px solid #ddd',
                    padding: '5px',
                    textAlign: 'left',
                    whiteSpace: 'nowrap',
                    fontSize: '0.8rem',
                  }}
                >
                  {typeof row[header] === 'object' ? JSON.stringify(row[header]) : String(row[header])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
});

const LeftPanel = ({
  isPanelOpen,
  temperature,
  setTemperature,
  topK,
  setTopK,
  topP,
  setTopP,
  commandHistory,
  onHistoryClick,
  areFiltersVisible,
  setAreFiltersVisible,
  isGraphVisible,
  setIsGraphVisible,
  areDownloadsVisible,
  setAreDownloadsVisible
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
          className="button-primary"
        >
          Reset Sliders
        </button>
        <hr style={{ borderTop: '1px solid #444', margin: '16px 0' }} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '0.875rem', fontWeight: 'semibold' }}>Show Filters</span>
                <input
                  type="checkbox"
                  checked={areFiltersVisible}
                  onChange={(e) => setAreFiltersVisible(e.target.checked)}
                  className="toggle-switch"
                />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '0.875rem', fontWeight: 'semibold' }}>Show Generate Graph</span>
                <input
                  type="checkbox"
                  checked={isGraphVisible}
                  onChange={(e) => setIsGraphVisible(e.target.checked)}
                  className="toggle-switch"
                />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '0.875rem', fontWeight: 'semibold' }}>Show Downloads</span>
                <input
                  type="checkbox"
                  checked={areDownloadsVisible}
                  onChange={(e) => setAreDownloadsVisible(e.target.checked)}
                  className="toggle-switch"
                />
              </div>
        </div>
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
const TableAndGraphOptions = ({ message, onUpdateMessage, onDownloadFile, areFiltersVisible, isGraphVisible, areDownloadsVisible }) => {
  const graphRef = useRef(null);

  // Use state hooks for this specific message's data and options
  const [viewMode, setViewMode] = useState(message.viewMode || 'table');
  const [selectedGraphType, setSelectedGraphType] = useState(message.selectedGraphType || 'bar');
  const [selectedXAxis, setSelectedXAxis] = useState(message.selectedXAxis || '');
  const [selectedYAxis, setSelectedYAxis] = useState(message.selectedYAxis || '');
  const [selectedAggregation, setSelectedAggregation] = useState(message.selectedAggregation || 'count');
  const [currentGraphData, setCurrentGraphData] = useState(message.currentGraphData || null);
  // Replaced hardcoded filters with a state for a generic array of filters
  const [filters, setFilters] = useState(message.filters || []);
  
  // New state to hold the filtered data
  const [filteredData, setFilteredData] = useState(message.filteredData || message.tableData);


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


  // New function to filter the data based on user input
  const applyFilters = (data, filters) => {
      let filtered = data;
      if (filters.length > 0) {
          filtered = filtered.filter(item => {
              return filters.every(filter => {
                  const columnValue = item[filter.column];
                  const filterValue = filter.value;
                  const operator = filter.operator;

                  if (columnValue === undefined || filterValue === '') {
                      // Skip filtering if column doesn't exist or value is empty
                      return true;
                  }

                  switch (operator) {
                      case 'equals':
                          return String(columnValue).toLowerCase() === String(filterValue).toLowerCase();
                      case 'not-equals':
                          return String(columnValue).toLowerCase() !== String(filterValue).toLowerCase();
                      case 'contains':
                          return String(columnValue).toLowerCase().includes(String(filterValue).toLowerCase());
                      case 'greater-than':
                          return Number(columnValue) > Number(filterValue);
                      case 'less-than':
                          return Number(columnValue) < Number(filterValue);
                      default:
                          return true;
                  }
              });
          });
      }
      return filtered;
  };
  
  // New function to handle the "Apply Filters" button click
  const handleApplyFilters = () => {
    const newData = applyFilters(excelData, filters);
    setFilteredData(newData);
    // Update the message state with the new filtered data and switch to table view
    onUpdateMessage({
      ...message,
      filters,
      filteredData: newData,
      viewMode: 'table'
    });
  };

  const aggregateAndGenerateGraph = () => {
    if (!selectedXAxis || !selectedYAxis) {
      alert('Please select both X and Y axis columns.');
      return;
    }

    const aggregatedMap = new Map();
    (filteredData || excelData).forEach(item => { // Use filteredData if available, otherwise original
      const xValue = item[selectedXAxis];
      const yValue = typeof item[selectedYAxis] === 'number' ? item[selectedYAxis] : 0;

      if (!aggregatedMap.has(xValue)) {
        switch (selectedAggregation) {
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

      switch (selectedAggregation) {
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
      if (selectedAggregation === 'average') {
        return val.count > 0 ? val.sum / val.count : 0;
      }
      return val;
    });

    const newGraphData = {
      type: selectedGraphType,
      labels: labels,
      data: values,
      title: `${selectedAggregation.charAt(0).toUpperCase() + selectedAggregation.slice(1)} of ${selectedYAxis} by ${selectedXAxis}`,
    };

    setCurrentGraphData(newGraphData);
    setViewMode('graph');
    
    // Update the message state with the new graph data and view mode
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
  
  // Functions for managing the new dynamic filters
  const addFilter = () => {
      setFilters([...filters, { column: availableColumns[0], operator: 'equals', value: '' }]);
      onUpdateMessage({ ...message, filters: [...filters, { column: availableColumns[0], operator: 'equals', value: '' }] });
  };

  const removeFilter = (indexToRemove) => {
      // Create the new array of filters
      const newFilters = filters.filter((_, index) => index !== indexToRemove);
      
      // Apply the new filters to the original data
      const newFilteredData = applyFilters(excelData, newFilters);
      
      // Update local state
      setFilters(newFilters);
      setFilteredData(newFilteredData);
      
      // Update the parent message state
      onUpdateMessage({
          ...message,
          filters: newFilters,
          filteredData: newFilteredData,
      });
  };

  const updateFilter = (indexToUpdate, key, value) => {
      const newFilters = filters.map((filter, index) => {
          if (index === indexToUpdate) {
              return { ...filter, [key]: value };
          }
          return filter;
      });
      setFilters(newFilters);
      onUpdateMessage({ ...message, filters: newFilters });
  };


  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '20px', padding: '16px', backgroundColor: '#252526', borderRadius: '8px' }}>
      <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 'bold' }}>Graph & View Options for this table</h4>
      {areFiltersVisible && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'center' }}>
          <label htmlFor={`graph-type-select-${message.id}`}>Type:</label>
          <select id={`graph-type-select-${message.id}`} value={selectedGraphType} onChange={(e) => handleDropdownChange(setSelectedGraphType, e.target.value)} disabled={!hasTableData}>
            <option value="bar">Bar Chart</option>
            <option value="line">Line Graph</option>
          </select>

          <label htmlFor={`x-axis-select-${message.id}`}>X-Axis (Group By):</label>
          <select id={`x-axis-select-${message.id}`} value={selectedXAxis} onChange={(e) => handleDropdownChange(setSelectedXAxis, e.target.value)} disabled={!hasTableData}>
            {availableColumns.map(col => (
              <option key={col} value={col}>{col}</option>
            ))}
          </select>

          <label htmlFor={`y-axis-select-${message.id}`}>Y-Axis (Aggregate):</label>
          <select id={`y-axis-select-${message.id}`} value={selectedYAxis} onChange={(e) => handleDropdownChange(setSelectedYAxis, e.target.value)} disabled={!hasTableData}>
            {availableColumns.map(col => (
              <option key={col} value={col}>{col}</option>
            ))}
          </select>

          <label htmlFor={`agg-select-${message.id}`}>Aggregation:</label>
          <select id={`agg-select-${message.id}`} value={selectedAggregation} onChange={(e) => handleDropdownChange(setSelectedAggregation, e.target.value)} disabled={!hasTableData}>
            <option value="count">Count</option>
            <option value="sum">Sum</option>
            <option value="average">Average</option>
            <option value="minimum">Minimum</option>
            <option value="maximum">Maximum</option>
          </select>
        </div>
      )}
        
        {/* Dynamic Filter Section */}
      {areFiltersVisible && (
        <>
          <hr style={{ borderTop: '1px solid #444' }} />
          <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 'bold' }}>Filter Data (Optional)</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {filters.map((filter, index) => (
                  <div key={index} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <select
                          value={filter.column}
                          onChange={(e) => updateFilter(index, 'column', e.target.value)}
                          style={{ flexShrink: 0 }}
                          disabled={!hasTableData}
                      >
                          {availableColumns.map(col => (
                              <option key={col} value={col}>{col}</option>
                          ))}
                      </select>
                      <select
                          value={filter.operator}
                          onChange={(e) => updateFilter(index, 'operator', e.target.value)}
                          style={{ flexShrink: 0 }}
                          disabled={!hasTableData}
                      >
                          <option value="equals">equals</option>
                          <option value="not-equals">not equals</option>
                          <option value="contains">contains</option>
                          <option value="greater-than">greater than</option>
                          <option value="less-than">less than</option>
                      </select>
                      <input
                          type="text"
                          value={filter.value}
                          onChange={(e) => updateFilter(index, 'value', e.target.value)}
                          placeholder="Enter value"
                          disabled={!hasTableData}
                          style={{ padding: '6px', borderRadius: '4px', border: '1px solid #444', backgroundColor: '#1e1e1e', color: '#d4d4d4', flexGrow: 1 }}
                      />
                      <button onClick={() => removeFilter(index)} className="button-icon" disabled={!hasTableData}>
                          <X size={16} />
                      </button>
                  </div>
              ))}
              <button onClick={addFilter} className="button-primary" style={{ flexGrow: '1' }} disabled={!hasTableData}>
                  + Add Filter
              </button>
          </div>
        </>
      )}

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'center' }}>
          {areFiltersVisible && (
            <button onClick={handleApplyFilters} className="button-primary" disabled={filters.length === 0 || !hasTableData}>Apply Filters</button>
          )}
          {isGraphVisible && (
            <button onClick={aggregateAndGenerateGraph} className="button-primary" disabled={!selectedXAxis || !selectedYAxis || !hasTableData}>Generate Graph</button>
          )}
          {currentGraphData && isGraphVisible && (
            <>
              <button onClick={handleToggleView} className="button-primary" disabled={!currentGraphData}>
                {viewMode === 'graph' ? 'Show Table' : 'Show Graph'}
              </button>
              {viewMode === 'graph' && (
                <button
                  onClick={handleSaveGraph}
                  className="button-primary"
                  disabled={!currentGraphData}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px' }}>
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                    <polyline points="7 10 12 15 17 10"></polyline>
                    <line x1="12" y1="15" x2="12" y2="3"></line>
                  </svg>
                  <span>Save Graph</span>
                </button>
              )}
            </>
          )}
        </div>
        {areDownloadsVisible && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', justifyContent: 'center' }}>
         <button 
              onClick={() => onDownloadFile('excel', excelData)} 
              className="button-primary"
              disabled={!hasTableData}
              >
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px' }}>
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <path d="M14 2v6h6M16 13h-4m0 4h-4m4-8h-4"></path>
              </svg>
              <span>Download Excel</span>
          </button>
          <button onClick={() => onDownloadFile('csv', excelData)} className="button-primary" disabled={!hasTableData}>
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px' }}>
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <path d="M14 2v6h6M16 13h-4m0 4h-4m4-8h-4"></path>
            </svg>
            <span>Download CSV</span>
          </button>
          <button onClick={() => onDownloadFile('pdf', excelData)} className="button-primary" disabled={!hasTableData}>
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#e04e4e" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px' }}>
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <path d="M14 2v6h6M10 13a2 2 0 0 1 2 2a2 2 0 0 1-2 2h-2v-4h2a2 2 0 0 1 2 2z"></path>
            </svg>
            <span>Download PDF</span>
          </button>
        </div>
        )}
      {viewMode === 'graph' && currentGraphData && isGraphVisible && (
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
  
  // New state variables to hide/unhide UI elements
  const [areFiltersVisible, setAreFiltersVisible] = useState(true);
  const [isGraphVisible, setIsGraphVisible] = useState(true);
  const [areDownloadsVisible, setAreDownloadsVisible] = useState(true);
  
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
          stream: ['direct', 'database', 'database1', 'langchain', 'langchainprompt', 'restful', 'embedded', 'embedded_narrated', 'generic_rag'].includes(interactionMode),
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
      
      if (['database', 'langchainprompt', 'restful', 'embedded', 'embedded_narrated', 'generic_rag', 'database1'].includes(interactionMode)) {
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

              currentResponseContent = narrationText ? `📝 ${narrationText}` : '';

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
        .button-primary {
          /* Slimmed down padding */
          padding: 8px 16px;
          font-size: 0.95rem; /* Slightly smaller font for a slimmer look */
          border-radius: 6px; /* Slightly smaller border radius */
          border: 1px solid #084c75;
          background: linear-gradient(180deg, #1177d1 0%, #0e639c 100%);
          color: white;
          cursor: pointer;
          user-select: none;
          font-weight: 500;
          /* Removed min-width for flexibility */
          box-shadow: 0 44px 10px rgba(0,0,0,0.2);
          transition: all 0.2s ease;
          flex-shrink: 0;
          display: flex;
          align-items: center;
        }
        .button-primary:hover:not(:disabled) {
          background: linear-gradient(180deg, #1283e3 0%, #1177d1 100%);
          transform: translateY(-2px);
          box-shadow: 0 6px 15px rgba(0,0,0,0.3);
        }
        .button-primary:disabled {
          background: #3a3d41;
          border-color: #333;
          cursor: not-allowed;
          box-shadow: none;
          opacity: 0.7;
          transform: none;
        }
        .button-icon {
            background: none;
            border: none;
            color: #d4d4d4;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: color 0.2s;
            padding: 4px;
            border-radius: 4px;
        }
        .button-icon:hover {
            color: #0e639c;
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
        .toggle-switch {
          position: relative;
          display: inline-block;
          width: 40px;
          height: 24px;
          cursor: pointer;
        }
        
        .toggle-switch input {
          opacity: 0;
          width: 0;
          height: 0;
        }
        
        .toggle-switch span {
          position: absolute;
          cursor: pointer;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background-color: #ccc;
          transition: .4s;
          border-radius: 24px;
        }
        
        .toggle-switch span:before {
          position: absolute;
          content: "";
          height: 16px;
          width: 16px;
          left: 4px;
          bottom: 4px;
          background-color: white;
          transition: .4s;
          border-radius: 50%;
        }
        
        .toggle-switch input:checked + span {
          background-color: #0e639c;
        }
        
        .toggle-switch input:checked + span:before {
          transform: translateX(16px);
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
            <option value="database1">Database - Direct Intent embeded nomodel Routes</option>
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
          areFiltersVisible={areFiltersVisible}
          setAreFiltersVisible={setAreFiltersVisible}
          isGraphVisible={isGraphVisible}
          setIsGraphVisible={setIsGraphVisible}
          areDownloadsVisible={areDownloadsVisible}
          setAreDownloadsVisible={setAreDownloadsVisible}
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

                  {msg.content && (
                    <ReactMarkdown
                      children={msg.content}
                      remarkPlugins={[remarkGfm]}
                      components={components}
                    />
                  )}
                  
                  {isTableMessage && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '10px' }}>
                      <p style={{ fontSize: '0.9rem', color: '#ccc' }}>
                        Displaying data. You can filter the table or generate a graph below.
                      </p>
                      <TableComponent data={msg.filteredData || msg.tableData} />
                      <p style={{ fontSize: '0.8rem', color: '#aaa', marginTop: '6px' }}>
                        Showing {msg.filteredData ? msg.filteredData.length : msg.tableData.length} rows. Full data available in downloads below.
                      </p>
                    </div>
                  )}

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
                    <TableAndGraphOptions
                      message={msg}
                      onUpdateMessage={handleUpdateMessage}
                      onDownloadFile={downloadFile}
                      areFiltersVisible={areFiltersVisible}
                      isGraphVisible={isGraphVisible}
                      areDownloadsVisible={areDownloadsVisible}
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
                 <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '10px' }}>
                    <p style={{ fontSize: '0.9rem', color: '#ccc' }}>
                        Displaying data. You can filter the table or generate a graph below.
                    </p>
                    <TableComponent data={currentStreamingMessage.filteredData || currentStreamingMessage.tableData} />
                    <p style={{ fontSize: '0.8rem', color: '#aaa', marginTop: '6px' }}>
                        Showing {currentStreamingMessage.filteredData ? currentStreamingMessage.filteredData.length : currentStreamingMessage.tableData.length} rows. Full data available in downloads below.
                    </p>
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
        <button type="submit" className="button-primary" style={{ minWidth: '100px' }} disabled={loading}>
          {loading ? 'Loading...' : 'Send'}
        </button>
      </form>
    </div>
  );
}
