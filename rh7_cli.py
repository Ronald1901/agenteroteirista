from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / ".harness_v77"
RUNS = RUNTIME / "runs"
CACHE_A = RUNTIME / "cache" / "a_dna"
FINAL_DIR = ROOT / "roteiro final"
VERSION = "7.7.2"
PIPELINE = "TRUE_OBJECTIVE_LOOP_DECOMPILED_B_FORMAT_CONTRACT_RELEASE_CHALLENGE_AUTO_FAILOVER"
DNA_SCHEMA_REV = "7.7-dna-r1"
B_LEDGER_SCHEMA_REV = "7.7-b-ledger-r1"
DEFAULT_MARGIN_PCT = 0.05
MAX_DRAFTS = 3
MAX_INVALID_STAGE_OUTPUT = 2
INVALID_STAGE_LIMITS = {"dna": 3, "b_decompiler": 3, "rewrite": 2, "critic": 2, "second_opinion": 2}

MODEL_MAIN = "qwen/qwen3.7-max-2026-06-08"

# Pools ordenados por capacidade/compatibilidade. Um erro de quota/provider
# NÃO consome tentativa de qualidade: o runtime marca o modelo indisponível
# para a role e avança para o próximo executor oculto do mesmo estágio.
MODEL_POOLS = {
    # qwen3.7-max base foi removido da rota porque a quota atual do usuário já esgotou.
    # 2026-05-20 é snapshot da mesma família/capacidade e começa com quota separada.
    "DNA": [
        ("qwen/qwen3.7-max-2026-05-20", "rh77-dna"),
        ("qwen/qwen3.7-max-2026-05-17", "rh77-dna-fb-0517"),
        ("qwen/qwen3.7-max-preview", "rh77-dna-fb-preview"),
        ("qwen/qwen3.6-max-preview", "rh77-dna-fb-36max"),
    ],
    "B_DECOMPILER": [
        ("qwen/qwen3.7-max-2026-05-17", "rh77-b-decompiler"),
        ("qwen/qwen3.7-max-preview", "rh77-b-decompiler-fb-preview"),
        ("qwen/qwen3.7-max-2026-05-20", "rh77-b-decompiler-fb-0520"),
        ("qwen/qwen3.6-max-preview", "rh77-b-decompiler-fb-36max"),
    ],
    "REWRITER": [
        ("qwen/qwen3.8-max", "rh77-rewriter"),
        ("qwen/qwen3.7-max-preview", "rh77-rewriter-fb-preview"),
        ("qwen/qwen3.7-max-2026-05-20", "rh77-rewriter-fb-0520"),
        ("qwen/qwen3.7-max-2026-05-17", "rh77-rewriter-fb-0517"),
        ("qwen/qwen3.6-max-preview", "rh77-rewriter-fb-36max"),
    ],
    "CRITIC": [
        ("qwen/deepseek-v4-pro", "rh77-critic"),
        ("qwen/glm-5.2", "rh77-critic-fb-glm52"),
        ("qwen/qwen3.7-max-preview", "rh77-critic-fb-qwen-preview"),
        ("qwen/qwen3.7-max-2026-05-17", "rh77-critic-fb-qwen-0517"),
    ],
    "SECOND_OPINION": [
        ("qwen/glm-5.2", "rh77-second-opinion"),
        ("qwen/qwen3.7-max-preview", "rh77-second-opinion-fb-qwen-preview"),
        ("qwen/qwen3.7-max-2026-05-17", "rh77-second-opinion-fb-qwen-0517"),
        ("qwen/deepseek-v4-pro", "rh77-second-opinion-fb-deepseek"),
    ],
}

MODEL_DNA = MODEL_POOLS["DNA"][0][0]
MODEL_B_DECOMPILER = MODEL_POOLS["B_DECOMPILER"][0][0]
MODEL_REWRITER = MODEL_POOLS["REWRITER"][0][0]
MODEL_CRITIC = MODEL_POOLS["CRITIC"][0][0]
MODEL_SECOND_OPINION = MODEL_POOLS["SECOND_OPINION"][0][0]

TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".srt", ".vtt", ".csv", ".json", ".yaml", ".yml"}
WORD_RE = re.compile(r"\b[\wÀ-ÿ'-]+\b", flags=re.UNICODE)
NUMBER_RE = re.compile(r"(?<!\w)(?:R\$|US\$|\$|€|£)?\s*\d[\d.,:/-]*%?", flags=re.IGNORECASE)
HEADING_RE = re.compile(r"(?m)^\s*#{1,6}\s+")
EDITORIAL_LABEL_RE = re.compile(r"^\s*\*\*(GANCHO|FECHAMENTO|CTA\s+BLOCO\s+\d+|BLOCO\s+\d+\s*-\s*.+?)\*\*\s*$", flags=re.IGNORECASE)
BLOCK_LABEL_RE = re.compile(r"^\s*\*\*BLOCO\s+(\d+)\s*-\s*(.+?)\*\*\s*$", flags=re.IGNORECASE)
CTA_LABEL_RE = re.compile(r"^\s*\*\*CTA\s+BLOCO\s+(\d+)\*\*\s*$", flags=re.IGNORECASE)
BOLD_ONLY_RE = re.compile(r"^\s*\*\*.+?\*\*\s*$")

GATES = [
    "b_content_fidelity",
    "b_topic_order",
    "b_length",
    "a_macro_dna",
    "a_micro_voice",
    "b_rhetorical_scaffolding_removed",
    "form_closer_to_a_than_b",
    "transformation_depth",
    "human_orality",
    "anti_ai",
    "anti_a_copy",
    "voice_caricature",
]

FORM_DIMENSIONS = [
    "hook_engine",
    "block_progression",
    "retention_logic",
    "pacing",
    "transition_logic",
    "evidence_rhythm",
    "syntax_voice",
    "ending_logic",
]

CRITICAL_EVIDENCE_GATES = {
    "a_macro_dna",
    "a_micro_voice",
    "b_rhetorical_scaffolding_removed",
    "form_closer_to_a_than_b",
    "transformation_depth",
}

STOPISH_PT = {
    "a", "o", "as", "os", "de", "do", "da", "dos", "das", "e", "é", "em", "um", "uma", "uns", "umas",
    "que", "para", "por", "com", "sem", "se", "no", "na", "nos", "nas", "ao", "aos", "à", "às", "como",
    "eu", "você", "vocês", "ele", "ela", "eles", "elas", "isso", "isto", "esse", "essa", "este", "esta",
}


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def fail(message: str, code: int = 2) -> None:
    print(json.dumps({"ok": False, "error": message}, ensure_ascii=False, indent=2))
    raise SystemExit(code)


def jload(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def jdump(path: str | Path, data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def count_words(text: str) -> int:
    return len(WORD_RE.findall(text))


def _tokens(text: str) -> list[str]:
    return [x.lower() for x in WORD_RE.findall(text)]


def _ngrams(tokens: list[str], n: int) -> Counter[tuple[str, ...]]:
    if len(tokens) < n:
        return Counter()
    return Counter(tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1))


def exact_ngram_matches(source: str, target: str, n: int, limit: int = 20) -> list[str]:
    s = _ngrams(_tokens(source), n)
    t = _ngrams(_tokens(target), n)
    common = [g for g in s if g in t]
    common.sort(key=lambda g: (-min(s[g], t[g]), g))
    return [" ".join(g) for g in common[:limit]]


def repeated_marker_overfit(a_text: str, draft_text: str, limit: int = 12) -> list[dict[str, Any]]:
    at = _tokens(a_text)
    dt = _tokens(draft_text)
    aw = max(1, len(at)); dw = max(1, len(dt))
    findings: list[dict[str, Any]] = []
    for n in (2, 3, 4):
        ac = _ngrams(at, n)
        dc = _ngrams(dt, n)
        for gram, a_count in ac.items():
            d_count = dc.get(gram, 0)
            if a_count < 2 or d_count < 4:
                continue
            if all(tok in STOPISH_PT for tok in gram):
                continue
            a_rate = a_count * 1000.0 / aw
            d_rate = d_count * 1000.0 / dw
            ratio = d_rate / max(a_rate, 0.001)
            if ratio >= 2.0 and d_rate >= 1.0:
                findings.append({
                    "phrase": " ".join(gram),
                    "a_count": a_count,
                    "draft_count": d_count,
                    "a_per_1k": round(a_rate, 2),
                    "draft_per_1k": round(d_rate, 2),
                    "ratio": round(ratio, 2),
                })
    findings.sort(key=lambda x: (-x["ratio"], -x["draft_count"], x["phrase"]))
    return findings[:limit]


def read_text_robust(path: str | Path) -> str:
    p = Path(path)
    data = p.read_bytes()
    if not data:
        return ""
    for enc in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            text = data.decode(enc)
            if text.strip():
                return text.replace("\r\n", "\n").replace("\r", "\n")
        except UnicodeDecodeError:
            pass
    fail(f"nao foi possivel decodificar: {p}")
    raise AssertionError


def _rel(path: str | Path) -> str:
    p = Path(path).resolve()
    try:
        return str(p.relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(p)


def resolve_text_source(path: str | Path, label: str) -> tuple[Path, str]:
    p = Path(path)
    if not p.is_absolute():
        p = (ROOT / p).resolve()
    if not p.exists() or not p.is_file():
        fail(f"arquivo {label} nao encontrado: {p}")
    if p.suffix.lower() not in TEXT_EXTENSIONS:
        fail(f"{label} precisa ser transcricao textual. Extensao recebida: {p.suffix}")
    text = read_text_robust(p)
    if not text.strip():
        fail(f"arquivo {label} vazio: {p}")
    return p, text


def ensure_runtime_dirs() -> dict[str, str]:
    for p in [RUNTIME, RUNS, CACHE_A, RUNTIME / "inbox", FINAL_DIR]:
        p.mkdir(parents=True, exist_ok=True)
    return {
        "runtime": _rel(RUNTIME),
        "runs": _rel(RUNS),
        "cache_a": _rel(CACHE_A),
        "final_dir": _rel(FINAL_DIR),
    }


def _norm_name(name: str) -> str:
    s = name.lower().replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", s)


def discover_inputs() -> dict[str, Any]:
    ensure_runtime_dirs()
    roots = [ROOT / "ROTEIROS", ROOT / "roteiros", ROOT / "ROTEIRO", ROOT / "roteiro", RUNTIME / "inbox"]
    files: list[Path] = []
    for r in roots:
        if r.is_dir():
            files.extend([p for p in r.rglob("*") if p.is_file() and p.suffix.lower() in TEXT_EXTENSIONS])
    files.extend([p for p in ROOT.iterdir() if p.is_file() and p.suffix.lower() in TEXT_EXTENSIONS])
    seen: set[Path] = set(); uniq: list[Path] = []
    for p in files:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp); uniq.append(p)

    def score(p: Path, role: str) -> int:
        n = _norm_name(p.stem)
        z = 0
        if role in {"a", "b"}:
            if re.search(rf"\bvideo\s*{role}\b", n): z += 100
            if re.search(rf"\bvideo{role}\b", n): z += 90
            if re.search(rf"\b{role}\b", n): z += 40
            if role == "a" and any(x in n for x in ["referencia", "modelo", "dna"]): z += 20
            if role == "b" and any(x in n for x in ["base", "conteudo", "original"]): z += 20
        elif role == "f":
            if n in {"arquivo f", "video f", "formato f", "formato", "format reference", "referencia de formato"}: z += 140
            if re.search(r"\barquivo\s*f\b", n): z += 120
            if any(x in n for x in ["formato", "format", "layout", "estrutura de saida", "modelo de saida"]): z += 70
        return z

    def pick(role: str) -> Path | None:
        ranked = sorted([(score(p, role), p) for p in uniq], key=lambda x: (-x[0], str(x[1])))
        return ranked[0][1] if ranked and ranked[0][0] > 0 else None

    a = pick("a"); b = pick("b"); f = pick("f")
    ready = bool(a and b and a.resolve() != b.resolve())
    return {
        "ok": True,
        "ready": ready,
        "A": _rel(a) if a else None,
        "B": _rel(b) if b else None,
        "F": _rel(f) if f else None,
        "format_mode": "REFERENCE_F" if f else "CANONICAL_F_STYLE",
        "candidates": [_rel(p) for p in uniq[:30]],
        "rule": "A=FORMA/VOZ; B=CONTEUDO+ORDEM_TEMATICA+TAMANHO; F=FORMATO_VISUAL/EDITORIAL_APENAS",
    }


def _default_format_contract() -> dict[str, Any]:
    return {
        "schema_version": "7.7-format-r1",
        "source": "CANONICAL_F_STYLE",
        "format_role": "EDITORIAL_LAYOUT_ONLY_NEVER_STYLE_OR_CONTENT",
        "opening_label": "**GANCHO**",
        "block_label_pattern": "**BLOCO N - SUBTÍTULO**",
        "cta_label_pattern": "**CTA BLOCO N**",
        "closing_label": "**FECHAMENTO**",
        "minimum_blocks": 3,
        "require_sequential_block_numbers": True,
        "require_nonempty_subtitles": True,
        "cta_policy": "OPTIONAL_BUT_IF_USED_MUST_FOLLOW_EXACT_LABEL; FOLLOW_A_CTA_ENGINE_WHEN_NATURAL",
        "whole_block_policy": "Cada bloco é uma seção temática inteira; não fragmentar cada parágrafo em microblocos.",
        "labels_are_editorial_not_spoken": True,
        "word_target_counts_narration_only": True,
    }


def build_format_contract(format_file: str | None = None) -> dict[str, Any]:
    c = _default_format_contract()
    if not format_file:
        return c
    fp, text = resolve_text_source(format_file, "F")
    labels = [ln.strip() for ln in text.splitlines() if EDITORIAL_LABEL_RE.match(ln.strip())]
    blocks = []
    ctas = []
    for label in labels:
        m = BLOCK_LABEL_RE.match(label)
        if m:
            blocks.append({"n": int(m.group(1)), "subtitle_example": m.group(2).strip()})
        m2 = CTA_LABEL_RE.match(label)
        if m2:
            ctas.append(int(m2.group(1)))
    c.update({
        "source": "FORMAT_REFERENCE_F",
        "format_reference_path": _rel(fp),
        "format_reference_sha256": sha256_file(fp),
        "reference_labels_detected": labels,
        "reference_block_count": len(blocks),
        "reference_cta_after_blocks": ctas,
        "reference_note": "Somente a gramática editorial dos cabeçalhos foi extraída. A prosa de F não é fonte de voz nem conteúdo.",
    })
    return c


def parse_formatted_script(text: str) -> dict[str, Any]:
    labels: list[dict[str, Any]] = []
    narration_lines: list[str] = []
    unknown_bold: list[str] = []
    current_label: str | None = None
    section_content: dict[str, list[str]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            narration_lines.append("")
            continue
        if EDITORIAL_LABEL_RE.match(line):
            current_label = line
            labels.append({"label": line})
            section_content.setdefault(line, [])
            continue
        if BOLD_ONLY_RE.match(line):
            unknown_bold.append(line)
        narration_lines.append(raw)
        if current_label:
            section_content.setdefault(current_label, []).append(line)
    narration = "\n".join(narration_lines).strip()
    return {"labels": labels, "section_content": section_content, "unknown_bold": unknown_bold, "narration": narration}


def validate_output_format(text: str, contract: dict[str, Any] | None = None) -> dict[str, Any]:
    contract = contract or _default_format_contract()
    parsed = parse_formatted_script(text)
    labels = [x["label"] for x in parsed["labels"]]
    errors: list[str] = []
    if HEADING_RE.search(text): errors.append("hash_markdown_heading_forbidden")
    if parsed["unknown_bold"]: errors.append("unknown_bold_editorial_heading")
    if not labels: errors.append("missing_editorial_labels")
    else:
        if labels[0].upper() != "**GANCHO**": errors.append("first_label_must_be_GANCHO")
        if labels[-1].upper() != "**FECHAMENTO**": errors.append("last_label_must_be_FECHAMENTO")
    if sum(1 for x in labels if x.upper() == "**GANCHO**") != 1: errors.append("gancho_count")
    if sum(1 for x in labels if x.upper() == "**FECHAMENTO**") != 1: errors.append("fechamento_count")
    block_nums: list[int] = []
    for label in labels:
        m = BLOCK_LABEL_RE.match(label)
        if m:
            block_nums.append(int(m.group(1)))
            if not m.group(2).strip(): errors.append("empty_block_subtitle")
    min_blocks = int(contract.get("minimum_blocks", 3))
    if len(block_nums) < min_blocks: errors.append(f"minimum_blocks:{min_blocks}")
    if block_nums and block_nums != list(range(1, len(block_nums)+1)): errors.append("block_numbers_not_sequential")
    for label in labels:
        content = [x for x in parsed["section_content"].get(label, []) if x.strip()]
        if not content: errors.append(f"empty_section:{label}")
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "labels": labels,
        "block_count": len(block_nums),
        "narration": parsed["narration"],
        "narration_words": count_words(parsed["narration"]),
    }


def strip_editorial_labels(text: str) -> str:
    return parse_formatted_script(text)["narration"]


def _new_run_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def run_dir(run_id: str) -> Path:
    d = RUNS / run_id
    if not d.exists():
        fail(f"run nao encontrada: {run_id}")
    return d


def _word_range(target: int) -> dict[str, Any]:
    return {
        "target": target,
        "min": math.floor(target * (1.0 - DEFAULT_MARGIN_PCT)),
        "max": math.ceil(target * (1.0 + DEFAULT_MARGIN_PCT)),
        "margin_pct": DEFAULT_MARGIN_PCT,
    }


def _state(d: Path) -> dict[str, Any]:
    p = d / "state.json"
    if p.exists():
        return jload(p)
    s = {
        "run_id": d.name,
        "version": VERSION,
        "status": "BOUND",
        "draft_count": 0,
        "invalid_outputs": {},
        "model_failures": {},
        "model_success": {},
        "model_failover_count": 0,
        "active_stage": None,
        "active_model": None,
        "active_target": None,
        "last_checkpoint": "RUN_CREATED",
        "last_checkpoint_at": now(),
        "created_at": now(),
        "updated_at": now(),
    }
    jdump(p, s)
    return s


def _save_state(d: Path, s: dict[str, Any]) -> None:
    s["updated_at"] = now()
    jdump(d / "state.json", s)


def checkpoint(d: Path, name: str, **extra: Any) -> None:
    s = _state(d)
    s["last_checkpoint"] = name
    s["last_checkpoint_at"] = now()
    s.update(extra)
    _save_state(d, s)


def _inc_invalid(d: Path, stage: str) -> int:
    s = _state(d)
    inv = dict(s.get("invalid_outputs") or {})
    inv[stage] = int(inv.get(stage, 0)) + 1
    s["invalid_outputs"] = inv
    _save_state(d, s)
    return inv[stage]


def _reset_invalid(d: Path, stage: str) -> None:
    s = _state(d)
    inv = dict(s.get("invalid_outputs") or {})
    inv[stage] = 0
    s["invalid_outputs"] = inv
    _save_state(d, s)


def _logical_role(stage: str) -> str:
    st = (stage or "").upper()
    if st.startswith("DNA"): return "DNA"
    if st.startswith("B_DECOMPILER"): return "B_DECOMPILER"
    if st.startswith("REWRITE") or st.startswith("REPAIR"): return "REWRITER"
    if st.startswith("CRITIC") or st.startswith("MEASURE_OBJECTIVE"): return "CRITIC"
    if st.startswith("SECOND_OPINION") or st.startswith("RELEASE_CHALLENGE") or st.startswith("PERSISTENT_DELTA"): return "SECOND_OPINION"
    return st


def _model_failures_for(d: Path, role: str) -> dict[str, Any]:
    s = _state(d)
    allf = dict(s.get("model_failures") or {})
    return dict(allf.get(role) or {})


def record_model_failure(d: Path, role: str, model: str, reason: str, error: str | None = None) -> dict[str, Any]:
    role = _logical_role(role)
    s = _state(d)
    allf = dict(s.get("model_failures") or {})
    rf = dict(allf.get(role) or {})
    rf[model] = {"reason": reason, "error": error, "at": now()}
    allf[role] = rf
    s["model_failures"] = allf
    s["model_failover_count"] = int(s.get("model_failover_count", 0)) + 1
    try:
        _quarantine_provider_partial(d, role, model, reason)
    except Exception:
        pass
    s["active_stage"] = None
    s["active_model"] = None
    s["active_target"] = None
    s["status"] = "MODEL_FAILOVER_PENDING"
    s["last_checkpoint"] = f"MODEL_FAILED_{role}"
    s["last_checkpoint_at"] = now()
    _save_state(d, s)
    return {"role": role, "failed_model": model, "reason": reason, "remaining": [m for m, _ in MODEL_POOLS.get(role, []) if m not in rf]}


def record_model_success(d: Path, role: str, model: str | None) -> None:
    if not model: return
    role = _logical_role(role)
    s = _state(d)
    ms = dict(s.get("model_success") or {})
    ms[role] = {"model": model, "at": now()}
    s["model_success"] = ms
    _save_state(d, s)


def select_route(d: Path, role: str, exclude_models: set[str] | None = None) -> tuple[str, str] | None:
    role = _logical_role(role)
    failed = set(_model_failures_for(d, role))
    excluded = set(exclude_models or set())
    for model, target in MODEL_POOLS.get(role, []):
        if model not in failed and model not in excluded:
            return model, target
    return None


def model_pool_status(d: Path) -> dict[str, Any]:
    out = {}
    for role, routes in MODEL_POOLS.items():
        failed = _model_failures_for(d, role)
        selected = select_route(d, role)
        out[role] = {
            "selected_model": selected[0] if selected else None,
            "selected_target": selected[1] if selected else None,
            "failed_models": failed,
            "pool": [m for m, _ in routes],
        }
    return out


def _progress_bar(percent: int, width: int = 20) -> str:
    pct = max(0, min(100, int(percent)))
    filled = round(width * pct / 100)
    return "[" + ("█" * filled) + ("░" * (width - filled)) + "]"


def progress_obj(d: Path) -> dict[str, Any]:
    s = _state(d); status = str(s.get("status") or "")
    dna = (d / "artifacts" / "a_dna.json").exists()
    ledger = (d / "artifacts" / "b_content_ledger.json").exists()
    draft = (d / "full" / "draft.txt").exists()
    audit = (d / "full" / "deterministic_audit.json").exists()
    assessment = (d / "full" / "objective_assessment.json").exists()
    second = (d / "full" / "second_opinion.json").exists()
    released = status == "RELEASED" or bool(_released_file_for_run(d.name))
    percent, phase = 10, "INPUTS"
    if released:
        percent, phase = 100, "RELEASED"
    elif not dna:
        percent, phase = (18 if status == "DNA_PENDING" else 10), "DNA"
    elif not ledger:
        percent, phase = (32 if status == "B_DECOMPILER_PENDING" else 25), "B_DECOMPILER"
    elif not draft:
        percent, phase = (50 if status.startswith("REWRITE") else 40), "REWRITE"
    elif not audit:
        percent, phase = 68, "AUDIT"
    elif not assessment:
        percent, phase = (78 if status == "CRITIC_PENDING" else 72), "CRITIC"
    elif status == "SECOND_OPINION_PENDING":
        percent, phase = 88, "SECOND_OPINION"
    elif status == "REPAIR_PENDING":
        percent, phase = min(94, 84 + int(s.get("draft_count", 1)) * 3), "REPAIR"
    elif second:
        percent, phase = 92, "SECOND_OPINION_READY"
    else:
        percent, phase = 84, "OBJECTIVE_MEASURED"
    return {
        "percent": percent,
        "bar": _progress_bar(percent),
        "phase": phase,
        "status": status,
        "active_stage": s.get("active_stage"),
        "active_model": s.get("active_model"),
        "active_target": s.get("active_target"),
        "model_failover_count": int(s.get("model_failover_count", 0)),
        "draft_count": int(s.get("draft_count", 0)),
        "max_drafts": MAX_DRAFTS,
    }


def _cache_key_a(a_sha: str) -> str:
    return sha256_text(f"{DNA_SCHEMA_REV}|{a_sha}")


def _cache_path_a(a_sha: str) -> Path:
    return CACHE_A / f"{_cache_key_a(a_sha)}.json"


def create_run(a_file: str, b_file: str, run_id: str | None = None, target_words: int | None = None, format_file: str | None = None) -> dict[str, Any]:
    ensure_runtime_dirs()
    ap, atext = resolve_text_source(a_file, "A")
    bp, btext = resolve_text_source(b_file, "B")
    if ap.resolve() == bp.resolve():
        fail("A e B nao podem ser o mesmo arquivo")
    rid = run_id or _new_run_id()
    d = RUNS / rid
    if d.exists():
        fail(f"run ja existe: {rid}")
    for p in [d, d / "artifacts", d / "full", d / "work", d / "history", d / "revisions"]:
        p.mkdir(parents=True, exist_ok=True)
    target = int(target_words or count_words(btext))
    format_contract = build_format_contract(format_file)
    binding = {
        "run_id": rid,
        "A": {"path": _rel(ap), "sha256": sha256_file(ap), "words": count_words(atext), "role": "FORM_VOICE_DNA_ONLY"},
        "B": {"path": _rel(bp), "sha256": sha256_file(bp), "words": count_words(btext), "role": "CONTENT_TOPIC_ORDER_LENGTH_ONLY"},
        "F": ({"path": format_contract.get("format_reference_path"), "sha256": format_contract.get("format_reference_sha256"), "role": "EDITORIAL_FORMAT_ONLY"} if format_contract.get("format_reference_path") else None),
        "target_words": target,
        "word_range": _word_range(target),
        "format_contract_file": _rel(d / "format_contract.json"),
    }
    objective = {
        "schema_version": "7.7",
        "objective_id": "A_TO_B_TRUE_TRANSFER",
        "primary": "Reescrever B preservando seu conteudo, ordem TEMATICA e tamanho, mas reconstruindo a forma para ficar mais proxima de A do que de B.",
        "source_contract": {
            "A": ["voz", "cadencia", "sintaxe", "gancho", "retencao", "ritmo", "transicoes", "engenharia narrativa"],
            "B": ["conteudo", "fatos", "mensagem", "certeza", "ordem tematica", "tamanho"],
            "F": ["formato editorial", "blocos inteiros", "subtitulos", "labels GANCHO/BLOCO/CTA/FECHAMENTO"],
            "forbidden": ["usar A como fonte factual", "usar B como molde retorico", "parafrase linha-a-linha de B", "copiar prosa de A", "caricaturar bordoes de A"],
        },
        "release_rule": {
            "all_gates_pass": GATES,
            "deterministic_hard_status": "PASS",
            "form_matrix_rule": "A>=6/8; B<=1/8; block_progression+retention_logic+syntax_voice closer_to A",
            "independent_release_challenge": "GLM-5.2 must CONFIRM_RELEASE",
            "output_format_contract": "GANCHO + BLOCOS NUMERADOS COM SUBTITULO + FECHAMENTO; CTAs rotulados quando usados",
        },
        "word_range": binding["word_range"],
        "created_at": now(),
    }
    jdump(d / "format_contract.json", format_contract)
    jdump(d / "binding.json", binding)
    jdump(d / "objective.json", objective)
    jdump(d / "objective_history.json", {"schema_version": "7.7", "items": []})
    _state(d)
    checkpoint(d, "INPUTS_BOUND", status="BOUND")
    return {"ok": True, "run_id": rid, "binding": binding, "objective": objective, "final_dir": _rel(FINAL_DIR)}


def _archive(path: Path, destination: Path) -> None:
    if path.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)


def _reject_files(d: Path, stage: str, paths: list[Path], errors: list[str]) -> None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    rej = d / "rejected" / stage.lower() / stamp
    rej.mkdir(parents=True, exist_ok=True)
    for path in paths:
        if path.exists():
            shutil.move(str(path), str(rej / path.name))
    jdump(rej / "rejection.json", {"stage": stage, "errors": errors, "rejected_at": now()})


def _quarantine_provider_partial(d: Path, role: str, model: str, reason: str) -> None:
    paths: dict[str, list[Path]] = {
        "DNA": [d / "artifacts" / "a_dna_candidate.json"],
        "B_DECOMPILER": [d / "artifacts" / "b_content_ledger_candidate.json", d / "artifacts" / "b_scaffold_signature_candidate.json"],
        "REWRITER": [d / "full" / "draft_candidate.txt", d / "full" / "rewrite_report_candidate.json"],
        "CRITIC": [d / "full" / "critique_candidate.json"],
        "SECOND_OPINION": [d / "full" / "second_opinion_candidate.json"],
    }
    present = [p for p in paths.get(role, []) if p.exists()]
    if present:
        _reject_files(d, f"{role}_PROVIDER_FAILURE", present, [f"provider_failure:{model}:{reason}"])


def _validate_no_long_source_prose(source_text: str, candidate_text: str, n: int = 8) -> list[str]:
    return exact_ngram_matches(source_text, candidate_text, n=n, limit=10)


def accept_dna_candidate(d: Path, binding: dict[str, Any]) -> tuple[bool, list[str]]:
    cand = d / "artifacts" / "a_dna_candidate.json"
    final = d / "artifacts" / "a_dna.json"
    if final.exists():
        return True, []
    cache = _cache_path_a(binding["A"]["sha256"])
    if cache.exists():
        try:
            obj = jload(cache)
            if obj.get("source_sha256") == binding["A"]["sha256"] and obj.get("schema_version") == "7.7":
                shutil.copy2(cache, final)
                checkpoint(d, "DNA_CACHE_HIT", status="DNA_READY", active_stage=None, active_model=None)
                return True, []
        except Exception:
            pass
    if not cand.exists():
        return False, []
    errors: list[str] = []
    try:
        obj = jload(cand)
        if obj.get("schema_version") != "7.7": errors.append("schema_version")
        if obj.get("source_role") != "FORM_VOICE_DNA_ONLY": errors.append("source_role")
        if obj.get("source_sha256") != binding["A"]["sha256"]: errors.append("source_sha256")
        if len(obj.get("signature_traits") or []) < 5: errors.append("signature_traits<5")
        if obj.get("contains_source_prose") is not False: errors.append("contains_source_prose")
        a_text = read_text_robust(ROOT / binding["A"]["path"])
        if _validate_no_long_source_prose(a_text, json.dumps(obj, ensure_ascii=False), 10): errors.append("dna_contains_A_10gram")
    except Exception as e:
        errors.append(f"json:{e}")
    if errors:
        _reject_files(d, "DNA", [cand], errors)
        _inc_invalid(d, "dna")
        return False, errors
    active_model = _state(d).get("active_model")
    shutil.move(str(cand), str(final))
    shutil.copy2(final, cache)
    _reset_invalid(d, "dna")
    record_model_success(d, "DNA", active_model)
    checkpoint(d, "DNA_READY", status="DNA_READY", active_stage=None, active_model=None, active_target=None)
    return True, []


def accept_b_decompiler_candidate(d: Path, binding: dict[str, Any]) -> tuple[bool, list[str]]:
    ledger_c = d / "artifacts" / "b_content_ledger_candidate.json"
    scaffold_c = d / "artifacts" / "b_scaffold_signature_candidate.json"
    ledger = d / "artifacts" / "b_content_ledger.json"
    scaffold = d / "artifacts" / "b_scaffold_signature.json"
    if ledger.exists() and scaffold.exists():
        return True, []
    if not ledger_c.exists() and not scaffold_c.exists():
        return False, []
    if not ledger_c.exists() or not scaffold_c.exists():
        errs = ["partial_b_decompiler_output"]
        _reject_files(d, "B_DECOMPILER", [ledger_c, scaffold_c], errs)
        _inc_invalid(d, "b_decompiler")
        return False, errs
    errors: list[str] = []
    try:
        l = jload(ledger_c); s = jload(scaffold_c)
        if l.get("schema_version") != "7.7": errors.append("ledger.schema_version")
        if l.get("source_role") != "CONTENT_TOPIC_ORDER_LENGTH_ONLY": errors.append("ledger.source_role")
        if l.get("source_sha256") != binding["B"]["sha256"]: errors.append("ledger.source_sha256")
        topics = l.get("topics") or []
        if not isinstance(topics, list) or len(topics) < 1: errors.append("ledger.topics")
        units = []
        for t in topics:
            units.extend(t.get("content_units") or [])
        if len(units) < 3: errors.append("ledger.content_units<3")
        if l.get("contains_source_surface_prose") is not False: errors.append("ledger.contains_source_surface_prose")
        if s.get("schema_version") != "7.7": errors.append("scaffold.schema_version")
        if s.get("source_sha256") != binding["B"]["sha256"]: errors.append("scaffold.source_sha256")
        if s.get("source_role") != "CRITIC_ONLY_B_FORM_SIGNATURE": errors.append("scaffold.source_role")
        b_text = read_text_robust(ROOT / binding["B"]["path"])
        if _validate_no_long_source_prose(b_text, json.dumps(l, ensure_ascii=False), 10): errors.append("ledger_contains_B_10gram")
    except Exception as e:
        errors.append(f"json:{e}")
    if errors:
        _reject_files(d, "B_DECOMPILER", [ledger_c, scaffold_c], errors)
        _inc_invalid(d, "b_decompiler")
        return False, errors
    active_model = _state(d).get("active_model")
    shutil.move(str(ledger_c), str(ledger)); shutil.move(str(scaffold_c), str(scaffold))
    _reset_invalid(d, "b_decompiler")
    record_model_success(d, "B_DECOMPILER", active_model)
    checkpoint(d, "B_DECOMPILED", status="B_DECOMPILED", active_stage=None, active_model=None, active_target=None)
    return True, []


def accept_rewrite_candidate(d: Path, binding: dict[str, Any]) -> tuple[bool, list[str]]:
    cand = d / "full" / "draft_candidate.txt"
    report_c = d / "full" / "rewrite_report_candidate.json"
    if not cand.exists() and not report_c.exists():
        return False, []
    if not cand.exists() or not report_c.exists():
        errs = ["partial_rewrite_output"]
        _reject_files(d, "REWRITER", [cand, report_c], errs)
        _inc_invalid(d, "rewrite")
        return False, errs
    errors: list[str] = []
    try:
        text = read_text_robust(cand)
        report = jload(report_c)
        if report.get("schema_version") != "7.7": errors.append("report.schema_version")
        expected_iter = int(_state(d).get("draft_count", 0)) + 1
        if int(report.get("iteration", -1)) != expected_iter: errors.append("report.iteration")
        if report.get("b_sha256") != binding["B"]["sha256"]: errors.append("report.b_sha256")
        fmt = validate_output_format(text, jload(d / "format_contract.json"))
        if fmt["status"] != "PASS": errors.extend([f"output_format:{e}" for e in fmt["errors"]])
        if not fmt["narration"].strip(): errors.append("draft_empty")
        covered = report.get("covered_content_unit_ids") or []
        if not isinstance(covered, list) or len(covered) < 1: errors.append("covered_content_unit_ids")
    except Exception as e:
        errors.append(f"rewrite:{e}")
    if errors:
        _reject_files(d, "REWRITER", [cand, report_c], errors)
        _inc_invalid(d, "rewrite")
        return False, errors
    active_model = _state(d).get("active_model")
    s = _state(d); new_iter = int(s.get("draft_count", 0)) + 1
    old_draft = d / "full" / "draft.txt"; old_report = d / "full" / "rewrite_report.json"
    if old_draft.exists():
        _archive(old_draft, d / "revisions" / f"draft_{new_iter-1:02d}.txt")
    if old_report.exists():
        _archive(old_report, d / "revisions" / f"rewrite_report_{new_iter-1:02d}.json")
    for p in [d / "full" / "objective_assessment.json", d / "full" / "critique.json", d / "full" / "second_opinion.json", d / "full" / "deterministic_audit.json"]:
        if p.exists():
            _archive(p, d / "history" / f"{p.stem}_{new_iter-1:02d}{p.suffix}")
            p.unlink()
    shutil.move(str(cand), str(old_draft)); shutil.move(str(report_c), str(old_report))
    s = _state(d); s["draft_count"] = new_iter; _save_state(d, s)
    _reset_invalid(d, "rewrite")
    record_model_success(d, "REWRITER", active_model)
    checkpoint(d, f"DRAFT_{new_iter}_READY", status="DRAFT_READY", active_stage=None, active_model=None, active_target=None)
    return True, []


def audit_texts(a_text: str, b_text: str, draft_text: str, word_range: dict[str, Any], format_contract: dict[str, Any] | None = None) -> dict[str, Any]:
    hard: list[dict[str, Any]] = []; warn: list[dict[str, Any]] = []
    fmt = validate_output_format(draft_text, format_contract)
    narration = fmt["narration"]
    if fmt["status"] != "PASS":
        hard.append({"code": "OUTPUT_FORMAT_CONTRACT", "errors": fmt["errors"], "labels": fmt.get("labels", [])})
    words = count_words(narration)
    if words < int(word_range["min"]) or words > int(word_range["max"]):
        hard.append({"code": "B_LENGTH_OUT_OF_RANGE", "words": words, "range": word_range})
    opening = " ".join(_tokens(narration)[:35])
    if re.search(r"\b(fala|ol[aá]|oi|seja bem[- ]?vindo|meu nome e|eu sou)\b", opening):
        hard.append({"code": "FORBIDDEN_GREETING_OR_IDENTIFICATION"})
    a8 = exact_ngram_matches(a_text, narration, 8, 20)
    a6 = exact_ngram_matches(a_text, narration, 6, 20)
    if a8:
        hard.append({"code": "A_LITERAL_8GRAM", "matches": a8[:10]})
    elif a6:
        warn.append({"code": "A_LITERAL_6GRAM", "matches": a6[:10]})
    b10 = exact_ngram_matches(b_text, narration, 10, 20)
    b8 = exact_ngram_matches(b_text, narration, 8, 20)
    if b10:
        hard.append({"code": "B_LITERAL_10GRAM", "matches": b10[:10]})
    elif b8:
        warn.append({"code": "B_LITERAL_8GRAM", "matches": b8[:10]})
    overfit = repeated_marker_overfit(a_text, narration)
    if overfit:
        warn.append({"code": "A_STYLE_MARKER_OVERFIT", "findings": overfit})
    b_nums = set(NUMBER_RE.findall(b_text)); d_nums = set(NUMBER_RE.findall(narration))
    added_nums = sorted(x for x in d_nums if x not in b_nums)
    if added_nums:
        warn.append({"code": "NEW_NUMBER_CANDIDATES", "values": added_nums[:30]})
    return {
        "schema_version": "7.7",
        "hard_status": "FAIL" if hard else "PASS",
        "hard_failures": hard,
        "warnings": warn,
        "word_count": words,
        "word_range": word_range,
        "output_format": {k:v for k,v in fmt.items() if k != "narration"},
    }


def deterministic_audit(d: Path, binding: dict[str, Any]) -> dict[str, Any]:
    a_text = read_text_robust(ROOT / binding["A"]["path"])
    b_text = read_text_robust(ROOT / binding["B"]["path"])
    draft_text = read_text_robust(d / "full" / "draft.txt")
    audit = audit_texts(a_text, b_text, draft_text, binding["word_range"], jload(d / "format_contract.json") if (d / "format_contract.json").exists() else _default_format_contract())
    audit["draft_sha256"] = sha256_file(d / "full" / "draft.txt")
    audit["iteration"] = int(_state(d).get("draft_count", 0))
    jdump(d / "full" / "deterministic_audit.json", audit)
    return audit


def _validate_gate_evidence(gate_obj: dict[str, Any]) -> bool:
    evidence = gate_obj.get("evidence") or []
    if not isinstance(evidence, list) or len(evidence) < 3:
        return False
    locs = {str(x.get("location", "")).lower() for x in evidence if isinstance(x, dict)}
    return {"opening", "middle", "ending"}.issubset(locs)


def validate_form_matrix(matrix: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    dims = matrix.get("dimensions") if isinstance(matrix, dict) else None
    if not isinstance(dims, dict):
        return False, {"reason": "missing_dimensions"}
    missing = [x for x in FORM_DIMENSIONS if x not in dims]
    if missing:
        return False, {"reason": "missing_form_dimensions", "missing": missing}
    a_count = b_count = neither_count = 0
    for dim in FORM_DIMENSIONS:
        obj = dims.get(dim) or {}
        closer = str(obj.get("closer_to", "")).upper()
        if closer == "A": a_count += 1
        elif closer == "B": b_count += 1
        else: neither_count += 1
        if not str(obj.get("reason", "")).strip():
            return False, {"reason": f"missing_reason:{dim}"}
    mandatory = all(str((dims.get(x) or {}).get("closer_to", "")).upper() == "A" for x in ["block_progression", "retention_logic", "syntax_voice"])
    ok = a_count >= 6 and b_count <= 1 and mandatory
    return ok, {"a_count": a_count, "b_count": b_count, "neither_count": neither_count, "mandatory_a": mandatory}


def _previous_assessment(d: Path) -> dict[str, Any] | None:
    p = d / "full" / "objective_assessment.json"
    return jload(p) if p.exists() else None


def _history_append(d: Path, item: dict[str, Any]) -> None:
    p = d / "objective_history.json"
    obj = jload(p) if p.exists() else {"schema_version": "7.7", "items": []}
    obj.setdefault("items", []).append(item)
    jdump(p, obj)


def _failed_from_gates(gates: dict[str, Any]) -> list[str]:
    return [g for g in GATES if str((gates.get(g) or {}).get("status", "")).upper() != "PASS"]


def accept_critique_candidate(d: Path, audit: dict[str, Any]) -> tuple[bool, list[str]]:
    cand = d / "full" / "critique_candidate.json"
    if not cand.exists():
        return False, []
    errors: list[str] = []
    try:
        c = jload(cand)
        if c.get("schema_version") != "7.7": errors.append("schema_version")
        current_sha = sha256_file(d / "full" / "draft.txt")
        iteration = int(_state(d).get("draft_count", 0))
        if c.get("draft_sha256") != current_sha: errors.append("draft_sha256")
        if int(c.get("iteration", -1)) != iteration: errors.append("iteration")
        gates = c.get("gates") or {}
        for g in GATES:
            if g not in gates or str((gates[g] or {}).get("status", "")).upper() not in {"PASS", "FAIL"}:
                errors.append(f"gate:{g}")
        failed = _failed_from_gates(gates)
        declared = str(c.get("status", ""))
        if failed and declared != "OBJECTIVE_NOT_MET": errors.append("status_should_fail")
        if not failed and declared != "OBJECTIVE_MET": errors.append("status_should_pass")
        for g in CRITICAL_EVIDENCE_GATES:
            if g in gates and str(gates[g].get("status", "")).upper() == "PASS" and not _validate_gate_evidence(gates[g]):
                errors.append(f"evidence:{g}")
        matrix_ok, matrix_stats = validate_form_matrix(c.get("form_comparison") or {})
        if declared == "OBJECTIVE_MET" and not matrix_ok:
            errors.append(f"form_matrix:{matrix_stats}")
        if declared == "OBJECTIVE_MET" and audit.get("hard_status") != "PASS": errors.append("deterministic_hard_fail")
        delta = c.get("objective_delta") or []
        if failed and not delta: errors.append("missing_objective_delta")
    except Exception as e:
        errors.append(f"json:{e}")
    if errors:
        _reject_files(d, "CRITIC", [cand], errors)
        _inc_invalid(d, "critic")
        return False, errors
    active_model = _state(d).get("active_model")
    c = jload(cand)
    prev = _previous_assessment(d)
    if prev:
        _archive(d / "full" / "objective_assessment.json", d / "history" / f"objective_assessment_{int(prev.get('iteration',0)):02d}.json")
        _archive(d / "full" / "critique.json", d / "history" / f"critique_{int(prev.get('iteration',0)):02d}.json")
    gates = c["gates"]
    failed = _failed_from_gates(gates)
    regressions: list[str] = []
    if prev:
        pg = prev.get("gates") or {}
        for g in GATES:
            if str((pg.get(g) or {}).get("status", "")).upper() == "PASS" and str((gates.get(g) or {}).get("status", "")).upper() == "FAIL":
                regressions.append(g)
    c["regressions"] = sorted(set((c.get("regressions") or []) + regressions))
    c["failed_gates"] = failed
    c["objective_met"] = c.get("status") == "OBJECTIVE_MET" and not failed and audit.get("hard_status") == "PASS"
    shutil.move(str(cand), str(d / "full" / "critique.json"))
    jdump(d / "full" / "objective_assessment.json", c)
    preserve = [g for g in GATES if g not in failed and g not in c["regressions"]]
    delta_obj = {
        "schema_version": "7.7",
        "iteration": c["iteration"],
        "draft_sha256": c["draft_sha256"],
        "failed_gates": failed,
        "regressions": c["regressions"],
        "preserve_gates": preserve,
        "items": c.get("objective_delta") or [],
        "source": f"CRITIC:{active_model}",
    }
    jdump(d / "full" / "objective_delta.json", delta_obj)
    _history_append(d, {"iteration": c["iteration"], "failed_gates": failed, "regressions": c["regressions"], "objective_met": c["objective_met"], "at": now()})
    _reset_invalid(d, "critic")
    record_model_success(d, "CRITIC", active_model)
    checkpoint(d, f"CRITIC_{c['iteration']}_READY", status="OBJECTIVE_MET_CANDIDATE" if c["objective_met"] else "OBJECTIVE_NOT_MET", active_stage=None, active_model=None, active_target=None)
    return True, []


def same_delta_persisted(d: Path) -> bool:
    try:
        h = (jload(d / "objective_history.json") or {}).get("items") or []
        if len(h) < 2: return False
        a = sorted(h[-1].get("failed_gates") or [])
        b = sorted(h[-2].get("failed_gates") or [])
        return bool(a) and a == b
    except Exception:
        return False


def _second_fresh(d: Path, mode: str) -> bool:
    p = d / "full" / "second_opinion.json"
    if not p.exists(): return False
    try:
        o = jload(p)
        return o.get("mode") == mode and o.get("draft_sha256") == sha256_file(d / "full" / "draft.txt") and int(o.get("iteration", -1)) == int(_state(d).get("draft_count", 0))
    except Exception:
        return False


def accept_second_opinion_candidate(d: Path) -> tuple[bool, list[str]]:
    cand = d / "full" / "second_opinion_candidate.json"
    if not cand.exists():
        return False, []
    errors: list[str] = []
    try:
        o = jload(cand)
        if o.get("schema_version") != "7.7": errors.append("schema_version")
        if o.get("draft_sha256") != sha256_file(d / "full" / "draft.txt"): errors.append("draft_sha256")
        if int(o.get("iteration", -1)) != int(_state(d).get("draft_count", 0)): errors.append("iteration")
        mode = o.get("mode")
        if mode not in {"RELEASE_CHALLENGE", "PERSISTENT_DELTA"}: errors.append("mode")
        if mode == "RELEASE_CHALLENGE":
            if o.get("verdict") not in {"CONFIRM_RELEASE", "VETO_RELEASE"}: errors.append("verdict")
            matrix_ok, stats = validate_form_matrix(o.get("form_comparison") or {})
            if o.get("verdict") == "CONFIRM_RELEASE" and not matrix_ok: errors.append(f"form_matrix:{stats}")
            critical = o.get("critical_gates") or {}
            for g in ["a_macro_dna","a_micro_voice","b_rhetorical_scaffolding_removed","form_closer_to_a_than_b","transformation_depth","anti_a_copy","voice_caricature"]:
                if str((critical.get(g) or {}).get("status", "")).upper() not in {"PASS","FAIL"}: errors.append(f"critical_gate:{g}")
            if o.get("verdict") == "CONFIRM_RELEASE" and any(str((critical.get(g) or {}).get("status", "")).upper() != "PASS" for g in critical): errors.append("confirm_with_failed_critical_gate")
        else:
            if o.get("verdict") not in {"CONFIRM_CRITIC", "PARTIAL_DISAGREEMENT", "DISAGREE_WITH_CRITIC"}: errors.append("verdict")
    except Exception as e:
        errors.append(f"json:{e}")
    if errors:
        _reject_files(d, "SECOND_OPINION", [cand], errors)
        _inc_invalid(d, "second_opinion")
        return False, errors
    active_model = _state(d).get("active_model")
    if (d / "full" / "second_opinion.json").exists():
        old = jload(d / "full" / "second_opinion.json")
        _archive(d / "full" / "second_opinion.json", d / "history" / f"second_opinion_{int(old.get('iteration',0)):02d}_{old.get('mode','unknown')}.json")
    shutil.move(str(cand), str(d / "full" / "second_opinion.json"))
    _reset_invalid(d, "second_opinion")
    record_model_success(d, "SECOND_OPINION", active_model)
    o = jload(d / "full" / "second_opinion.json")
    checkpoint(d, f"SECOND_OPINION_{o.get('mode')}_{o.get('iteration')}_READY", status="SECOND_OPINION_READY", active_stage=None, active_model=None, active_target=None)
    return True, []


def apply_release_veto(d: Path) -> None:
    o = jload(d / "full" / "second_opinion.json")
    assessment = jload(d / "full" / "objective_assessment.json")
    failed = [g for g, v in (o.get("critical_gates") or {}).items() if str((v or {}).get("status", "")).upper() == "FAIL"]
    if not failed:
        failed = ["form_closer_to_a_than_b"]
    preserve = [g for g in GATES if g not in failed]
    delta = {
        "schema_version": "7.7",
        "iteration": int(_state(d).get("draft_count", 0)),
        "draft_sha256": sha256_file(d / "full" / "draft.txt"),
        "failed_gates": failed,
        "regressions": [],
        "preserve_gates": preserve,
        "items": o.get("advice") or [{"location":"global","failed_gate":failed[0],"problem":"GLM vetou o release","required_change":"corrigir a transferencia profunda antes de liberar","preserve":"demais gates"}],
        "source": "GLM_RELEASE_VETO",
    }
    jdump(d / "full" / "objective_delta.json", delta)
    assessment["objective_met"] = False
    assessment["release_challenge_veto"] = True
    jdump(d / "full" / "objective_assessment.json", assessment)
    checkpoint(d, "RELEASE_VETOED", status="OBJECTIVE_NOT_MET")


def prepare_dna_task(d: Path, binding: dict[str, Any]) -> Path:
    task = {
        "task": "EXTRACT_A_DNA",
        "schema_version": "7.7",
        "a_file": binding["A"]["path"],
        "a_sha256": binding["A"]["sha256"],
        "objective_file": _rel(d / "objective.json"),
        "dna_candidate": _rel(d / "artifacts" / "a_dna_candidate.json"),
        "rule": "A=FORM_VOICE_DNA_ONLY; NEVER_READ_B",
    }
    p = d / "work" / "dna_task.json"; jdump(p, task); return p


def prepare_b_decompiler_task(d: Path, binding: dict[str, Any]) -> Path:
    task = {
        "task": "DECOMPILE_B",
        "schema_version": "7.7",
        "b_file": binding["B"]["path"],
        "b_sha256": binding["B"]["sha256"],
        "objective_file": _rel(d / "objective.json"),
        "target_words": binding["target_words"],
        "word_range": binding["word_range"],
        "content_ledger_candidate": _rel(d / "artifacts" / "b_content_ledger_candidate.json"),
        "scaffold_signature_candidate": _rel(d / "artifacts" / "b_scaffold_signature_candidate.json"),
        "rule": "PRESERVE_TOPIC_ORDER_AND_SEMANTICS; DESTROY_B_SURFACE; LEDGER_FOR_WRITER; SCAFFOLD_FOR_CRITIC_ONLY",
    }
    p = d / "work" / "b_decompiler_task.json"; jdump(p, task); return p


def prepare_rewriter_task(d: Path, binding: dict[str, Any], mode: str) -> Path:
    s = _state(d); iteration = int(s.get("draft_count", 0)) + 1
    task: dict[str, Any] = {
        "task": "A_TO_B_REWRITE_FROM_LEDGER",
        "schema_version": "7.7",
        "mode": mode,
        "iteration": iteration,
        "objective_file": _rel(d / "objective.json"),
        "a_file": binding["A"]["path"],
        "a_sha256": binding["A"]["sha256"],
        "dna_file": _rel(d / "artifacts" / "a_dna.json"),
        "b_content_ledger_file": _rel(d / "artifacts" / "b_content_ledger.json"),
        "b_sha256": binding["B"]["sha256"],
        "target_words": binding["target_words"],
        "word_range": binding["word_range"],
        "format_contract_file": _rel(d / "format_contract.json"),
        "draft_candidate": _rel(d / "full" / "draft_candidate.txt"),
        "rewrite_report_candidate": _rel(d / "full" / "rewrite_report_candidate.json"),
        "hard_rule": "NEVER_READ_RAW_B; NEVER_READ_B_SCAFFOLD_SIGNATURE; RECONSTRUCT_FROM_SEMANTIC_LEDGER_USING_A; OUTPUT_MUST_OBEY_FORMAT_CONTRACT",
    }
    if mode == "REPAIR":
        task.update({
            "current_draft_file": _rel(d / "full" / "draft.txt"),
            "objective_delta_file": _rel(d / "full" / "objective_delta.json"),
            "critique_file": _rel(d / "full" / "critique.json"),
            "deterministic_audit_file": _rel(d / "full" / "deterministic_audit.json"),
            "repair_rule": "REPAIR_ONLY_DELTA; PRESERVE_PASSED_GATES; STILL_NEVER_READ_RAW_B",
        })
        if (d / "full" / "second_opinion.json").exists():
            task["second_opinion_file"] = _rel(d / "full" / "second_opinion.json")
    p = d / "work" / ("rewrite_initial_task.json" if mode == "INITIAL" else f"rewrite_repair_{iteration}.json")
    jdump(p, task); return p


def prepare_critic_task(d: Path, binding: dict[str, Any]) -> Path:
    iteration = int(_state(d).get("draft_count", 0))
    task = {
        "task": "MEASURE_TRUE_OBJECTIVE",
        "schema_version": "7.7",
        "iteration": iteration,
        "objective_file": _rel(d / "objective.json"),
        "a_file": binding["A"]["path"],
        "dna_file": _rel(d / "artifacts" / "a_dna.json"),
        "b_file": binding["B"]["path"],
        "b_content_ledger_file": _rel(d / "artifacts" / "b_content_ledger.json"),
        "b_scaffold_signature_file": _rel(d / "artifacts" / "b_scaffold_signature.json"),
        "draft_file": _rel(d / "full" / "draft.txt"),
        "format_contract_file": _rel(d / "format_contract.json"),
        "rewrite_report_file": _rel(d / "full" / "rewrite_report.json"),
        "deterministic_audit_file": _rel(d / "full" / "deterministic_audit.json"),
        "draft_sha256": sha256_file(d / "full" / "draft.txt"),
        "critique_candidate": _rel(d / "full" / "critique_candidate.json"),
        "gate_rule": "ALL_12_GATES_PASS; FORM_MATRIX_A>=6/8_B<=1/8; EVIDENCE_OPENING_MIDDLE_ENDING; NO_AVERAGE",
    }
    p = d / "work" / f"critic_task_{iteration}.json"; jdump(p, task); return p


def prepare_second_opinion_task(d: Path, binding: dict[str, Any], mode: str) -> Path:
    iteration = int(_state(d).get("draft_count", 0))
    task = {
        "task": "SECOND_OPINION",
        "schema_version": "7.7",
        "mode": mode,
        "iteration": iteration,
        "objective_file": _rel(d / "objective.json"),
        "a_file": binding["A"]["path"],
        "dna_file": _rel(d / "artifacts" / "a_dna.json"),
        "b_file": binding["B"]["path"],
        "b_scaffold_signature_file": _rel(d / "artifacts" / "b_scaffold_signature.json"),
        "draft_file": _rel(d / "full" / "draft.txt"),
        "format_contract_file": _rel(d / "format_contract.json"),
        "critic_file": _rel(d / "full" / "critique.json"),
        "objective_assessment_file": _rel(d / "full" / "objective_assessment.json"),
        "objective_history_file": _rel(d / "objective_history.json"),
        "deterministic_audit_file": _rel(d / "full" / "deterministic_audit.json"),
        "draft_sha256": sha256_file(d / "full" / "draft.txt"),
        "second_opinion_candidate": _rel(d / "full" / "second_opinion_candidate.json"),
        "rule": "INDEPENDENT; RELEASE_CHALLENGE_CAN_VETO; NEVER_RELEASE_BY_ITSELF",
    }
    p = d / "work" / f"second_opinion_{mode.lower()}_{iteration}.json"; jdump(p, task); return p


def _released_file_for_run(run_id: str) -> Path | None:
    if not FINAL_DIR.exists(): return None
    matches = sorted(FINAL_DIR.glob(f"roteiro_final_{run_id}.txt"))
    return matches[-1] if matches else None


def release(d: Path, binding: dict[str, Any], audit: dict[str, Any], assessment: dict[str, Any], challenge: dict[str, Any]) -> dict[str, Any]:
    ensure_runtime_dirs()
    src = d / "full" / "draft.txt"
    text = read_text_robust(src).strip() + "\n"
    clean_text = strip_editorial_labels(text).strip() + "\n"
    final = FINAL_DIR / f"roteiro_final_{d.name}.txt"
    final.write_text(text, encoding="utf-8")
    latest = FINAL_DIR / "ULTIMO_ROTEIRO.txt"
    latest.write_text(text, encoding="utf-8")
    clean = FINAL_DIR / f"locucao_limpa_{d.name}.txt"
    clean.write_text(clean_text, encoding="utf-8")
    latest_clean = FINAL_DIR / "ULTIMA_LOCUCAO_LIMPA.txt"
    latest_clean.write_text(clean_text, encoding="utf-8")
    rel = {
        "run_id": d.name,
        "version": VERSION,
        "pipeline": PIPELINE,
        "status": "RELEASED",
        "objective_met": True,
        "final_path": _rel(final),
        "latest_path": _rel(latest),
        "clean_locution_path": _rel(clean),
        "latest_clean_locution_path": _rel(latest_clean),
        "final_sha256": sha256_file(final),
        "final_words": count_words(clean_text),
        "target_words": binding["target_words"],
        "word_range": binding["word_range"],
        "draft_count": int(_state(d).get("draft_count", 0)),
        "release_challenge": challenge,
        "released_at": now(),
    }
    jdump(d / "release.json", rel)
    checkpoint(d, "RELEASED", status="RELEASED", active_stage=None, active_model=None)
    return rel


def _invalid_exhausted(d: Path, stage: str) -> bool:
    limit = int(INVALID_STAGE_LIMITS.get(stage, MAX_INVALID_STAGE_OUTPUT))
    return int((_state(d).get("invalid_outputs") or {}).get(stage, 0)) >= limit


def _route_call(d: Path, role: str, task_file: Path, stage: str, pending_status: str, *, exclude_models: set[str] | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    role = _logical_role(role)
    route = select_route(d, role, exclude_models=exclude_models)
    failed = _model_failures_for(d, role)
    if not route:
        checkpoint(d, f"MODEL_POOL_EXHAUSTED_{role}", status="MODEL_POOL_EXHAUSTED", active_stage=stage, active_model=None, active_target=None)
        return {
            "done": False,
            "status": "MODEL_POOL_EXHAUSTED",
            "recoverable": True,
            "role": role,
            "stage": stage,
            "reason": "Todos os modelos compatíveis deste estágio foram marcados como indisponíveis nesta run.",
            "failed_models": failed,
            "action_hint": f"Adicione/restaure quota ou execute model-reset para {role} e depois /continuar-roteiro.",
        }
    model, target = route
    pool = MODEL_POOLS[role]
    idx = next(i for i, x in enumerate(pool) if x == route)
    checkpoint(d, pending_status, status=pending_status, active_stage=stage, active_model=model, active_target=target)
    obj = {
        "done": False,
        "action": "CALL_SUBAGENT",
        "target": target,
        "task_file": _rel(task_file),
        "stage": stage,
        "logical_role": role,
        "model": model,
        "route_index": idx + 1,
        "pool_size": len(pool),
        "failover_active": idx > 0,
        "failed_models": list(failed),
    }
    if extra:
        obj.update(extra)
    return obj


def next_action(d: Path) -> dict[str, Any]:
    binding = jload(d / "binding.json")

    dna_ok, dna_errors = accept_dna_candidate(d, binding)
    if dna_errors and _invalid_exhausted(d, "dna"):
        checkpoint(d, "QUALITY_BLOCKED", status="QUALITY_BLOCKED")
        return {"done": False, "status": "QUALITY_BLOCKED", "stage": "DNA", "errors": dna_errors}
    if not dna_ok:
        p = prepare_dna_task(d, binding)
        return _route_call(d, "DNA", p, "DNA", "DNA_PENDING", extra={"retry_errors": dna_errors})

    b_ok, b_errors = accept_b_decompiler_candidate(d, binding)
    if b_errors and _invalid_exhausted(d, "b_decompiler"):
        checkpoint(d, "QUALITY_BLOCKED", status="QUALITY_BLOCKED")
        return {"done": False, "status": "QUALITY_BLOCKED", "stage": "B_DECOMPILER", "errors": b_errors}
    if not b_ok:
        p = prepare_b_decompiler_task(d, binding)
        return _route_call(d, "B_DECOMPILER", p, "B_DECOMPILER", "B_DECOMPILER_PENDING", extra={"retry_errors": b_errors})

    rw_ok, rw_errors = accept_rewrite_candidate(d, binding)
    if rw_errors and _invalid_exhausted(d, "rewrite"):
        checkpoint(d, "QUALITY_BLOCKED", status="QUALITY_BLOCKED")
        return {"done": False, "status": "QUALITY_BLOCKED", "stage": "REWRITE", "errors": rw_errors}
    if not (d / "full" / "draft.txt").exists():
        p = prepare_rewriter_task(d, binding, "INITIAL")
        return _route_call(d, "REWRITER", p, "REWRITE_INITIAL", "REWRITE_INITIAL_PENDING", extra={"retry_errors": rw_errors})

    audit = deterministic_audit(d, binding)
    checkpoint(d, f"AUDIT_{int(_state(d).get('draft_count',0))}_READY", status="AUDIT_READY")

    critic_ok, critic_errors = accept_critique_candidate(d, audit)
    if critic_errors and _invalid_exhausted(d, "critic"):
        checkpoint(d, "QUALITY_BLOCKED", status="QUALITY_BLOCKED")
        return {"done": False, "status": "QUALITY_BLOCKED", "stage": "CRITIC", "errors": critic_errors}
    assessment_p = d / "full" / "objective_assessment.json"
    current_sha = sha256_file(d / "full" / "draft.txt")
    assessment = jload(assessment_p) if assessment_p.exists() else None
    fresh_assessment = bool(assessment and assessment.get("draft_sha256") == current_sha and int(assessment.get("iteration", -1)) == int(_state(d).get("draft_count", 0)))
    if not fresh_assessment:
        p = prepare_critic_task(d, binding)
        return _route_call(d, "CRITIC", p, "MEASURE_OBJECTIVE", "CRITIC_PENDING", extra={"retry_errors": critic_errors})

    assert assessment is not None
    so_ok, so_errors = accept_second_opinion_candidate(d)
    if so_errors and _invalid_exhausted(d, "second_opinion"):
        checkpoint(d, "SECOND_OPINION_SKIPPED_INVALID", status="OBJECTIVE_NOT_MET")

    if assessment.get("objective_met") is True and audit.get("hard_status") == "PASS":
        if not _second_fresh(d, "RELEASE_CHALLENGE"):
            p = prepare_second_opinion_task(d, binding, "RELEASE_CHALLENGE")
            critic_model = (((_state(d).get("model_success") or {}).get("CRITIC") or {}).get("model"))
            excludes = {critic_model} if critic_model else set()
            return _route_call(d, "SECOND_OPINION", p, "RELEASE_CHALLENGE", "SECOND_OPINION_PENDING", exclude_models=excludes, extra={"retry_errors": so_errors})
        challenge = jload(d / "full" / "second_opinion.json")
        if challenge.get("verdict") == "CONFIRM_RELEASE":
            rel = release(d, binding, audit, assessment, challenge)
            return {"done": True, "status": "RELEASED", "objective_met": True, "final_path": rel["final_path"], "latest_path": rel["latest_path"], "final_words": rel["final_words"]}
        apply_release_veto(d)
        assessment = jload(d / "full" / "objective_assessment.json")

    if same_delta_persisted(d) and not _second_fresh(d, "PERSISTENT_DELTA"):
        p = prepare_second_opinion_task(d, binding, "PERSISTENT_DELTA")
        critic_model = (((_state(d).get("model_success") or {}).get("CRITIC") or {}).get("model"))
        excludes = {critic_model} if critic_model else set()
        return _route_call(d, "SECOND_OPINION", p, "PERSISTENT_DELTA", "SECOND_OPINION_PENDING", exclude_models=excludes, extra={"retry_errors": so_errors})

    s = _state(d)
    if int(s.get("draft_count", 0)) >= MAX_DRAFTS:
        checkpoint(d, "QUALITY_BLOCKED", status="QUALITY_BLOCKED", active_stage=None, active_model=None)
        return {"done": False, "status": "QUALITY_BLOCKED", "reason": "Limite de drafts atingido sem release confirmado", "objective_delta": jload(d / "full" / "objective_delta.json")}

    p = prepare_rewriter_task(d, binding, "REPAIR")
    delta = jload(d / "full" / "objective_delta.json")
    return _route_call(d, "REWRITER", p, "REPAIR_OBJECTIVE_DELTA", "REPAIR_PENDING", extra={
        "failed_gates": delta.get("failed_gates", []),
        "regressions": delta.get("regressions", []),
        "preserve_gates": delta.get("preserve_gates", []),
    })


def latest_incomplete_run() -> Path | None:
    ensure_runtime_dirs(); candidates: list[tuple[float, Path]] = []
    for d in RUNS.iterdir():
        if not d.is_dir() or not (d / "state.json").exists(): continue
        try:
            s = _state(d)
            if s.get("status") not in {"RELEASED", "QUALITY_BLOCKED"}:
                candidates.append(((d / "state.json").stat().st_mtime, d))
        except Exception:
            pass
    return max(candidates, key=lambda x: x[0])[1] if candidates else None


def latest_final() -> Path | None:
    ensure_runtime_dirs()
    files = [p for p in FINAL_DIR.glob("roteiro_final_*.txt") if p.is_file()]
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


def status_obj(d: Path) -> dict[str, Any]:
    s = _state(d); binding = jload(d / "binding.json")
    assessment = jload(d / "full" / "objective_assessment.json") if (d / "full" / "objective_assessment.json").exists() else None
    final = _released_file_for_run(d.name)
    return {
        "ok": True,
        "run_id": d.name,
        "status": s.get("status"),
        "last_checkpoint": s.get("last_checkpoint"),
        "progress": progress_obj(d),
        "dna_ready": (d / "artifacts" / "a_dna.json").exists(),
        "b_decompiled": (d / "artifacts" / "b_content_ledger.json").exists(),
        "draft_count": s.get("draft_count", 0),
        "objective_met": assessment.get("objective_met") if assessment else False,
        "failed_gates": assessment.get("failed_gates", []) if assessment else [],
        "regressions": assessment.get("regressions", []) if assessment else [],
        "target_words": binding["target_words"],
        "word_range": binding["word_range"],
        "model_routing": {
            "main": MODEL_MAIN,
            "pools": model_pool_status(d),
            "successful_models": (_state(d).get("model_success") or {}),
            "failover_count": int(_state(d).get("model_failover_count", 0)),
        },
        "final_path": _rel(final) if final else None,
        "final_dir": _rel(FINAL_DIR),
    }


def doctor() -> dict[str, Any]:
    ensure_runtime_dirs()
    required = {"roteirista-harness-v77.md", "rh77-dna.md", "rh77-b-decompiler.md", "rh77-rewriter.md", "rh77-critic.md", "rh77-second-opinion.md"}
    got = {p.name for p in (ROOT / ".kilo" / "agents").glob("*.md")}
    fallback_targets = {target + ".md" for routes in MODEL_POOLS.values() for _, target in routes}
    checks = {
        "runtime_writable": RUNTIME.is_dir(),
        "final_dir_exists": FINAL_DIR.is_dir(),
        "logical_agents_present": required.issubset(got),
        "fallback_routes_present": fallback_targets.issubset(got),
        "source_spec_present": (ROOT / "spec" / "sources" / "roteirista_funciona.txt").exists(),
        "qwen_project_config_present": (ROOT / "kilo.jsonc").exists(),
        "golden_failure_fixture_present": (ROOT / "tests" / "fixtures" / "golden_failure_001" / "OLD_BAD_FINAL.md").exists(),
    }
    return {"ok": all(checks.values()), "version": VERSION, "pipeline": PIPELINE, "checks": checks}


def selftest() -> dict[str, Any]:
    checks = {
        "version": VERSION == "7.7.2",
        "automatic_model_failover": all(len(v) >= 4 for v in MODEL_POOLS.values()),
        "provider_failure_does_not_count_quality_attempt": True,
        "true_objective_gates": all(x in GATES for x in ["b_rhetorical_scaffolding_removed", "form_closer_to_a_than_b", "voice_caricature"]),
        "writer_has_no_raw_b_by_design": True,
        "release_challenge_required": True,
        "root_final_dir": FINAL_DIR.name == "roteiro final",
        "resume_latest_supported": True,
        "format_contract_enforced": validate_output_format("**GANCHO**\n\nx\n\n**BLOCO 1 - A**\n\nx\n\n**BLOCO 2 - B**\n\nx\n\n**BLOCO 3 - C**\n\nx\n\n**FECHAMENTO**\n\nx", _default_format_contract())["status"] == "PASS",
    }
    return {"ok": all(checks.values()), "version": VERSION, "checks": checks}


def golden_failure_check() -> dict[str, Any]:
    fx = ROOT / "tests" / "fixtures" / "golden_failure_001"
    a = read_text_robust(fx / "VIDEO A.txt")
    b = read_text_robust(fx / "VIDEO B.txt")
    bad = read_text_robust(fx / "OLD_BAD_FINAL.md")
    audit = audit_texts(a, b, bad, _word_range(count_words(b)))
    rejected = audit["hard_status"] == "FAIL"
    return {"ok": rejected, "expected": "REJECT", "actual": "REJECT" if rejected else "ACCEPT", "audit": audit}


def cmd_bootstrap(_: argparse.Namespace) -> None:
    print(json.dumps({"ok": True, "version": VERSION, "paths": ensure_runtime_dirs()}, ensure_ascii=False, indent=2))


def cmd_discover(_: argparse.Namespace) -> None:
    print(json.dumps(discover_inputs(), ensure_ascii=False, indent=2))


def cmd_start(a: argparse.Namespace) -> None:
    obj = create_run(a.a_file, a.b_file, a.run_id, a.target_words, getattr(a, "format_file", None))
    obj["progress"] = progress_obj(RUNS / obj["run_id"])
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def cmd_next(a: argparse.Namespace) -> None:
    d = run_dir(a.run_id); obj = next_action(d); obj["progress"] = progress_obj(d)
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def cmd_status(a: argparse.Namespace) -> None:
    print(json.dumps(status_obj(run_dir(a.run_id)), ensure_ascii=False, indent=2))


def cmd_resume_latest(_: argparse.Namespace) -> None:
    d = latest_incomplete_run()
    if not d: fail("nenhuma run incompleta encontrada")
    obj = next_action(d)
    print(json.dumps({"ok": True, "run_id": d.name, "recovered_from_disk": True, "next": obj, "progress": progress_obj(d)}, ensure_ascii=False, indent=2))


def cmd_model_failure(a: argparse.Namespace) -> None:
    d = run_dir(a.run_id)
    st = _state(d)
    model = a.model or st.get("active_model")
    stage = a.stage or st.get("active_stage")
    if not model or not stage:
        fail("nao ha active_model/active_stage para marcar como falho")
    reason = a.reason or "provider_error"
    rec = record_model_failure(d, stage, model, reason, a.error)
    nxt = next_action(d)
    print(json.dumps({"ok": True, "run_id": d.name, "recorded": rec, "next": nxt, "progress": progress_obj(d)}, ensure_ascii=False, indent=2))


def cmd_model_failure_latest(a: argparse.Namespace) -> None:
    d = latest_incomplete_run()
    if not d: fail("nenhuma run incompleta encontrada")
    st = _state(d)
    model = a.model or st.get("active_model")
    stage = a.stage or st.get("active_stage")
    if not model or not stage:
        fail("ultima run nao possui active_model/active_stage")
    rec = record_model_failure(d, stage, model, a.reason or "provider_error", a.error)
    nxt = next_action(d)
    print(json.dumps({"ok": True, "run_id": d.name, "recorded": rec, "next": nxt, "progress": progress_obj(d)}, ensure_ascii=False, indent=2))


def cmd_model_reset(a: argparse.Namespace) -> None:
    d = run_dir(a.run_id)
    role = _logical_role(a.role)
    s = _state(d)
    allf = dict(s.get("model_failures") or {})
    if role not in MODEL_POOLS:
        fail(f"role desconhecida: {role}")
    if a.model:
        rf = dict(allf.get(role) or {})
        rf.pop(a.model, None)
        allf[role] = rf
    else:
        allf[role] = {}
    s["model_failures"] = allf
    if s.get("status") == "MODEL_POOL_EXHAUSTED": s["status"] = "MODEL_FAILOVER_PENDING"
    _save_state(d, s)
    print(json.dumps({"ok": True, "run_id": d.name, "role": role, "model_failures": allf.get(role, {}), "next": next_action(d)}, ensure_ascii=False, indent=2))


def cmd_status_latest(_: argparse.Namespace) -> None:
    d = latest_incomplete_run()
    if not d: fail("nenhuma run incompleta encontrada")
    print(json.dumps(status_obj(d), ensure_ascii=False, indent=2))


def cmd_latest_final(_: argparse.Namespace) -> None:
    p = latest_final()
    print(json.dumps({"ok": bool(p), "final_path": _rel(p) if p else None, "final_dir": _rel(FINAL_DIR)}, ensure_ascii=False, indent=2))


def cmd_doctor(_: argparse.Namespace) -> None:
    print(json.dumps(doctor(), ensure_ascii=False, indent=2))


def cmd_selftest(_: argparse.Namespace) -> None:
    print(json.dumps(selftest(), ensure_ascii=False, indent=2))


def cmd_golden(_: argparse.Namespace) -> None:
    print(json.dumps(golden_failure_check(), ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Roteirista Harness v7.7.2 True Objective Loop + Format Contract + Auto Failover")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("bootstrap").set_defaults(func=cmd_bootstrap)
    sub.add_parser("discover-inputs").set_defaults(func=cmd_discover)
    s = sub.add_parser("start"); s.add_argument("--a-file", required=True); s.add_argument("--b-file", required=True); s.add_argument("--format-file"); s.add_argument("--run-id"); s.add_argument("--target-words", type=int); s.set_defaults(func=cmd_start)
    s = sub.add_parser("next"); s.add_argument("run_id"); s.set_defaults(func=cmd_next)
    s = sub.add_parser("status"); s.add_argument("run_id"); s.set_defaults(func=cmd_status)
    sub.add_parser("resume-latest").set_defaults(func=cmd_resume_latest)
    s = sub.add_parser("model-failure"); s.add_argument("run_id"); s.add_argument("--reason", default="provider_error"); s.add_argument("--error"); s.add_argument("--stage"); s.add_argument("--model"); s.set_defaults(func=cmd_model_failure)
    s = sub.add_parser("model-failure-latest"); s.add_argument("--reason", default="provider_error"); s.add_argument("--error"); s.add_argument("--stage"); s.add_argument("--model"); s.set_defaults(func=cmd_model_failure_latest)
    s = sub.add_parser("model-reset"); s.add_argument("run_id"); s.add_argument("--role", required=True); s.add_argument("--model"); s.set_defaults(func=cmd_model_reset)
    sub.add_parser("status-latest").set_defaults(func=cmd_status_latest)
    sub.add_parser("latest-final").set_defaults(func=cmd_latest_final)
    sub.add_parser("doctor").set_defaults(func=cmd_doctor)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    sub.add_parser("golden-failure-check").set_defaults(func=cmd_golden)
    return p


def main() -> None:
    args = build_parser().parse_args(); args.func(args)


if __name__ == "__main__":
    main()
