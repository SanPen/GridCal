# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import os
import numpy as np
import time
from typing import List, Tuple
from sklearn.cluster import KMeans
from sklearn.cluster import SpectralClustering
from VeraGridEngine.basic_structures import IntVec, Vec, Mat


def kmeans_sampling(x_input: Mat, n_points: int = 10) -> Tuple[IntVec, Vec, IntVec]:
    """
    K-Means clustering, fit to the closest points
    :param x_input: matrix to evaluate (time, params)
    :param n_points: number of clusters
    :return: indices of the closest to the cluster centers,
             deviation of the closest representatives,
             array signifying to which cluster does each simulation belong
    """
    os.environ['OPENBLAS_NUM_THREADS'] = '12'

    # # declare the model
    model = KMeans(n_clusters=n_points, random_state=0, n_init=10)

    # model fitting
    original_points_cluster_indices = model.fit_predict(x_input)

    # compute probabilities
    centroids, counts = np.unique(model.labels_, return_counts=True)
    cluster_probability = counts.astype(float) / len(model.labels_)

    # Find the indices from the original data that best represent the found clusters
    cluster_representative_indices = np.zeros(n_points, dtype=int)
    for c in range(n_points):
        # all rows in that cluster
        idx = np.where(original_points_cluster_indices == c)[0]

        # distances from the original points to the cluster center
        dists = np.linalg.norm(x_input[idx] - model.cluster_centers_[c], axis=1)

        # index of the
        rep_idx = idx[np.argmin(dists)]  # single best representative
        cluster_representative_indices[c] = rep_idx

    # 1. Sort the representatives …
    sorting_idx = np.argsort(cluster_representative_indices)

    cluster_representative_indices = cluster_representative_indices[sorting_idx]
    cluster_probability = cluster_probability[sorting_idx]

    # 2. … build a mapping “old label  ➜  new (sorted) label” …
    #    sorting_idx[new_label] == old_label   ⇒   inverse permutation:
    label_map = np.empty_like(sorting_idx)  # same length, same dtype
    label_map[sorting_idx] = np.arange(n_points)  # old_label → new_label

    # 3. … and remap every sample’s label.
    original_points_cluster_indices = label_map[original_points_cluster_indices]

    return cluster_representative_indices, cluster_probability, original_points_cluster_indices


def kmeans_approximate_sampling(x_input: Mat, n_points: int = 10) -> Tuple[IntVec, Vec]:
    """
    K-Means clustering, corrected to the closest points
    :param x_input: Injections matrix (time, bus)
    :param n_points: number of clusters
    :return: indices of the closest to the cluster centers, deviation of the closest representatives
    """

    # declare the model
    model = KMeans(n_clusters=n_points, random_state=0, n_init=10)

    # model fitting
    model.fit(x_input)

    centers = model.cluster_centers_
    labels = model.labels_

    # get the closest indices to the cluster centers
    closest_idx = np.zeros(n_points, dtype=int)
    closest_prob = np.zeros(n_points, dtype=float)
    nt = x_input.shape[0]

    unique_labels, counts = np.unique(labels, return_counts=True)
    probabilities = counts.astype(float) / float(nt)

    prob_dict = {u: p for u, p in zip(unique_labels, probabilities)}
    for i in range(n_points):
        deviations = np.sum(np.power(x_input - centers[i, :], 2.0), axis=1)
        idx = deviations.argmin()
        closest_idx[i] = idx

    # sort the indices
    closest_idx = np.sort(closest_idx)

    # compute the probabilities of each index (sorted already)
    for i, idx in enumerate(closest_idx):
        lbl = model.predict(x_input[idx, :].reshape(1, -1))[0]
        prob = prob_dict[lbl]
        closest_prob[i] = prob

    return closest_idx, closest_prob


def spectral_approximate_sampling(x_input: Mat, n_points: int = 10) -> Tuple[IntVec, Vec, int]:
    """
    K-Means clustering, corrected to the closest points
    :param x_input: Injections matrix (time, bus)
    :param n_points: number of clusters
    :return: indices of the closest to the cluster centers, deviation of the closest representatives
    """

    # declare the model
    model = SpectralClustering(n_clusters=n_points)

    # model fitting
    model.fit(x_input)

    labels = model.labels_

    # categorize labels
    label_indices_init: List[List[int]] = [list() for _ in range(n_points)]
    for i, k in enumerate(labels):
        label_indices_init[k].append(i)

    # there may be fewer clusters than specified, hence we need to correct
    n_points_new = 0
    label_indices = list()
    for i in range(n_points):
        if len(label_indices_init[i]):
            label_indices.append(label_indices_init[i])
            n_points_new += 1

    # compute the centers
    centers = np.empty((n_points_new, x_input.shape[1]))
    closest_prob = np.empty(n_points_new)
    n = x_input.shape[0]  # number of samples

    for k in range(n_points_new):
        idx = label_indices[k]
        centers[k, :] = x_input[idx, :].mean(axis=0)
        closest_prob[k] = len(idx) / n

    # get the closest indices to the cluster centers
    closest_idx = np.zeros(n_points_new, dtype=int)
    for i in range(n_points_new):
        deviations = np.sum(np.power(x_input - centers[i, :], 2.0), axis=1)
        idx = deviations.argmin()
        closest_idx[i] = idx

    # sort the indices
    closest_idx = np.sort(closest_idx)

    return closest_idx, closest_prob, n_points_new

