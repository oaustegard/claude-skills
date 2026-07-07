import { useEffect, useRef, useState } from 'react';

// Inline data island - embedded in component
const DATA = __DATA__;

export default function ChartExplorer() {
  const [selectedChart, setSelectedChart] = useState(0);
  const [specs] = useState(__CHART_SPECS__);
  const [scriptsLoaded, setScriptsLoaded] = useState(false);
  const [error, setError] = useState(null);
  const chartRefs = specs.map(() => useRef());
  
  // Load Vega libraries sequentially
  useEffect(() => {
    const loadScript = (src) => new Promise((resolve, reject) => {
      const existing = document.querySelector(`script[src="${src}"]`);
      if (existing) {
        resolve();
        return;
      }
      const script = document.createElement('script');
      script.src = src;
      script.async = false;
      document.head.appendChild(script);
      script.addEventListener('load', resolve, { once: true });
      script.addEventListener('error', reject, { once: true });
    });

    loadScript('https://cdn.jsdelivr.net/npm/vega@5')
      .then(() => loadScript('https://cdn.jsdelivr.net/npm/vega-lite@5'))
      .then(() => loadScript('https://cdn.jsdelivr.net/npm/vega-embed@6'))
      .then(() => {
        const checkInterval = setInterval(() => {
          if (window.vegaEmbed) {
            clearInterval(checkInterval);
            setScriptsLoaded(true);
          }
        }, 50);
        setTimeout(() => {
          clearInterval(checkInterval);
          if (!window.vegaEmbed) setError('Timeout loading Vega libraries');
        }, 5000);
      })
      .catch(err => setError(`Failed to load Vega: ${err.message}`));
  }, []);
  
  // Render chart when scripts load or selection changes
  useEffect(() => {
    if (!scriptsLoaded || !window.vegaEmbed) return;
    const ref = chartRefs[selectedChart]?.current;
    if (!ref) return;
    
    // Inject data into spec
    const specWithData = {
      ...specs[selectedChart].spec,
      data: { values: DATA }
    };
    
    window.vegaEmbed(ref, specWithData, {
      actions: {export: {svg: true, png: true}, source: false, compiled: false, editor: false},
      theme: 'dark'
    }).catch(err => setError(err.message));
  }, [scriptsLoaded, selectedChart]);
  
  const currentSpec = specs[selectedChart];
  
  return (
    <div style={{fontFamily: 'Arial, sans-serif', maxWidth: 1200, margin: '0 auto', padding: 20, background: '#1a1a1a', color: '#e0e0e0', minHeight: '100vh'}}>
      <h1 style={{marginBottom: 10, color: '#64b5f6'}}>Chart Explorer</h1>
      <p style={{color: '#b0bec5', marginBottom: 30}}>
        Select a chart type to visualize your data. Export specs for production use.
      </p>
      
      {error && (
        <div style={{background: 'rgba(244, 67, 54, 0.1)', color: '#ef5350', padding: 15, borderRadius: 4, marginBottom: 20, border: '1px solid rgba(244, 67, 54, 0.3)'}}>
          <strong>Error:</strong> {error}
        </div>
      )}
      
      {!scriptsLoaded && !error && (
        <div style={{padding: 20, textAlign: 'center', color: '#90caf9'}}>
          Loading Vega-Lite...
        </div>
      )}
      
      {/* Chart Type Selector */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
        gap: 15,
        marginBottom: 30
      }}>
        {specs.map((item, idx) => (
          <button
            key={idx}
            onClick={() => setSelectedChart(idx)}
            style={{
              padding: 15,
              border: selectedChart === idx ? '2px solid #64b5f6' : '1px solid rgba(255, 255, 255, 0.12)',
              borderRadius: 8,
              background: selectedChart === idx ? 'rgba(100, 181, 246, 0.15)' : 'rgba(255, 255, 255, 0.05)',
              cursor: 'pointer',
              textAlign: 'left',
              transition: 'all 0.2s',
              color: '#e0e0e0'
            }}
          >
            <div style={{fontWeight: 'bold', marginBottom: 5, color: '#64b5f6'}}>
              {item.type}
            </div>
            <div style={{fontSize: 13, color: '#b0bec5'}}>
              {item.reason}
            </div>
          </button>
        ))}
      </div>
      
      {/* Chart Display */}
      <div style={{
        background: 'rgba(255, 255, 255, 0.03)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: 8,
        padding: 20,
        marginBottom: 20,
        minHeight: 450
      }}>
        {specs.map((_, idx) => (
          <div 
            key={idx}
            ref={chartRefs[idx]} 
            style={{display: selectedChart === idx ? 'block' : 'none'}}
          />
        ))}
      </div>
      
      {/* Spec Export */}
      {scriptsLoaded && currentSpec && (
        <details style={{marginTop: 20}}>
          <summary style={{
            cursor: 'pointer',
            padding: 15,
            background: 'rgba(255, 255, 255, 0.05)',
            borderRadius: 8,
            fontWeight: 'bold',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            color: '#64b5f6'
          }}>
            📋 Export Vega-Lite Spec
          </summary>
          <div style={{marginTop: 15, padding: 20, background: 'rgba(255, 255, 255, 0.03)', borderRadius: 8, border: '1px solid rgba(255, 255, 255, 0.08)'}}>
            <p style={{marginTop: 0, color: '#b0bec5', fontSize: 14}}>
              This JSON specification is framework-agnostic. Use with vega-embed in React, Angular, Vue, or any framework.
              Add your data via: <code style={{background: 'rgba(255, 255, 255, 0.1)', padding: '2px 6px', borderRadius: 3}}>spec.data = {'{values: yourData}'}</code>
            </p>
            <pre style={{
              background: 'rgba(0, 0, 0, 0.3)',
              padding: 15,
              borderRadius: 4,
              overflow: 'auto',
              fontSize: 12,
              border: '1px solid rgba(255, 255, 255, 0.08)',
              maxHeight: 400,
              color: '#e0e0e0'
            }}>
              {JSON.stringify(currentSpec.spec, null, 2)}
            </pre>
            <button
              onClick={() => {
                navigator.clipboard.writeText(JSON.stringify(currentSpec.spec, null, 2));
                alert('Spec copied to clipboard!');
              }}
              style={{
                padding: '10px 20px',
                background: '#64b5f6',
                color: '#000',
                border: 'none',
                borderRadius: 4,
                cursor: 'pointer',
                fontSize: 14,
                fontWeight: 'bold',
                marginTop: 10
              }}
            >
              📋 Copy to Clipboard
            </button>
          </div>
        </details>
      )}
      
      <div style={{marginTop: 40, padding: 20, textAlign: 'center', color: '#78909c', fontSize: 14, borderTop: '1px solid rgba(255, 255, 255, 0.08)'}}>
        <p>Data is embedded inline. Specs are portable and production-ready.</p>
        <p style={{fontSize: 12, marginTop: 10}}>Vega-Lite v5 • {DATA.length.toLocaleString()} data points</p>
      </div>
    </div>
  );
}
