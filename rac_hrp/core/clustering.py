"""
rac_hrp.core.clustering
=======================
The clustering layer that RAC-HRP re-fits when the absorption ratio triggers.

Two spaces are supported:

  "correlation"  vanilla Lopez de Prado: d_ij = sqrt(0.5 * (1 - rho_ij)),
                 single linkage. This is the STATIC HRP baseline's tree.

  "pca"          cluster on the MP-retained eigenvector coordinates (see
                 pca_mp.pca_features), Euclidean distance, Ward linkage. This is
                 the project's tree.

Why the PCA space is not just a reparameterisation of the correlation space:
correlation distance is pairwise and treats every pair independently. Two stocks
with rho = 0.3 sit at the same distance whether that 0.3 comes from a shared
market beta or from a shared sector. Projecting onto the retained components
first means "close" specifically means "loads similarly on the factors that
survived the MP cut" -- and it discards the noise bulk before the tree is built,
rather than letting it perturb every pairwise distance.

The number of clusters is tied to the MP-retained component count k (config
`n_clusters_rule="mp_k"`), bounded to [n_clusters_min, n_clusters_max]. That is
a rule, not a tuned knob -- it deliberately avoids a silhouette-maximising
search, which would be a model-selection step running on data the pre-analysis
plan forbids selecting on.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from scipy.cluster.hierarchy import (linkage, fcluster, leaves_list,
                                     optimal_leaf_ordering)
from scipy.spatial.distance import squareform, pdist

from .covariance import cov_to_corr
from .pca_mp import Spectrum, pca_features


def correlation_distance(cov: np.ndarray) -> np.ndarray:
    corr = cov_to_corr(cov)
    d = np.sqrt(np.maximum(0.5 * (1.0 - corr), 0.0))
    np.fill_diagonal(d, 0.0)
    return 0.5 * (d + d.T)


def build_tree(cov: np.ndarray,
               spec: Optional[Spectrum] = None,
               space: str = "pca",
               method: str = "ward",
               k: Optional[int] = None,
               canonical_order: bool = True):
    """Return (linkage_matrix, leaf_order, condensed_distance).

    CANONICAL LEAF ORDER -- why this is not cosmetic.

    A dendrogram does not determine a leaf order. At every internal node the two
    children can be drawn in either order, so a tree over N assets admits 2^(N-1)
    equally valid leaf sequences. `leaves_list` returns whichever one falls out of
    the merge bookkeeping, which depends on the order the columns happened to
    arrive in.

    HRP's recursive bisection splits the leaf list BY POSITION -- it cuts the
    sequence in half, not the tree at a node. So two identical trees with
    different (equally valid) leaf orders produce DIFFERENT HRP WEIGHTS. Permuting
    the columns of the covariance matrix changes the portfolio. That is a real and
    well-known wart in HRP, and normally it is merely embarrassing.

    Here it is dangerous. This project's entire question is WHEN TO RE-CLUSTER.
    Every time the tree is rebuilt, an arbitrary sibling-swap can reshuffle the
    leaf order and move weights -- generating turnover, and an apparent "response
    to the regime", that is pure tie-breaking noise with no economic content. It
    would inflate RAC-HRP's measured activity, contaminate the Phase 3 transaction
    -cost result, and make a re-clustering rule look like it is doing something
    when it is doing nothing.

    `optimal_leaf_ordering` (Bar-Joseph et al. 2001) removes the ambiguity: it
    chooses, among all 2^(N-1) orderings, the one minimising the total distance
    between adjacent leaves. It is a deterministic function of the distance matrix
    alone, so the leaf order now changes if and only if the CORRELATION STRUCTURE
    changes -- which is exactly the property the re-clustering experiment needs.
    """
    if space == "correlation":
        D = correlation_distance(cov)
        cond = squareform(D, checks=False)
        meth = "single" if method == "ward" else method
        Z = linkage(cond, method=meth)
    elif space == "pca":
        if spec is None:
            raise ValueError("pca space requires a Spectrum")
        F = pca_features(spec, k=k)
        cond = pdist(F, metric="euclidean")
        Z = linkage(cond, method=method)
    else:
        raise ValueError(f"unknown cluster space {space!r}")

    if canonical_order:
        Z = optimal_leaf_ordering(Z, cond)
    return Z, leaves_list(Z), cond


def cluster_labels(Z, n_clusters: int) -> np.ndarray:
    return fcluster(Z, t=int(n_clusters), criterion="maxclust")


def n_clusters_from_rule(spec: Spectrum, rule: str, lo: int, hi: int) -> int:
    if rule == "mp_k":
        return int(np.clip(spec.k, lo, hi))
    raise ValueError(f"unknown n_clusters_rule {rule!r}")


def adjusted_rand_index(a: np.ndarray, b: np.ndarray) -> float:
    """ARI between two labelings. Phase 2's cluster-stability diagnostic, but
    computed here because the null gate needs it: under a null, re-clustering
    should be re-arranging noise, and ARI tells you whether the "regimes" the
    trigger fires on correspond to any actual change in structure."""
    a, b = np.asarray(a), np.asarray(b)
    n = len(a)
    if n == 0 or len(b) != n:
        return np.nan
    ua, ub = np.unique(a), np.unique(b)
    C = np.zeros((len(ua), len(ub)), dtype=np.int64)
    ai = {v: i for i, v in enumerate(ua)}
    bi = {v: i for i, v in enumerate(ub)}
    for x, y in zip(a, b):
        C[ai[x], bi[y]] += 1

    def comb2(x):
        return x * (x - 1) / 2.0

    sum_ij = comb2(C).sum()
    sum_i = comb2(C.sum(axis=1)).sum()
    sum_j = comb2(C.sum(axis=0)).sum()
    total = comb2(np.array([n], dtype=np.int64)).sum()
    expected = sum_i * sum_j / total if total else 0.0
    maxi = 0.5 * (sum_i + sum_j)
    denom = maxi - expected
    if abs(denom) < 1e-12:
        return 1.0
    return float((sum_ij - expected) / denom)


def variation_of_information(a: np.ndarray, b: np.ndarray) -> float:
    """Variation of information between two clusterings of the SAME items.

        VI(A, B) = H(A) + H(B) - 2 I(A; B)

    in nats. VI is a true metric on the space of partitions: 0 iff the two
    clusterings are identical, larger when they differ more. This is the
    statistic behind the frozen D_VI cluster-informativeness gate (Phase 2
    pre-registration rev.5, section 2), where larger VI at triggered rebalances
    than at non-triggered ones is the evidence that the trigger fires when the
    correlation structure has genuinely moved.

    Both inputs must be label arrays over the same, identically ordered items.
    """
    a = np.asarray(a).ravel()
    b = np.asarray(b).ravel()
    if len(a) != len(b):
        raise ValueError(f"clusterings cover different item counts: {len(a)} vs {len(b)}")
    n = len(a)
    if n == 0:
        return np.nan

    ua, ia = np.unique(a, return_inverse=True)
    ub, ib = np.unique(b, return_inverse=True)
    joint = np.zeros((len(ua), len(ub)), dtype=float)
    np.add.at(joint, (ia, ib), 1.0)
    joint /= n

    pa = joint.sum(axis=1)
    pb = joint.sum(axis=0)

    def _H(p):
        p = p[p > 0]
        return float(-(p * np.log(p)).sum())

    nz = joint > 0
    mi = float((joint[nz] * np.log(joint[nz] / np.outer(pa, pb)[nz])).sum())
    return max(0.0, _H(pa) + _H(pb) - 2.0 * mi)
