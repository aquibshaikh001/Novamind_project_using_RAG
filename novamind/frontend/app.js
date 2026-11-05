/* ======================================================================
   app.js - the behaviour of the NovaMind web page.

   WHY THIS FILE EXISTS
     The browser cannot talk to Ollama or ChromaDB directly. This file
     sends requests to our FastAPI backend and draws the results.

   SECTIONS
     1. Shortcuts & state
     2. Status, documents and model panel (sidebar)
     3. Chat: sending a message and reading the streamed answer (SSE)
     4. Voice: microphone recording and reading answers aloud
     5. Start-up
   ====================================================================== */

// ---------- 1. SHORTCUTS & STATE ----------
const $ = (id) => document.getElementById(id);   // short helper: $("send-btn")

const messagesEl = $("messages");
const inputEl    = $("input");
const sendBtn    = $("send-btn");

let mode = "auto";      // "auto" | "docs" | "web"  (set by the three buttons on top)
let history = [];       // earlier turns, sent to the backend so the AI remembers context
let busy = false;       // true while an answer is streaming (prevents double sending)


// ---------- 2. SIDEBAR ----------

/** Shows a green/red box: is the backend + Ollama running? */
async function refreshHealth() {
  const box = $("status");
  try {
    const res = await fetch("/api/health");
    const h = await res.json();
    if (h.ollama_running) {
      box.textContent = `Connected · ${h.llm_model} · ${h.chunks_stored} chunks stored`;
      box.className = "status ok";
    } else {
      box.textContent = "Ollama is not running. Start it with: ollama serve";
      box.className = "status bad";
    }
  } catch (e) {
    box.textContent = "Backend not reachable. Is the server running?";
    box.className = "status bad";
  }
}

/** Loads the list of uploaded documents and draws it. */
async function loadDocs() {
  const res = await fetch("/api/documents");
  const data = await res.json();
  const list = $("doc-list");
  list.innerHTML = "";                         // clear old rows

  if (data.documents.length === 0) {
    const li = document.createElement("li");
    li.className = "small";
    li.textContent = "No documents yet.";
    list.appendChild(li);
    return;
  }
  for (const doc of data.documents) {
    const li = document.createElement("li");

    const name = document.createElement("span");
    name.className = "doc-name";
    name.textContent = `${doc.name} (${doc.chunks})`;   // textContent = safe against HTML injection
    name.title = doc.name;

    const del = document.createElement("button");
    del.className = "doc-del";
    del.textContent = "Remove";
    del.onclick = async () => {
      await fetch("/api/documents/" + encodeURIComponent(doc.name), { method: "DELETE" });
      loadDocs();
      refreshHealth();
    };

    li.append(name, del);
    list.appendChild(li);
  }
}

/** Sends the chosen file to the backend. Embedding can take a while. */
async function uploadFile(file) {
  const msg = $("upload-msg");
  msg.textContent = `Reading ${file.name}… this can take a minute.`;
  const form = new FormData();
  form.append("file", file);                   // field name "file" must match the backend parameter
  try {
    const res = await fetch("/api/documents/upload", { method: "POST", body: form });
    const data = await res.json();
    msg.textContent = res.ok
      ? `Added ${data.filename} (${data.chunks} chunks).`
      : `Could not add file: ${data.detail}`;
  } catch (e) {
    msg.textContent = "Upload failed. Is the server running?";
  }
  loadDocs();
  refreshHealth();
}

/** Fills the model dropdown with the models installed in Ollama. */
async function loadModels() {
  const select = $("model-select");
  const res = await fetch("/api/models");
  const data = await res.json();
  select.innerHTML = "";
  for (const name of data.installed) {
    const opt = document.createElement("option");
    opt.value = opt.textContent = name;
    opt.selected = name === data.active;
    select.appendChild(opt);
  }
  if (data.installed.length === 0) {
    select.innerHTML = "<option>No models installed</option>";
  }
  const hw = await (await fetch("/api/hardware")).json();
  $("hardware-tip").textContent = `${hw.gpu}. Suggested model: ${hw.recommended_model}`;
}

$("model-select").onchange = async (e) => {
  await fetch("/api/models/select", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ llm_model: e.target.value }),
  });
  refreshHealth();
};

$("file-input").onchange = (e) => {
  if (e.target.files[0]) uploadFile(e.target.files[0]);
  e.target.value = "";                         // allows choosing the same file again
};

// Mode buttons: highlight the clicked one and remember it.
document.querySelectorAll(".mode").forEach((btn) => {
  btn.onclick = () => {
    document.querySelectorAll(".mode").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    mode = btn.dataset.mode;
  };
});


// ---------- 3. CHAT ----------

/** Adds one message to the screen and returns its parts so we can update them. */
function addMessage(role) {
  const empty = $("empty");
  if (empty) empty.remove();                   // hide the welcome text after first message

  const wrap = document.createElement("div");
  wrap.className = "msg " + role;

  const state = document.createElement("div");   // "Searching…" line (bot only)
  state.className = "state";
  const bubble = document.createElement("div");
  bubble.className = "bubble";

  if (role === "bot") wrap.appendChild(state);
  wrap.appendChild(bubble);
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return { wrap, state, bubble };
}

/** Draws the list of sources (document pages or web links) under an answer. */
function showSources(wrap, sources) {
  const box = document.createElement("div");
  box.className = "sources";
  for (const s of sources) {
    const row = document.createElement("div");
    // IMPORTANT: only allow http(s) links - blocks "javascript:" tricks.
    if (s.type === "web" && /^https?:\/\//.test(s.url || "")) {
      const a = document.createElement("a");
      a.href = s.url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = s.title || s.url;
      row.appendChild(a);
    } else {
      row.textContent = `${s.title}  ·  match ${Math.round((s.score || 0) * 100)}%`;
    }
    box.appendChild(row);
  }
  wrap.appendChild(box);
}

/**
 * Sends the message and reads the streamed reply.
 *
 * HOW SSE READING WORKS
 *   The server sends text like  "event: token\ndata: {...}\n\n".
 *   Network chunks do not align with messages, so we keep a `buffer`,
 *   and cut out complete messages whenever we see a blank line ("\n\n").
 */
async function sendMessage(text) {
  text = text.trim();
  if (!text || busy) return;
  busy = true;
  sendBtn.disabled = true;

  addMessage("user").bubble.textContent = text;
  const bot = addMessage("bot");
  let answer = "";

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, mode: mode, history: history }),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let end;
      while ((end = buffer.indexOf("\n\n")) !== -1) {
        const raw = buffer.slice(0, end);        // one complete SSE message
        buffer = buffer.slice(end + 2);

        // Split "event: x" and "data: {...}" lines
        let event = "message", data = {};
        for (const line of raw.split("\n")) {
          if (line.startsWith("event: ")) event = line.slice(7);
          if (line.startsWith("data: "))  data = JSON.parse(line.slice(6));
        }

        if (event === "status")  bot.state.textContent = data.text;
        if (event === "sources") showSources(bot.wrap, data.sources);
        if (event === "token") {
          answer += data.text;
          bot.bubble.textContent = answer;
          messagesEl.scrollTop = messagesEl.scrollHeight;
        }
        if (event === "error") {
          bot.wrap.classList.add("error");
          bot.bubble.textContent = data.text;
        }
      }
    }
  } catch (e) {
    bot.wrap.classList.add("error");
    bot.bubble.textContent = "Could not reach the server. Check that it is running.";
  }

  bot.state.textContent = "";
  if (answer) {
    history.push({ role: "user", content: text }, { role: "assistant", content: answer });
    if ($("speak-toggle").checked) speak(answer);
  }
  busy = false;
  sendBtn.disabled = false;
  inputEl.focus();
}

sendBtn.onclick = () => { const t = inputEl.value; inputEl.value = ""; sendMessage(t); };

// Enter sends, Shift+Enter makes a new line.
inputEl.onkeydown = (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendBtn.click(); }
};


// ---------- 4. VOICE ----------

/** Asks the backend for MP3 speech and plays it. */
async function speak(text) {
  try {
    const res = await fetch("/api/voice/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text }),
    });
    if (!res.ok) return;                       // voice is optional: fail silently
    const blob = await res.blob();
    new Audio(URL.createObjectURL(blob)).play();
  } catch (e) { /* ignore */ }
}

let recorder = null;      // the MediaRecorder while recording, else null
let chunks = [];          // pieces of recorded audio

$("mic-btn").onclick = async () => {
  const btn = $("mic-btn");

  // Second click: stop recording (the "stop" handler below sends the audio).
  if (recorder) { recorder.stop(); return; }

  try {
    // IMPORTANT: the browser only allows the microphone on http://localhost or https.
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recorder = new MediaRecorder(stream);
    chunks = [];
    recorder.ondataavailable = (e) => chunks.push(e.data);
    recorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());     // release the microphone
      btn.classList.remove("recording");
      btn.textContent = "Mic";
      recorder = null;

      const form = new FormData();
      form.append("file", new Blob(chunks, { type: "audio/webm" }), "voice.webm");
      inputEl.placeholder = "Transcribing…";
      const res = await fetch("/api/voice/transcribe", { method: "POST", body: form });
      const data = await res.json();
      inputEl.placeholder = "Type a message…";
      if (res.ok && data.text) sendMessage(data.text);        // speak -> text -> answer
      else alert(data.detail || "Could not understand the audio.");
    };
    recorder.start();
    btn.classList.add("recording");
    btn.textContent = "Stop";
  } catch (e) {
    alert("Microphone not available: " + e.message);
  }
};


// ---------- 5. START-UP ----------
refreshHealth();
loadDocs();
loadModels();
setInterval(refreshHealth, 15000);     // re-check the connection every 15 seconds
