import contextlib
import io
from collections import defaultdict
from unittest import TestCase
from unittest.mock import Mock, call, patch

import numpy as np
import pandas as pd
import pytest

from rdt import HyperTransformer
from rdt.errors import Error, NotFittedError
from rdt.transformers import (
    BinaryEncoder, FloatFormatter, FrequencyEncoder, GaussianNormalizer, OneHotEncoder,
    UnixTimestampEncoder)


class TestHyperTransformer(TestCase):

    @patch('rdt.hyper_transformer.print')
    def test_print_tip(self, mock_print):
        """Test that the ``print_tip`` function prints a message with a ``Tip: `` at the start.

        Mock:
            - Mock print function.

        Side Effects:
            - Print has been called once with ``Tip: my tip.``.
        """
        # Run
        HyperTransformer.print_tip('my tip.')

        # Assert
        mock_print.assert_called_once_with('Tip: my tip.')

    def test__add_field_to_set_string(self):
        """Test the ``_add_field_to_set`` method.

        Test that ``field`` is added to the ``field_set``.

        Input:
            - a field name.
            - a set of field names.

        Expected behavior:
            - the passed field name should be added to the set of field names.
        """
        # Setup
        ht = HyperTransformer()
        field = 'abc'
        field_set = {'def', 'ghi'}

        # Run
        ht._add_field_to_set(field, field_set)

        # Assert
        assert field_set == {'abc', 'def', 'ghi'}

    def test__add_field_to_set_tuple(self):
        """Test the ``_add_field_to_set`` method when given a tuple.

        Test that each ``field`` name is added to the ``field_set``.

        Input:
            - a tuple of field names.
            - a set of field names.

        Expected behavior:
            - the passed field names should be added to the set of field names.
        """
        # Setup
        ht = HyperTransformer()
        field = ('abc', 'jkl')
        field_set = {'def', 'ghi'}

        # Run
        ht._add_field_to_set(field, field_set)

        # Assert
        assert field_set == {'abc', 'def', 'ghi', 'jkl'}

    def test__validate_field_transformers(self):
        """Test the ``_validate_field_transformers`` method.

        Tests that a ``ValueError`` is raised if a field has multiple
        definitions in the ``field_transformers`` dict.

        Setup:
            - field_transformers set to have duplicate definitions.

        Expected behavior:
            - A ``ValueError`` should be raised if a field is defined
            more than once.
        """
        # Setup
        int_transformer = Mock()
        float_transformer = Mock()

        field_transformers = {
            'integer': int_transformer,
            'float': float_transformer,
            ('integer',): int_transformer
        }
        ht = HyperTransformer()
        ht.field_transformers = field_transformers

        # Run / Assert
        error_msg = (
            r'Multiple transformers specified for the field \(\'integer\',\). '
            'Each field can have at most one transformer defined in field_transformers.'
        )

        with pytest.raises(ValueError, match=error_msg):
            ht._validate_field_transformers()

    @patch('rdt.hyper_transformer.HyperTransformer._create_multi_column_fields')
    @patch('rdt.hyper_transformer.HyperTransformer._validate_field_transformers')
    def test___init__(self, validation_mock, multi_column_mock):
        """Test create new instance of HyperTransformer"""
        # Run
        ht = HyperTransformer()

        # Asserts
        assert ht.copy is True
        assert ht._provided_field_sdtypes == {}
        assert ht.field_sdtypes == {}
        assert ht.default_sdtype_transformers == {}
        assert ht._provided_field_transformers == {}
        assert ht.field_transformers == {}
        multi_column_mock.assert_called_once()
        validation_mock.assert_called_once()

    def test__unfit(self):
        """Test the ``_unfit`` method.

        The ``_unfit`` method should reset most attributes of the HyperTransformer.

        Setup:
            - instance._fitted is set to True
            - instance._transformers_sequence is a list of transformers
            - instance._output_columns is a list of columns
            - instance._input_columns is a list of columns
            - instance._provided_field_sdtypes is a dict of strings to strings
            - instance._provided_field_transformers is a dict of strings to transformers

        Expected behavior:
            - instance._fitted is set to False
            - instance._transformers_sequence is set to []
            - instance._output_columns is an empty list
            - instance._input_columns is an empty list
            - instance._provided_field_sdtypes doesn't change
            - instance.field_sdtypes is the same as instance._provided_field_sdtypes
            - instance._provided_field_transformers doesn't change
            - instance.field_transformers is the same as instance._provided_field_transformers
        """
        # Setup
        ht = HyperTransformer()
        ht._fitted = True
        ht._transformers_sequence = [BinaryEncoder(), FloatFormatter()]
        ht._output_columns = ['col1', 'col2']
        ht._input_columns = ['col3', 'col4']
        sdtypes = {'col1': 'float', 'col2': 'categorical'}
        ht._provided_field_sdtypes = sdtypes
        transformers = {'col2': FloatFormatter(), 'col3': BinaryEncoder()}
        ht._provided_field_transformers = transformers

        # Run
        ht._unfit()

        # Assert
        assert ht._fitted is False
        assert ht._transformers_sequence == []
        assert ht._fitted_fields == set()
        assert ht._output_columns == []
        assert ht._input_columns == []
        assert ht._transformers_tree == {}
        assert ht.field_sdtypes == sdtypes
        assert ht._provided_field_sdtypes == sdtypes
        assert ht.field_transformers == transformers
        assert ht._provided_field_transformers == transformers

    def test__create_multi_column_fields(self):
        """Test the ``_create_multi_column_fields`` method.

        This tests that the method goes through both the ``field_transformers``
        dict and ``field_sdtypes`` dict to find multi_column fields and map
        each column to its corresponding tuple.

        Setup:
            - instance.field_transformers will be populated with multi-column fields
            - instance.field_sdtypes will be populated with multi-column fields

        Output:
            - A dict mapping each column name that is part of a multi-column
            field to the tuple of columns in the field it belongs to.
        """
        # Setup
        ht = HyperTransformer()
        ht.field_transformers = {
            'a': BinaryEncoder,
            'b': UnixTimestampEncoder,
            ('c', 'd'): UnixTimestampEncoder,
            'e': FloatFormatter
        }
        ht.field_sdtypes = {
            'f': 'categorical',
            ('g', 'h'): 'datetime'
        }

        # Run
        multi_column_fields = ht._create_multi_column_fields()

        # Assert
        expected = {
            'c': ('c', 'd'),
            'd': ('c', 'd'),
            'g': ('g', 'h'),
            'h': ('g', 'h')
        }
        assert multi_column_fields == expected

    def test__get_next_transformer_field_transformer(self):
        """Test the ``_get_next_transformer method.

        This tests that if the transformer is defined in the
        ``instance.field_transformers`` dict, then it is returned
        even if the output sdtype is final.

        Setup:
            - field_transformers is given a transformer for the
            output field.
            - default_sdtype_transformers will be given a different transformer
            for the output sdtype of the output field.

        Input:
            - An output field name in field_transformers.
            - Output sdtype  is numerical.
            - next_transformers is None.

        Output:
            - The transformer defined in field_transformers.
        """
        # Setup
        transformer = FloatFormatter()
        ht = HyperTransformer(
            field_transformers={'a.out': transformer},
            default_sdtype_transformers={'numerical': GaussianNormalizer()}
        )

        # Run
        next_transformer = ht._get_next_transformer('a.out', 'numerical', None)

        # Assert
        assert next_transformer == transformer

    def test__get_next_transformer_final_output_sdtype(self):
        """Test the ``_get_next_transformer method.

        This tests that if the transformer is not defined in the
        ``instance.field_transformers`` dict and its output sdtype
        is in ``instance._transform_output_sdtypes``, then ``None``
        is returned.

        Setup:
            - default_sdtype_transformers will be given a transformer
            for the output sdtype of the output field.

        Input:
            - An output field name in field_transformers.
            - Output sdtype  is numerical.
            - next_transformers is None.

        Output:
            - None.
        """
        # Setup
        ht = HyperTransformer(
            default_sdtype_transformers={'numerical': GaussianNormalizer()}
        )

        # Run
        next_transformer = ht._get_next_transformer('a.out', 'numerical', None)

        # Assert
        assert next_transformer is None

    def test__get_next_transformer_next_transformers(self):
        """Test the ``_get_next_transformer method.

        This tests that if the transformer is not defined in the
        ``instance.field_transformers`` dict and its output sdtype
        is not in ``instance._transform_output_sdtypes`` and the
        ``next_transformers`` dict has a transformer for the output
        field, then it is used.

        Setup:
            - default_sdtype_transformers will be given a transformer
            for the output sdtype of the output field.

        Input:
            - An output field name in field_transformers.
            - Output sdtype  is categorical.
            - next_transformers is has a transformer defined
            for the output field.

        Output:
            - The transformer defined in next_transformers.
        """
        # Setup
        transformer = FrequencyEncoder()
        ht = HyperTransformer(
            default_sdtype_transformers={'categorical': OneHotEncoder()}
        )
        next_transformers = {'a.out': transformer}

        # Run
        next_transformer = ht._get_next_transformer('a.out', 'categorical', next_transformers)

        # Assert
        assert next_transformer == transformer

    @patch('rdt.transformers.get_default_transformer')
    def test__get_next_transformer_default_transformer(self, mock):
        """Test the ``_get_next_transformer method.

        This tests that if the transformer is not defined in the
        ``instance.field_transformers`` dict or ``next_transformers``
        and its output sdtype is not in ``instance._transform_output_sdtypes``
        then the default_transformer is used.

        Setup:
            - A mock is used for ``get_default_transformer``.

        Input:
            - An output field name in field_transformers.
            - Output sdtype  is categorical.
            - next_transformers is None.

        Output:
            - The default transformer.
        """
        # Setup
        transformer = FrequencyEncoder(add_noise=True)
        mock.return_value = transformer
        ht = HyperTransformer(
            default_sdtype_transformers={'categorical': OneHotEncoder()}
        )

        # Run
        next_transformer = ht._get_next_transformer('a.out', 'categorical', None)

        # Assert
        assert isinstance(next_transformer, FrequencyEncoder)
        assert next_transformer.add_noise is False

    def test_detect_initial_config(self):
        """Test the ``detect_initial_config`` method.

        This tests that ``field_sdtypes`` and ``field_transformers`` are correctly set,
        and that the appropriate configuration is printed.

        Input:
            - A DataFrame.
        """
        # Setup
        ht = HyperTransformer()
        data = pd.DataFrame({
            'col1': [1, 2, np.nan],
            'col2': ['a', 'b', 'c'],
            'col3': [True, False, True],
            'col4': pd.to_datetime(['2010-02-01', '2010-01-01', '2010-02-01']),
            'col5': [1, 2, 3]
        })

        # Run
        f_out = io.StringIO()
        with contextlib.redirect_stdout(f_out):
            ht.detect_initial_config(data)

        output = f_out.getvalue()

        # Assert
        assert ht._provided_field_sdtypes == {}
        assert ht._provided_field_transformers == {}

        assert ht.field_sdtypes == {
            'col1': 'float',
            'col2': 'categorical',
            'col3': 'boolean',
            'col4': 'datetime',
            'col5': 'integer'
        }

        field_transformers = {k: repr(v) for (k, v) in ht.field_transformers.items()}
        assert field_transformers == {
            'col1': "FloatFormatter(missing_value_replacement='mean')",
            'col2': 'FrequencyEncoder()',
            'col3': "BinaryEncoder(missing_value_replacement='mode')",
            'col4': "UnixTimestampEncoder(missing_value_replacement='mean')",
            'col5': "FloatFormatter(missing_value_replacement='mean')"
        }

        expected_output = '\n'.join((
            'Detecting a new config from the data ... SUCCESS',
            'Setting the new config ... SUCCESS',
            'Config:',
            '{',
            '    "sdtypes": {',
            '        "col1": "float",',
            '        "col2": "categorical",',
            '        "col3": "boolean",',
            '        "col4": "datetime",',
            '        "col5": "integer"',
            '    },',
            '    "transformers": {',
            '        "col1": "FloatFormatter(missing_value_replacement=\'mean\')",',
            '        "col2": "FrequencyEncoder()",',
            '        "col3": "BinaryEncoder(missing_value_replacement=\'mode\')",',
            '        "col4": "UnixTimestampEncoder(missing_value_replacement=\'mean\')",',
            '        "col5": "FloatFormatter(missing_value_replacement=\'mean\')"',
            '    }',
            '}',
            ''
        ))
        assert output == expected_output

    @patch('rdt.hyper_transformer.get_transformer_instance')
    def test__fit_field_transformer(self, get_transformer_instance_mock):
        """Test the ``_fit_field_transformer`` method.

        This tests that the ``_fit_field_transformer`` behaves as expected.
        It should fit the transformer it is provided, loops through its
        outputs, transform the data if the output is not ML ready and call
        itself recursively if it can.

        Setup:
            - A mock for ``get_transformer_instance``.
            - A mock for the transformer returned by ``get_transformer_instance``.
            The ``get_output_sdtypes`` method will return two outputs, one that
            is ML ready and one that isn't.

        Input:
            - A DataFrame with one column.
            - A column name to fit the transformer to.
            - A transformer.

        Output:
            - A DataFrame with columns that result from transforming the
            outputs of the original transformer.
        """
        # Setup
        data = pd.DataFrame({'a': [1, 2, 3]})
        transformed_data1 = pd.DataFrame({
            'a.out1': ['2', '4', '6'],
            'a.out2': [1, 2, 3]
        })
        transformer1 = Mock()
        transformer2 = Mock()
        transformer1.get_output_sdtypes.return_value = {
            'a.out1': 'categorical',
            'a.out2': 'numerical'
        }
        transformer1.get_next_transformers.return_value = {
            'a.out1': transformer2
        }
        transformer1.transform.return_value = transformed_data1
        transformer2.get_output_sdtypes.return_value = {
            'a.out1.value': 'numerical'
        }
        transformer2.get_next_transformers.return_value = None
        get_transformer_instance_mock.side_effect = [
            transformer1,
            transformer2,
            None,
            None
        ]
        ht = HyperTransformer()
        ht._get_next_transformer = Mock()
        ht._get_next_transformer.side_effect = [
            transformer2,
            None,
            None
        ]

        # Run
        out = ht._fit_field_transformer(data, 'a', transformer1)

        # Assert
        expected = pd.DataFrame({
            'a.out1': ['2', '4', '6'],
            'a.out2': [1, 2, 3]
        })
        pd.testing.assert_frame_equal(out, expected)
        transformer1.fit.assert_called_once()
        transformer1.transform.assert_called_once_with(data)
        transformer2.fit.assert_called_once()
        assert ht._transformers_sequence == [transformer1, transformer2]
        assert ht._transformers_tree == {
            'a': {'transformer': transformer1, 'outputs': ['a.out1', 'a.out2']},
            'a.out1': {'transformer': transformer2, 'outputs': ['a.out1.value']}
        }

    @patch('rdt.hyper_transformer.get_transformer_instance')
    def test__fit_field_transformer_multi_column_field_not_ready(
        self,
        get_transformer_instance_mock
    ):
        """Test the ``_fit_field_transformer`` method.

        This tests that the ``_fit_field_transformer`` behaves as expected.
        If the column is part of a multi-column field, and the other columns
        aren't present in the data, then it should not fit the next transformer.
        It should however, transform the data.

        Setup:
            - A mock for ``get_transformer_instance``.
            - A mock for the transformer returned by ``get_transformer_instance``.
            The ``get_output_sdtypes`` method will return one output that is part of
            a multi-column field.
            - A mock for ``_multi_column_fields`` to return the multi-column field.

        Input:
            - A DataFrame with two columns.
            - A column name to fit the transformer to.
            - A transformer.

        Output:
            - A DataFrame with columns that result from transforming the
            outputs of the original transformer.
        """
        # Setup
        data = pd.DataFrame({
            'a': [1, 2, 3],
            'b': [4, 5, 6]
        })
        transformed_data1 = pd.DataFrame({
            'a.out1': ['1', '2', '3'],
            'b': [4, 5, 6]
        })
        transformer1 = Mock()
        transformer2 = Mock()
        transformer1.get_output_sdtypes.return_value = {
            'a.out1': 'categorical'
        }
        transformer1.get_next_transformers.return_value = None
        transformer1.transform.return_value = transformed_data1
        get_transformer_instance_mock.side_effect = [transformer1]
        ht = HyperTransformer()
        ht._get_next_transformer = Mock()
        ht._get_next_transformer.side_effect = [transformer2]
        ht._multi_column_fields = Mock()
        ht._multi_column_fields.get.return_value = ('a.out1', 'b.out1')

        # Run
        out = ht._fit_field_transformer(data, 'a', transformer1)

        # Assert
        expected = pd.DataFrame({
            'a.out1': ['1', '2', '3'],
            'b': [4, 5, 6]
        })
        assert ht._output_columns == []
        pd.testing.assert_frame_equal(out, expected)
        transformer1.fit.assert_called_once()
        transformer1.transform.assert_called_once_with(data)
        transformer2.fit.assert_not_called()
        assert ht._transformers_sequence == [transformer1]

    @patch('rdt.hyper_transformer.warnings')
    def test__validate_all_fields_fitted(self, warnings_mock):
        """Test the ``_validate_all_fields_fitted`` method.

        Tests that the ``_validate_all_fields_fitted`` method raises a warning
        if there are fields in ``field_transformers`` that were not fitted.

        Setup:
            - A mock for warnings.
            - A mock for ``field_transformers`` with a misspelled field.
            - A mock for ``_fitted_fields`` containing the other fields.

        Expected behavior:
            - Warnings should be raised.
        """
        # Setup
        int_transformer = Mock()
        float_transformer = Mock()
        field_transformers = {
            'integer': int_transformer,
            'float': float_transformer,
            'intege': int_transformer
        }
        ht = HyperTransformer(field_transformers=field_transformers)
        ht._fitted_fields = {'integer', 'float'}

        # Run
        ht._validate_all_fields_fitted()

        # Assert
        warnings_mock.warn.assert_called_once()

    def test__sort_output_columns(self):
        """Test the ``_sort_output_columns`` method.

        Assert the method correctly sorts the ``_output_columns`` attribute
        according to ``_input_columns``.

        Setup:
            - Initialize the ``HyperTransformer`` with:
                - A mock for the ``get_final_output_columns`` method, with ``side_effect``
                set to the lists of generated output columns for each input column.
                - A list of columns names for ``_input_columns``.

        Expected behavior:
            - ``_output_columns`` should be sorted according to the ``_input_columns``.
        """
        # Setup
        ht = HyperTransformer()
        ht.get_final_output_columns = Mock()
        ht.get_final_output_columns.side_effect = [
            ['a.is_null'], ['b.value', 'b.is_null'], ['c.value']
        ]
        ht._input_columns = ['a', 'b', 'c']

        # Run
        ht._sort_output_columns()

        # Assert
        assert ht._output_columns == ['a.is_null', 'b.value', 'b.is_null', 'c.value']

    @patch('rdt.hyper_transformer.warnings')
    def test__validate_config(self, warnings_mock):
        """Test the ``_validate_config`` method.

        The method should throw a warnings if the ``sdtypes`` of any column name doesn't match
        the ``sdtype`` of its transformer.

        Setup:
            - A mock for warnings.

        Input:
            - A config with a transformers dict that has a transformer that doesn't match the
            sdtype for the same column in sdtypes dict.

        Expected behavior:
            - There should be a warning.
        """
        # Setup
        transformers = {
            'column1': FloatFormatter(),
            'column2': FrequencyEncoder()
        }
        sdtypes = {
            'column1': 'numerical',
            'column2': 'numerical'
        }
        config = {
            'sdtypes': sdtypes,
            'transformers': transformers
        }

        # Run
        HyperTransformer._validate_config(config)

        # Assert
        expected_message = (
            "You are assigning a categorical transformer to a numerical column ('column2'). "
            "If the transformer doesn't match the sdtype, it may lead to errors."
        )
        warnings_mock.warn.assert_called_once_with(expected_message)

    @patch('rdt.hyper_transformer.warnings')
    def test__validate_config_no_warning(self, warnings_mock):
        """Test the ``_validate_config`` method with no warning.

        The method should not throw a warnings if the ``sdtypes`` of all columns match
        the ``sdtype`` of their transformers.

        Setup:
            - A mock for warnings.

        Input:
            - A config with a transformers dict that matches the sdtypes for each column.

        Expected behavior:
            - There should be no warning.
        """
        # Setup
        transformers = {
            'column1': FloatFormatter(),
            'column2': FrequencyEncoder()
        }
        sdtypes = {
            'column1': 'numerical',
            'column2': 'categorical'
        }
        config = {
            'sdtypes': sdtypes,
            'transformers': transformers
        }

        # Run
        HyperTransformer._validate_config(config)

        # Assert
        warnings_mock.warn.assert_not_called()

    def test_get_config(self):
        """Test the ``get_config`` method.

        The method should return a dictionary containing the following keys:
            - sdtypes: Maps to a dictionary that maps column names to ``sdtypes``.
            - transformers: Maps to a dictionary that maps column names to transformers.

        Setup:
            - Add entries to the ``field_sdtypes`` attribute.
            - Add entries to the ``field_transformers`` attribute.

        Output:
            - A dictionary with the key sdtypes mapping to the ``field_sdtypes`` attribute and
            the key transformers mapping to the ``field_transformers`` attribute.
        """
        # Setup
        ht = HyperTransformer()
        ht.field_transformers = {
            'column1': FloatFormatter(),
            'column2': FrequencyEncoder()
        }
        ht.field_sdtypes = {
            'column1': 'numerical',
            'column2': 'categorical'
        }

        # Run
        config = ht.get_config()

        # Assert
        expected_config = {
            'sdtypes': ht.field_sdtypes,
            'transformers': ht.field_transformers
        }
        assert config == expected_config

    def test_get_config_empty(self):
        """Test the ``get_config`` method when the config is empty.

        The method should return a dictionary containing the following keys:
            - sdtypes: Maps to a dictionary that maps column names to ``sdtypes``.
            - transformers: Maps to a dictionary that maps column names to transformers.

        Output:
            - A dictionary with the key sdtypes mapping to an empty dict and the key
            transformers mapping to an empty dict.
        """
        # Setup
        ht = HyperTransformer()

        # Run
        config = ht.get_config()

        # Assert
        expected_config = {
            'sdtypes': {},
            'transformers': {}
        }
        assert config == expected_config

    def test_set_config(self):
        """Test the ``set_config`` method.

        The method should set the ``instance._provided_field_sdtypes``,
        ``instance.field_sdtypes``, ``instance._provided_field_transformers ``and
        ``instance.field_transformers`` attributes based on the config.

        Setup:
            - Mock the ``_validate_config`` method so no warnings get raised.

        Input:
            - A dict with two keys:
                - transformers: Maps to a dict that maps column names to transformers.
                - sdtypes: Maps to a dict that maps column names to ``sdtypes``.

        Expected behavior:
            - The attributes ``instance._provided_field_sdtypes``, ``instance.field_sdtypes``,
            ``instance._provided_field_transformers `` and ``instance.field_transformers``
            should be set.
        """
        # Setup
        transformers = {
            'column1': FloatFormatter(),
            'column2': FrequencyEncoder()
        }
        sdtypes = {
            'column1': 'numerical',
            'column2': 'categorical'
        }
        config = {
            'sdtypes': sdtypes,
            'transformers': transformers
        }
        ht = HyperTransformer()
        ht._validate_config = Mock()

        # Run
        ht.set_config(config)

        # Assert
        ht._validate_config.assert_called_once_with(config)
        assert ht._provided_field_transformers == config['transformers']
        assert ht.field_transformers == config['transformers']
        assert ht._provided_field_sdtypes == config['sdtypes']
        assert ht.field_sdtypes == config['sdtypes']

    def get_data(self):
        return pd.DataFrame({
            'integer': [1, 2, 1, 3],
            'float': [0.1, 0.2, 0.1, 0.1],
            'categorical': ['a', 'a', 'b', 'a'],
            'bool': [False, False, True, False],
            'datetime': pd.to_datetime(['2010-02-01', '2010-01-01', '2010-02-01', '2010-01-01'])
        })

    def get_transformed_data(self, drop=False):
        data = pd.DataFrame({
            'integer': [1, 2, 1, 3],
            'float': [0.1, 0.2, 0.1, 0.1],
            'categorical': ['a', 'a', 'b', 'a'],
            'bool': [False, False, True, False],
            'datetime': pd.to_datetime(['2010-02-01', '2010-01-01', '2010-02-01', '2010-01-01']),
            'integer.out': ['1', '2', '1', '3'],
            'integer.out.value': [1, 2, 1, 3],
            'float.value': [0.1, 0.2, 0.1, 0.1],
            'categorical.value': [0.375, 0.375, 0.875, 0.375],
            'bool.value': [0.0, 0.0, 1.0, 0.0],
            'datetime.value': [
                1.2649824e+18,
                1.262304e+18,
                1.2649824e+18,
                1.262304e+18
            ]
        })

        if drop:
            return data.drop([
                'integer',
                'float',
                'categorical',
                'bool',
                'datetime',
                'integer.out'
            ], axis=1)

        return data

    @patch('rdt.hyper_transformer.get_default_transformer')
    def test_fit(self, get_default_transformer_mock):
        """Test the ``fit`` method.

        Tests that the ``fit`` method loops through the fields in ``field_transformers``
        and ``field_sdtypes`` that are in the data. It should try to find a transformer
        in ``default_sdtype_transformers`` and then use the default if it doesn't find one
        when looping through ``field_sdtypes``. It should then call ``_fit_field_transformer``
        with the correct arguments.

        Setup:
            - A mock for ``_fit_field_transformer``.
            - A mock for ``_field_in_set``.
            - A mock for ``get_default_tranformer``.

        Input:
            - A DataFrame with multiple columns of different sdtypes.

        Expected behavior:
            - The ``_fit_field_transformer`` mock should be called with the correct
            arguments in the correct order.
        """
        # Setup
        int_transformer = Mock()
        int_out_transformer = Mock()
        float_transformer = Mock()
        categorical_transformer = Mock()
        bool_transformer = Mock()
        datetime_transformer = Mock()

        data = self.get_data()
        field_transformers = {
            'integer': int_transformer,
            'float': float_transformer,
            'integer.out': int_out_transformer
        }
        default_sdtype_transformers = {
            'boolean': bool_transformer,
            'categorical': categorical_transformer
        }
        get_default_transformer_mock.return_value = datetime_transformer
        ht = HyperTransformer(
            field_transformers=field_transformers,
            default_sdtype_transformers=default_sdtype_transformers
        )
        ht._fit_field_transformer = Mock()
        ht._fit_field_transformer.return_value = data
        ht._field_in_set = Mock()
        ht._field_in_set.side_effect = [True, True, False, False, False]
        ht._validate_all_fields_fitted = Mock()
        ht._sort_output_columns = Mock()

        # Run
        ht.fit(data)

        # Assert
        ht._fit_field_transformer.assert_has_calls([
            call(data, 'integer', int_transformer),
            call(data, 'float', float_transformer),
            call(data, 'categorical', categorical_transformer),
            call(data, 'bool', bool_transformer),
            call(data, 'datetime', datetime_transformer)
        ])
        ht._validate_all_fields_fitted.assert_called_once()
        ht._sort_output_columns.assert_called_once()

    def test_transform(self):
        """Test the ``transform`` method.

        Tests that ``transform`` loops through the ``_transformers_sequence``
        and calls ``transformer.transform`` in the correct order.

        Setup:
            - The ``_transformers_sequence`` will be hardcoded with a list
            of transformer mocks.
            - The ``_input_columns`` will be hardcoded.
            - The ``_output_columns`` will be hardcoded.

        Input:
            - A DataFrame of multiple sdtypes.

        Output:
            - The transformed DataFrame with the correct columns dropped.
        """
        # Setup
        int_transformer = Mock()
        int_out_transformer = Mock()
        float_transformer = Mock()
        categorical_transformer = Mock()
        bool_transformer = Mock()
        datetime_transformer = Mock()
        data = self.get_data()
        transformed_data = self.get_transformed_data()
        datetime_transformer.transform.return_value = transformed_data
        ht = HyperTransformer()
        ht._fitted = True
        ht._transformers_sequence = [
            int_transformer,
            int_out_transformer,
            float_transformer,
            categorical_transformer,
            bool_transformer,
            datetime_transformer
        ]
        ht._input_columns = list(data.columns)
        expected = self.get_transformed_data(True)
        ht._output_columns = list(expected.columns)

        # Run
        transformed = ht.transform(data)

        # Assert
        pd.testing.assert_frame_equal(transformed, expected)
        int_transformer.transform.assert_called_once()
        int_out_transformer.transform.assert_called_once()
        float_transformer.transform.assert_called_once()
        categorical_transformer.transform.assert_called_once()
        bool_transformer.transform.assert_called_once()
        datetime_transformer.transform.assert_called_once()

    def test_transform_raises_error_if_not_fitted(self):
        """Test that ``transform`` raises an error.

        The ``transform`` method should raise a ``NotFittedError`` if the
        ``_transformers_sequence`` is empty.

        Setup:
            - The ``_fitted`` attribute will be False.

        Input:
            - A DataFrame of multiple sdtypes.

        Expected behavior:
            - A ``NotFittedError`` is raised.
        """
        # Setup
        data = self.get_data()
        ht = HyperTransformer()

        # Run
        with pytest.raises(NotFittedError):
            ht.transform(data)

    def test_fit_transform(self):
        """Test call fit_transform"""
        # Run
        transformer = Mock()

        HyperTransformer.fit_transform(transformer, pd.DataFrame())

        # Asserts
        expect_call_count_fit = 1
        expect_call_count_transform = 1
        expect_call_args_fit = pd.DataFrame()
        expect_call_args_transform = pd.DataFrame()

        assert transformer.fit.call_count == expect_call_count_fit
        pd.testing.assert_frame_equal(
            transformer.fit.call_args[0][0],
            expect_call_args_fit
        )

        assert transformer.transform.call_count == expect_call_count_transform
        pd.testing.assert_frame_equal(
            transformer.transform.call_args[0][0],
            expect_call_args_transform
        )

    def test_reverse_transform(self):
        """Test the ``reverse_transform`` method.

        Tests that ``reverse_transform`` loops through the ``_transformers_sequence``
        in reverse order and calls ``transformer.reverse_transform``.

        Setup:
            - The ``_transformers_sequence`` will be hardcoded with a list
            of transformer mocks.
            - The ``_output_columns`` will be hardcoded.
            - The ``_input_columns`` will be hardcoded.

        Input:
            - A DataFrame of multiple sdtypes.

        Output:
            - The reverse transformed DataFrame with the correct columns dropped.
        """
        # Setup
        int_transformer = Mock()
        int_out_transformer = Mock()
        float_transformer = Mock()
        categorical_transformer = Mock()
        bool_transformer = Mock()
        datetime_transformer = Mock()
        data = self.get_transformed_data(True)
        reverse_transformed_data = self.get_transformed_data()
        int_transformer.reverse_transform.return_value = reverse_transformed_data
        ht = HyperTransformer()
        ht._fitted = True
        ht._transformers_sequence = [
            int_transformer,
            int_out_transformer,
            float_transformer,
            categorical_transformer,
            bool_transformer,
            datetime_transformer
        ]
        ht._output_columns = list(data.columns)
        expected = self.get_data()
        ht._input_columns = list(expected.columns)

        # Run
        reverse_transformed = ht.reverse_transform(data)

        # Assert
        pd.testing.assert_frame_equal(reverse_transformed, expected)
        int_transformer.reverse_transform.assert_called_once()
        int_out_transformer.reverse_transform.assert_called_once()
        float_transformer.reverse_transform.assert_called_once()
        categorical_transformer.reverse_transform.assert_called_once()
        bool_transformer.reverse_transform.assert_called_once()
        datetime_transformer.reverse_transform.assert_called_once()

    def test_reverse_transform_raises_error_if_not_fitted(self):
        """Test that ``reverse_transform`` raises an error.

        The ``reverse_transform`` method should raise a ``NotFittedError`` if the
        ``_transformers_sequence`` is empty.

        Setup:
            - The ``_fitted`` attribute will be False.

        Input:
            - A DataFrame of multiple sdtypes.

        Expected behavior:
            - A ``NotFittedError`` is raised.
        """
        # Setup
        data = self.get_transformed_data()
        ht = HyperTransformer()

        # Run
        with pytest.raises(NotFittedError):
            ht.reverse_transform(data)

    @patch('rdt.hyper_transformer.print')
    def test_update_transformers_by_sdtype_no_field_sdtypes(self, mock_print):
        """Test that ``update_transformers_by_sdtype`` prints an error message.

        Ensure that no changes have been made and an error message has been printed.

        Setup:
            - HyperTransformer instance.

        Mock:
            - Print function.

        Side Effects:
            - HyperTransformer's field_transformers have not been upated.
            - Print has been called once with the expected error message.
        """
        # Setup
        ht = HyperTransformer()

        # Run
        expected_msg = (
            'Nothing to update. Use the `detect_initial_config` method to '
            'pre-populate all the sdtypes and transformers from your dataset.'
        )
        with pytest.raises(Error, match=expected_msg):
            ht.update_transformers_by_sdtype('categorical', object())

        # Assert
        assert ht.field_transformers == {}

    @patch('rdt.hyper_transformer.print')
    def test_update_transformers_by_sdtype_field_sdtypes_not_fitted(self, mock_print):
        """Test that ``update_transformers_by_sdtype`` doesn't print anything.

        Ensure that the ``field_transformers`` that have the input ``sdtype`` have been updated.

        Setup:
            - HyperTransformer instance with ``field_transformers`` and ``field-data_types``.

        Mock:
            - Print function.

        Side Effects:
            - HyperTransformer's ``field_transformers`` are upated with the input data.
            - Print not called.
        """
        # Setup
        ht = HyperTransformer()
        ht.field_transformers = {
            'categorical_column': 'rdt.transformers.BaseTransformer',
            'numerical_column': 'rdt.transformers.FloatFormatter',
        }
        ht.field_sdtypes = {
            'categorical_column': 'categorical',
            'numerical_column': 'numerical',

        }
        transformer = object()

        # Run
        ht.update_transformers_by_sdtype('categorical', transformer)

        # Assert
        mock_print.assert_not_called()
        expected_field_transformers = {
            'categorical_column': transformer,
            'numerical_column': 'rdt.transformers.FloatFormatter',
        }
        assert ht.field_transformers == expected_field_transformers

    @patch('rdt.hyper_transformer.warnings')
    @patch('rdt.hyper_transformer.print')
    def test_update_transformers_by_sdtype_field_sdtypes_fitted(self, mock_print, mock_warnings):
        """Test that ``update_transformers_by_sdtype`` doesn't print anything.

        Ensure that the ``field_transformers`` that have the input ``sdtype`` have been updated and
        a warning message has been printed.

        Setup:
            - HyperTransformer instance with ``field_transformers`` and ``field-data_types``.

        Mock:
            - Print function.
            - Warnings from the HyperTransformer.

        Side Effects:
            - HyperTransformer's ``field_transformers`` are upated with the input data.
            - Print not called.
        """
        # Setup
        ht = HyperTransformer()
        ht._fitted = True
        ht.field_transformers = {'categorical_column': 'rdt.transformers.BaseTransformer'}
        ht.field_sdtypes = {'categorical_column': 'categorical'}
        transformer = object()

        # Run
        ht.update_transformers_by_sdtype('categorical', transformer)

        # Assert
        expected_warnings_msg = (
            'For this change to take effect, please refit your data using '
            "'fit' or 'fit_transform'."
        )

        mock_print.assert_not_called()
        mock_warnings.warn.assert_called_once_with(expected_warnings_msg)
        assert ht.field_transformers == {'categorical_column': transformer}

    def test_update_field_sdtypes(self):
        """Test the ``update_field_sdtypes`` method.

        This method should update the ``field_sdtypes`` and
        ``_provided_field_sdtypes`` attributes.

        Setup:
            - Initialize ``HyperTransformer`` with ``field_sdtypes`` having
            one entry.

        Input:
            - Dict mapping fields to sdtypes.
        """
        # Setup
        field_sdtypes = {
            'a': 'categorical',
            'b': 'integer'
        }
        ht = HyperTransformer(field_sdtypes={'a': 'float'})
        ht._transformers_sequence = [FrequencyEncoder()]

        # Run
        ht.update_field_sdtypes(field_sdtypes)

        # Assert
        assert ht._provided_field_sdtypes == {'a': 'categorical', 'b': 'integer'}
        assert ht.field_sdtypes == {'a': 'categorical', 'b': 'integer'}

    def test_get_default_sdtype_transformers(self):
        """Test the ``get_default_sdtype_transformers`` method.

        This method should return the ``default_sdtype_transformers`` attribute.

        Output:
            - Dict mapping sdtypes to transformers.
        """
        # Setup
        sdtype_transformers = {
            'categorical': FrequencyEncoder,
            'integer': FloatFormatter
        }
        ht = HyperTransformer(default_sdtype_transformers=sdtype_transformers)

        # Run
        out = ht.get_default_sdtype_transformers()

        # Assert
        assert out == {'categorical': FrequencyEncoder, 'integer': FloatFormatter}

    @patch('rdt.hyper_transformer.warnings')
    def test_update_transformers_fitted(self, mock_warnings):
        """Test update transformers.

        Ensure that the function updates properly the ``self.field_transformers`` and prints the
        expected messages to guide the end-user.

        Setup:
            - Initialize ``HyperTransformer`` with ``_fitted`` as ``True``.
            - Set some ``field_transformers``.

        Input:
            - Dictionary with a ``column_name`` and ``object()``.

        Mock:
            - Patch the ``warnings`` in order to ensure that expected message is being
              warn to the end user.
            - Transformer, mock for the transformer.

        Side Effects:
            - ``self.field_transformers`` has been updated.
        """
        # Setup
        instance = HyperTransformer()
        instance._fitted = True
        instance.field_transformers = {'a': object()}
        mock_transformer = Mock()
        mock_transformer.get_input_type.return_value = 'datetime'
        column_name_to_transformer = {
            'my_column': mock_transformer
        }

        # Run
        instance.update_transformers(column_name_to_transformer)

        # Assert
        expected_message = (
            "For this change to take effect, please refit your data using 'fit' "
            "or 'fit_transform'."
        )

        mock_warnings.warn.assert_called_once_with(expected_message)
        assert instance.field_transformers['my_column'] == mock_transformer
        assert instance._provided_field_transformers == {'my_column': mock_transformer}

    @patch('rdt.hyper_transformer.warnings')
    def test_update_transformers_not_fitted(self, mock_warnings):
        """Test update transformers.

        Ensure that the function updates properly the ``self.field_transformers`` and prints the
        expected messages to guide the end-user.

        Setup:
            - Initialize ``HyperTransformer`` with ``_fitted`` as ``False``.
            - Set some ``field_transformers``.

        Input:
            - Dictionary with a ``column_name`` and a ``Mock`` transformer.

        Mock:
            - Patch the ``print`` function in order to ensure that expected message is being
              printed to the end user.
            - Transformer, mock for the transformer.

        Side Effects:
            - ``self.field_transformers`` has been updated.
            - ``self._provided_field_transformers`` has been updated.
        """
        # Setup
        instance = HyperTransformer()
        instance._fitted = False
        instance.field_transformers = {'a': object()}
        mock_transformer = Mock()
        mock_transformer.get_input_type.return_value = 'datetime'
        column_name_to_transformer = {
            'my_column': mock_transformer
        }

        # Run
        instance.update_transformers(column_name_to_transformer)

        # Assert
        mock_warnings.warn.assert_not_called()
        assert instance.field_transformers['my_column'] == mock_transformer
        assert instance._provided_field_transformers == {'my_column': mock_transformer}

    def test_update_transformers_no_field_transformers(self):
        """Test update transformers.

        Ensure that the function updates properly the ``self.field_transformers`` and prints the
        expected messages to guide the end-user.

        Setup:
            - Initialize ``HyperTransformer`` with ``_fitted`` as ``False``.

        Input:
            - Dictionary with a ``column_name`` and a ``Mock`` transformer.

        Mock:
            - Patch the ``print`` function in order to ensure that expected message is being
              printed to the end user.
            - Transformer, mock for the replacement transformer.

        Side Effects:
            - ``self.field_transformers`` has been updated.
            - ``self._provided_field_transformers`` has been updated.
        """
        # Setup
        instance = HyperTransformer()
        instance._fitted = False
        mock_transformer = Mock()
        mock_transformer.get_input_type.return_value = 'datetime'
        column_name_to_transformer = {
            'my_column': mock_transformer
        }

        # Run
        expected_msg = (
            'Nothing to update. Use the ``detect_initial_config`` method to pre-populate '
            'all the sdtypes and transformers from your dataset.'
        )
        with pytest.raises(Error, match=expected_msg):
            instance.update_transformers(column_name_to_transformer)

    @patch('rdt.hyper_transformer.print')
    def test_update_transformers_missmatch_sdtypes(self, mock_warnings):
        """Test update transformers.

        Ensure that the function updates properly the ``self.field_transformers`` and prints the
        expected messages to guide the end-user.

        Setup:
            - Initialize ``HyperTransformer``.
            - Set ``field_transformers`` to contain a column and a mock transformer to be
              updated by ``update_transformer``.

        Input:
            - Dictionary with a ``column_name`` and a ``Mock`` transformer.

        Mock:
            - Patch the ``print`` function in order to ensure that expected message is being
              printed to the end user.
            - Transformer, mock for the replacement transformer.

        Side Effects:
            - ``self.field_transformers`` has been updated.
            - ``self._provided_field_transformers`` has been updated.
        """
        # Setup
        instance = HyperTransformer()
        instance._fitted = False
        mock_numerical = Mock()
        instance.field_transformers = {'my_column': mock_numerical}
        instance.field_sdtypes = {'my_column': 'categorical'}
        mock_transformer = Mock()
        mock_transformer.get_input_type.return_value = 'datetime'
        column_name_to_transformer = {
            'my_column': mock_transformer
        }

        # Run
        instance.update_transformers(column_name_to_transformer)

        # Assert
        expected_call = (
            'You are assigning a datetime transformer to a numerical column '
            "(my_column). If the transformer doesn't match the "
            'sdtype, it may lead to errors.'
        )

        assert mock_warnings.called_once_with(expected_call)
        assert instance.field_transformers['my_column'] == mock_transformer
        assert instance._provided_field_transformers == {'my_column': mock_transformer}

    def test_set_first_transformers_for_fields(self):
        """Test the ``set_first_transformers_for_fields`` method.

        This method should update the ``field_transformers`` and
        ``_provided_field_transformers`` attributes.

        Setup:
            - Initialize ``HyperTransformer`` with ``field_transformers`` dict that only
            has some fields set.

        Input:
            - Dict mapping one new field to a transformer and one old field to a different
            transformer.
        """
        # Setup
        field_transformers = {
            'a': FrequencyEncoder,
            'b': FloatFormatter
        }
        ht = HyperTransformer(field_transformers=field_transformers)
        ht._transformers_sequence = [FrequencyEncoder()]

        # Run
        ht.set_first_transformers_for_fields({
            'c': BinaryEncoder,
            'b': FrequencyEncoder
        })

        # Assert
        assert ht.field_transformers == {
            'a': FrequencyEncoder,
            'b': FrequencyEncoder,
            'c': BinaryEncoder
        }
        assert ht._provided_field_transformers == {
            'a': FrequencyEncoder,
            'b': FrequencyEncoder,
            'c': BinaryEncoder
        }

    def test_get_transformer(self):
        """Test the ``get_transformer`` method.

        The method should return the transformer instance stored for the field in the
        ``_transformers_tree``.

        Setup:
            - Set the ``_transformers_tree`` to have values for a few fields.
            - Set ``_fitted`` to ``True``.

        Input:
            - Each field name.

        Output:
            - The transformer instance used for each field.
        """
        # Setup
        ht = HyperTransformer()
        transformer1 = Mock()
        transformer2 = Mock()
        transformer3 = Mock()
        ht._transformers_tree = {
            'field': {'transformer': transformer1, 'outputs': ['field.out1', 'field.out2']},
            'field.out1': {'transformer': transformer2, 'outputs': ['field.out1.value']},
            'field.out2': {'transformer': transformer3, 'outputs': ['field.out2.value']}
        }
        ht._fitted = True

        # Run
        out1 = ht.get_transformer('field')
        out2 = ht.get_transformer('field.out1')
        out3 = ht.get_transformer('field.out2')

        # Assert
        out1 == transformer1
        out2 == transformer2
        out3 == transformer3

    def test_get_transformer_raises_error_if_not_fitted(self):
        """Test that ``get_transformer`` raises ``NotFittedError``.

        If the ``HyperTransformer`` hasn't been fitted, a ``NotFittedError`` should be raised.

        Setup:
            - Set ``_fitted`` to ``False``.

        Expected behavior:
            - ``NotFittedError`` is raised.
        """
        # Setup
        ht = HyperTransformer()
        transformer1 = Mock()
        ht._transformers_tree = {
            'field1': {'transformer': transformer1, 'outputs': ['field1.out1', 'field1.out2']}
        }
        ht._fitted = False

        # Run / Assert
        with pytest.raises(NotFittedError):
            ht.get_transformer('field1')

    def test_get_output_transformers(self):
        """Test the ``get_output_transformers`` method.

        The method should return a dict mapping each output column created from
        transforming the specified field, to the transformers to be used on them.

        Setup:
            - Set the ``_transformers_tree`` to have values for a few fields.
            - Set ``_fitted`` to ``False``.

        Output:
            - Dict mapping the outputs of the specified field to the transformers used on them.
        """
        # Setup
        ht = HyperTransformer()
        transformer1 = Mock()
        transformer2 = Mock()
        transformer3 = Mock()
        transformer4 = Mock()
        ht._transformers_tree = {
            'field1': {'transformer': transformer1, 'outputs': ['field1.out1', 'field1.out2']},
            'field1.out1': {'transformer': transformer2, 'outputs': ['field1.out1.value']},
            'field1.out2': {'transformer': transformer3, 'outputs': ['field1.out2.value']},
            'field2': {'transformer': transformer4, 'outputs': ['field2.value']}
        }
        ht._fitted = True

        # Run
        output_transformers = ht.get_output_transformers('field1')

        # Assert
        output_transformers == {
            'field1.out1': transformer2,
            'field1.out2': transformer3
        }

    def test_get_output_transformers_raises_error_if_not_fitted(self):
        """Test that the ``get_output_transformers`` raises ``NotFittedError``.

        If the ``HyperTransformer`` hasn't been fitted, a ``NotFittedError`` should be raised.

        Setup:
            - Set ``_fitted`` to ``False``.

        Expected behavior:
            - ``NotFittedError`` is raised.
        """
        # Setup
        ht = HyperTransformer()
        ht._fitted = False

        # Run / Assert
        with pytest.raises(NotFittedError):
            ht.get_output_transformers('field')

    def test_get_final_output_columns(self):
        """Test the ``get_fianl_output_columns`` method.

        The method should traverse the tree starting at the provided field and return a list of
        all final column names (leaf nodes) that are descedants of that field.

        Setup:
            - Set the ``_transformers_tree`` to have some fields with multiple generations
            of descendants.
            - Set ``_fitted`` to ``False``.

        Output:
            - List of all column nodes with the specified field as an ancestor.
        """
        # Setup
        ht = HyperTransformer()
        transformer = Mock()
        ht._transformers_tree = {
            'field1': {'transformer': transformer, 'outputs': ['field1.out1', 'field1.out2']},
            'field1.out1': {'transformer': transformer, 'outputs': ['field1.out1.value']},
            'field1.out2': {
                'transformer': transformer,
                'outputs': ['field1.out2.out1', 'field.out2.out2']
            },
            'field1.out2.out1': {
                'transformer': transformer,
                'outputs': ['field1.out2.out1.value']
            },
            'field1.out2.out2': {
                'transformer': transformer,
                'outputs': ['field1.out2.out2.value']
            },
            'field2': {'transformer': transformer, 'outputs': ['field2.value']}
        }
        ht._fitted = True

        # Run
        outputs = ht.get_final_output_columns('field1')

        # Assert
        outputs == ['field1.out1.value', 'field1.out2.out1.value', 'field1.out2.out2.value']

    def test_get_final_output_columns_raises_error_if_not_fitted(self):
        """Test that the ``get_final_output_columns`` raises ``NotFittedError``.

        If the ``HyperTransformer`` hasn't been fitted, a ``NotFittedError`` should be raised.

        Setup:
            - Set ``_fitted`` to ``False``.

        Expected behavior:
            - ``NotFittedError`` is raised.
        """
        # Setup
        ht = HyperTransformer()
        ht._fitted = False

        # Run / Assert
        with pytest.raises(NotFittedError):
            ht.get_final_output_columns('field')

    def test_get_transformer_tree_yaml(self):
        """Test the ``get_transformer_tree_yaml`` method.

        The method should return a YAML representation of the tree.

        Setup:
            - Set the ``_transformers_tree`` to have values for a few fields.

        Output:
            - YAML object rrepresenting tree.
        """
        # Setup
        ht = HyperTransformer()
        ht._transformers_tree = defaultdict(dict, {
            'field1': {
                'transformer': FrequencyEncoder(),
                'outputs': ['field1.out1', 'field1.out2']
            },
            'field1.out1': {
                'transformer': FloatFormatter(),
                'outputs': ['field1.out1.value']
            },
            'field1.out2': {
                'transformer': FloatFormatter(),
                'outputs': ['field1.out2.value']
            },
            'field2': {'transformer': FrequencyEncoder(), 'outputs': ['field2.value']}
        })
        ht._fitted = True

        # Run
        tree_yaml = ht.get_transformer_tree_yaml()

        # Assert
        assert tree_yaml == (
            'field1:\n  outputs:\n  - field1.out1\n  - field1.out2\n  '
            'transformer: FrequencyEncoder\nfield1.out1:\n  outputs:\n  - '
            'field1.out1.value\n  transformer: FloatFormatter\nfield1.out2:\n  '
            'outputs:\n  - field1.out2.value\n  transformer: FloatFormatter\nfield2:\n  '
            'outputs:\n  - field2.value\n  transformer: FrequencyEncoder\n'
        )
