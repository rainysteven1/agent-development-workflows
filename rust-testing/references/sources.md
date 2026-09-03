# Sources And Design Provenance

## Primary Tool Sources

Use the repository's pinned versions and read the matching documentation before applying commands.

- Rust testing and Cargo layout: https://doc.rust-lang.org/book/ch11-00-testing.html and
  https://doc.rust-lang.org/cargo/guide/tests.html
- nextest: https://nexte.st/ and https://github.com/nextest-rs/nextest
- Tokio testing: https://tokio.rs/tokio/topics/testing
- Loom: https://github.com/tokio-rs/loom
- proptest: https://github.com/proptest-rs/proptest and
  https://proptest-rs.github.io/proptest/intro.html
- cargo-fuzz: https://github.com/rust-fuzz/cargo-fuzz and https://rust-fuzz.github.io/book/
- cargo-mutants: https://github.com/sourcefrog/cargo-mutants
- testcontainers-rs: https://github.com/testcontainers/testcontainers-rs
- Miri: https://github.com/rust-lang/miri
- cargo-llvm-cov: https://github.com/taiki-e/cargo-llvm-cov

## Skill Sources Evaluated

This skill is an original synthesis. Upstream materials informed its structure and were not copied as
a complete policy.

- `affaan-m/ECC`: useful unit/integration/Tokio/proptest/TDD baseline; its single-file tutorial,
  coverage target, and missing advanced-tool routing were not adopted.
- `leonardomso/rust-skills`: useful atomic Rust rules and progressive disclosure; its full 265-rule
  index is broader than a focused testing skill.
- `pproenca/dot-skills` `rust-write-tests`: useful failure-hypothesis, semantic-assertion, and flake
  analysis ideas; mandatory assertion libraries, file layout, and fixed test counts were not adopted.
- `trailofbits/skills`: useful property-based testing, fuzzing, harness, and coverage specialization;
  it is not a base unit/integration/recovery testing system.

Project URLs:

- https://github.com/affaan-m/ECC
- https://github.com/leonardomso/rust-skills
- https://github.com/pproenca/dot-skills
- https://github.com/trailofbits/skills

## Authority Rule

Prefer, in order:

1. checked-in repository policy and executable CI;
2. behavior of the pinned tool version;
3. official or maintainer documentation for that version;
4. this skill's selection guidance;
5. community examples.

Do not present a version-sensitive command or flag as universal without checking the installed tool.
