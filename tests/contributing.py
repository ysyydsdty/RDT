"""Validation methods for contributing to RDT."""


import importlib
import inspect
import subprocess
import traceback

import numpy as np
import pandas as pd
from tabulate import tabulate

from rdt.transformers import get_transformers_by_type
from tests.code_style import (
    load_transformer, validate_test_location, validate_test_names, validate_transformer_addon,
    validate_transformer_importable_from_parent_module, validate_transformer_module,
    validate_transformer_name, validate_transformer_subclass)
from tests.datasets import get_dataset_generators_by_type
from tests.integration.test_transformers import validate_transformer
from tests.performance import evaluate_transformer_performance, validate_performance
from tests.quality.test_quality import (
    TEST_THRESHOLD, get_regression_scores, get_results_table, get_test_cases)

# Mapping of validation method to (check name, check description).
CHECK_DETAILS = {
    '_validate_dataset_generators': (
        'Dataset Generators',
        'At least one Dataset Generator exists for the Transformer data type.',
    ),
    '_validate_transformed_data': (
        'Output Types',
        'The Transformer can transform data and produce output(s) of the indicated data type(s).',
    ),
    '_validate_reverse_transformed_data': (
        'Reverse Transform',
        (
            'The Transformer can reverse transform the data it produces, going back to the ',
            'original data type.',
        ),
    ),
    '_validate_composition': (
        'Composition is Identity',
        (
            'Transforming data and reversing it recovers the original data, if composition is ',
            'identity is specified.',
        ),
    ),
    '_validate_hypertransformer_transformed_data': (
        'Hypertransformer can transform',
        'The HyperTransformer is able to use the Transformer and produce float values.',
    ),
    '_validate_hypertransformer_reverse_transformed_data': (
        'Hypertransformer can reverse transform',
        (
            'The HyperTransformer is able to reverse the data that it has previously transformed ',
            'and restore the original data type.',
        ),
    ),
}


def get_class(class_name):
    """Get the specified class.

    Args:
        class (str):
            Full name of class to import.
    """
    obj = None
    if isinstance(class_name, str):
        package, name = class_name.rsplit('.', 1)
        obj = getattr(importlib.import_module(package), name)

    return obj


def validate_transformer_integration(transformer):
    """Validate the integration tests of a transformer.

    This function runs the automated integration test functions on the Transformer.
    It will print to console a summary of the integration tests, along with which
    checks have passed or failed.

    Args:
        transformer (string or rdt.transformers.BaseTransformer):
            The transformer to validate.

    Returns:
        bool:
            Whether or not the transformer passes all integration checks.
    """
    if isinstance(transformer, str):
        transformer = get_class(transformer)

    print(f'Validating Integration Tests for transformer {transformer.__name__}\n')

    steps = []
    validation_error = None
    error_trace = None

    try:
        validate_transformer(transformer, steps=steps)
    except Exception as error:
        error_trace = ''.join(traceback.TracebackException.from_exception(error).format())

        for check in CHECK_DETAILS:
            if check in error_trace:
                validation_error = str(error)

    if validation_error is None and error_trace is None:
        print('SUCCESS: The integration tests were successful.\n')
    elif validation_error:
        print('ERROR: One or more integration tests were NOT successful.\n')
    elif error_trace:
        print('ERROR: Transformer errored out with the following error:\n')
        print(error_trace)

    result_summaries = []
    seen_checks = set()
    failed_step = None if validation_error is None else steps[-1]
    for step in steps:
        check, details = CHECK_DETAILS[step]
        if check in seen_checks:
            continue

        seen_checks.add(check)

        if failed_step and step == failed_step:
            result_summaries.append([check, 'No', validation_error])
        else:
            result_summaries.append([check, 'Yes', details])

    summary = pd.DataFrame(result_summaries, columns=['Check', 'Correct', 'Details'])
    print(tabulate(summary, headers='keys', showindex=False))

    return validation_error is None and error_trace is None


def _validate_third_party_code_style(command, tag, success_message,
                                     error_message, transformer_path):
    run_command = command.split(' ')
    run_command.append(transformer_path)
    output_capture = subprocess.run(run_command, capture_output=True).stdout.decode()
    if output_capture:
        return {
            'Check': tag,
            'Correct': 'No',
            'Details': error_message,
            'output_capture': output_capture,
        }

    return {
        'Check': tag,
        'Correct': 'Yes',
        'Details': success_message,
    }


def _custom_validation(function, tag, success_message, error_message, transformer):
    try:
        function(transformer)
        return {
            'Check': tag,
            'Correct': 'Yes',
            'Details': success_message,
        }

    except AssertionError as error:
        return {
            'Check': tag,
            'Correct': 'No',
            'Details': error_message,
            'output_capture': error
        }


def _validate_third_party_checks(transformer_path):
    results = [
        _validate_third_party_code_style(
            'flake8',
            'flake8',
            'Code follows PEP8 standards.',
            'Code must follow PEP8 standards.',
            transformer_path
        ),
        _validate_third_party_code_style(
            'isort -c',
            'isort',
            'Imports are properly sorted.',
            'Imports are not properly sorted.',
            transformer_path
        ),
        _validate_third_party_code_style(
            'pylint --rcfile=setup.cfg ',
            'pylint',
            'Code is properly formatted and structured.',
            'Code is not properly formatted and structured.',
            transformer_path
        ),
        _validate_third_party_code_style(
            'pydocstyle',
            'pydocstyle',
            'The docstrings are properly written.',
            'The docstrings are not properly written.',
            transformer_path
        )
    ]

    return results


def _validate_custom_checks(transformer):
    results = [
        _custom_validation(
            validate_transformer_name,
            'Transformer Name',
            'Transformer name ends with ``Transformer``.',
            'Transformer name must end with ``Transformer``.',
            transformer
        ),
        _custom_validation(
            validate_transformer_subclass,
            'Transformer is subclass',
            'The transformer is subclass of ``BaseTransformer``.',
            'The transformer must be a subclass of ``BaseTransformer``.',
            transformer
        ),
        _custom_validation(
            validate_transformer_module,
            'Valid module',
            'The transformer is placed inside a valid module.',
            'The transformer is not placed inside a valid module.',
            transformer
        ),
        _custom_validation(
            validate_test_location,
            'Valid test module',
            'The transformer tests are placed inside the valid module.',
            'The transformer tests are not placed inside the valid module.',
            transformer
        ),
        _custom_validation(
            validate_test_names,
            'Valid test function names',
            'The transformer tests are named correctly.',
            'The transformer tests are not named properly.',
            transformer
        ),
        _custom_validation(
            validate_transformer_addon,
            'Valid transformer addon',
            'The addon is configured properly.',
            'The addon is not configured properly.',
            transformer
        ),
        _custom_validation(
            validate_transformer_importable_from_parent_module,
            'Importable from module',
            'The transformer can be imported from the parent module.',
            'The transformer can not be imported from the parent module.',
            transformer
        )
    ]

    return results


def validate_transformer_code_style(transformer):
    """Validate all third party code style checkers as well as custom code analysis.

    This function validates whether or not a ``rdt.transformers.BaseTransformer`` subclass
    is following the standard code style checks (``flake8``, ``isort``, ``pylint``, ...) and
    additionally custom made code style validations for ``RDT``.

    Args:
        transformer (string or rdt.transformers.BaseTransformer):
            The transformer to validate.
    Output:
        bool:
            Whether or not the transformer passes all code style checks.
    """
    if not inspect.isclass(transformer):
        transformer = load_transformer(transformer)

    transformer_path = inspect.getfile(transformer)
    print(f'Validating source file {transformer_path}')

    results = (_validate_third_party_checks(transformer_path))
    results.extend(_validate_custom_checks(transformer))

    errors = [
        (result.get('Check'), result.pop('output_capture'))
        for result in results
        if 'output_capture' in result
    ]
    valid = not bool(errors)
    if valid:
        print('\nSUCCESS: The code style is correct.\n')
    else:
        print('\nERROR the code style is NOT correct.\n')

    table = pd.DataFrame(results)
    print(tabulate(table, headers='keys', showindex=False))
    for check, error in errors:
        print(f"\nThe check '{check}' produced the following error/s:")
        print(error)

    return not bool(errors)


def validate_transformer_quality(transformer):
    """Validate quality tests for a transformer.

    This function creates a DataFrame containing the results
    from running the quality tests for this transformer against
    all the datasets with columns of its input type. It does the
    following steps:
    1. A DataFrame containing the regression scores obtained from running the
    transformers of the input type against the datasets in the test cases is
    created. Each row in the DataFrame has the transformer name, dataset name,
    column name and score. The scores are computed as follows:
        - For every transformer of the data type, transform all the
        columns of that data type.
        - For every numerical column in the dataset, the transformed
        columns are used as features to train a regression model.
        - The score is the coefficient of determination obtained from
        that model trying to predict the target column.
    2. Once the scores are gathered, a results table is created. Each row has
    a transformer name, dataset name, average score for the dataset,
    a score comparing the transformer's average score for the dataset to
    the average of the average score for the dataset across all transformers of
    the same data type, and whether or not the score passed the test threshold.
    3. The table described above is printed when this function is run.

    Returns:
        DataFrame containing the following columns for each dataset the transformer
        is validated against: ``Dataset``, ``Score``, ``Compared To Average``, ``Acceptable``.
    """
    if isinstance(transformer, str):
        transformer = get_class(transformer)

    print(f'Validating Quality Tests for transformer {transformer.__name__}\n')

    input_type = transformer.get_input_type()
    test_cases = get_test_cases({input_type})
    regression_scores = get_regression_scores(test_cases, get_transformers_by_type())
    results = get_results_table(regression_scores)

    transformer_results = results[results['transformer_name'] == transformer.__name__]
    transformer_results = transformer_results.drop('transformer_name', axis=1)
    transformer_results['Acceptable'] = False
    passing_relative_scores = transformer_results['score_relative_to_average'] > TEST_THRESHOLD
    acceptable_indices = passing_relative_scores | (transformer_results['score'] > TEST_THRESHOLD)
    transformer_results.loc[acceptable_indices, 'Acceptable'] = True
    new_names = {
        'dataset_name': 'Dataset',
        'score': 'Score',
        'score_relative_to_average': 'Compared To Average'
    }
    transformer_results = transformer_results.rename(columns=new_names)

    if transformer_results['Acceptable'].all():
        print('SUCCESS: The quality tests were successful.\n')
    else:
        print('Failure: The quality tests were NOT successful.\n')

    print(tabulate(transformer_results, headers='keys', showindex=False))

    return transformer_results


def validate_transformer_performance(transformer):
    """Validate the performance of a transformer.

    Run the specified Transformer on all the Dataset Generators of the indicated data type
    and produce a report about its performance and how it compares to the other
    Transformers of the same data type.

    Args:
        transformer (string or rdt.transformers.BaseTransformer):
            The transformer to validate.

    Returns:
        pandas.DataFrame:
            Performance results of the transformer.
    """
    if isinstance(transformer, str):
        transformer = get_class(transformer)

    print(f'Validating Performance for transformer {transformer.__name__}\n')

    data_type = transformer.get_input_type()
    transformers = get_transformers_by_type().get(data_type, [])
    dataset_generators = get_dataset_generators_by_type().get(data_type, [])

    total_results = pd.DataFrame()
    for current_transformer in transformers:
        for dataset_generator in dataset_generators:
            performance = evaluate_transformer_performance(current_transformer, dataset_generator)
            valid = validate_performance(performance, dataset_generator)

            results = pd.DataFrame({
                'Value': performance.to_numpy(),
                'Valid': valid,
                'transformer': current_transformer.__name__,
                'dataset': dataset_generator.__name__,
            })
            results['Evaluation Metric'] = performance.index
            total_results = total_results.append(results)

    if total_results['Valid'].all():
        print('SUCCESS: The Performance Tests were successful.')
    else:
        print('ERROR: One or more Performance Tests were NOT successful.')

    other_results = total_results[total_results.transformer != transformer.__name__]
    average = other_results.groupby('Evaluation Metric')['Value'].mean()

    total_results = total_results[total_results.transformer == transformer.__name__]
    final_results = total_results.groupby('Evaluation Metric').agg({
        'Value': 'mean',
        'Valid': 'any'
    })
    final_results = final_results.rename(columns={'Valid': 'Acceptable'})
    final_results['Units'] = np.where(
        final_results.index.str.contains('Time'),
        's / row',
        'Mb / row',
    )
    final_results['Acceptable'] = np.where(final_results['Acceptable'], 'Yes', 'No')
    final_results['Compared to Average'] = final_results['Value'].div(average).replace(
        np.inf, np.nan)

    return final_results.reset_index()
