from __future__ import annotations

import hashlib
import json
import multiprocessing
from pathlib import Path

import pytest

from serenity_v2.runtime import RunStore, SerenityError


def _concurrent_start(root: str, barrier, results) -> None:
    try:
        barrier.wait(timeout=10)
        manifest = RunStore(Path(root)).start(
            mode="single-name",
            question="Can concurrent starts claim one lifecycle?",
            subjects=["NVDA"],
            as_of="2026-08-17",
        )
        results.put({"ok": True, "run": manifest})
    except SerenityError as exc:
        results.put(exc.payload)


def _concurrent_refresh(root: str, barrier, results, run_id: str, expected_attachment: dict, path: str) -> None:
    try:
        barrier.wait(timeout=10)
        manifest = RunStore(Path(root)).refresh_artifact(
            run_id,
            name="hypothesis-ledger",
            expected_attachment=expected_attachment,
            path=Path(path),
            schema_id="urn:serenity:schema:hypothesis-ledger:1",
            phase="hypotheses_updated",
        )
        results.put({"ok": True, "run": manifest})
    except SerenityError as exc:
        results.put(exc.payload)


def _concurrent_publish(root: str, barrier, results, run_id: str, path: str, content: bytes) -> None:
    try:
        barrier.wait(timeout=10)
        manifest = RunStore(Path(root)).publish_artifact(
            run_id,
            name="hypothesis-ledger",
            path=Path(path),
            content=content,
            schema_id="urn:serenity:schema:hypothesis-ledger:1",
            phase="hypotheses_updated",
        )
        results.put({"ok": True, "run": manifest})
    except SerenityError as exc:
        results.put(exc.payload)


def _concurrent_decision_finalize(root: str, barrier, results, run_id: str, decision_path: str) -> None:
    try:
        barrier.wait(timeout=10)

        def publish() -> Path:
            path = Path(decision_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{"decision":"immutable"}\n', encoding="utf-8")
            (path.parent.parent / "current.json").write_text('{"current":"v001"}\n', encoding="utf-8")
            return path

        manifest = RunStore(Path(root)).finalize_with_publication(run_id, decision_path=Path(decision_path), publish=publish)
        results.put({"ok": True, "run": manifest})
    except SerenityError as exc:
        results.put(exc.payload)


def _concurrent_abandon(root: str, barrier, results, run_id: str) -> None:
    try:
        barrier.wait(timeout=10)
        manifest = RunStore(Path(root)).abandon(run_id, "concurrent terminal transition")
        results.put({"ok": True, "run": manifest})
    except SerenityError as exc:
        results.put(exc.payload)


def _concurrent_publish_or_refresh(root: str, barrier, results, run_id: str, expected_attachment: dict, path: str, content: bytes) -> None:
    try:
        barrier.wait(timeout=10)
        manifest = RunStore(Path(root)).publish_or_refresh_artifact(
            run_id,
            name="hypothesis-ledger",
            expected_attachment=expected_attachment,
            path=Path(path),
            content=content,
            schema_id="urn:serenity:schema:hypothesis-ledger:1",
            phase="hypotheses_updated",
        )
        results.put({"ok": True, "run": manifest})
    except SerenityError as exc:
        results.put(exc.payload)


def test_concurrent_runstore_starts_claim_exactly_one_active_run(tmp_path: Path) -> None:
    context = multiprocessing.get_context("fork")
    process_count = 12
    barrier = context.Barrier(process_count)
    results = context.Queue()
    processes = [context.Process(target=_concurrent_start, args=(str(tmp_path), barrier, results)) for _ in range(process_count)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=20)
    assert all(process.exitcode == 0 for process in processes)

    payloads = [results.get(timeout=5) for _ in processes]
    successes = [payload for payload in payloads if payload["ok"] is True]
    failures = [payload for payload in payloads if payload["ok"] is False]

    assert len(successes) == 1
    assert len(failures) == len(processes) - 1
    assert all(payload["error"]["code"] in {"invalid_lifecycle", "persistence_conflict"} for payload in failures)
    assert all(payload["error"]["exit_code"] in {3, 5} for payload in failures)

    manifests = [json.loads(path.read_text(encoding="utf-8")) for path in (tmp_path / ".serenity" / "runs").glob("run-*/run-manifest.json")]
    assert len(manifests) == 1
    assert [manifest["run_id"] for manifest in manifests if manifest["status"] == "OPEN"] == [successes[0]["run"]["run_id"]]

    pointer = json.loads((tmp_path / ".serenity" / "active-run.json").read_text(encoding="utf-8"))
    unsigned = {key: value for key, value in pointer.items() if key != "content_hash"}
    expected_hash = hashlib.sha256(json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    assert pointer["content_hash"] == expected_hash
    assert pointer == {
        "run_id": manifests[0]["run_id"],
        "status": "OPEN",
        "updated_at": manifests[0]["updated_at"],
        "content_hash": expected_hash,
    }
    assert RunStore(tmp_path).read_active() == pointer
    assert RunStore(tmp_path).list_open() == manifests


def test_reconcile_restores_an_active_pointer_after_start_crash_boundary(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    run = store.start(
        mode="single-name",
        question="Can an interrupted start restore its active pointer?",
        subjects=["NVDA"],
        as_of="2026-08-17",
    )
    store.active_path.unlink()

    recovered = store.reconcile()

    assert recovered["active_run"] == store.read_active()
    assert recovered["active_run"]["run_id"] == run["run_id"]
    assert recovered["reconciled"] is True


def test_reconcile_completes_terminal_pointer_boundaries_after_abandon_and_close(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    abandoned = store.start(
        mode="single-name",
        question="Can an interrupted abandon clear the stale pointer?",
        subjects=["NVDA"],
        as_of="2026-08-17",
    )
    open_pointer = json.loads(store.active_path.read_text(encoding="utf-8"))
    store.abandon(abandoned["run_id"], "fixture complete")
    store.active_path.write_text(json.dumps(open_pointer), encoding="utf-8")

    assert store.reconcile() == {"reconciled": True, "active_run": None}
    assert store.read(abandoned["run_id"])["status"] == "ABANDONED"

    closed = store.start(
        mode="single-name",
        question="Can an interrupted close clear the stale pointer?",
        subjects=["AMD"],
        as_of="2026-08-17",
    )
    decision_path = tmp_path / "decision.json"
    decision_path.write_text("{}\n", encoding="utf-8")
    store.finalize(closed["run_id"], decision_path=decision_path)
    finalized_pointer = json.loads(store.active_path.read_text(encoding="utf-8"))
    store.close(closed["run_id"], "fixture complete")
    store.active_path.write_text(json.dumps(finalized_pointer), encoding="utf-8")

    assert store.reconcile() == {"reconciled": True, "active_run": None}
    assert store.read(closed["run_id"])["status"] == "CLOSED"


def test_reconcile_updates_a_stale_open_pointer_after_finalize_boundary(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    run = store.start(
        mode="single-name",
        question="Can an interrupted finalization restore the finalized pointer?",
        subjects=["NVDA"],
        as_of="2026-08-17",
    )
    open_pointer = json.loads(store.active_path.read_text(encoding="utf-8"))
    decision_path = tmp_path / "decision.json"
    decision_path.write_text("{}\n", encoding="utf-8")
    finalized = store.finalize(run["run_id"], decision_path=decision_path)
    store.active_path.write_text(json.dumps(open_pointer), encoding="utf-8")

    recovered = store.reconcile()

    assert recovered["active_run"]["status"] == "FINALIZED"
    assert recovered["active_run"]["run_id"] == finalized["run_id"]


def test_publish_artifact_creates_and_attaches_one_content_addressed_file(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    run = store.start(
        mode="single-name",
        question="Can a published artifact be attached atomically?",
        subjects=["NVDA"],
        as_of="2026-08-17",
    )
    artifact_path = tmp_path / "published-ledger.json"
    content = b'{"revision":1}\n'

    published = store.publish_artifact(
        run["run_id"],
        name="hypothesis-ledger",
        path=artifact_path,
        content=content,
        schema_id="urn:serenity:schema:hypothesis-ledger:1",
        phase="hypotheses_updated",
    )

    attachment = published["artifacts"]["hypothesis-ledger"]
    assert artifact_path.read_bytes() == content
    assert attachment["content_hash"] == hashlib.sha256(content).hexdigest()
    assert attachment["path"] == "published-ledger.json"


def test_publish_or_refresh_artifact_cas_keeps_the_current_file_unchanged_for_a_stale_writer(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    run = store.start(
        mode="single-name",
        question="Can an immutable candidate supersede an attached artifact safely?",
        subjects=["NVDA"],
        as_of="2026-08-17",
    )
    first_path = tmp_path / "ledger-v1.json"
    first = store.publish_artifact(
        run["run_id"],
        name="hypothesis-ledger",
        path=first_path,
        content=b'{"revision":1}\n',
        schema_id="urn:serenity:schema:hypothesis-ledger:1",
    )
    expected = dict(first["artifacts"]["hypothesis-ledger"])
    second_path = tmp_path / "ledger-v2.json"

    refreshed = store.publish_or_refresh_artifact(
        run["run_id"],
        name="hypothesis-ledger",
        expected_attachment=expected,
        path=second_path,
        content=b'{"revision":2}\n',
        schema_id="urn:serenity:schema:hypothesis-ledger:1",
        phase="hypotheses_updated",
    )

    current = refreshed["artifacts"]["hypothesis-ledger"]
    assert current["path"] == "ledger-v2.json"
    assert first_path.read_bytes() == b'{"revision":1}\n'
    stale_path = tmp_path / "ledger-v3.json"
    with pytest.raises(SerenityError) as stale:
        store.publish_or_refresh_artifact(
            run["run_id"],
            name="hypothesis-ledger",
            expected_attachment=expected,
            path=stale_path,
            content=b'{"revision":3}\n',
            schema_id="urn:serenity:schema:hypothesis-ledger:1",
        )
    assert stale.value.payload["error"]["code"] == "persistence_conflict"
    assert refreshed["artifacts"]["hypothesis-ledger"] == RunStore(tmp_path).read(run["run_id"])["artifacts"]["hypothesis-ledger"]
    assert not stale_path.exists()


def test_concurrent_publish_or_refresh_allows_one_candidate_and_leaves_no_stale_candidate(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    run = store.start(
        mode="single-name",
        question="Can two candidate revisions compare-and-swap one attachment?",
        subjects=["NVDA"],
        as_of="2026-08-17",
    )
    first_path = tmp_path / "ledger-v1.json"
    first = store.publish_artifact(
        run["run_id"],
        name="hypothesis-ledger",
        path=first_path,
        content=b'{"revision":1}\n',
        schema_id="urn:serenity:schema:hypothesis-ledger:1",
    )
    expected = dict(first["artifacts"]["hypothesis-ledger"])
    candidates = [(tmp_path / "ledger-v2a.json", b'{"revision":2}\n'), (tmp_path / "ledger-v2b.json", b'{"revision":3}\n')]
    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(2)
    results = context.Queue()
    processes = [
        context.Process(target=_concurrent_publish_or_refresh, args=(str(tmp_path), barrier, results, run["run_id"], expected, str(path), content))
        for path, content in candidates
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=20)
    assert all(process.exitcode == 0 for process in processes)

    payloads = [results.get(timeout=5) for _ in processes]
    successes = [payload for payload in payloads if payload["ok"] is True]
    failures = [payload for payload in payloads if payload["ok"] is False]
    assert len(successes) == 1
    assert [payload["error"]["code"] for payload in failures] == ["persistence_conflict"]
    current = RunStore(tmp_path).read(run["run_id"])["artifacts"]["hypothesis-ledger"]
    assert current == successes[0]["run"]["artifacts"]["hypothesis-ledger"]
    assert sum(path.exists() for path, _ in candidates) == 1


def test_pending_decision_publication_blocks_close_until_the_same_finalizer_retries(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    run = store.start(
        mode="single-name",
        question="Can a published decision recover before an abandon can win?",
        subjects=["NVDA"],
        as_of="2026-08-17",
    )
    decision_path = tmp_path / "records" / "decisions" / "lineage-nvda" / "v001" / "decision.json"

    def publish_then_fail() -> Path:
        decision_path.parent.mkdir(parents=True, exist_ok=True)
        decision_path.write_text('{"decision":"immutable"}\n', encoding="utf-8")
        raise RuntimeError("simulated process interruption after publication")

    with pytest.raises(RuntimeError, match="simulated process interruption"):
        store.finalize_with_publication(run["run_id"], decision_path=decision_path, publish=publish_then_fail)
    with pytest.raises(SerenityError) as closed_early:
        store.close(run["run_id"], "must not close without the current decision pointer")
    assert closed_early.value.payload["error"]["code"] == "persistence_conflict"
    with pytest.raises(SerenityError) as abandoned_early:
        store.abandon(run["run_id"], "must retry finalization first")
    assert abandoned_early.value.payload["error"]["code"] == "persistence_conflict"
    assert store.read(run["run_id"])["status"] == "OPEN"
    current_path = decision_path.parent.parent / "current.json"
    assert not current_path.exists()

    def publish_retry() -> Path:
        current_path.write_text('{"current":"v001"}\n', encoding="utf-8")
        return decision_path

    finalized = store.finalize_with_publication(run["run_id"], decision_path=decision_path, publish=publish_retry)
    assert finalized["status"] == "FINALIZED"
    assert current_path.is_file()
    assert store.close(run["run_id"], "current decision repaired")["status"] == "CLOSED"


def test_concurrent_artifact_publish_has_one_winner_and_a_manifest_matched_file(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    run = store.start(
        mode="single-name",
        question="Can concurrent artifact publishers claim one attachment?",
        subjects=["NVDA"],
        as_of="2026-08-17",
    )
    artifact_path = tmp_path / "published-ledger.json"
    contents = [b'{"writer":"one"}\n', b'{"writer":"two"}\n']
    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(2)
    results = context.Queue()
    processes = [
        context.Process(target=_concurrent_publish, args=(str(tmp_path), barrier, results, run["run_id"], str(artifact_path), content))
        for content in contents
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=20)
    assert all(process.exitcode == 0 for process in processes)

    payloads = [results.get(timeout=5) for _ in processes]
    successes = [payload for payload in payloads if payload["ok"] is True]
    failures = [payload for payload in payloads if payload["ok"] is False]
    assert len(successes) == 1
    assert [payload["error"]["code"] for payload in failures] == ["persistence_conflict"]

    attachment = RunStore(tmp_path).read(run["run_id"])["artifacts"]["hypothesis-ledger"]
    assert attachment == successes[0]["run"]["artifacts"]["hypothesis-ledger"]
    assert attachment["content_hash"] == hashlib.sha256(artifact_path.read_bytes()).hexdigest()


def test_concurrent_decision_finalization_and_abandon_leave_no_decision_for_an_abandoned_run(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    run = store.start(
        mode="single-name",
        question="Can one terminal transition own decision publication?",
        subjects=["NVDA"],
        as_of="2026-08-17",
    )
    decision_path = tmp_path / "records" / "decisions" / "lineage-nvda" / "v001" / "decision.json"
    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(2)
    results = context.Queue()
    processes = [
        context.Process(target=_concurrent_decision_finalize, args=(str(tmp_path), barrier, results, run["run_id"], str(decision_path))),
        context.Process(target=_concurrent_abandon, args=(str(tmp_path), barrier, results, run["run_id"])),
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=20)
    assert all(process.exitcode == 0 for process in processes)

    payloads = [results.get(timeout=5) for _ in processes]
    assert len([payload for payload in payloads if payload["ok"] is True]) == 1
    assert len([payload for payload in payloads if payload["ok"] is False]) == 1
    terminal = RunStore(tmp_path).read(run["run_id"])
    current_path = decision_path.parent.parent / "current.json"
    if terminal["status"] == "ABANDONED":
        assert not decision_path.exists()
        assert not current_path.exists()
    else:
        assert terminal["status"] == "FINALIZED"
        assert decision_path.is_file()
        assert current_path.is_file()
        assert terminal["artifacts"]["research-decision"]["content_hash"] == hashlib.sha256(decision_path.read_bytes()).hexdigest()


def test_refresh_artifact_replaces_a_current_attachment_and_rejects_a_stale_writer(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    run = store.start(
        mode="single-name",
        question="Can revised hypotheses retain their attachment lineage?",
        subjects=["NVDA"],
        as_of="2026-08-17",
    )
    first_path = tmp_path / "hypothesis-ledger-v1.json"
    first_content = '{"revision":1}\n'
    first_path.write_text(first_content, encoding="utf-8")
    attached = store.attach_artifact(
        run["run_id"],
        name="hypothesis-ledger",
        path=first_path,
        schema_id="urn:serenity:schema:hypothesis-ledger:1",
    )
    expected_attachment = dict(attached["artifacts"]["hypothesis-ledger"])
    replacement_path = first_path
    replacement_path.write_text('{"revision":2}\n', encoding="utf-8")

    refreshed = store.refresh_artifact(
        run["run_id"],
        name="hypothesis-ledger",
        expected_attachment=expected_attachment,
        path=replacement_path,
        schema_id="urn:serenity:schema:hypothesis-ledger:1",
        phase="hypotheses_updated",
    )

    replacement = refreshed["artifacts"]["hypothesis-ledger"]
    assert replacement["path"] == "hypothesis-ledger-v1.json"
    assert replacement["content_hash"] == hashlib.sha256(replacement_path.read_bytes()).hexdigest()
    audit = json.loads(refreshed["events"][-1]["detail"])
    assert refreshed["events"][-1]["type"] == "artifact_superseded"
    assert audit == {"name": "hypothesis-ledger", "previous": expected_attachment, "replacement": replacement}

    stale_path = tmp_path / "hypothesis-ledger-v3.json"
    stale_path.write_text('{"revision":3}\n', encoding="utf-8")
    with pytest.raises(SerenityError) as caught:
        store.refresh_artifact(
            run["run_id"],
            name="hypothesis-ledger",
            expected_attachment=expected_attachment,
            path=stale_path,
            schema_id="urn:serenity:schema:hypothesis-ledger:1",
        )
    assert caught.value.payload["error"]["code"] == "persistence_conflict"


def test_concurrent_artifact_refresh_allows_one_current_writer_and_rejects_the_stale_writer(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    run = store.start(
        mode="single-name",
        question="Can one refreshed hypothesis ledger retain audit lineage?",
        subjects=["NVDA"],
        as_of="2026-08-17",
    )
    first_path = tmp_path / "hypothesis-ledger-v1.json"
    first_path.write_text('{"revision":1}\n', encoding="utf-8")
    attached = store.attach_artifact(
        run["run_id"],
        name="hypothesis-ledger",
        path=first_path,
        schema_id="urn:serenity:schema:hypothesis-ledger:1",
    )
    expected_attachment = dict(attached["artifacts"]["hypothesis-ledger"])
    replacements = [tmp_path / "hypothesis-ledger-v2a.json", tmp_path / "hypothesis-ledger-v2b.json"]
    for index, path in enumerate(replacements, start=2):
        path.write_text(f'{{"revision":{index}}}\n', encoding="utf-8")

    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(2)
    results = context.Queue()
    processes = [
        context.Process(target=_concurrent_refresh, args=(str(tmp_path), barrier, results, run["run_id"], expected_attachment, str(path)))
        for path in replacements
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=20)
    assert all(process.exitcode == 0 for process in processes)

    payloads = [results.get(timeout=5) for _ in processes]
    successes = [payload for payload in payloads if payload["ok"] is True]
    failures = [payload for payload in payloads if payload["ok"] is False]
    assert len(successes) == 1
    assert [payload["error"]["code"] for payload in failures] == ["persistence_conflict"]

    refreshed = RunStore(tmp_path).read(run["run_id"])
    assert refreshed["artifacts"]["hypothesis-ledger"] == successes[0]["run"]["artifacts"]["hypothesis-ledger"]
    assert [event["type"] for event in refreshed["events"]].count("artifact_superseded") == 1
