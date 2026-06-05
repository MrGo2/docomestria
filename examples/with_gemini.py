"""End-to-end LLM provenance example.

This example uses Gemini Flash Lite naming but works with any LLM (Claude,
OpenAI, local models) that returns JSON — `bind_provenance` only takes dicts.

Steps:
  1. Fuse the PDF into enriched items.
  2. Send a compact context to your LLM of choice (pseudo-code below).
  3. Bind the LLM's JSON output back to the source items.
  4. Detect hallucinations and role mismatches.

Install the optional extras first:

    pip install docomestria[llm]
"""

from __future__ import annotations

import sys
from pathlib import Path

from docomestria import fuse
from docomestria.llm import (
    bind_provenance,
    detect_hallucinations,
    detect_role_mismatches,
)


def main(pdf_path: str) -> int:
    # 1. Extract from PDF (3-engine fusion).
    result = fuse(pdf_path)
    items = list(result.items)
    print(f"fused {len(items)} items from {Path(pdf_path).name}")

    # 2. Pseudo-code for the actual LLM call (kept out of the library to keep
    #    docomestria provider-neutral). Example using google-genai:
    #
    #        from google import genai
    #        client = genai.Client()
    #        prompt = f"Extract titular data from:\n{render_items(items)}"
    #        response = client.models.generate_content(
    #            model="gemini-2.0-flash-lite",
    #            contents=prompt,
    #            config={"response_mime_type": "application/json"},
    #        )
    #        gemini_output = json.loads(response.text)
    #
    # For demonstration we use a hand-crafted dict that mirrors a real reply.
    gemini_output = {
        "datos_titular": {
            "apellidos": "ZAIDAN HASSAN",
            "nombre": "CLAUDIO ALEJANDRO",
            "nif": "51789286W",
        }
    }

    # 3. Bind values back to PDF provenance.
    bound = bind_provenance(gemini_output, items)
    for bv in bound:
        page = bv.page if bv.page is not None else "-"
        print(
            f"  {bv.field_name:32s} = {bv.value!r:32s} "
            f"page={page} method={bv.match_method:9s} score={bv.match_score:.2f}"
        )

    # 4. Detect issues.
    issues = list(detect_hallucinations(bound)) + list(detect_role_mismatches(bound))
    if not issues:
        print("no issues detected")
        return 0
    print(f"{len(issues)} issue(s) found:")
    for issue in issues:
        print(f"  [{issue.severity:6s}] {issue.issue_type:14s} — {issue.detail}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python with_gemini.py <pdf>", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
