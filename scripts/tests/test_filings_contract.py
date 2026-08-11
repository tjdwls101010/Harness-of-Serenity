"""The filings layer's error contract, tested offline.

WHY THIS EXISTS. `serenity-filings` is the sole source of every structured disclosure number an
analysis uses — customer-concentration %, geographic revenue %, inventory composition, purchase
obligations. The doctrine routes around web search specifically because a web figure can silently be
the wrong ticker's or a stale period's, and an identity error of that kind is worse than noise: it
*looks* right while inverting the call. So this layer's failure mode matters more than most. If a
blocked EDGAR read produced a plausible-looking number instead of an explicit null, every guard
downstream would be intact and the input would still be wrong.

The scorecard agent's promises have already provably drifted in the wild — seven of seven real
scorecards violate the schema its own body pins. Nobody had run the equivalent check here.

WHAT THIS TESTS, AND WHAT IT DOES NOT.
Tested: the CLI's machine contract — on any failure it emits `{"error": "data_unavailable", ...}`,
never a traceback, never a fabricated value, and exits 0 so the caller reads the JSON rather than the
exit code. Offline and deterministic; `_company` is the single network chokepoint, so faulting it
faults every command.

NOT tested, and stated plainly rather than implied: whether the *subagent* honors "silence is null,
never a guess" and "quote the filing; cite where it came from." Those are judgment-holding promises
in an LLM's system prompt. Checking them needs a live agent loop with real filings — non-deterministic
and token-expensive, so it does not belong in a suite that must run on every change. What IS mechanized
here is the layer beneath: if the CLI cannot fabricate, the agent's most dangerous failure mode has no
raw material to work with. The residue — an agent that ignores a clean `data_unavailable` and answers
from memory anyway — remains an accepted, unverified gap. Write it down rather than let the presence
of a test file imply coverage it does not have.

DELIBERATELY NOT WIRED INTO `validate`. `validate` runs the hook fixture suite and is called by
`session_status.py` behind a 30s timeout at every SessionStart. Anything network-bound in that path
turns a timeout into a silent unverified session, which is the exact blind spot that path was just
fixed to remove. pytest is never invoked by `validate`, so living here is what keeps that true.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
ROOT = SCRIPTS_DIR.parent
CLI = SCRIPTS_DIR / "serenity_filings.py"

# One representative command per output shape, so a contract break in any shape is caught. Each is a
# (subcommand, extra-args) pair; every one routes through `_company`.
COMMANDS = [
    ("company", []),
    ("financials", []),
    ("segments", []),
    ("filings", []),
    ("eightk", []),
    ("xbrl-facts", ["--concept", "Revenues"]),
]


@pytest.fixture(scope="module")
def filings_module():
    sys.path.insert(0, str(SCRIPTS_DIR))
    import serenity_filings  # noqa: PLC0415
    return serenity_filings


@pytest.mark.parametrize("subcommand,extra", COMMANDS)
def test_network_failure_yields_data_unavailable_not_a_traceback(
    filings_module, monkeypatch, capsys, subcommand, extra
):
    """A blocked or throttled EDGAR read must surface as an explicit null, never as a value.

    Faults `_company`, the single point every command reaches the network through — so this covers
    the 403 EDGAR genuinely returns under a bad identity, a 429 throttle, and a hard network outage
    without distinguishing between them, which is correct: the caller's obligation is identical in
    all three ("data unavailable, proceed without it, sections marked").
    """
    def blocked(*_args, **_kwargs):
        raise RuntimeError("HTTPError: 403 Client Error: Forbidden")

    monkeypatch.setattr(filings_module, "_company", blocked)
    parser = filings_module.build_parser() if hasattr(filings_module, "build_parser") else None
    if parser is None:
        pytest.skip("CLI does not expose build_parser(); covered by the subprocess test below")
    args = parser.parse_args([subcommand, "AAPL", *extra])
    result = args.func(args)

    assert isinstance(result, dict), f"{subcommand} returned {type(result).__name__}, not a dict"
    assert result.get("error") == "data_unavailable", (
        f"{subcommand} swallowed a blocked read into {result!r}. A blocked EDGAR line must be an "
        f"explicit null the caller can hard-stop on — a plausible-looking value here is the "
        f"'data error is itself the mispricing' failure, aimed at the harness's own input."
    )
    assert "403" in result.get("detail", ""), "the detail must carry what actually failed"
    # No fabricated payload rides along with the error.
    for fabricated in ("company_relationships", "country_exposure", "critical_inputs",
                       "financing_facts", "revenue", "customers"):
        assert fabricated not in result, (
            f"{subcommand} emitted `{fabricated}` alongside an error — a partial payload beside a "
            f"failure reads as data"
        )
    capsys.readouterr()


def test_cli_emits_json_and_exits_zero_on_a_bad_ticker():
    """End-to-end through the real process boundary: stdout parses as JSON, exit code is 0.

    Exit 0 is deliberate and documented in the CLI's own module docstring — the caller must read the
    JSON rather than branch on the exit code, because a partial success is still JSON. This test is
    what makes that a contract rather than a comment.

    This one MAY touch the network: the ticker is syntactically valid and cannot resolve, so
    edgartools may consult SEC's ticker file before failing. That is acceptable here and would not be
    in the hook suite — pytest is developer-invoked, while the hook suite runs inside `validate`
    behind `session_status.py`'s 30s SessionStart timeout. Either outcome (a resolution failure or a
    network failure) exercises the same contract, so an offline machine sees the same assertion pass.
    """
    p = subprocess.run(
        [sys.executable, str(CLI), "company", "ZZZZNOTAREALTICKER"],
        capture_output=True, text=True, cwd=ROOT, timeout=120,
    )
    assert p.returncode == 0, f"exited {p.returncode}; callers are told to read the JSON, not the code"
    payload = json.loads(p.stdout)  # raises if a traceback leaked into stdout
    assert payload.get("error") == "data_unavailable"
    assert payload.get("detail"), "an error with no detail cannot be acted on"


def test_agent_body_still_pins_the_two_hard_rules():
    """The agent's two fabrication guards must survive edits to its body.

    Mechanically weak — it greps for the rule, it cannot confirm the model obeys it. Kept anyway
    because the failure it catches is real and silent: someone tightening the agent's prose deletes
    the sentence that makes silence a null, and nothing else in the repository would notice. This is
    the same class of check as `validate`'s schema sentinels, with the same honest limit.
    """
    body = (ROOT / ".claude" / "agents" / "serenity-filings.md").read_text(encoding="utf-8")
    assert "Silence is null" in body, "the silence-is-null rule was removed from the agent body"
    assert "cite where it came from" in body, "the quote-and-cite rule was removed from the agent body"
    assert "never judge" in body.lower(), "the extract-never-judge boundary was removed"
