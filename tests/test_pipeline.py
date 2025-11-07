import unittest
import pandas as pd
from unittest.mock import patch, MagicMock
import sys
import os

from scripts.pipeline import Pipeline

@patch('scripts.pipeline.ClickUpConnector')
class TestPipeline(unittest.TestCase):

    def test_step1_export_deduplication(self, MockClickUpConnector):
        # Create a mock instance of the ClickUpConnector
        mock_connector = MockClickUpConnector.return_value
        mock_connector.test_connection.return_value = True

        # Sample data with duplicates, whitespace, and nulls
        sample_data = {
            'task_id': ['1', '2', '3', '4', '5', '6'],
            'company': [' Company A ', 'Company B', 'Company A', None, '', 'Company C'],
            'description': ['desc A1', 'desc B', 'desc A2', 'desc D', 'desc E', 'desc C'],
            'email': ['a1@test.com', 'b@test.com', 'a2@test.com', 'd@test.com', 'e@test.com', 'c@test.com']
        }
        sample_df = pd.DataFrame(sample_data)

        # Configure the mock to return the sample DataFrame
        mock_connector.export_leads.return_value = sample_df

        # Initialize the pipeline (with a dummy config file path)
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', new_callable=unittest.mock.mock_open, read_data='{"clickup_api_key": "fake_key", "list_id": "fake_list"}'):
            pipeline = Pipeline()

        # Run the step1_export method
        result_df = pipeline.step1_export()

        # --- Assertions ---
        # 1. Check that rows with null/empty company names are dropped
        self.assertEqual(len(result_df), 3)

        # 2. Check that task_ids are correctly aggregated for 'Company A'
        company_a_row = result_df[result_df['company'] == 'Company A'].iloc[0]
        self.assertIn('1', company_a_row['task_id'])
        self.assertIn('3', company_a_row['task_id'])

        # 3. Check that other columns retain the 'first' value
        self.assertEqual(company_a_row['description'], 'desc A1')

        # 4. Check that a non-duplicated company is preserved correctly
        company_b_row = result_df[result_df['company'] == 'Company B'].iloc[0]
        self.assertEqual(company_b_row['task_id'], '2')

if __name__ == '__main__':
    unittest.main()
