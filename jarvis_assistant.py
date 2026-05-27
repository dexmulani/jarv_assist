import ast
import json
import operator
import os
import queue
import re
import subprocess
import threading
import time
import tkinter as tk
from collections import Counter
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from urllib import request, error


APP_CATALOG = {
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "paint": ["mspaint.exe"],
    "wordpad": ["write.exe"],
    "explorer": ["explorer.exe"],
    "task manager": ["taskmgr.exe"],
    "settings": ["start", "ms-settings:"],
    "control panel": ["control.exe"],
    "cmd": ["cmd.exe"],
    "powershell": ["powershell.exe"],
}

COLORS = {
    "bg": "#070b12",
    "panel": "#101822",
    "panel_alt": "#0c131c",
    "panel_edge": "#1d3342",
    "text": "#eef8ff",
    "muted": "#8da4b5",
    "cyan": "#36e6ff",
    "cyan_soft": "#123544",
    "green": "#74f2a9",
    "amber": "#ffcc66",
    "danger": "#ff6b7a",
    "entry": "#070d15",
}

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "he", "in", "is", "it", "its", "of", "on", "or", "that", "the", "this",
    "to", "was", "were", "will", "with", "you", "your", "i", "we", "they",
}

KNOWN_TOPICS = {
    "life": (
        "Life is the condition that separates living things from non-living matter. "
        "In simple terms, living things use energy, grow or repair themselves, respond "
        "to their environment, maintain internal balance, and can reproduce or pass on "
        "information. A human definition also includes experience, purpose, relationships, "
        "learning, and choice."
    ),
    "ai": (
        "Artificial intelligence is software that performs tasks that normally need human "
        "thinking, such as understanding language, recognizing patterns, making decisions, "
        "or generating text and images."
    ),
    "machine learning": (
        "Machine learning is a way to build AI by training a system on examples instead of "
        "writing every rule by hand. The system finds patterns and uses them to make predictions."
    ),
    "python": (
        "Python is a beginner-friendly programming language used for automation, AI, web apps, "
        "data analysis, scripting, and desktop tools like this assistant."
    ),
    "smartphone": (
        "A smartphone is a mobile phone that works like a small computer. It can make calls, "
        "send messages, connect to the internet, run apps, take photos and videos, use GPS, "
        "play media, and store personal data. In simple words, it is a pocket-sized device "
        "for communication, work, entertainment, navigation, and online services."
    ),
    "computer": (
        "A computer is an electronic machine that accepts input, processes data using instructions, "
        "stores information, and produces output. It is used for work, learning, communication, "
        "design, programming, gaming, and automation."
    ),
    "internet": (
        "The internet is a worldwide network of connected computers and servers. It lets people "
        "share information, open websites, send messages, stream media, use cloud services, and "
        "connect apps across the world."
    ),
    "laptop": (
        "A laptop is a portable computer with a built-in screen, keyboard, touchpad, battery, "
        "processor, memory, and storage. People use laptops for studying, office work, coding, "
        "video calls, entertainment, design, and browsing the internet."
    ),
    "coding": (
        "Coding means writing instructions that a computer can understand and run. It is used to "
        "build websites, apps, games, automation scripts, AI tools, and software systems."
    ),
    "education": (
        "Education is the process of learning knowledge, skills, values, and ways of thinking. "
        "It helps people understand the world, solve problems, communicate better, and create "
        "more opportunities in life and work."
    ),
}

MATH_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

AI_SYSTEM_PROMPT = (
    "You are JARVIS, a helpful desktop assistant. Answer naturally and clearly. "
    "You can help with explanations, planning, writing, coding, studying, and everyday questions. "
    "If a user asks for current facts, say when you are not sure instead of pretending. "
    "Keep answers useful, direct, and easy to understand."
)

CONFIG_PATH = Path(__file__).with_name("jarvis_config.json")


class LocalBrain:
    """Assistant brain with OpenAI-compatible, Ollama, and offline fallback modes."""

    def __init__(self):
        self.history = []
        self.last_topics = []
        self.provider_name = "Offline fallback"
        self.config = self._load_config()

    def reply(self, text):
        prompt = text.strip()
        if not prompt:
            return "I'm listening."

        external = self._try_openai_compatible(prompt)
        if external:
            self.provider_name = self._configured_provider_label()
            self.history.append((self.provider_name, prompt, external))
            return external

        ollama = self._try_ollama(prompt)
        if ollama:
            self.provider_name = "Ollama"
            self.history.append(("ollama", prompt, ollama))
            return ollama

        response = self._offline_reply(prompt)
        self.provider_name = "Offline fallback"
        self.history.append(("offline", prompt, response))
        return response

    def _offline_reply(self, prompt):
        lowered = prompt.lower()

        if any(phrase in lowered for phrase in ("are you using ollama", "connected to ollama", "using ollama")):
            return (
                f"Right now my active brain is: {self.provider_status()}. "
                "I can use an OpenAI-compatible API, Ollama, or the built-in offline fallback."
            )
        if re.search(r"\bhelp\b", lowered) or "what can you do" in lowered:
            return (
                "I can open Windows apps, summarize files, answer offline questions, make plans, "
                "solve basic math, explain common topics, turn notes into action steps, and use "
                "Ollama automatically whenever it is running."
            )
        if "time" in lowered:
            return time.strftime("It is %I:%M %p.")
        if "date" in lowered:
            return time.strftime("Today is %A, %B %d, %Y.")
        if any(word in lowered for word in ("calculate", "solve", "what is")):
            math_answer = self._try_math(prompt)
            if math_answer:
                return math_answer
        if "summarize" in lowered:
            pasted = self._extract_after_keyword(prompt, "summarize")
            if len(pasted.split()) > 10:
                return self._summarize_text(pasted)
            return "Choose a file in the File Summarizer panel, or paste text after the word summarize."
        if lowered.startswith(("open ", "launch ", "start ")):
            target = re.sub(r"^(open|launch|start)\s+", "", lowered).strip()
            return f"Use the Apps panel or command box to open {target}."
        if self._is_explain_question(lowered):
            return self._explain(prompt)
        if lowered.startswith(("why ", "why is ", "why are ", "why do ", "why does ")):
            return self._why_answer(prompt)
        if lowered.startswith(("how ", "how can ", "how does ", "how do ", "how to ")):
            return self._how_answer(prompt)
        if lowered.startswith(("who ", "where ", "when ")):
            return self._fact_limited_answer(prompt)
        if any(word in lowered for word in ("plan", "roadmap", "steps", "how do i", "how to")):
            return self._make_plan(prompt)
        if any(phrase in lowered for phrase in ("pros and cons", "advantages", "disadvantages", "compare")):
            return self._compare(prompt)
        if any(word in lowered for word in ("todo", "action", "checklist")):
            return self._action_list(prompt)
        if lowered in {"expand", "expand it", "tell me more", "more"} and self.last_topics:
            return self._expand_topics()

        topics = self._keywords(prompt)
        self.last_topics = topics
        if topics:
            return (
                "Offline analysis: the main ideas I see are "
                f"{', '.join(topics[:5])}. I can expand them, make a checklist, "
                "create a plan, or summarize pasted notes."
            )
        return "I can help reason through that. Give me one more detail and I will narrow it down."

    def _keywords(self, text):
        words = re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", text.lower())
        counts = Counter(w for w in words if w not in STOP_WORDS)
        return [word for word, _ in counts.most_common(8)]

    def _is_explain_question(self, lowered):
        patterns = (
            r"^\s*(define|explain)\b",
            r"^\s*(what is|what are|what does)\b",
            r"^\s*tell\s+(me\s+)?(what is|what are|about)\b",
            r"^\s*can you\s+(define|explain|tell me about)\b",
            r"\bmeaning of\b",
        )
        return any(re.search(pattern, lowered) for pattern in patterns)

    def _explain(self, prompt):
        lowered = prompt.lower()
        for topic, definition in KNOWN_TOPICS.items():
            if topic in lowered:
                return self._format_explanation(topic, definition)

        topic = self._clean_explain_topic(prompt)
        if not topic:
            topic = "that"
        return self._generic_definition(topic)

    def _format_explanation(self, topic, definition):
        return (
            f"{topic.title()}:\n"
            f"{definition}\n\n"
            "Simple example:\n"
            f"- If someone asks about {topic}, explain what it is, what it does, and why people use it.\n\n"
            "Key points:\n"
            f"- Meaning: the basic idea of {topic}.\n"
            "- Use: where it helps in real life.\n"
            "- Importance: why it matters."
        )

    def _generic_definition(self, topic):
        clean = topic.strip().strip("?.")
        return (
            f"{clean.title()}:\n"
            f"{clean.title()} is something I can explain in offline mode using a general structure, "
            "but I cannot verify live facts without a model or internet source.\n\n"
            "Simple explanation:\n"
            f"- It is the main thing, idea, person, place, or process named by '{clean}'.\n"
            "- To understand it, look at what it is, what it does, where it is used, and why it matters.\n\n"
            "Useful way to think about it:\n"
            f"- Definition: What is {clean}?\n"
            f"- Function: What does {clean} do?\n"
            f"- Example: Where would you see {clean} in real life?\n"
            f"- Importance: Why should someone care about {clean}?"
        )

    def _why_answer(self, prompt):
        topic = self._clean_topic(prompt)
        return (
            f"Why {topic} matters:\n"
            "- It usually affects a result, decision, behavior, or real-world outcome.\n"
            "- The main reason depends on context, so identify what changed and what it impacts.\n"
            "- A good answer should connect cause -> effect -> example.\n\n"
            f"In simple terms: {topic.title()} matters because it can change what people know, "
            "what they can do, and what choices they can make.\n\n"
            "Offline answer pattern:\n"
            f"1. Cause: what creates or drives {topic}.\n"
            "2. Effect: what happens because of it.\n"
            "3. Example: where you can see it in real life."
        )

    def _how_answer(self, prompt):
        topic = self._clean_topic(prompt)
        heading = topic if topic.startswith(("learn ", "build ", "make ", "create ", "use ")) else f"work with {topic}"
        return (
            f"How to {heading}:\n"
            "1. Identify the goal.\n"
            "2. Break it into small steps.\n"
            "3. Find the tools or information needed.\n"
            "4. Do the first step and check the result.\n"
            "5. Improve based on what happens.\n\n"
            "Give me the exact goal and I can turn it into a more specific checklist."
        )

    def _fact_limited_answer(self, prompt):
        topic = self._clean_topic(prompt)
        return (
            f"I can try to reason about {topic}, but offline mode cannot reliably verify people, places, "
            "dates, latest facts, news, or current events. For factual questions like who/where/when, "
            "use Ollama with a capable model or connect an internet/search source.\n\n"
            "What I can do now:\n"
            "- Explain the question structure.\n"
            "- Help you form a better query.\n"
            "- Turn known information you paste into a summary or answer."
        )

    def _make_plan(self, prompt):
        topic = self._clean_topic(prompt)
        return (
            f"Offline plan for {topic}:\n"
            "1. Define the exact goal in one sentence.\n"
            "2. List what you already have: files, tools, time, and blockers.\n"
            "3. Break the work into small tasks that can be finished in 20-40 minutes.\n"
            "4. Do the first useful task immediately, then test the result.\n"
            "5. Improve the weakest part, document what changed, and repeat.\n"
            "6. When it works, make a simple demo so you can prove it is real."
        )

    def _compare(self, prompt):
        topics = self._keywords(prompt)
        subject = ", ".join(topics[:3]) if topics else "this choice"
        return (
            f"Offline comparison for {subject}:\n"
            "Pros:\n"
            "- Faster to start when the requirements are clear.\n"
            "- Easier to test because the pieces are visible.\n"
            "- Can work without internet or cloud services.\n\n"
            "Cons:\n"
            "- Less flexible than a full AI model.\n"
            "- Needs hand-built rules for deeper understanding.\n"
            "- May miss nuance if the prompt is vague.\n\n"
            "Best move: use offline mode for commands, summaries, plans, and simple answers; use a model when you need deep reasoning."
        )

    def _action_list(self, prompt):
        topics = self._keywords(prompt)
        focus = ", ".join(topics[:4]) if topics else "your request"
        return (
            f"Action checklist for {focus}:\n"
            "- Decide the result you want.\n"
            "- Gather the required file, app, or information.\n"
            "- Run the smallest test that proves progress.\n"
            "- Fix the first visible problem.\n"
            "- Save the working version.\n"
            "- Write down the next improvement."
        )

    def _expand_topics(self):
        lines = ["Here is the expanded offline read:"]
        for topic in self.last_topics[:5]:
            lines.append(f"- {topic.title()}: likely an important part of the request; define it clearly and decide what action it needs.")
        return "\n".join(lines)

    def _summarize_text(self, text):
        sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text.strip()))
        if len(sentences) <= 3:
            return "Summary:\n- " + "\n- ".join(sentence for sentence in sentences if sentence)
        words = re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", text.lower())
        frequencies = Counter(w for w in words if w not in STOP_WORDS)
        scored = []
        for index, sentence in enumerate(sentences):
            sentence_words = re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", sentence.lower())
            score = sum(frequencies.get(word, 0) for word in sentence_words)
            scored.append((score, index, sentence))
        selected = sorted(sorted(scored, reverse=True)[:4], key=lambda item: item[1])
        return "Summary:\n" + "\n".join(f"- {sentence.strip()}" for _, _, sentence in selected)

    def _try_math(self, prompt):
        expression = prompt.lower()
        expression = expression.replace("calculate", "").replace("solve", "").replace("what is", "")
        expression = expression.replace("x", "*")
        expression = re.sub(r"[^0-9+\-*/().% ]", "", expression).strip()
        if not expression or not re.search(r"\d", expression):
            return ""
        try:
            value = self._safe_eval(expression)
        except (ValueError, ZeroDivisionError, SyntaxError):
            return ""
        return f"The answer is {value}."

    def _safe_eval(self, expression):
        tree = ast.parse(expression, mode="eval")
        return self._eval_node(tree.body)

    def _eval_node(self, node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in MATH_OPERATORS:
            return MATH_OPERATORS[type(node.op)](self._eval_node(node.left), self._eval_node(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in MATH_OPERATORS:
            return MATH_OPERATORS[type(node.op)](self._eval_node(node.operand))
        raise ValueError("Unsupported expression")

    def _extract_after_keyword(self, prompt, keyword):
        parts = re.split(keyword, prompt, maxsplit=1, flags=re.IGNORECASE)
        return parts[1].strip(" :.-") if len(parts) > 1 else ""

    def _clean_topic(self, prompt):
        text = prompt.lower()
        text = re.sub(r"^(make|create|build|give me|show me|tell me|tell|who is|where is|when is|how do i|how can i|how to|how does|why does|why do|why is|why are)\s+", "", text)
        text = re.sub(r"\bis important\b|\bimportant\b", "", text)
        text = re.sub(r"\b(plan|roadmap|steps|for|about|please)\b", " ", text)
        text = re.sub(r"^a\s+", "", text)
        text = re.sub(r"\s+", " ", text).strip(" ?.")
        return text or "this task"

    def _clean_explain_topic(self, prompt):
        text = prompt.lower().strip()
        replacements = (
            r"^can you\s+",
            r"^please\s+",
            r"^tell\s+me\s+what\s+is\s+",
            r"^tell\s+what\s+is\s+",
            r"^tell\s+me\s+about\s+",
            r"^tell\s+about\s+",
            r"^what\s+is\s+",
            r"^what\s+are\s+",
            r"^what\s+does\s+",
            r"^define\s+",
            r"^explain\s+",
            r"^the\s+meaning\s+of\s+",
            r"^meaning\s+of\s+",
        )
        for pattern in replacements:
            text = re.sub(pattern, "", text)
        text = re.sub(r"\bin simple words\b|\bsimply\b|\bplease\b", "", text)
        text = re.sub(r"\s+", " ", text).strip(" ?.")
        return text

    def _try_openai_compatible(self, prompt):
        self.config = self._load_config()
        api_key = (
            self.config.get("api_key")
            or os.getenv("JARVIS_AI_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )
        base_url = (
            self.config.get("base_url")
            or os.getenv("JARVIS_AI_BASE_URL")
            or "https://api.openai.com/v1"
        ).rstrip("/")
        model = (
            self.config.get("model")
            or os.getenv("JARVIS_AI_MODEL")
            or os.getenv("OPENAI_MODEL")
            or "gpt-4o-mini"
        )

        if not api_key and "api.openai.com" in base_url:
            return ""

        messages = [{"role": "system", "content": AI_SYSTEM_PROMPT}]
        for provider, old_prompt, old_reply in self.history[-5:]:
            if provider in {"offline", "Offline fallback"}:
                continue
            messages.append({"role": "user", "content": old_prompt})
            messages.append({"role": "assistant", "content": old_reply})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.5,
            "max_tokens": 700,
        }
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        req = request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=25) as response:
                body = json.loads(response.read().decode("utf-8"))
                choices = body.get("choices", [])
                if not choices:
                    return ""
                return choices[0].get("message", {}).get("content", "").strip()
        except (error.URLError, TimeoutError, json.JSONDecodeError, OSError, KeyError):
            return ""

    def _configured_provider_label(self):
        self.config = self._load_config()
        base_url = (
            self.config.get("base_url")
            or os.getenv("JARVIS_AI_BASE_URL")
            or "https://api.openai.com/v1"
        ).lower()
        if "api.openai.com" in base_url:
            return "OpenAI API"
        if "127.0.0.1" in base_url or "localhost" in base_url:
            return "Local API brain"
        return "Custom AI API"

    def _try_ollama(self, prompt):
        payload = {
            "model": "llama3.2",
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.4},
        }
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=8) as response:
                body = json.loads(response.read().decode("utf-8"))
                return body.get("response", "").strip()
        except (error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            return ""

    def ollama_available(self):
        req = request.Request("http://127.0.0.1:11434/api/tags", method="GET")
        try:
            with request.urlopen(req, timeout=2) as response:
                return response.status == 200
        except (error.URLError, TimeoutError, OSError):
            return False

    def openai_compatible_configured(self):
        self.config = self._load_config()
        api_key = (
            self.config.get("api_key")
            or os.getenv("JARVIS_AI_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )
        base_url = (
            self.config.get("base_url")
            or os.getenv("JARVIS_AI_BASE_URL")
            or "https://api.openai.com/v1"
        ).lower()
        return bool(api_key) or "api.openai.com" not in base_url

    def provider_status(self):
        if self.openai_compatible_configured():
            return self._configured_provider_label()
        if self.ollama_available():
            return "Ollama connected"
        return "Offline fallback"

    def _load_config(self):
        if not CONFIG_PATH.exists():
            return {}
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}


class FileSummarizer:
    def summarize(self, path):
        file_path = Path(path)
        text = self._read_text(file_path)
        if not text.strip():
            return "I could not find readable text in that file."

        sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text.strip()))
        if len(sentences) <= 3:
            return text.strip()

        words = re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", text.lower())
        frequencies = Counter(w for w in words if w not in STOP_WORDS)
        scored = []
        for index, sentence in enumerate(sentences):
            sentence_words = re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", sentence.lower())
            score = sum(frequencies.get(word, 0) for word in sentence_words)
            scored.append((score, index, sentence))

        selected = sorted(scored, reverse=True)[:5]
        selected = sorted(selected, key=lambda item: item[1])
        bullets = [f"- {sentence.strip()}" for _, _, sentence in selected if sentence.strip()]
        stats = f"{len(words):,} words across {len(sentences):,} sentences"
        return f"Summary of {file_path.name} ({stats}):\n\n" + "\n".join(bullets)

    def _read_text(self, file_path):
        suffix = file_path.suffix.lower()
        if suffix in {".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".csv", ".log"}:
            return file_path.read_text(encoding="utf-8", errors="ignore")
        if suffix == ".docx":
            return self._read_docx(file_path)
        return file_path.read_text(encoding="utf-8", errors="ignore")

    def _read_docx(self, file_path):
        import zipfile
        from xml.etree import ElementTree

        with zipfile.ZipFile(file_path) as archive:
            xml = archive.read("word/document.xml")
        root = ElementTree.fromstring(xml)
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        return "\n".join(node.text or "" for node in root.findall(".//w:t", namespace))


class VoiceInput:
    def __init__(self, callback, status_callback):
        self.callback = callback
        self.status_callback = status_callback
        self.listening = False
        self.thread = None

    def toggle(self):
        if self.listening:
            self.listening = False
            self.status_callback("Voice stopped.")
            return
        self.listening = True
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()

    def _listen_loop(self):
        try:
            import speech_recognition as sr
        except ImportError:
            self.listening = False
            self.status_callback("Install SpeechRecognition and PyAudio to enable voice input.")
            return

        recognizer = sr.Recognizer()
        try:
            microphone = sr.Microphone()
        except OSError:
            self.listening = False
            self.status_callback("No microphone was found.")
            return

        self.status_callback("Voice listening...")
        with microphone as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)

        while self.listening:
            try:
                with microphone as source:
                    audio = recognizer.listen(source, timeout=4, phrase_time_limit=7)
                text = recognizer.recognize_google(audio)
                self.callback(text)
            except sr.WaitTimeoutError:
                continue
            except sr.UnknownValueError:
                self.status_callback("I heard something, but could not parse it.")
            except Exception as exc:
                self.status_callback(f"Voice error: {exc}")
                self.listening = False


class JarvisApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("JARVIS Desktop Assistant")
        self.geometry("1240x760")
        self.minsize(1040, 680)
        self.configure(bg=COLORS["bg"])

        self.brain = LocalBrain()
        self.summarizer = FileSummarizer()
        self.voice_queue = queue.Queue()
        self.voice = VoiceInput(self.voice_queue.put, self.set_status_threadsafe)

        self.status_var = tk.StringVar(value="Ready.")
        self.ai_status_var = tk.StringVar(value="Checking Ollama...")
        self.command_var = tk.StringVar()
        self.app_var = tk.StringVar(value="notepad")

        self._build_styles()
        self._build_layout()
        self._refresh_ai_status()
        self.after(250, self._drain_voice_queue)

    def _build_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Panel.TFrame", background=COLORS["panel"], relief="flat")
        style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"])
        style.configure("Panel.TLabel", background=COLORS["panel"], foreground=COLORS["text"])
        style.configure("Muted.TLabel", background=COLORS["panel"], foreground=COLORS["muted"])
        style.configure("TButton", padding=(14, 9), font=("Segoe UI", 10), borderwidth=0)
        style.map("TButton", background=[("active", COLORS["cyan_soft"])])
        style.configure(
            "Accent.TButton",
            background=COLORS["cyan"],
            foreground="#031017",
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Accent.TButton", background=[("active", "#7df2ff")])
        style.configure("Ghost.TButton", background=COLORS["panel_alt"], foreground=COLORS["text"])
        style.configure(
            "TCombobox",
            fieldbackground=COLORS["entry"],
            background=COLORS["panel_alt"],
            foreground=COLORS["text"],
            arrowcolor=COLORS["cyan"],
            padding=8,
        )

    def _build_layout(self):
        root = ttk.Frame(self, padding=20)
        root.pack(fill="both", expand=True)

        header = tk.Frame(root, bg=COLORS["bg"], height=86)
        header.pack(fill="x", pady=(0, 18))
        header.pack_propagate(False)

        title_block = tk.Frame(header, bg=COLORS["bg"])
        title_block.pack(side="left", fill="y")
        tk.Label(
            title_block,
            text="JARVIS",
            bg=COLORS["bg"],
            fg=COLORS["cyan"],
            font=("Segoe UI", 34, "bold"),
        ).pack(anchor="w")
        tk.Label(
            title_block,
            text="Desktop command center",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=("Segoe UI", 11),
        ).pack(anchor="w")

        telemetry = tk.Frame(header, bg=COLORS["bg"])
        telemetry.pack(side="right", anchor="e")
        self._status_pill(telemetry, "SYSTEM", self.status_var, COLORS["green"]).pack(anchor="e", pady=(4, 8))
        self._status_pill(telemetry, "AI CORE", self.ai_status_var, COLORS["cyan"]).pack(anchor="e")

        body = ttk.Frame(root)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=0, minsize=250)
        body.columnconfigure(1, weight=3)
        body.columnconfigure(2, weight=2)
        body.rowconfigure(0, weight=1)

        sidebar = self._panel(body, padding=16)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        sidebar.columnconfigure(0, weight=1)
        self._panel_title(sidebar, "Quick Control", "Common commands").grid(row=0, column=0, sticky="ew")

        quick_actions = [
            ("Open Notepad", "open notepad"),
            ("Open Calculator", "open calculator"),
            ("Current Time", "what time is it?"),
            ("Offline Powers", "what can you do?"),
        ]
        for index, (label, command) in enumerate(quick_actions, start=1):
            tk.Button(
                sidebar,
                text=label,
                command=lambda value=command: self.quick_command(value),
                bg=COLORS["panel_alt"],
                fg=COLORS["text"],
                activebackground=COLORS["cyan_soft"],
                activeforeground=COLORS["text"],
                relief="flat",
                bd=0,
                padx=12,
                pady=12,
                anchor="w",
                font=("Segoe UI", 10, "bold"),
            ).grid(row=index, column=0, sticky="ew", pady=(0, 9))

        tips = tk.Frame(sidebar, bg=COLORS["panel_alt"], padx=12, pady=12)
        tips.grid(row=6, column=0, sticky="ew", pady=(18, 0))
        tk.Label(
            tips,
            text="Try typing:",
            bg=COLORS["panel_alt"],
            fg=COLORS["cyan"],
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")
        for text in ("open paint", "define life simply", "make a plan for Python"):
            tk.Label(
                tips,
                text=f">> {text}",
                bg=COLORS["panel_alt"],
                fg=COLORS["muted"],
                font=("Consolas", 9),
            ).pack(anchor="w", pady=(5, 0))

        chat_panel = self._panel(body, padding=16)
        chat_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 14))
        chat_panel.rowconfigure(1, weight=1)
        chat_panel.columnconfigure(0, weight=1)

        self._panel_title(chat_panel, "Local AI Chat", "Works offline, upgrades itself when Ollama is running").grid(
            row=0, column=0, columnspan=4, sticky="ew", pady=(0, 12)
        )
        self.chat_log = scrolledtext.ScrolledText(
            chat_panel,
            wrap=tk.WORD,
            bg=COLORS["entry"],
            fg=COLORS["text"],
            insertbackground=COLORS["cyan"],
            relief="flat",
            font=("Consolas", 10),
            padx=14,
            pady=12,
        )
        self.chat_log.grid(row=1, column=0, columnspan=4, sticky="nsew")
        self.chat_log.tag_configure("jarvis", foreground=COLORS["cyan"])
        self.chat_log.tag_configure("user", foreground=COLORS["green"])
        self.chat_log.insert(
            "end",
            "JARVIS: Systems online. I can answer offline, and I will use Ollama automatically if it is running.\n\n",
            "jarvis",
        )
        self.chat_log.configure(state="disabled")

        input_bar = tk.Frame(chat_panel, bg=COLORS["panel"], pady=2)
        input_bar.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(13, 0))
        input_bar.columnconfigure(0, weight=1)

        entry = tk.Entry(
            input_bar,
            textvariable=self.command_var,
            font=("Segoe UI", 12),
            bg=COLORS["entry"],
            fg=COLORS["text"],
            insertbackground=COLORS["cyan"],
            relief="flat",
            bd=0,
        )
        entry.grid(row=0, column=0, sticky="ew", ipady=11, padx=(0, 8))
        entry.bind("<Return>", lambda _event: self.handle_command())
        entry.focus_set()
        ttk.Button(input_bar, text="Send", style="Accent.TButton", command=self.handle_command).grid(
            row=0, column=1, padx=(0, 8)
        )
        ttk.Button(input_bar, text="Voice", style="Ghost.TButton", command=self.toggle_voice).grid(row=0, column=2)

        tools = ttk.Frame(body)
        tools.grid(row=0, column=2, sticky="nsew")
        tools.rowconfigure(1, weight=1)
        tools.columnconfigure(0, weight=1)

        apps = self._panel(tools, padding=16)
        apps.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        apps.columnconfigure(0, weight=1)
        self._panel_title(apps, "App Launcher", "Select and launch Windows tools").grid(
            row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12)
        )
        app_picker = ttk.Combobox(apps, textvariable=self.app_var, values=sorted(APP_CATALOG), state="readonly")
        app_picker.grid(row=1, column=0, sticky="ew", padx=(0, 8), ipady=3)
        ttk.Button(apps, text="Launch", style="Accent.TButton", command=lambda: self.open_app(self.app_var.get())).grid(
            row=1, column=1, sticky="e"
        )

        files = self._panel(tools, padding=16)
        files.grid(row=1, column=0, sticky="nsew")
        files.rowconfigure(2, weight=1)
        files.columnconfigure(0, weight=1)
        self._panel_title(files, "File Summarizer", "Choose a document and get key points").grid(
            row=0, column=0, sticky="ew", pady=(0, 10)
        )
        self.summary_box = scrolledtext.ScrolledText(
            files,
            wrap=tk.WORD,
            height=12,
            bg=COLORS["entry"],
            fg=COLORS["text"],
            insertbackground=COLORS["cyan"],
            relief="flat",
            font=("Segoe UI", 10),
            padx=12,
            pady=12,
        )
        self.summary_box.grid(row=2, column=0, columnspan=2, sticky="nsew")
        self.summary_box.insert("end", "Choose a file to generate a concise summary here.")
        ttk.Button(files, text="Choose File", style="Accent.TButton", command=self.choose_file).grid(
            row=3, column=0, sticky="ew", pady=(12, 0)
        )

    def _panel(self, parent, padding):
        return tk.Frame(parent, bg=COLORS["panel"], padx=padding, pady=padding)

    def _panel_title(self, parent, title, subtitle):
        frame = tk.Frame(parent, bg=COLORS["panel"])
        tk.Label(
            frame,
            text=title,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w")
        tk.Label(
            frame,
            text=subtitle,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(1, 0))
        return frame

    def _status_pill(self, parent, label, variable, color):
        frame = tk.Frame(parent, bg=COLORS["panel_edge"], padx=1, pady=1)
        inner = tk.Frame(frame, bg=COLORS["panel_alt"], padx=12, pady=6)
        inner.pack()
        tk.Label(
            inner,
            text=label,
            bg=COLORS["panel_alt"],
            fg=color,
            font=("Segoe UI", 8, "bold"),
        ).pack(side="left", padx=(0, 8))
        tk.Label(
            inner,
            textvariable=variable,
            bg=COLORS["panel_alt"],
            fg=COLORS["text"],
            font=("Segoe UI", 9),
        ).pack(side="left")
        return frame

    def handle_command(self, forced_text=None):
        text = (forced_text or self.command_var.get()).strip()
        if not text:
            return
        self.command_var.set("")
        self._append_chat(f"You: {text}")

        app_match = re.match(r"^(open|launch|start)\s+(.+)$", text.lower())
        if app_match:
            response = self.open_app(app_match.group(2), from_chat=True)
        else:
            response = self.brain.reply(text)
        self._append_chat(f"JARVIS: {response}\n", "jarvis")

    def quick_command(self, text):
        self.command_var.set(text)
        self.handle_command()

    def toggle_voice(self):
        self.voice.toggle()

    def open_app(self, name, from_chat=False):
        normalized = name.strip().lower()
        command = APP_CATALOG.get(normalized)
        if not command:
            for app_name, app_command in APP_CATALOG.items():
                if normalized in app_name or app_name in normalized:
                    command = app_command
                    normalized = app_name
                    break
        if not command:
            return f"I do not have an app shortcut for '{name}' yet."

        try:
            if command[0] == "start":
                subprocess.Popen(command, shell=True)
            else:
                subprocess.Popen(command)
            self.set_status(f"Opened {normalized}.")
            return f"Opening {normalized}."
        except OSError as exc:
            self.set_status(f"Could not open {normalized}.")
            return f"I could not open {normalized}: {exc}"

    def choose_file(self):
        path = filedialog.askopenfilename(
            title="Choose a file to summarize",
            filetypes=[
                ("Readable files", "*.txt *.md *.py *.js *.ts *.tsx *.jsx *.json *.csv *.log *.docx"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        self.set_status("Summarizing file...")
        try:
            summary = self.summarizer.summarize(path)
        except Exception as exc:
            messagebox.showerror("Summarizer", f"Could not summarize this file:\n{exc}")
            self.set_status("Summary failed.")
            return
        self.summary_box.delete("1.0", "end")
        self.summary_box.insert("end", summary)
        self.set_status("Summary ready.")

    def _append_chat(self, line, tag=None):
        self.chat_log.configure(state="normal")
        if line.startswith("You:"):
            tag = "user"
        self.chat_log.insert("end", line + "\n", tag)
        self.chat_log.see("end")
        self.chat_log.configure(state="disabled")

    def _refresh_ai_status(self):
        def check():
            text = self.brain.provider_status()
            self.after(0, lambda: self.ai_status_var.set(text))
            self.after(15000, self._refresh_ai_status)

        threading.Thread(target=check, daemon=True).start()

    def _drain_voice_queue(self):
        while not self.voice_queue.empty():
            self.handle_command(self.voice_queue.get_nowait())
        self.after(250, self._drain_voice_queue)

    def set_status(self, text):
        self.status_var.set(text)

    def set_status_threadsafe(self, text):
        self.after(0, lambda: self.set_status(text))


if __name__ == "__main__":
    app = JarvisApp()
    app.mainloop()
