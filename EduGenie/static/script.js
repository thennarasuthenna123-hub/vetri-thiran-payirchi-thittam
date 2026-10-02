/* EduGenie frontend - plain JavaScript, no build step, no external libraries. */
(function () {
  "use strict";

  // ------------------------------------------------------------------
  // Task definitions: one entry per backend endpoint
  // ------------------------------------------------------------------
  const TASKS = {
    qa: {
      title: "Ask a question",
      help: "Ask anything from history to physics. You get a short, clear answer.",
      placeholder: "Which is the largest ocean?",
      button: "Get answer",
      label: "Answer",
      maxChars: 1000,
      request: (v) => fetch("/qa?question=" + encodeURIComponent(v)),
      render: (data, out) => out.append(markdown(data.answer)),
    },
    explain: {
      title: "Explain a concept",
      help: "Enter a topic and get a simple explanation written for beginners.",
      placeholder: "Photosynthesis",
      button: "Explain",
      label: "Explanation",
      maxChars: 500,
      request: (v) => postJSON("/explain", { topic: v }),
      render: (data, out) => {
        out.append(markdown(data.explanation));
        const meta = document.createElement("p");
        meta.className = "result-meta";
        meta.textContent =
          data.engine === "local" ? "Written by the local LaMini-Flan-T5 model." : "Written by Google Gemini.";
        out.append(meta);
      },
    },
    summarize: {
      title: "Summarize text",
      help: "Paste a long paragraph or article. You get a short summary with key points.",
      placeholder: "Paste the text you want to summarize...",
      button: "Summarize",
      label: "Summary",
      maxChars: 8000,
      request: (v) => postJSON("/summarize", { text: v }),
      render: (data, out) => out.append(markdown(data.summary)),
    },
    quiz: {
      title: "Take a quiz",
      help: "Enter a topic or paste a passage. You get 3 multiple-choice questions to test yourself.",
      placeholder: "The Pythagorean theorem",
      button: "Generate quiz",
      label: "Quiz",
      maxChars: 8000,
      request: (v) => postJSON("/quiz", { text: v }),
      render: (data, out) => renderQuiz(data.quiz, out),
    },
    path: {
      title: "Plan my learning",
      help: "Enter a subject and get a path from beginner to advanced, with timelines and resources.",
      placeholder: "SQL",
      button: "Create learning path",
      label: "Learning path",
      maxChars: 500,
      request: (v) => fetch("/learn/recommendations?topic=" + encodeURIComponent(v)),
      render: (data, out) => out.append(markdown(data.recommendation)),
    },
  };

  const $ = (id) => document.getElementById(id);
  const els = {
    form: $("input-form"),
    input: $("user-input"),
    button: $("submit-btn"),
    title: $("task-title"),
    help: $("task-help"),
    result: $("result"),
    count: $("char-count"),
    notice: $("setup-notice"),
    taskRadios: document.querySelectorAll('input[name="task"]'),
  };

  let currentTask = "qa";
  let requestId = 0; // ignore stale responses if the user switches tasks mid-request

  // ------------------------------------------------------------------
  // Helpers
  // ------------------------------------------------------------------
  function postJSON(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  // Inline Markdown on already-escaped text.
  function inline(s) {
    return s
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*\w])\*([^*\s][^*]*?)\*(?![*\w])/g, "$1<em>$2</em>")
      .replace(
        /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
        '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
      );
  }

  // Small, safe Markdown renderer (headings, bullet/numbered lists incl. nesting,
  // bold, italic, code, links). All text is HTML-escaped first, so model output
  // can never inject markup.
  function markdown(text) {
    const lines = String(text || "").replace(/\r/g, "").split("\n");
    let html = "";
    const stack = []; // open lists: {indent, tag}
    let para = [];

    const flushPara = () => {
      if (para.length) {
        html += "<p>" + inline(para.join(" ")) + "</p>";
        para = [];
      }
    };
    const closeTo = (indent) => {
      while (stack.length && stack[stack.length - 1].indent > indent) {
        html += "</li></" + stack.pop().tag + ">";
      }
    };

    for (const line of lines) {
      if (!line.trim()) {
        flushPara();
        continue;
      }
      const esc = escapeHtml(line);

      if (/^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
        flushPara(); closeTo(-1);
        html += "<hr>";
        continue;
      }

      let m = esc.match(/^\s{0,3}(#{1,4})\s+(.*)$/);
      if (m) {
        flushPara(); closeTo(-1);
        const level = Math.min(m[1].length + 2, 5); // h3-h5; page already has h1/h2
        html += `<h${level}>${inline(m[2].trim())}</h${level}>`;
        continue;
      }

      m = esc.match(/^(\s*)([*+-]|\d+\.)\s+(.*)$/);
      if (m) {
        flushPara();
        const indent = m[1].replace(/\t/g, "    ").length;
        const tag = /\d/.test(m[2]) ? "ol" : "ul";
        closeTo(indent);
        const top = stack[stack.length - 1];
        if (!top || top.indent < indent) {
          html += `<${tag}><li>${inline(m[3])}`;
          stack.push({ indent, tag });
        } else if (top.tag !== tag) {
          html += `</li></${top.tag}><${tag}><li>${inline(m[3])}`;
          top.tag = tag;
        } else {
          html += `</li><li>${inline(m[3])}`;
        }
        continue;
      }

      if (stack.length && /^\s+/.test(line)) {
        html += " " + inline(esc.trim()); // continuation of a list item
      } else {
        closeTo(-1);
        para.push(esc.trim());
      }
    }
    flushPara();
    closeTo(-1);

    const box = document.createElement("div");
    box.innerHTML = html; // safe: everything above was escaped
    return box;
  }

  // ------------------------------------------------------------------
  // Interactive quiz
  // ------------------------------------------------------------------
  function renderQuiz(quiz, out) {
    const total = quiz.length;
    let answered = 0;
    let correctCount = 0;

    const scoreBox = document.createElement("p");
    scoreBox.className = "quiz-score";
    scoreBox.hidden = true;

    quiz.forEach((q, qi) => {
      const field = document.createElement("fieldset");
      field.className = "quiz-question";

      const legend = document.createElement("legend");
      legend.textContent = `${qi + 1}. ${q.question}`;
      field.append(legend);

      const list = document.createElement("div");
      list.className = "quiz-options";
      const feedback = document.createElement("p");
      feedback.className = "quiz-feedback";
      feedback.setAttribute("role", "status");

      q.options.forEach((opt, oi) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "quiz-option";
        btn.textContent = `${String.fromCharCode(65 + oi)}. ${opt}`;
        btn.dataset.value = opt;

        btn.addEventListener("click", () => {
          const isRight = opt === q.answer;
          list.querySelectorAll("button").forEach((b) => {
            b.disabled = true;
            if (b.dataset.value === q.answer) b.classList.add("correct");
            else if (b === btn) b.classList.add("wrong");
            else b.classList.add("dim");
          });
          if (isRight) {
            feedback.textContent = "Correct!";
            feedback.className = "quiz-feedback good";
            correctCount++;
          } else {
            feedback.textContent = `Not quite. The correct answer is: ${q.answer}`;
            feedback.className = "quiz-feedback bad";
          }
          answered++;
          if (answered === total) {
            scoreBox.textContent = `You scored ${correctCount} out of ${total}.`;
            scoreBox.hidden = false;
          }
        });
        list.append(btn);
      });

      field.append(list, feedback);
      out.append(field);
    });

    out.append(scoreBox);
  }

  // ------------------------------------------------------------------
  // UI state
  // ------------------------------------------------------------------
  function updateCount() {
    const task = TASKS[currentTask];
    const len = els.input.value.length;
    els.count.textContent = `${len} / ${task.maxChars}`;
    els.count.classList.toggle("over", len > task.maxChars);
  }

  function selectTask(name) {
    currentTask = name;
    const t = TASKS[name];
    els.title.textContent = t.title;
    els.help.textContent = t.help;
    els.input.placeholder = t.placeholder;
    els.input.rows = name === "summarize" ? 8 : name === "quiz" ? 5 : 3;
    els.button.textContent = t.button;
    els.result.hidden = true;
    els.result.replaceChildren();
    requestId++; // discard any in-flight response for the previous task
    setBusy(false);
    updateCount();
  }

  function setBusy(busy) {
    els.button.disabled = busy;
    els.result.setAttribute("aria-busy", String(busy));
  }

  function showResult(kind, build) {
    els.result.hidden = false;
    els.result.className = "result" + (kind ? " is-" + kind : "");
    els.result.replaceChildren();
    build(els.result);
  }

  function showError(message) {
    showResult("error", (box) => {
      const p = document.createElement("p");
      p.textContent = message;
      box.append(p);
    });
  }

  async function submit(event) {
    event.preventDefault();
    const task = TASKS[currentTask];
    const value = els.input.value.trim();

    if (!value) {
      showError("Enter some text first, then press the button.");
      els.input.focus();
      return;
    }
    if (value.length > task.maxChars) {
      showError(`That is too long for this tool. Keep it under ${task.maxChars} characters.`);
      return;
    }

    const myId = ++requestId;
    setBusy(true);
    showResult("loading", (box) => {
      const span = document.createElement("span");
      span.className = "spinner";
      span.setAttribute("aria-hidden", "true");
      box.append(span, document.createTextNode("Working on it..."));
    });

    try {
      const response = await task.request(value);
      let data = {};
      try {
        data = await response.json();
      } catch (_) {
        /* non-JSON error body */
      }
      if (myId !== requestId) return; // user switched tasks; drop this response

      if (!response.ok) {
        showError(data.error || `Something went wrong (HTTP ${response.status}). Please try again.`);
        return;
      }
      showResult("", (box) => {
        const label = document.createElement("h3");
        label.className = "result-label";
        label.textContent = task.label;
        box.append(label);
        task.render(data, box);
      });
    } catch (err) {
      if (myId !== requestId) return;
      showError("Could not reach the EduGenie server. Make sure it is running, then try again.");
    } finally {
      if (myId === requestId) setBusy(false);
    }
  }

  async function checkHealth() {
    try {
      const res = await fetch("/health");
      const info = await res.json();
      if (!info.gemini_configured) {
        els.notice.hidden = false;
        els.notice.textContent = "";
        els.notice.append(
          document.createTextNode("Gemini API key missing: copy "),
          codeEl(".env.example"),
          document.createTextNode(" to "),
          codeEl(".env"),
          document.createTextNode(", set "),
          codeEl("GEMINI_API_KEY"),
          document.createTextNode(", then restart the server.")
        );
      }
    } catch (_) {
      /* server unreachable; the submit handler reports it */
    }
  }

  function codeEl(text) {
    const c = document.createElement("code");
    c.textContent = text;
    return c;
  }

  // ------------------------------------------------------------------
  // Wire up
  // ------------------------------------------------------------------
  els.taskRadios.forEach((r) => r.addEventListener("change", () => r.checked && selectTask(r.value)));
  els.form.addEventListener("submit", submit);
  els.input.addEventListener("input", updateCount);
  els.input.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" || e.shiftKey || e.isComposing) return;
    const shortTask = TASKS[currentTask].maxChars <= 1000; // question / topic style inputs
    if (shortTask || e.ctrlKey || e.metaKey) {
      e.preventDefault();
      els.form.requestSubmit();
    }
  });

  selectTask("qa");
  checkHealth();
})();
