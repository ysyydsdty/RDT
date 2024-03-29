from unittest import TestCase
from unittest.mock import Mock

import numpy as np
import pandas as pd

from rdt.transformers import BinaryEncoder
from rdt.transformers.null import NullTransformer


class TestBinaryEncoder(TestCase):

    def test___init__(self):
        """Test default instance"""
        # Run
        transformer = BinaryEncoder()

        # Asserts
        error_message = 'Unexpected missing_value_replacement'
        assert transformer.missing_value_replacement is None, error_message
        assert not transformer.model_missing_values, 'model_missing_values is False by default'

    def test_get_output_sdtypes_model_missing_values_column_created(self):
        """Test the ``get_output_sdtypes`` method when a null column is created.

        When a null column is created, this method should apply the ``_add_prefix``
        method to the following dictionary of output sdtypes:

        output_sdtypes = {
            'value': 'float',
            'is_null': 'float'
        }

        Setup:
            - initialize a ``BinaryEncoder`` transformer which:
                - sets ``self.null_transformer`` to a ``NullTransformer`` where
                ``self._model_missing_values`` is True.
                - sets ``self.column_prefix`` to a string.

        Output:
            - the ``output_sdtypes`` dictionary, but with ``self.column_prefix``
            added to the beginning of the keys.
        """
        # Setup
        transformer = BinaryEncoder()
        transformer.null_transformer = NullTransformer(missing_value_replacement='fill')
        transformer.null_transformer._model_missing_values = True
        transformer.column_prefix = 'abc'

        # Run
        output = transformer.get_output_sdtypes()

        # Assert
        expected = {
            'abc.value': 'float',
            'abc.is_null': 'float'
        }
        assert output == expected

    def test__fit_missing_value_replacement_ignore(self):
        """Test _fit missing_value_replacement equal to ignore"""
        # Setup
        data = pd.Series([False, True, True, False, True])

        # Run
        transformer = BinaryEncoder(missing_value_replacement=None)
        transformer._fit(data)

        # Asserts
        error_msg = 'Unexpected fill value'
        assert transformer.null_transformer._missing_value_replacement is None, error_msg

    def test__fit_missing_value_replacement_not_ignore(self):
        """Test _fit missing_value_replacement not equal to ignore"""
        # Setup
        data = pd.Series([False, True, True, False, True])

        # Run
        transformer = BinaryEncoder(missing_value_replacement=0)
        transformer._fit(data)

        # Asserts
        error_msg = 'Unexpected fill value'
        assert transformer.null_transformer._missing_value_replacement == 0, error_msg

    def test__fit_array(self):
        """Test _fit with numpy.array"""
        # Setup
        data = pd.Series([False, True, True, False, True])

        # Run
        transformer = BinaryEncoder(missing_value_replacement=0)
        transformer._fit(data)

        # Asserts
        error_msg = 'Unexpected fill value'
        assert transformer.null_transformer._missing_value_replacement == 0, error_msg

    def test__transform_series(self):
        """Test transform pandas.Series"""
        # Setup
        data = pd.Series([False, True, None, True, False])

        # Run
        transformer = Mock()

        BinaryEncoder._transform(transformer, data)

        # Asserts
        expect_call_count = 1
        expect_call_args = pd.Series([0., 1., None, 1., 0.], dtype=float)

        error_msg = 'NullTransformer.transform must be called one time'
        assert transformer.null_transformer.transform.call_count == expect_call_count, error_msg
        pd.testing.assert_series_equal(
            transformer.null_transformer.transform.call_args[0][0],
            expect_call_args
        )

    def test__transform_array(self):
        """Test transform numpy.array"""
        # Setup
        data = pd.Series([False, True, None, True, False])

        # Run
        transformer = Mock()

        BinaryEncoder._transform(transformer, data)

        # Asserts
        expect_call_count = 1
        expect_call_args = pd.Series([0., 1., None, 1., 0.], dtype=float)

        error_msg = 'NullTransformer.transform must be called one time'
        assert transformer.null_transformer.transform.call_count == expect_call_count, error_msg
        pd.testing.assert_series_equal(
            transformer.null_transformer.transform.call_args[0][0],
            expect_call_args
        )

    def test__reverse_transform_missing_value_replacement_ignore(self):
        """Test _reverse_transform with missing_value_replacement equal to ignore"""
        # Setup
        data = pd.Series([0.0, 1.0, 0.0, 1.0, 0.0])

        # Run
        transformer = Mock()
        transformer.missing_value_replacement = None

        result = BinaryEncoder._reverse_transform(transformer, data)

        # Asserts
        expect = np.array([False, True, False, True, False])
        expect_call_count = 0

        np.testing.assert_equal(result, expect)
        error_msg = (
            'NullTransformer.reverse_transform should not be called when'
            'missing_value_replacement is ignore'
        )
        transformer_call_count = transformer.null_transformer.reverse_transform.call_count
        assert transformer_call_count == expect_call_count, error_msg

    def test__reverse_transform_missing_value_replacement_not_ignore(self):
        """Test _reverse_transform with missing_value_replacement not equal to ignore"""
        # Setup
        data = np.array([0.0, 1.0, 0.0, 1.0, 0.0])
        transformed_data = np.array([0.0, 1.0, 0.0, 1.0, 0.0])

        # Run
        transformer = Mock()
        transformer.missing_value_replacement = 0
        transformer.null_transformer.reverse_transform.return_value = transformed_data

        result = BinaryEncoder._reverse_transform(transformer, data)

        # Asserts
        expect = np.array([False, True, False, True, False])
        expect_call_count = 1

        np.testing.assert_equal(result, expect)

        error_msg = (
            'NullTransformer.reverse_transform should not be called when '
            'missing_value_replacement is ignore'
        )
        reverse_transform_call_count = transformer.null_transformer.reverse_transform.call_count
        assert reverse_transform_call_count == expect_call_count, error_msg

    def test__reverse_transform_not_null_values(self):
        """Test _reverse_transform not null values correctly"""
        # Setup
        data = np.array([1., 0., 1.])

        # Run
        transformer = Mock()
        transformer.missing_value_replacement = None

        result = BinaryEncoder._reverse_transform(transformer, data)

        # Asserts
        expected = np.array([True, False, True])

        assert isinstance(result, pd.Series)
        np.testing.assert_equal(result.array, expected)

    def test__reverse_transform_2d_ndarray(self):
        """Test _reverse_transform not null values correctly"""
        # Setup
        data = np.array([[1.], [0.], [1.]])

        # Run
        transformer = Mock()
        transformer.missing_value_replacement = None

        result = BinaryEncoder._reverse_transform(transformer, data)

        # Asserts
        expected = np.array([True, False, True])

        assert isinstance(result, pd.Series)
        np.testing.assert_equal(result.array, expected)

    def test__reverse_transform_float_values(self):
        """Test the ``_reverse_transform`` method with decimals.

        Expect that the ``_reverse_transform`` method handles decimal inputs
        correctly by rounding them.

        Input:
            - Transformed data with decimal values.
        Output:
            - Reversed transformed data.
        """
        # Setup
        data = np.array([1.2, 0.32, 1.01])
        transformer = Mock()
        transformer.missing_value_replacement = None

        # Run
        result = BinaryEncoder._reverse_transform(transformer, data)

        # Asserts
        expected = np.array([True, False, True])

        assert isinstance(result, pd.Series)
        np.testing.assert_equal(result.to_numpy(), expected)

    def test__reverse_transform_float_values_out_of_range(self):
        """Test the ``_reverse_transform`` method with decimals that are out of range.

        Expect that the ``_reverse_transform`` method handles decimal inputs
        correctly by rounding them. If the rounded decimal inputs are < 0 or > 1, expect
        expect them to be clipped.

        Input:
            - Transformed data with decimal values, some of which round to < 0 or > 1.
        Output:
            - Reversed transformed data.
        """
        # Setup
        data = np.array([1.9, -0.7, 1.01])
        transformer = Mock()
        transformer.missing_value_replacement = None

        # Run
        result = BinaryEncoder._reverse_transform(transformer, data)

        # Asserts
        expected = np.array([True, False, True])

        assert isinstance(result, pd.Series)
        np.testing.assert_equal(result.array, expected)

    def test__reverse_transform_numpy_nan(self):
        """Test the ``_reverse_transform`` method with decimals that are out of range.

        Expect that the ``_reverse_transform`` method contains the `np.nan` instead of
        other `nan` value.

        Input:
            - Transformed data with decimal values, some of which are ``np.nan``.

        Mock:
            - Mock `np.nan`.

        Output:
            - Reversed transformed data containing `np.nan` mocked value.
        """
        # Setup
        data = np.array([1.9, np.nan, 1.01])
        transformer = Mock()
        transformer.missing_value_replacement = None

        # Run
        result = BinaryEncoder._reverse_transform(transformer, data)

        # Asserts
        assert np.isnan(result[1])
        assert isinstance(result[1], float)
