# tests/test_bfk_encoder.py
import math

import numpy as np
import pytest

graphix = pytest.importorskip("graphix")

import brickwork_transpiler.circuits as circuits
from brickwork_transpiler import brickwork_transpiler
from brickwork_transpiler.bfk_encoder import encode_pattern, sample_qubit_preparations
from graphix import Pattern
from graphix.command import M, X, Z
from graphix.measurements import Measurement


if not hasattr(M, "angle"):
    M.angle = property(lambda self: self.measurement.angle)
if not hasattr(M, "plane"):
    M.plane = property(lambda self: self.measurement.plane.name)


def _m(node, plane, angle, s_domain=None, t_domain=None):
    s_domain = set() if s_domain is None else set(s_domain)
    t_domain = set() if t_domain is None else set(t_domain)
    return M(node, getattr(Measurement, plane)(angle), s_domain, t_domain)


def _angles_close(a, b, tol=1e-12):
    # a, b are in units of π; equality up to mod 2.
    return math.isclose(((a - b) % 2.0), 0.0, abs_tol=tol) or math.isclose(((b - a) % 2.0), 0.0, abs_tol=tol)


def _extract_Ms(pat: Pattern):
    return [cmd for cmd in pat._Pattern__seq if isinstance(cmd, M)]


@pytest.fixture(scope="module")
def bw_pattern():
    # Build the same pattern the user described
    experiment, _ = circuits.cx_and_h_circ()
    bw_pat, col_map, _ = brickwork_transpiler.transpile(
        experiment,
        routing_method="sabre",
        layout_method="trivial",
        with_ancillas=False,
    )
    # Sanity: make sure we actually have measurements to test
    orig_Ms = _extract_Ms(bw_pat)
    if not orig_Ms:
        pytest.skip("Brickwork pattern contains no measurements (M); cannot test encoding.")
    return bw_pat


def test_bfk_encoder_on_brickwork_pattern_delta_rule(bw_pattern):
    """
    For every measurement M(node, plane, φ, s_domain, t_domain) in the original brickwork pattern,
    the encoded pattern must set angle to δ = φ + θ + r (mod 2), in units of π.
    """
    rng = np.random.default_rng(2025)

    # Choose a deterministic subset of nodes for theta_lookup override
    orig_Ms = _extract_Ms(bw_pattern)
    nodes = [m.node for m in orig_Ms]
    chosen_for_lookup = set(nodes[::2])  # every other measurement
    theta_lookup = {n: 0.75 for n in chosen_for_lookup}  # 3π/4 in units of π

    # Encode
    new_pat, info = encode_pattern(bw_pattern, theta_lookup=theta_lookup, rng=rng, remove_dependencies=False)

    new_Ms = _extract_Ms(new_pat)
    assert len(new_Ms) == len(orig_Ms) == len(info), "Number of measurements must be preserved."

    # Pairwise check (preserving order)
    for k, (m_old, m_new, meta) in enumerate(zip(orig_Ms, new_Ms, info)):
        # Node and plane should be preserved
        assert m_new.node == m_old.node
        assert m_new.plane == m_old.plane

        # θ: overridden when provided, otherwise sampled from the 8-point grid
        theta = meta["theta"]
        if m_old.node in chosen_for_lookup:
            assert theta == 0.75, "theta_lookup must override RNG."
        else:
            assert theta in {i / 4.0 for i in range(8)}, "θ must be in {0,1/4,...,7/4}."

        # δ rule (units of π; modulo 2)
        phi = m_old.angle
        r = meta["r"]
        expected_delta = (phi + theta + r) % 2.0
        assert _angles_close(m_new.angle, expected_delta), (
            f"Encoded angle for node {m_old.node} must be δ = φ + θ + r (mod 2). "
            f"Got {m_new.angle}, expected {expected_delta}."
        )

        # s/t domains must be copied (not evaluated here)
        assert set(meta["s_domain"]) == set(m_old.s_domain)
        assert set(meta["t_domain"]) == set(m_old.t_domain)


def test_bfk_encoder_non_mutating_on_brickwork(bw_pattern):
    """The input Pattern must not be mutated (deepcopy semantics)."""
    orig_seq_ids = [id(c) for c in bw_pattern._Pattern__seq]
    new_pat, info = encode_pattern(bw_pattern, rng=np.random.default_rng(1), remove_dependencies=False)
    # Input untouched
    assert [id(c) for c in bw_pattern._Pattern__seq] == orig_seq_ids
    # Output distinct
    assert [id(c) for c in new_pat._Pattern__seq] != orig_seq_ids

def _mk_pattern(seq):
    """Helper: build a Pattern with a given private sequence."""
    p = Pattern()
    # We match the function's use of the private field for maximum fidelity.
    p._Pattern__seq = list(seq)
    return p


def test_blinds_to_delta_and_records_metadata():
    """
    Protocol 1 requires δ = φ' + θ + π r (units of π; mod 2).
    We set θ via lookup so the RNG only decides r; then check:
      - output M.angle equals δ (mod 2)
      - plane unchanged
      - info entries contain expected fields
    """
    phi1, phi2 = 0.50, 1.75    # units of π
    s1, t1 = {7}, {3}
    s2, t2 = {8}, {4}

    seq = [
        _m(1, "XY", phi1, s1, t1),
        X(99),  # byproduct for the previous M
        Z(101),
        _m(2, "XY", phi2, s2, t2),
    ]
    pat = _mk_pattern(seq)

    theta_lookup = {1: 0.25, 2: 1.00}
    rng = np.random.default_rng(12345)

    new_pat, info = encode_pattern(pat, theta_lookup=theta_lookup, rng=rng, remove_dependencies=False)

    # Extract the new M commands (in order)
    new_Ms = [cmd for cmd in new_pat._Pattern__seq if isinstance(cmd, M)]
    assert len(new_Ms) == 2
    assert len(info) == 2

    # Check metadata keys
    for entry in info:
        for k in ["node", "phi", "theta", "r", "s_domain", "t_domain", "x_byproducts", "z_byproducts"]:
            assert k in entry, f"Missing key '{k}' in info"
        # Optional but expected from the docstring/spec:
        # uncomment to enforce presence once implemented
        # assert "delta" in entry, "Missing 'delta' in info (per spec)"

    # Entry 0
    r0 = info[0]["r"]
    expected_delta0 = (phi1 + theta_lookup[1] + r0) % 2
    assert info[0]["phi"] == phi1
    assert info[0]["theta"] == theta_lookup[1]
    assert _angles_close(new_Ms[0].angle, expected_delta0), "M(1) angle must equal δ (φ+θ+r) mod 2 per BFK"

    # Entry 1
    r1 = info[1]["r"]
    expected_delta1 = (phi2 + theta_lookup[2] + r1) % 2
    assert info[1]["phi"] == phi2
    assert info[1]["theta"] == theta_lookup[2]
    assert _angles_close(new_Ms[1].angle, expected_delta1), "M(2) angle must equal δ (φ+θ+r) mod 2 per BFK"

    # Planes unchanged
    assert new_Ms[0].plane == "XY"
    assert new_Ms[1].plane == "XY"

    # Byproduct tracking: X(99), Z(101) occur after first M only
    assert info[0]["x_byproducts"] == {99}
    assert info[0]["z_byproducts"] == {101}
    assert info[1]["x_byproducts"] == set()
    assert info[1]["z_byproducts"] == set()

    # Domains copied as sets
    assert info[0]["s_domain"] == s1 and info[0]["t_domain"] == t1
    assert info[1]["s_domain"] == s2 and info[1]["t_domain"] == t2


def test_theta_lookup_overrides_rng_and_rng_used_for_others():
    """
    For nodes in theta_lookup, θ must be exactly the provided value.
    For others, θ must lie in {0,1/4,...,7/4}. We verify δ construction via info['r'].
    """
    # Three measurements, only node 2 has θ pre-set
    phi = [0.00, 0.50, 0.25]
    seq = [
        _m(1, "XY", phi[0], set(), set()),
        _m(2, "XY", phi[1], {1}, {2}),
        _m(3, "XY", phi[2], {3}, {4}),
    ]
    pat = _mk_pattern(seq)

    theta_lookup = {2: 1.25}
    rng = np.random.default_rng(2024)

    new_pat, info = encode_pattern(pat, theta_lookup=theta_lookup, rng=rng, remove_dependencies=False)
    new_Ms = [cmd for cmd in new_pat._Pattern__seq if isinstance(cmd, M)]

    assert len(new_Ms) == 3
    assert len(info) == 3

    # Node 2 exactness
    assert info[1]["theta"] == 1.25
    expected_delta2 = (phi[1] + info[1]["theta"] + info[1]["r"]) % 2
    assert _angles_close(new_Ms[1].angle, expected_delta2)

    # Nodes 1 and 3 θ grid membership and δ correctness
    for i in (0, 2):
        theta_i = info[i]["theta"]
        assert theta_i in {k / 4.0 for k in range(8)}, "θ must be chosen from {0,1/4,...,7/4}"
        expected_delta = (phi[i] + theta_i + info[i]["r"]) % 2
        assert _angles_close(new_Ms[i].angle, expected_delta)


def test_remove_dependencies_strips_XZ_and_keeps_M():
    seq = [
        _m(1, "XY", 0.0, set(), set()),
        X(7),
        Z(8),
        _m(2, "XY", 0.25, set(), set()),
        Z(9),
        X(10),
    ]
    pat = _mk_pattern(seq)
    new_pat_keep, info_keep = encode_pattern(pat, rng=np.random.default_rng(7), remove_dependencies=False)
    new_pat_strip, info_strip = encode_pattern(pat, rng=np.random.default_rng(7), remove_dependencies=True)

    # With dependencies kept: all commands still present
    assert len(new_pat_keep._Pattern__seq) == len(seq)
    assert any(isinstance(c, X) for c in new_pat_keep._Pattern__seq)
    assert any(isinstance(c, Z) for c in new_pat_keep._Pattern__seq)

    # With dependencies removed: only Ms remain
    assert all(isinstance(c, M) for c in new_pat_strip._Pattern__seq)
    assert len([c for c in new_pat_strip._Pattern__seq if isinstance(c, M)]) == 2

    # Byproduct tracking per M when kept
    assert info_keep[0]["x_byproducts"] == {7}
    assert info_keep[0]["z_byproducts"] == {8}
    assert info_keep[1]["x_byproducts"] == {10}
    assert info_keep[1]["z_byproducts"] == {9}

    # When stripped, info still reflects logical dependencies encountered
    assert info_strip[0]["x_byproducts"] == {7}
    assert info_strip[0]["z_byproducts"] == {8}


def test_xz_before_first_measurement_are_not_recorded_and_strip_behavior():
    seq = [
        X(5),
        Z(6),
        _m(1, "XY", 0.5, set(), set()),
    ]
    pat = _mk_pattern(seq)

    new_keep, info_keep = encode_pattern(pat, rng=np.random.default_rng(0), remove_dependencies=False)
    new_strip, info_strip = encode_pattern(pat, rng=np.random.default_rng(0), remove_dependencies=True)

    # Kept: X/Z remain at head; but not recorded as byproducts (occur before first M)
    assert isinstance(new_keep._Pattern__seq[0], X) and isinstance(new_keep._Pattern__seq[1], Z)
    assert info_keep[0]["x_byproducts"] == set()
    assert info_keep[0]["z_byproducts"] == set()

    # Stripped: only the M remains
    assert len(new_strip._Pattern__seq) == 1 and isinstance(new_strip._Pattern__seq[0], M)


def test_pattern_is_deepcopied_not_mutated():
    seq = [_m(1, "XY", 0.75, set(), set())]
    pat = _mk_pattern(seq)
    original_seq_ids = [id(c) for c in pat._Pattern__seq]

    new_pat, info = encode_pattern(pat, rng=np.random.default_rng(42), remove_dependencies=False)

    # Original sequence objects unchanged
    assert [id(c) for c in pat._Pattern__seq] == original_seq_ids
    # New pattern has distinct sequence objects
    assert [id(c) for c in new_pat._Pattern__seq] != original_seq_ids


def test_rng_reproducibility_with_same_seed_and_no_theta_lookup():
    seq = [_m(i, "XY", 0.0, set(), set()) for i in range(1, 21)]
    pat = _mk_pattern(seq)

    seed = 314159
    new_pat1, info1 = encode_pattern(_mk_pattern(seq), rng=np.random.default_rng(seed), remove_dependencies=False)
    new_pat2, info2 = encode_pattern(_mk_pattern(seq), rng=np.random.default_rng(seed), remove_dependencies=False)

    angles1 = [cmd.angle for cmd in new_pat1._Pattern__seq if isinstance(cmd, M)]
    angles2 = [cmd.angle for cmd in new_pat2._Pattern__seq if isinstance(cmd, M)]
    r1 = [e["r"] for e in info1]
    r2 = [e["r"] for e in info2]

    assert angles1 == angles2
    assert r1 == r2

    # θ grid membership
    for e in info1:
        assert e["theta"] in {k / 4.0 for k in range(8)}


def test_mod2_wraparound_of_delta():
    """
    Choose φ=1.75 and θ=0.5. Depending on r∈{0,1}, δ = (1.75 + 0.5 + r) mod 2 ∈ {0.25, 1.25}.
    """
    phi = 1.75
    theta = 0.50
    seq = [_m(1, "XY", phi, set(), set())]
    pat = _mk_pattern(seq)

    # θ via lookup; RNG picks r deterministically from seed
    rng = np.random.default_rng(1234)
    new_pat, info = encode_pattern(pat, theta_lookup={1: theta}, rng=rng, remove_dependencies=False)

    new_M = [c for c in new_pat._Pattern__seq if isinstance(c, M)][0]
    r = info[0]["r"]
    expected = (phi + theta + r) % 2
    assert _angles_close(new_M.angle, expected), "δ must be computed modulo 2 (units of π)"


def test_info_delta_matches_emitted_angle_and_formula():
    phi = 0.75
    theta = 0.25
    pat = _mk_pattern([_m(1, "XY", phi, {1}, {2})])

    rng = np.random.default_rng(123)
    new_pat, info = encode_pattern(pat, theta_lookup={1: theta}, rng=rng)
    m = _extract_Ms(new_pat)[0]

    assert "delta" in info[0]
    expected = (phi + theta + info[0]["r"]) % 2.0
    assert _angles_close(info[0]["delta"], expected)
    assert _angles_close(m.angle, expected), "Emitted M.angle must equal info['delta']."


def test_negative_and_out_of_range_phi_are_normalized_mod_2():
    # φ = -0.25 and φ = 2 + 0.6 should be treated modulo 2
    phi_vals = [-0.25, 2.6]
    thetas = [0.5, 1.0]
    nodes = [1, 2]
    seq = [_m(n, "XY", p, set(), set()) for n, p in zip(nodes, phi_vals)]
    pat = _mk_pattern(seq)

    rng = np.random.default_rng(7)  # fixes r
    t_lookup = {1: thetas[0], 2: thetas[1]}
    new_pat, info = encode_pattern(pat, theta_lookup=t_lookup, rng=rng)

    for k, m in enumerate(_extract_Ms(new_pat)):
        phi = phi_vals[k]
        theta = thetas[k]
        r = info[k]["r"]
        expected = ((phi % 2.0) + theta + r) % 2.0
        assert _angles_close(m.angle, expected), f"φ normalization failed for node {nodes[k]}"


def test_planes_preserved_for_various_planes():
    seq = [
        _m(1, "XY", 0.0, set(), set()),
        _m(2, "XZ", 0.25, set(), set()),
        _m(3, "YZ", 0.5, set(), set()),
    ]
    pat = _mk_pattern(seq)
    new_pat, info = encode_pattern(pat, rng=np.random.default_rng(0))
    planes_new = [m.plane for m in _extract_Ms(new_pat)]
    assert planes_new == ["XY", "XZ", "YZ"]


def test_multiple_byproducts_grouped_until_next_measurement_and_trailing():
    seq = [
        _m(1, "XY", 0.0, set(), set()),
        X(10), X(11), Z(12),
        X(13),  # still belongs to M1
        _m(2, "XY", 0.0, set(), set()),
        Z(20), Z(21), X(22),
        # trailing byproducts should attach to the last M (M2)
        Z(23), X(24),
    ]
    pat = _mk_pattern(seq)
    _, info = encode_pattern(pat, rng=np.random.default_rng(1), remove_dependencies=False)

    # For M1: 10,11,13 in x; 12 in z
    assert info[0]["x_byproducts"] == {10, 11, 13}
    assert info[0]["z_byproducts"] == {12}

    # For M2: 22,24 in x; 20,21,23 in z
    assert info[1]["x_byproducts"] == {22, 24}
    assert info[1]["z_byproducts"] == {20, 21, 23}


def test_remove_dependencies_only_strips_XZ_but_keeps_other_unknown_commands():
    class OtherCmd:
        def __init__(self, tag):
            self.tag = tag
        def __repr__(self):
            return f"OtherCmd({self.tag})"

    seq = [
        OtherCmd("before"),
        _m(1, "XY", 0.0, set(), set()),
        X(7),
        OtherCmd("between"),
        Z(8),
        _m(2, "XY", 0.0, set(), set()),
        OtherCmd("after"),
    ]
    pat = _mk_pattern(seq)

    # keep deps
    keep_pat, _ = encode_pattern(_mk_pattern(seq), rng=np.random.default_rng(0), remove_dependencies=False)
    # strip deps
    strip_pat, _ = encode_pattern(_mk_pattern(seq), rng=np.random.default_rng(0), remove_dependencies=True)

    # In stripped pattern, X/Z are removed, OtherCmds and Ms remain, order preserved
    assert any(isinstance(c, OtherCmd) for c in strip_pat._Pattern__seq)
    assert all(not isinstance(c, X) and not isinstance(c, Z) for c in strip_pat._Pattern__seq)
    # The number of Ms should be unchanged
    assert len([c for c in strip_pat._Pattern__seq if isinstance(c, M)]) == 2
    # Other commands should bracket as before
    tags = [c.tag for c in strip_pat._Pattern__seq if isinstance(c, OtherCmd)]
    assert tags == ["before", "between", "after"]


def test_theta_lookup_is_respected_for_provided_nodes_and_augmented_for_others():
    seq = [_m(1, "XY", 0.0, set(), set()),
           _m(2, "XY", 0.0, set(), set()),
           _m(3, "XY", 0.0, set(), set())]
    pat = _mk_pattern(seq)

    t_lookup = {2: 0.75}
    rng = np.random.default_rng(123)

    _, info = encode_pattern(pat, theta_lookup=t_lookup, rng=rng)

    # Provided value must be unchanged
    assert info[1]["theta"] == 0.75

    # For nodes 1 and 3, θ must be on the 8-point grid
    for i in (0, 2):
        assert info[i]["theta"] in {k / 4.0 for k in range(8)}

    # theta_lookup should be augmented with new nodes but not overwrite existing key 2
    assert set(t_lookup.keys()) == {1, 2, 3}
    assert t_lookup[2] == 0.75


def test_rng_seed_sensitivity_affects_delta_when_no_lookup():
    seq = [_m(i, "XY", 0.25, set(), set()) for i in range(1, 6)]
    pat = _mk_pattern(seq)

    new1, info1 = encode_pattern(_mk_pattern(seq), rng=np.random.default_rng(1))
    new2, info2 = encode_pattern(_mk_pattern(seq), rng=np.random.default_rng(2))

    angles1 = [m.angle for m in _extract_Ms(new1)]
    angles2 = [m.angle for m in _extract_Ms(new2)]
    # Not guaranteed to differ in every position, but highly likely to differ somewhere
    assert angles1 != angles2 or [e["r"] for e in info1] != [e["r"] for e in info2]


def test_r_is_always_0_or_1():
    seq = [_m(i, "XY", 0.0, set(), set()) for i in range(1, 64)]
    pat = _mk_pattern(seq)
    _, info = encode_pattern(pat, rng=np.random.default_rng(12345))
    assert set(e["r"] for e in info).issubset({0, 1})


def test_domains_are_copied_not_aliased():
    s = {1}
    t = {2}
    m = _m(1, "XY", 0.0, s, t)
    pat = _mk_pattern([m])

    new_pat, info = encode_pattern(pat, rng=np.random.default_rng(0))
    # Mutate the info view; should not affect the original Pattern's M domains
    info[0]["s_domain"].add(99)
    info[0]["t_domain"].add(100)

    orig_m = _extract_Ms(pat)[0]
    assert orig_m.s_domain == {1}
    assert orig_m.t_domain == {2}

    # Also mutate original and check info remains as it was after our additions
    s.add(77)
    t.add(88)
    assert info[0]["s_domain"].issuperset({1, 99}) and 77 not in info[0]["s_domain"]
    assert info[0]["t_domain"].issuperset({2, 100}) and 88 not in info[0]["t_domain"]


def test_empty_pattern_round_trip():
    pat = _mk_pattern([])
    new_pat, info = encode_pattern(pat, rng=np.random.default_rng(0))
    assert new_pat._Pattern__seq == []
    assert info == []


def test_non_grid_theta_lookup_is_rejected_by_default():
    pat = _mk_pattern([_m(1, "XY", 0.6, set(), set())])

    with pytest.raises(ValueError, match="multiples of pi/4"):
        encode_pattern(pat, theta_lookup={1: 0.33}, rng=np.random.default_rng(9))


def test_sample_qubit_preparations_covers_all_pattern_nodes():
    pat = _mk_pattern([
        _m(1, "XY", 0.0, set(), set()),
        X(2),
        Z(3),
    ])
    pat._Pattern__output_nodes = [4]

    theta_lookup = {1: 0.25}
    preps = sample_qubit_preparations(
        pat,
        theta_lookup=theta_lookup,
        rng=np.random.default_rng(123),
    )

    prep_by_node = {prep.node: prep for prep in preps}
    assert set(prep_by_node) == {1, 2, 3, 4}
    assert prep_by_node[1].theta == 0.25
    assert all(prep.theta in {k / 4.0 for k in range(8)} for prep in preps)
    assert all(prep.state_label.startswith("|+_") for prep in preps)


def test_return_metadata_includes_bfk_preparations_and_measurements():
    pat = _mk_pattern([_m(1, "XY", 0.5, set(), set())])

    _, metadata = encode_pattern(
        pat,
        theta_lookup={1: 0.75},
        rng=np.random.default_rng(7),
        return_metadata=True,
    )

    assert set(metadata) == {"preparations", "measurements"}
    assert metadata["preparations"][0]["node"] == 1
    assert metadata["preparations"][0]["theta"] == 0.75
    assert metadata["measurements"][0]["preparation"]["theta"] == 0.75
