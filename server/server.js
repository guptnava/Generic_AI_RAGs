import express from 'express';
import fetch from 'node-fetch';
import cors from 'cors';
import { fetch as undiciFetch } from 'undici';
import ExcelJS from 'exceljs'; // ← Add at top


import fs from 'fs';
import path from 'path';

import { fileURLToPath } from 'url';

// 👇 Recreate __dirname in ESM
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);



const app = express();


app.use(cors());

// Increase JSON body limit (example: 10 MB)
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ limit: '10mb', extended: true }));

const hostname='Naveens-Mac-Pro.local';
const port = 3000;

const FLASK_DATABASE_INTENT_URL = `http://${hostname}:5000`;
const FLASK_DATABASE_LANGCHAIN_URL = `http://${hostname}:5001`;
const FLASK_DATABASE_LANGCHAIN_PROMPT_ENG_URL = `http://${hostname}:5002`;
const FLASK_DATABASE_LLAMAINDEX_PROMPT_ENG_URL = `http://${hostname}:5003`;
const FLASK_DATABASE_LANGCHAIN_PROMPT_ENG_EMBD_URL = `http://${hostname}:5004`;
const FLASK_RESTFUL_PROMPT_ENG_EMBD_URL = `http://${hostname}:5006`;
const FLASK_DATABASE_LANGCHAIN_PROMPT_ENG_EMBD_NARRATED_URL = `http://${hostname}:5009`;
const FLASK_DATABASE_GENERIC_RAG_URL = `http://${hostname}:5010`;
const FLASK_DATABASE_INTENT_EMBDED_NOMODEL_URL = `http://${hostname}:5011`;

const OLLAMA_API_URL = `http://${hostname}:11434`; // Ollama HTTP API URL

const CACHE_EXPIRATION_MS = 30 * 60 * 1000; // 30 minutes cache expiration

// Simple in-memory cache: { key: { data, expiresAt } }
const cache = new Map();

function getCache(key) {
  const cached = cache.get(key);
  if (cached && cached.expiresAt > Date.now()) {
    return cached.data;
  }
  if (cached) cache.delete(key);
  return null;
}

function setCache(key, data) {
  cache.set(key, {
    data,
    expiresAt: Date.now() + CACHE_EXPIRATION_MS,
  });
}

app.post('/api/generate', async (req, res) => {
  const { model, prompt, mode, stream } = req.body;
  let flask_endpoint = '';

  if (mode === 'database') flask_endpoint = `${FLASK_DATABASE_INTENT_URL}/query`;
  else if (mode === 'langchain') flask_endpoint = `${FLASK_DATABASE_LANGCHAIN_URL}/query`;
  else if (mode === 'langchainprompt') flask_endpoint = `${FLASK_DATABASE_LANGCHAIN_PROMPT_ENG_URL}/query`;
  else if (mode === 'restful') flask_endpoint = `${FLASK_RESTFUL_PROMPT_ENG_EMBD_URL}/query`;
  else if (mode === 'embedded') flask_endpoint = `${FLASK_DATABASE_LANGCHAIN_PROMPT_ENG_EMBD_URL}/query`;
  else if (mode === 'llamaindex') flask_endpoint = `${FLASK_DATABASE_LLAMAINDEX_PROMPT_ENG_URL}/query`;
  else if (mode === 'embedded_narrated') flask_endpoint = `${FLASK_DATABASE_LANGCHAIN_PROMPT_ENG_EMBD_NARRATED_URL}/query`;
  else if (mode === 'generic_rag') flask_endpoint = `${FLASK_DATABASE_GENERIC_RAG_URL}/query`;
  else if (mode === 'database1') flask_endpoint = `${FLASK_DATABASE_INTENT_EMBDED_NOMODEL_URL}/query`;
  
  
  try {
    if (["database", "langchainprompt", "restful", "embedded", "embedded_narrated", "generic_rag", "database1",].includes(mode))  {
      // Proxy to Flask API for DB queries with caching and logging
     /*  const cached = getCache(prompt);
      if (cached) {
        return res.json({ response: cached, cached: true });
      }
 */
      // Pass user-agent and IP info
      const userAgent = req.headers['user-agent'] || 'unknown';
      const clientIp = req.ip || req.connection.remoteAddress || 'unknown';

      const flaskRes = await undiciFetch(flask_endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'User-Agent': userAgent,
          'X-Forwarded-For': clientIp,
        },
        body: JSON.stringify({prompt, model}),
      });

      if (!flaskRes.ok) {
        const error = await flaskRes.json();
        return res.status(flaskRes.status).json({ error: error.error || 'Flask API error' });
      }

      // Set the same content-type header so frontend knows it's NDJSON
      res.setHeader('Content-Type', 'application/x-ndjson; charset=utf-8');
      // Pipe the Flask response stream to the client response stream
      const reader = flaskRes.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let done = false;

      while (!done) {
          const { value, done: doneReading } = await reader.read();
          done = doneReading;
          if (value) {
            const chunk = decoder.decode(value);
            res.write(chunk);
          }
        }
        res.end();

        // Optionally, you can implement caching logic here by buffering chunks, but streaming + caching is more complex

    } else if (mode === 'direct') {
      // Direct mode — call Ollama HTTP API with streaming

      const ollamaRes = await undiciFetch(`${OLLAMA_API_URL}/api/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model,
          prompt,
          stream,
        }),
      });

      if (!ollamaRes.ok || !ollamaRes.body) {
        throw new Error(`Failed to start stream: ${ollamaRes.status} ${ollamaRes.statusText}`);
      }

      res.setHeader('Content-Type', 'application/json; charset=utf-8');

      const reader = ollamaRes.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let done = false;

      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        if (value) {
          const chunk = decoder.decode(value);
          res.write(chunk);
        }
      }
      res.end();

    } else if (["langchain", "llamaindex"].includes(mode)){
      // Direct mode — call Ollama HTTP API with streaming

      // Proxy to Flask API for DB queries with caching and logging
     /*  const cached = getCache(prompt);
      if (cached) {
        return res.json({ response: cached, cached: true });
      }
       */
      // Pass user-agent and IP info
      const userAgent = req.headers['user-agent'] || 'unknown';
      const clientIp = req.ip || req.connection.remoteAddress || 'unknown';

      const flaskRes = await undiciFetch(flask_endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'User-Agent': userAgent,
          'X-Forwarded-For': clientIp,
        },
        body: JSON.stringify({prompt, model}),
      });
      
      if (!flaskRes.ok || !flaskRes.body) {
        throw new Error(`Failed to start stream: ${flaskRes.status} ${flaskRes.statusText}`);
      }

      res.setHeader('Content-Type', 'application/json; charset=utf-8');

      const reader = flaskRes.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let done = false;

      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        if (value) {
          const chunk = decoder.decode(value);
          res.write(chunk);
        }
      }
      res.end();

    } else {
      res.status(400).json({ error: 'Invalid interaction mode' });
    }
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});



// Excel file download route
app.post('/api/download-excel', async (req, res) => {
  const { data, filename = 'chatbot_data.xlsx' } = req.body;

  if (!Array.isArray(data) || data.length === 0) {
    return res.status(400).json({ error: 'No tabular data provided' });
  }

  try {
    const workbook = new ExcelJS.Workbook();
    const worksheet = workbook.addWorksheet('Data');

    // Auto-set columns from keys of first row
    worksheet.columns = Object.keys(data[0]).map((key) => ({
      header: key,
      key: key,
      width: 20,
    }));

    // Add each row
    data.forEach((row) => {
      worksheet.addRow(row);
    });

    // Set headers for file download
    res.setHeader(
      'Content-Type',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    );
    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);

    // Stream workbook to response
    await workbook.xlsx.write(res);
    res.end();
  } catch (error) {
    console.error('Excel export error:', error);
    res.status(500).json({ error: 'Failed to generate Excel file' });
  }
});

app.post('/api/download-csv', async (req, res) => {
  const { data, filename = 'chatbot_data.csv' } = req.body;

  if (!Array.isArray(data) || data.length === 0) {
    return res.status(400).json({ error: 'No tabular data provided' });
  }

  const headers = Object.keys(data[0]);
  const csv = [headers.join(',')].concat(
    data.map(row => headers.map(h => JSON.stringify(row[h] ?? '')).join(','))
  ).join('\n');

  res.setHeader('Content-Type', 'text/csv');
  res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
  res.send(csv);
});

app.post('/api/download-pdf', async (req, res) => {
  const { data, filename = 'chatbot_data.pdf' } = req.body;

  if (!Array.isArray(data) || data.length === 0) {
    return res.status(400).json({ error: 'No tabular data provided' });
  }

  // Lazy import PDFKit
  const { default: PDFDocument } = await import('pdfkit');

  const doc = new PDFDocument({ margin: 30, size: 'A4' });
  res.setHeader('Content-Type', 'application/pdf');
  res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
  doc.pipe(res);

  
  const normalFontPath = path.join(__dirname, 'fonts', 'DejaVuSans.ttf');
  const boldFontPath = path.join(__dirname, 'fonts', 'DejaVuSans-Bold.ttf');

  const normalFontBuffer = fs.readFileSync(normalFontPath);
  const boldFontBuffer   = fs.readFileSync(boldFontPath);



    // 👉 Register safe fonts (supports full UTF-8)
  doc.registerFont('Normal', normalFontBuffer );
  doc.registerFont('Bold', boldFontBuffer);



  const headers = Object.keys(data[0]);
  const cellPadding = 5;

  // Title
  doc.font('Bold')
     .fontSize(16)
     .text('Chatbot Data Export', { align: 'center' })
     .moveDown(1.5);

  // Table dimensions
  const pageWidth = doc.page.width - doc.page.margins.left - doc.page.margins.right;
  const colWidth = pageWidth / headers.length;
  let y = doc.y;

  // Function to draw a cell
const drawCell = (text, x, y, width, height, isHeader = false) => {
  doc.rect(x, y, width, height).stroke();

  doc.font(isHeader ? 'Bold' : 'Normal')   // ✅ use registered fonts
    .fontSize(isHeader ? 12 : 10)
    .text(String(text ?? ''), x + cellPadding, y + cellPadding, {
      width: width - cellPadding * 2,
      height: height - cellPadding * 2,
      align: 'left',
    });
  };

  // Draw header row
  const headerHeight = 20;
  headers.forEach((h, i) => {
    drawCell(h, doc.page.margins.left + i * colWidth, y, colWidth, headerHeight, true);
  });
  y += headerHeight;

  // Draw data rows
  const rowHeight = 20;
  data.forEach(row => {
    headers.forEach((key, i) => {
      drawCell(String(row[key] ?? ''), doc.page.margins.left + i * colWidth, y, colWidth, rowHeight, false);
    });
    y += rowHeight;

    // Page break if needed
    if (y + rowHeight > doc.page.height - doc.page.margins.bottom) {
      doc.addPage();
      y = doc.page.margins.top;
    }
  });

  doc.end();
});




// Health check endpoint that proxies Flask health
app.get('/health', async (req, res) => {
  try {
    const flaskHealth = await fetch(`${FLASK_API_URL}/health`);
    if (!flaskHealth.ok) {
      return res.status(500).json({ status: 'Flask API unhealthy' });
    }
    const healthJson = await flaskHealth.json();
    res.json({ status: 'ok', flask: healthJson });
  } catch (e) {
    res.status(500).json({ status: 'error', error: e.message });
  }
});

// const PORT = process.env.PORT || 3000;
// app.listen(PORT, () => {
//   console.log(`Node.js server listening on port ${PORT}`);
// });


app.listen(port, hostname,  () => {
  console.log(`AI-Nova Server Running at http://${hostname}:${port}/`);
});
