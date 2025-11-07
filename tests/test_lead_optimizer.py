import unittest
from unittest.mock import patch, Mock
from scripts.lead_optimizer import LeadOptimizer

class TestLeadOptimizer(unittest.TestCase):

    def setUp(self):
        self.optimizer = LeadOptimizer()

    @patch('requests.Session.get')
    def test_check_nonprofit_status_propublica_success(self, mock_get):
        # Mock the API response from ProPublica
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'organizations': [{
                'ein': '123456789',
                'name': 'Test Charity'
            }]
        }
        mock_get.return_value = mock_response

        # Mock the detailed response
        mock_detail_response = Mock()
        mock_detail_response.status_code = 200
        mock_detail_response.json.return_value = {
            'organization': {
                'name': 'Test Charity',
                'city': 'Test City',
                'state': 'TS',
                'ntee_code': 'A01',
                'ruling_date': '2022-01-01',
                'revenue_amount': 1000000,
                'asset_amount': 5000000
            }
        }
        # The first call is for the search, the second for the details
        mock_get.side_effect = [mock_response, mock_detail_response]


        result = self.optimizer.check_nonprofit_status('Test Charity')
        self.assertTrue(result['is_nonprofit'])
        self.assertEqual(result['ein'], '123456789')
        self.assertEqual(result['nonprofit_name'], 'Test Charity')
        self.assertEqual(result['revenue'], 1000000)

    @patch('requests.Session.get')
    def test_check_nonprofit_status_propublica_fail(self, mock_get):
        # Mock a failed API response from ProPublica
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'organizations': []}
        mock_get.return_value = mock_response

        result = self.optimizer.check_nonprofit_status('Unknown Org')
        self.assertFalse(result['is_nonprofit'])

    def test_score_for_product_compass(self):
        # Test a lead that is a good fit for Compass
        lead_data = {
            'company': 'Halfway House Recovery',
            'mission_statement': 'We provide residential recovery programs for individuals.',
            'org_type': 'halfway_house',
            'is_nonprofit': True
        }
        result = self.optimizer.score_for_product(lead_data, 'compass')
        self.assertGreater(result['score'], 5.0)
        self.assertIn('High-value org type: halfway_house', result['reason'])

    def test_score_for_product_upcurve(self):
        # Test a lead that is a good fit for Upcurve
        lead_data = {
            'company': 'New Charity Foundation',
            'is_nonprofit': True,
            'has_donation_page': True,
            'revenue': 1000000,
            'ruling_year': '2020'
        }
        result = self.optimizer.score_for_product(lead_data, 'upcurve')
        self.assertGreaterEqual(result['score'], 6.5)
        self.assertIn('Verified nonprofit (6.5)', result['reason'])
        self.assertIn('Has donation page', result['reason'])
        self.assertIn('Small nonprofit (<$5M)', result['reason'])

    def test_classify_organization_b2b_override(self):
        # Test that B2B keywords override other classifications
        org_data = {
            'company': 'Recovery Software Solutions',
            'mission_statement': 'We provide software solutions for recovery centers.'
        }
        result = self.optimizer.classify_organization(org_data)
        self.assertEqual(result['org_type'], 'generic_b2b')
        self.assertIn('software', result['org_type_keywords'])
        self.assertIn('solutions', result['org_type_keywords'])

    def test_score_for_product_requires_nonprofit(self):
        # Test that Upcurve requires a nonprofit
        lead_data = {'company': 'For-Profit Inc.', 'is_nonprofit': False}
        result = self.optimizer.score_for_product(lead_data, 'upcurve')
        self.assertEqual(result['score'], 2.0)
        self.assertEqual(result['reason'], 'Not a nonprofit (required for this product)')

if __name__ == '__main__':
    unittest.main()
