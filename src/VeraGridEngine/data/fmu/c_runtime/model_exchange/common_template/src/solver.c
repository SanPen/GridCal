#include "model_instance.h"

#include "generated_model.h"
#include "runtime_support.h"

static double* algebraic_ptr(ModelInstance* instance, size_t index) {
    if (index < (size_t)VG_NUM_ALGEBRAICS) {
        return &instance->algebraics[index];
    }
    return NULL;
}

static double residual_norm(const double* residual, size_t count) {
    size_t i;
    double max_abs = 0.0;
    for (i = 0u; i < count; ++i) {
        double value = fabs(residual[i]);
        if (value > max_abs) {
            max_abs = value;
        }
    }
    return max_abs;
}

static int solve_dense_system(size_t n, double* matrix, double* rhs) {
    size_t i;
    size_t j;
    size_t k;
    for (i = 0u; i < n; ++i) {
        size_t pivot = i;
        double pivot_abs = fabs(matrix[i * n + i]);
        for (j = i + 1u; j < n; ++j) {
            double candidate = fabs(matrix[j * n + i]);
            if (candidate > pivot_abs) {
                pivot = j;
                pivot_abs = candidate;
            }
        }
        if (pivot_abs < 1e-14) {
            return 1;
        }
        if (pivot != i) {
            for (k = i; k < n; ++k) {
                double tmp = matrix[i * n + k];
                matrix[i * n + k] = matrix[pivot * n + k];
                matrix[pivot * n + k] = tmp;
            }
            {
                double tmp_rhs = rhs[i];
                rhs[i] = rhs[pivot];
                rhs[pivot] = tmp_rhs;
            }
        }
        for (j = i + 1u; j < n; ++j) {
            double factor = matrix[j * n + i] / matrix[i * n + i];
            matrix[j * n + i] = 0.0;
            for (k = i + 1u; k < n; ++k) {
                matrix[j * n + k] -= factor * matrix[i * n + k];
            }
            rhs[j] -= factor * rhs[i];
        }
    }
    for (i = n; i-- > 0u;) {
        double sum = rhs[i];
        for (j = i + 1u; j < n; ++j) {
            sum -= matrix[i * n + j] * rhs[j];
        }
        rhs[i] = sum / matrix[i * n + i];
    }
    return 0;
}

int solver_solve_algebraics(ModelInstance* instance) {
    size_t n = (size_t)VG_NUM_ALGEBRAICS;
    size_t i;
    size_t j;
    double* jacobian;
    double* residual0;
    double* residual1;
    double* delta;

    if (instance == NULL) {
        return 1;
    }
    if (n == 0u) {
        return 0;
    }

    jacobian = (double*)calloc(n * n, sizeof(double));
    residual0 = (double*)calloc(n, sizeof(double));
    residual1 = (double*)calloc(n, sizeof(double));
    delta = (double*)calloc(n, sizeof(double));
    if (jacobian == NULL || residual0 == NULL || residual1 == NULL || delta == NULL) {
        free(jacobian);
        free(residual0);
        free(residual1);
        free(delta);
        return 1;
    }

    for (i = 0u; i < (size_t)VG_MAX_NEWTON_ITERATIONS; ++i) {
        generated_eval_algebraic_residual(instance, residual0);
        if (residual_norm(residual0, n) <= VG_NEWTON_TOLERANCE) {
            break;
        }
        for (j = 0u; j < n; ++j) {
            double* x = algebraic_ptr(instance, j);
            double original = *x;
            double epsilon = 1e-7 * (fabs(original) + 1.0);
            size_t row;
            *x = original + epsilon;
            generated_eval_algebraic_residual(instance, residual1);
            *x = original;
            for (row = 0u; row < n; ++row) {
                jacobian[row * n + j] = (residual1[row] - residual0[row]) / epsilon;
            }
            delta[j] = -residual0[j];
        }
        if (solve_dense_system(n, jacobian, delta) != 0) {
            free(jacobian);
            free(residual0);
            free(residual1);
            free(delta);
            return 2;
        }
        for (j = 0u; j < n; ++j) {
            double* x = algebraic_ptr(instance, j);
            *x += delta[j];
        }
    }

    free(jacobian);
    free(residual0);
    free(residual1);
    free(delta);
    return 0;
}
