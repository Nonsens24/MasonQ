"""RSP handoff tests."""

import pytest

from brickwork_transpiler.bfk_encoder import BFKQubitPreparation
from brickwork_transpiler.cloak.rsp import (
    LocalRSPClient,
    PreparationHandle,
    RemoteRSPClient,
    RSPClient,
)


def _mk_preparations(n: int):
    return [BFKQubitPreparation(node=i, theta=(i % 8) / 4.0) for i in range(n)]


def test_local_rsp_returns_handle_with_correct_count():
    client = LocalRSPClient()
    preps = _mk_preparations(5)
    handle = client.prepare(preps)
    assert isinstance(handle, PreparationHandle)
    assert handle.num_qubits == 5
    assert handle.backend == "local"
    assert handle.handle_id.startswith("local-")


def test_local_rsp_handles_are_distinct_across_calls():
    client = LocalRSPClient()
    h1 = client.prepare(_mk_preparations(1))
    h2 = client.prepare(_mk_preparations(1))
    assert h1.handle_id != h2.handle_id


def test_remote_rsp_stub_raises_until_wired():
    client = RemoteRSPClient(endpoint="quantum.example.com")
    with pytest.raises(NotImplementedError):
        client.prepare(_mk_preparations(2))


def test_local_rsp_satisfies_protocol():
    client = LocalRSPClient()
    assert isinstance(client, RSPClient)
