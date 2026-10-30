"""Shared constants and helpers for the jurisprudencia-pt pipeline (standard library only)."""
import gzip
import json
import re
import struct
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path

VERSION = "0.1"
USER_AGENT = "LawAgents-jurisprudencia (github.com/LawAgents)"
HOST = "https://www.dgsi.pt"
REPO_URL = "https://github.com/LawAgents/jurisprudencia-pt"

# Fixed texts (pt-PT on purpose: data shown to users).
TEXT_VERSION = "sumário e metadados, sem texto integral"
LEGAL_NOTICE = ("Sem valor legal: só a decisão publicada pelo tribunal faz fé. Confirma na fonte (DGSI) antes de citar. "
                "Não substitui aconselhamento jurídico.")
NO_SUMMARY = "Sem sumário publicado. Texto integral na fonte."
SUMMARY_HEADING = "## Sumário"
# A sumário longer than this is almost always the full text pasted into the sumário field by the court: it is not
# published (the fixed no-sumário sentence is used) and it is counted in excluded.json.
MAX_SUMMARY_CHARS = 20000

# Front matter fields in file order.
FIELDS = ["id", "title", "tribunal", "secao", "processo", "relator", "data", "votacao", "meio_processual", "decisao",
          "descritores", "texto_integral", "privacidade", "source", "ecli", "ecli_confirmed", "retrieved",
          "text_version", "legal_notice"]
REQUIRED = ["id", "title", "tribunal", "processo", "data", "source", "retrieved", "text_version", "legal_notice"]
DATE_FIELDS = {"data", "retrieved"}
BOOL_FIELDS = {"ecli_confirmed"}
LIST_FIELDS = {"descritores"}
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SOURCE_RE = re.compile(r"^https://www\.dgsi\.pt/([a-z0-9]+)\.nsf/[0-9a-f]{32}/([0-9a-f]{32})\?OpenDocument$")
ROOT_INDEX = re.compile(r"^(indice(-.*)?|descritores(-.*)?)\.md$")


def fold(s):
    """Lower case without accents."""
    s = unicodedata.normalize("NFD", str(s or ""))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", fold(s)).strip("-")


class Tribunal:
    def __init__(self, id, nome, caminho, sigla, lista):
        self.id, self.nome, self.caminho, self.sigla, self.lista = id, nome, caminho, sigla, lista
        self.db = caminho.strip("/").removesuffix(".nsf")

    def __repr__(self):
        return f"Tribunal({self.id})"


def load_tribunais(path):
    """{id: Tribunal} from config/tribunais.txt (`id | nome | caminho | sigla ECLI | lista`)."""
    out = {}
    for n, ln in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        c = [x.strip() for x in ln.split("|")]
        if len(c) != 5 or not (c[0] and c[1] and c[2]) or c[4] not in ("recentes", "completa"):
            raise ValueError(f"{path}:{n}: expected `id | nome | caminho | sigla ECLI | recentes/completa`")
        if c[0] in out:
            raise ValueError(f"{path}:{n}: duplicate id {c[0]}")
        out[c[0]] = Tribunal(*c)
    return out


def load_retirada(path):
    """Set of ids that must never be published."""
    p = Path(path)
    if not p.exists():
        return set()
    return {ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")}


def format_frontmatter(meta):
    """Flat `key: value` lines; strings JSON-quoted (valid YAML), lists as JSON arrays, dates bare ISO."""
    lines = ["---"]
    for k in FIELDS:
        v = meta.get(k)
        if v is None or v == "" or v == []:
            continue
        if k in BOOL_FIELDS:
            lines.append(f"{k}: {'true' if v else 'false'}")
        elif k in DATE_FIELDS:
            lines.append(f"{k}: {v}")
        elif k in LIST_FIELDS:
            lines.append(f"{k}: {json.dumps(list(v), ensure_ascii=False)}")
        else:
            lines.append(f"{k}: {json.dumps(str(v), ensure_ascii=False)}")
    lines.append("---")
    return "\n".join(lines)


def parse_frontmatter(text):
    """Return (dict, body). Raises ValueError when there is no well-formed front matter."""
    if not text.startswith("---\n"):
        raise ValueError("missing front matter")
    end = text.find("\n---\n", 4)
    if end < 0:
        if text.endswith("\n---"):
            end = len(text) - 4
        else:
            raise ValueError("unterminated front matter")
    meta = {}
    for ln in text[4:end].split("\n"):
        if not ln.strip():
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", ln)
        if not m:
            raise ValueError(f"bad front matter line: {ln!r}")
        k, v = m.group(1), m.group(2).strip()
        if v.startswith('"') or v.startswith("["):
            v = json.loads(v)
        elif v in ("true", "false"):
            v = v == "true"
        elif re.fullmatch(r"-?\d+", v):
            v = int(v)
        meta[k] = v
    return meta, text[end + 5:]


def read_frontmatter(path, head_bytes=16384):
    """(front matter dict, head text) of a file, reading only its head when possible."""
    with open(path, "rb") as fh:
        head = fh.read(head_bytes).decode("utf-8", "replace")
    if "\n---\n" not in head[4:]:
        head = Path(path).read_text(encoding="utf-8")
    return parse_frontmatter(head)[0], head


def atomic_write(path, data, binary=False):
    """Write via tmp + rename so a reader never sees a partial file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    if binary:
        tmp.write_bytes(data)
    else:
        tmp.write_text(data, encoding="utf-8", newline="\n")
    tmp.replace(path)


def gz_bytes(data, mtime=None):
    """gzip with the fetch time in the header, so the retrieval date survives copies of the cache."""
    ts = mtime if mtime is not None else datetime.now(timezone.utc).timestamp()
    return gzip.compress(data, compresslevel=6, mtime=int(ts))


def gz_mtime_date(path):
    """ISO date (UTC) stored in the gzip header of `path`."""
    with open(path, "rb") as fh:
        head = fh.read(10)
    ts = struct.unpack("<I", head[4:8])[0]
    return datetime.fromtimestamp(ts, timezone.utc).date().isoformat()


def read_gz(path):
    with gzip.open(path, "rb") as fh:
        return fh.read()


def valid_iso_date(s):
    if not isinstance(s, str) or not ISO_DATE.match(s):
        return False
    try:
        date.fromisoformat(s)
    except ValueError:
        return False
    return True


def iter_decision_files(root, tribunais):
    """Every markdown file of the tribunal folders under root, sorted."""
    root = Path(root)
    for tid in sorted(tribunais):
        if (root / tid).is_dir():
            yield from sorted((root / tid).rglob("*.md"))
