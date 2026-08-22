"""XTBL engine: parse / query / patch / diff with comment preservation.

Saints Row XTBLs are XML with two conventions that break naive ElementTree:
  - attributes carry the record identity (<Name>Foo</Name> as FIRST child)
  - inline comments document fields and MUST survive round-trips
We keep comments and formatting by parsing to a lightweight node tree.
"""
import xml.etree.ElementTree as ET
import re


class Xtbl:
    def __init__(self, text=None):
        self.comments_before_root = []
        self.root = None
        if text is not None:
            self.parse(text)

    def parse(self, text: str):
        # strip BOM
        if text.startswith("\ufeff"):
            text = text[1:]
        # capture leading comments before <root...>
        pre = re.match(r"^(.*?)<root\b", text, re.S | re.I)
        if pre:
            for m in re.finditer(r"<!--(.*?)-->", pre.group(1), re.S):
                self.comments_before_root.append(m.group(1))
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        self.root = ET.fromstring(text, parser=parser)
        return self

    @classmethod
    def load(cls, path):
        with open(path, "r", encoding="utf-8") as f:
            return cls(f.read())

    def tostring(self) -> str:
        return _serialize(self.root)

    def records(self):
        """Record elements. Real XTBLs use two layouts:
        - root/Records/<Record>   (customization_items etc.)
        - root/Table/<ItemType>   (weapons.xtbl: Table/Weapon, templates
                                   live in sibling TableTemplates - excluded)
        """
        recs = self.root.find("Records")
        if recs is None:
            recs = self.root.find("Table")
        if recs is None:
            return []
        return [c for c in recs if isinstance(c.tag, str)]

    def find_record(self, name: str):
        low = name.lower()
        for r in self.records():
            n = r.find("Name")
            if n is not None and (n.text or "").strip().lower() == low:
                return r
        return None

    def get_field(self, record_name: str, field_path: str):
        """field_path like 'Damage' or 'Physics/Ragdoll_Impulse'."""
        r = self.find_record(record_name)
        if r is None:
            raise KeyError(f"record {record_name!r} not found")
        el = r
        for part in field_path.split("/"):
            el = el.find(part)
            if el is None:
                raise KeyError(f"field {field_path!r} not found in {record_name!r}")
        return el

    def set_field(self, record_name: str, field_path: str, value):
        el = self.get_field(record_name, field_path)
        el.text = _fmt_value(el.text, value)

    def multiply_field(self, record_name: str, field_path: str, factor: float):
        cur = _to_number(self.get_field(record_name, field_path).text)
        self.set_field(record_name, field_path, cur * factor)
        return cur * factor

    def clone_record(self, source_name: str, new_name: str) -> bool:
        src = self.find_record(source_name)
        if src is None:
            raise KeyError(source_name)
        if self.find_record(new_name) is not None:
            return False
        import copy
        dup = copy.deepcopy(src)
        name_el = dup.find("Name")
        if name_el is not None:
            name_el.text = new_name
        self.root.find("Records").append(dup)
        return True

    def remove_record(self, name: str) -> bool:
        r = self.find_record(name)
        if r is None:
            return False
        self.root.find("Records").remove(r)
        return True

    def validate(self):
        problems = []
        names = []
        for r in self.records():
            n = r.find("Name")
            names.append((n.text or "").strip() if n is not None else None)
        seen = {}
        for i, nm in enumerate(names):
            if nm is None:
                problems.append({"code": "SRF-XTBL-E01", "message": f"record #{i} has no <Name>"})
                continue
            key = nm.lower()
            if key in seen:
                problems.append({"code": "SRF-XTBL-E02",
                                 "message": f"duplicate record Name {nm!r} (rows {seen[key]} and {i})"})
            else:
                seen[key] = i
        try:
            self.tostring()
        except Exception as e:
            problems.append({"code": "SRF-XTBL-E03", "message": f"re-serialization failed: {e}"})
        return problems


# ---------- semantic diff ----------

def semantic_diff(a: "Xtbl", b: "Xtbl"):
    changes = []
    ra = {(_name(r) or f"#row{i}").lower(): r for i, r in enumerate(a.records())}
    rb = {(_name(r) or f"#row{i}").lower(): r for i, r in enumerate(b.records())}
    for k, r in rb.items():
        if k not in ra:
            changes.append({"type": "record_added", "record": k})
            continue
        _diff_elem(ra[k], rb[k], k, "", changes)
    for k in ra:
        if k not in rb:
            changes.append({"type": "record_removed", "record": k})
    return changes


def _diff_elem(ea, eb, rec, path, out):
    ca = [c for c in ea if isinstance(c.tag, str)]
    cb = [c for c in eb if isinstance(c.tag, str)]
    ta = {c.tag: c for c in ca}
    tb = {c.tag: c for c in cb}
    for t, bel in tb.items():
        p = f"{path}/{t}" if path else t
        if t not in ta:
            out.append({"type": "field_added", "record": rec, "field": p,
                        "new": (bel.text or "")})
            continue
        ael = ta[t]
        at = (ael.text or "")
        bt = (bel.text or "")
        kids_a = [c for c in ael if isinstance(c.tag, str)]
        kids_b = [c for c in bel if isinstance(c.tag, str)]
        if kids_a or kids_b:
            _diff_elem(ael, bel, rec, p, out)
        elif at != bt:
            out.append({"type": "field_changed", "record": rec, "field": p,
                        "old": at, "new": bt})
    for t, ael in ta.items():
        if t not in tb:
            p = f"{path}/{t}" if path else t
            out.append({"type": "field_removed", "record": rec, "field": p,
                        "old": (ael.text or "")})


# ---------- helpers ----------

def _name(r):
    n = r.find("Name")
    return (n.text or "").strip() if n is not None else None


_NUM_RE = re.compile(r"^-?\d+(\.\d+)?$")

def _to_number(text):
    t = (text or "").strip()
    if not _NUM_RE.match(t):
        raise ValueError(f"value {text!r} is not numeric")
    f = float(t)
    return int(f) if f.is_integer() and "." not in t else f


def _fmt_value(old_text, new_value):
    """Keep float formatting sane: avoid 106.25000000000001-style artifacts."""
    if isinstance(new_value, float):
        s = repr(round(new_value, 6)).rstrip("0").rstrip(".")
        if old_text and "." not in old_text and new_value.is_integer():
            return str(int(new_value))
        return s
    return str(new_value)


def _serialize(elem) -> str:
    parts = [_ser_rec(elem, 0)]
    return "".join(parts)


def _ser_rec(e, depth, lead=None) -> str:
    pad = "\t" * depth
    head = _esc(lead) if lead else ""
    inner = []
    for node in e:
        if not isinstance(node.tag, str):  # Comment
            comment_text = self_text(node)
            inner.append(f"<!--{comment_text}-->")
        else:
            node_lead = (node.text or "").strip()
            if len(node):
                inner.append(_ser_rec(node, depth + 1, lead=node_lead or None))
            elif node_lead:
                inner.append(f"{pad}\t<{node.tag}>{_esc(node_lead)}</{node.tag}>")
            else:
                inner.append(f"{pad}\t<{node.tag} />")
    body = "\n" + "\n".join(inner) + ("\n" + pad if inner else "")
    attrs = "".join(f' {k}="{v}"' for k, v in e.attrib.items())
    return f"{pad}<{e.tag}{attrs}>{head}{body}</{e.tag}>"


def self_text(comment_node) -> str:
    # ElementTree stores comment payload on .tail? No - it keeps it via
    # 'comment' function target; safest is attrib-free node text trick:
    return getattr(comment_node, "text", "") or ""


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


if __name__ == "__main__":
    sample = """<?xml version="1.0"?>
<root><!-- top comment -->
<Table_Name>Weapons</Table_Name>
	<Records>
		<Record><!-- dmg -->
			<Name>Pump Shotgun</Name>
			<Weapon>
				<Damage>85</Damage>
				<Impulse>240</Impulse>
				<Flags />
			</Weapon>
		</Record>
	</Records>
</root>"""
    x = Xtbl(sample)
    x.multiply_field("Pump Shotgun", "Weapon/Damage", 1.25)
    x.set_field("Pump Shotgun", "Weapon/Impulse", 420)
    out = x.tostring()
    assert "<!--dmg-->" in out.replace(" ", "") and "<!--topcomment-->" in out.replace(" ", ""), "comments lost!"
    y = Xtbl(out)
    d = semantic_diff(Xtbl(sample), y)
    kinds = {(c["type"], c["record"]) for c in d}
    assert ("field_changed", "pump shotgun") in kinds, d
    assert len([c for c in d if c["type"] == "field_changed"]) == 2, d
    probs = y.validate()
    assert not probs, probs
    print("xtbl round-trip + semantic diff OK")
