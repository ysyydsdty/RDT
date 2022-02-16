"""Functions for evaluating transformer performance."""

import numpy as np
import pandas as pd

from rdt.performance.datasets import get_dataset_generators_by_type
from rdt.performance.profiling import profile_transformer
from rdt.transformers import BaseTransformer

DATASET_SIZES = [1000, 10000, 100000]

# Additional arguments for transformers
TRANSFORMER_ARGS = {
    'BinaryEncoder': {
        'missing_value_replacement': -1,
        'model_missing_values': True
    },
    'DatetimeTransformer': {
        'missing_value_replacement': 'mean',
        'model_missing_values': True
    },
    'DatetimeRoundedTransformer': {
        'missing_value_replacement': 'mean',
        'model_missing_values': True
    },
    'FloatFormatter': {
        'missing_value_replacement': 'mean',
        'model_missing_values': True
    },
    'NumericalRoundedBoundedTransformer': {
        'missing_value_replacement': 'mean',
        'model_missing_values': True
    },
    'NumericalBoundedTransformer': {
        'missing_value_replacement': 'mean',
        'model_missing_values': True
    },
    'GaussianNormalizer': {
        'missing_value_replacement': 'mean',
        'model_missing_values': True
    },
    'ClusterBasedNormalizer': {
        'missing_value_replacement': 'mean',
        'model_missing_values': True
    },
}


def _get_dataset_sizes(data_type):
    """Get a list of (fit_size, transform_size) for each dataset generator.

    Based on the data type of the dataset generator, return the list of
    sizes to run performance tests on. Each element in this list is a tuple
    of (fit_size, transform_size).

    Args:
        input_type (str):
            The type of data that the generator returns.

    Returns:
        sizes (list[tuple]):
            A list of (fit_size, transform_size) configs to run tests on.
    """
    sizes = [(s, s) for s in DATASET_SIZES]

    if data_type == 'categorical':
        sizes = [(s, max(s, 1000)) for s in DATASET_SIZES if s <= 10000]

    return sizes


def evaluate_transformer_performance(transformer, dataset_generator, verbose=False):
    """Evaluate the given transformer's performance against the given dataset generator.

    Args:
        transformer (rdt.transformers.BaseTransformer):
            The transformer to evaluate.
        dataset_generator (rdt.tests.datasets.BaseDatasetGenerator):
            The dataset generator to performance test against.
        verbose (bool):
            Whether or not to add extra columns about the dataset and transformer,
            and return data for all dataset sizes. If false, it will only return
            the max performance values of all the dataset sizes used.

    Returns:
        pandas.DataFrame:
            The performance test results.
    """
    transformer_args = TRANSFORMER_ARGS.get(transformer.__name__, {})
    transformer_instance = transformer(**transformer_args)

    sizes = _get_dataset_sizes(dataset_generator.DATA_TYPE)

    out = []
    for fit_size, transform_size in sizes:
        performance = profile_transformer(
            transformer=transformer_instance,
            dataset_generator=dataset_generator,
            fit_size=fit_size,
            transform_size=transform_size,
        )
        size = np.array([fit_size, transform_size, transform_size] * 2)
        performance = performance / size
        if verbose:
            performance = performance.rename(lambda x: x + ' (s)' if 'Time' in x else x + ' (B)')
            performance['Number of fit rows'] = fit_size
            performance['Number of transform rows'] = transform_size
            performance['Dataset'] = dataset_generator.__name__
            performance['Transformer'] = f'{transformer.__module__ }.{transformer.__name__}'

        out.append(performance)

    summary = pd.DataFrame(out)
    if verbose:
        return summary

    return summary.max(axis=0)


def evaluate_transformers(transformers=None):
    """Evaluate the performance for each transformer against all applicable datasets.

    Args:
        transformers (list<rdt.transformers.BaseTransformer>):
            List of transformer classes to evaluate.

    Returns:
        pandas.DataFrame:
            A table containing the times and memory usages for ``fit``, ``transform`` and
            ``reverse_transform`` for each transformer provided against every dataset generator
            that applies to it.
    """
    summary = pd.DataFrame()

    dataset_generators = get_dataset_generators_by_type()
    transformers = transformers or BaseTransformer.get_subclasses()

    for transformer in transformers:
        dataset_generators_for_type = dataset_generators.get(transformer.get_input_type(), [])

        for dataset_generator in dataset_generators_for_type:
            performance = evaluate_transformer_performance(
                transformer, dataset_generator, verbose=True)

            summary = pd.concat([summary, performance], ignore_index=True)

    return summary
