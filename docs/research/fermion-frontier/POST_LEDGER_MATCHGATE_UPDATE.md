# Post-ledger update: 2026 QC-AFQMC matchgate-shadow workflow

Review date: 2026-07-11

Source: [APS accepted paper, DOI 10.1103/n1tf-8kr7](https://journals.aps.org/prresearch/accepted/10.1103/n1tf-8kr7)
and [arXiv:2506.22408v1](https://arxiv.org/abs/2506.22408)

This update was discovered after the 70-claim focused ledger closed. It is not
included in that ledger's 64 accepted / 6 refuted count; the 64 accepted
findings comprise 56 unanimous and 8 split/partial decisions. Three reviewers
independently checked the accepted-paper metadata and full arXiv text.

## Verdict

| Component | A | B | C | Consensus |
|---|:---:|:---:|:---:|---|
| Accepted by Physical Review Research on 2026-06-17 | P | P | P | VERIFIED; accepted paper, not yet a volume/article publication |
| 24-qubit experiment means 16 data qubits plus 8 leakage ancillas | P | P | P | VERIFIED |
| End-to-end hybrid application workflow | P* | P* | P* | VERIFIED only for the molecule-to-barrier QPU–GPU workflow; not an end-to-end QPU algorithm or timed quantum advantage |
| `9x` improvement | P* | P* | P* | VERIFIED only as workload-tuned Forte circuit execution, with median `9.9 s` to `1.1 s`; not fewer measurements or a quantum speedup |
| `656x` improvement | P* | P* | P* | Arithmetic verified only for the authors' normalized, projected classical post-processing estimate |
| `656x` measured end-to-end time-to-solution or quantum speedup | R | R | R | REFUTED |
| Chemical accuracy or reliable reaction ordering on QPU | R | R | R | REFUTED |
| Independent replication | R | R | R | REFUTED |

`P*` means the numerical or workflow core passed only with the boundary in the
consensus column.

## Safe finding

The paper demonstrates a molecule-to-reaction-barrier hybrid QC-AFQMC workflow
using IonQ Forte matchgate-shadow sampling and GPU post-processing. The
experiment uses 24 qubits: 16 encode an `(8e, 8o)` active-space trial state and
8 are leakage-detection ancillas. It retains about 180,000 shadows from 300,983
one-shot circuits.

This is an important algorithm and systems-engineering scale-up. It does not
establish quantum advantage, chemical accuracy, or a complete wall-clock,
cost, or energy advantage.

The absolute workload remains large: the three molecular structures consume
about 48,000 GPU-hours in total (`13,200–17,400` GPU-hours per structure), and
the 300,983 QPU circuits were collected over multiple weeks rather than one
continuously timed production run.

## Resource normalization

### The `9x` number

The control-stack comparison is on the same Forte device:

- ordinary execution: median `9.9 s` per one-shot matchgate circuit;
- workload-tuned execution: median `1.1 s` per circuit.

The improvement uses waveform caching, pipelining, and workload-specific
control optimization. It excludes submission and queue time, and the two modes
were measured over different circuit counts. It is a circuit-throughput result,
not a reduction in the number of shadows and not a QPU-versus-classical speedup.

### The `656x` number

The ratio compares a new normalized GPU post-processing kernel against an old
four-qubit implementation after several transformations:

1. the old measured kernel is extrapolated from 4 to 16 qubits as `O(N_q^8)`;
2. the new result is normalized per time step, walker, and shadow;
3. GPU time is converted to CPU-equivalent time using an assumed `50x`
   H200/AMD-Rome factor;
4. the chemical problem, hardware, walkers, shadows, and propagation settings
   differ between the two studies.

The resulting `656x` arithmetic is reproducible, but it is not a same-task A/B
benchmark and excludes QPU collection and full workflow time. The paper's
headline therefore updates engineering practicality, not evidence for quantum
advantage.

## Accuracy boundary

For the two reported reaction barriers, the central values are:

| Method | Barrier 1 | Barrier 2 |
|---|---:|---:|
| frozen-core CCSD(T) reference | `53.3` | `45.4` kcal/mol |
| ideal-shadow QC-AFQMC | `57(4)` | `44(4)` kcal/mol |
| Forte QPU-shadow QC-AFQMC | `43(3)` | `55(3)` kcal/mol |

The QPU values differ from the reference by about 10 kcal/mol and reverse the
relative ordering of the two barriers. The model also uses a truncated
molecular structure, a minimal STO-3G basis, an `(8e, 8o)` active space, and
virtual-correlation embedding. CCSD(T) is a reference inside this approximate
model, not experimental truth or a complete-basis exact result.

## Source independence

The 41 authors are drawn entirely from IonQ, AstraZeneca, NVIDIA, and AWS. This
is a cross-company engineering collaboration, but all organizations are
stakeholders in the tested hardware, cloud, GPU, or application workflow. The
paper also shares Benchen Huang and Yi-Ting Chen with the 2024 matchgate
QC-AFQMC baseline. It should not be called an independent replication.

## Program consequence

The update weakens the claim that polynomial matchgate post-processing is
necessarily unusable at modest scale: aggressive algorithmic, GPU, and control
co-design can move the practical boundary substantially. It does not change
the central synthesis. The gain comes from a matched fermionic representation
plus classical and systems engineering, and remains far from a demonstrated
end-to-end quantum advantage.
