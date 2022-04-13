# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import json
import pandas as pd
import numpy as np
import time
import multiprocessing
from sklearn.cluster import KMeans
from sklearn.cluster import SpectralClustering


def kmeans_approximate_sampling(X, n_points=10):
    """
    K-Means clustering, corrected to the closest points
    :param X: injections matrix (time, bus)
    :param n_points: number of clusters
    :return: indices of the closest to the cluster centers, deviation of the closest representatives
    """

    # declare the model
    model = KMeans(n_clusters=n_points, random_state=0)

    # model fitting
    model.fit(X)

    centers = model.cluster_centers_
    labels = model.labels_

    # get the closest indices to the cluster centers
    closest_idx = np.zeros(n_points, dtype=int)
    closest_prob = np.zeros(n_points, dtype=float)
    nt = X.shape[0]

    unique_labels, counts = np.unique(labels, return_counts=True)
    probabilities = counts.astype(float) / float(nt)

    prob_dict = {u: p for u, p in zip(unique_labels, probabilities)}
    for i in range(n_points):
        deviations = np.sum(np.power(X - centers[i, :], 2.0), axis=1)
        idx = deviations.argmin()
        closest_idx[i] = idx

    # sort the indices
    closest_idx = np.sort(closest_idx)

    # compute the probabilities of each index (sorted already)
    for i, idx in enumerate(closest_idx):
        lbl = model.predict(X[idx, :].reshape(1, -1))[0]
        prob = prob_dict[lbl]
        closest_prob[i] = prob

    return closest_idx, closest_prob


def spectral_approximate_sampling(X, n_points=10):
    """
    K-Means clustering, corrected to the closest points
    :param X: injections matrix (time, bus)
    :param n_points: number of clusters
    :return: indices of the closest to the cluster centers, deviation of the closest representatives
    """

    # declare the model
    model = SpectralClustering(n_points=n_points)

    # model fitting
    model.fit(X)

    labels = model.labels_

    # categorize labels
    label_indices_init = [list() for i in range(n_points)]
    for i, k in enumerate(labels):
        label_indices_init[k].append(i)

    # there may be less clusters than specified, hence we need to correct
    n_points_new = 0
    label_indices = list()
    for i in range(n_points):
        if len(label_indices_init[i]):
            label_indices.append(label_indices_init[i])
            n_points_new += 1

    # compute the centers
    centers = np.empty((n_points_new, X.shape[1]))
    closest_prob = np.empty(n_points_new)
    n = X.shape[0]  # number of samples

    for k in range(n_points_new):
        idx = label_indices[k]
        centers[k, :] = X[idx, :].mean(axis=0)
        closest_prob[k] = len(idx) / n

    # get the closest indices to the cluster centers
    closest_idx = np.zeros(n_points_new, dtype=int)
    for i in range(n_points_new):
        deviations = np.sum(np.power(X - centers[i, :], 2.0), axis=1)
        idx = deviations.argmin()
        closest_idx[i] = idx

    # sort the indices
    closest_idx = np.sort(closest_idx)

    return closest_idx, closest_prob, n_points_new

