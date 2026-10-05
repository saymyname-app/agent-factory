#!/usr/bin/env python3
"""PROTOTYPE JETABLE (af-0sayxf.18) -- moyen 1 : controle mecanique sur les
SOURCES (aucun navigateur) : tokens, polices, classes sans style, litteraux.
Lit out/prototype.html et out/delivered.html, ecrit out/check1.json.
"""
import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
GENERIC = {"system-ui", "sans-serif", "serif", "monospace", "ui-monospace", "ui-sans-serif", "inherit"}


def styles(html):
    return "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S))


def rules(css, ctx=""):
    """Yield (at-context, selector, declarations) -- flat, at-rules recursed."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    i, n = 0, len(css)
    while i < n:
        j = css.find("{", i)
        if j < 0:
            return
        head = css[i:j].strip()
        depth, k = 1, j + 1
        while k < n and depth:
            depth += {"{": 1, "}": -1}.get(css[k], 0)
            k += 1
        body = css[j + 1:k - 1]
        if head.startswith("@media") or head.startswith("@supports"):
            yield from rules(body, (ctx + " " + head).strip())
        elif not head.startswith("@"):
            yield ctx, head, body
        i = k


def decls(body):
    out = {}
    for d in body.split(";"):
        if ":" in d:
            k, v = d.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def tokens(rs):
    t = {}
    for ctx, sel, body in rs:
        if ":root" in sel or "data-theme" in sel or sel.strip() == "html":
            theme = "dark" if ("dark" in ctx or "dark" in sel) else "light"
            for k, v in decls(body).items():
                if k.startswith("--"):
                    t[theme + " " + k] = v.lower().replace(" ", "")
    return t


def families(rs, toks):
    fams = set()
    for _, _, body in rs:
        for k, v in decls(body).items():
            if k in ("font-family", "--font", "--mono"):
                for f in v.split(","):
                    f = f.strip().strip("\"'")
                    if f and not f.startswith("var(") and f.lower() not in GENERIC and not f.startswith("-"):
                        fams.add(f)
    return fams


def loaded_families(html):
    fams = set()
    for href in re.findall(r"<link[^>]+href=\"([^\"]*fonts[^\"]*)\"", html):
        for fam in re.findall(r"family=([^:&]+)", href):
            fams.add(fam.replace("+", " "))
    for ff in re.findall(r"@font-face\s*{[^}]*font-family\s*:\s*([^;}]+)", html):
        fams.add(ff.strip().strip("\"'"))
    return fams


def main():
    import sys
    other = sys.argv[1] if len(sys.argv) > 1 else "delivered"  # ou "mutant"
    proto = (OUT / "prototype.html").read_text(encoding="utf-8-sig")
    deliv = (OUT / (other + ".html")).read_text(encoding="utf-8-sig")
    pr_all = list(rules(styles(proto)))
    # Variante D = regles communes + .vd, et elle reutilise .vc et .va ; seule B est ecartee.
    pr = [r for r in pr_all if not re.match(r"\.vb\b", r[1].strip())]
    dr = list(rules(styles(deliv)))
    if other == "mutant":
        dr = [r for r in dr if not re.match(r"\.vb\b", r[1].strip())]
    pt, dt = tokens(pr), tokens(dr)
    # Regles (hors tokens) dont les declarations different, a selecteur egal.
    pmap = {(c, s): b.strip() for c, s, b in pr if ":root" not in s}
    rule_diff = [s for (c, s, b) in dr if ":root" not in s and (c, s) in pmap and pmap[(c, s)] != b.strip()]

    tok_missing = sorted(k for k in pt if k not in dt)
    tok_diff = sorted((k, pt[k], dt[k]) for k in pt if k in dt and pt[k] != dt[k])
    tok_extra = sorted(k for k in dt if k not in pt)

    body = deliv.split("</head>", 1)[-1]
    emitted = set(c for cl in re.findall(r"class=\"([^\"]+)\"", body) for c in cl.split())
    styled = set(re.findall(r"\.([A-Za-z_][\w-]*)", " ".join(r[1] for r in dr)))
    unstyled = sorted(emitted - styled)

    p_used, d_used = families(pr, pt), families(dr, dt)
    p_loaded, d_loaded = loaded_families(proto), loaded_families(deliv)

    def literals(rs):
        txt = " ".join(v for _, sel, b in rs if ":root" not in sel for k, v in decls(b).items() if not k.startswith("--"))
        return {"hex_colours": len(re.findall(r"#[0-9a-fA-F]{3,8}\b", txt)), "px_values": len(re.findall(r"\b\d+(?:\.\d+)?px\b", txt))}

    res = {
        "rule_count": {"prototype_all": len(pr_all), "prototype_variant_D": len(pr), "delivered": len(dr)},
        "tokens": {"prototype": len(pt), "delivered": len(dt), "identical": len([k for k in pt if dt.get(k) == pt[k]]),
                   "missing_in_delivered": tok_missing, "different": tok_diff, "extra_in_delivered": tok_extra},
        "fonts": {"prototype_named": sorted(p_used), "prototype_loaded": sorted(p_loaded),
                  "delivered_named": sorted(d_used), "delivered_loaded": sorted(d_loaded),
                  "delivered_named_not_loaded": sorted(d_used - d_loaded)},
        "classes": {"delivered_emitted": len(emitted), "delivered_unstyled": unstyled},
        "raw_literals_outside_tokens": {"prototype_variant_D": literals(pr), "delivered": literals(dr)},
    }
    res["same_selector_different_declarations"] = rule_diff
    (OUT / ("check1-%s.json" % other)).write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
