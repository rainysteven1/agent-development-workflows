# Property And Fuzz Testing

## Choose By Question

Use example tests for named business cases and exact regressions. Use property testing when many
structured values should satisfy a semantic relationship. Use fuzzing when coverage-guided byte or
structured input exploration can discover crashes, hangs, parser defects, or invariant violations.

High-value property shapes include:

- round trip: `decode(encode(x)) == x` within the documented domain;
- idempotence: `normalize(normalize(x)) == normalize(x)`;
- model equivalence: optimized or concurrent behavior matches a simple reference model;
- preservation: sorting preserves cardinality and members;
- state-machine invariants across generated command sequences;
- monotonicity, identity, inverse, or compatibility properties.

"Does not panic" is useful for fuzzing hostile input but is usually a weak business property.

## Design Proptest Strategies From The Domain

- Generate valid and invalid domains deliberately instead of filtering arbitrary data heavily.
- Keep strategies small enough to shrink effectively.
- Assert the strongest semantic property available.
- Preserve minimal failing cases in source-controlled regression inputs or the repository's configured
  persistence mechanism.
- Print or retain the seed and minimized counterexample.
- Convert important discovered failures into clear example regression tests when that improves
  readability and protects the exact contract.

Do not replace a known edge-case matrix with random generation. Combine properties with named cases
for boundaries, compatibility vectors, and security-sensitive inputs.

## Design Cargo Fuzz Harnesses

Use cargo-fuzz when the project can run a nightly fuzz toolchain and the target has a bounded,
deterministic harness. Prefer library entry points over driving a whole binary.

A useful harness:

- rejects only inputs outside the target's meaningful domain;
- avoids network access, wall-clock dependence, unbounded allocation, and global mutation;
- treats documented errors as normal outcomes;
- asserts a semantic invariant when possible;
- supports structure-aware input for protocols and domain objects;
- keeps corpora and dictionaries free of secrets and proprietary production data.

Record campaign budget, toolchain, target, sanitizer, corpus revision, and artifact path. Reproduce a
crash from its saved artifact before fixing it, minimize it when practical, then add durable regression
evidence.

## Separate Campaigns From Merge Gates

Keep a bounded smoke run in CI only when its cost and signal are stable. Run longer campaigns on a
schedule or dedicated worker. A campaign that simply times out is not a passing correctness proof;
report executions, coverage growth, crashes, hangs, and remaining corpus limitations.

## Combine Techniques Carefully

- Use property testing to validate a reference model before relying on it as a fuzz oracle.
- Use mutation testing to discover weak properties or assertions.
- Use coverage to find harness blind spots, not as the fuzzing objective by itself.
- Use Loom for synchronization interleavings and proptest for command/state sequences; neither fully
  substitutes for the other.
- Run Miri on minimized unsafe regressions when supported.

## Review Checklist

- Is the property stronger than "no crash"?
- Does the generator represent the actual input domain?
- Can failures shrink and reproduce with recorded evidence?
- Is the harness deterministic and bounded?
- Are discovered artifacts promoted into lasting regression evidence?
- Is campaign cost separated from ordinary merge-request feedback?
