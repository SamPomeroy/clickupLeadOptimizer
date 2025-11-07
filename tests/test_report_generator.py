import unittest
import pandas as pd
from scripts.report_generator import ReportGenerator

class TestReportGenerator(unittest.TestCase):

    def setUp(self):
        self.reporter = ReportGenerator()
        self.test_df = pd.DataFrame({
            'company': ['Org1', 'Org2', 'Org3'],
            'email': ['test1@email.com', 'test2@email.com', 'test3@email.com'],
            'phone': ['111', '222', '333'],
            'compass_score': [8.5, 6.2, 9.1],
            'upcurve_score': [5.0, 8.8, 7.5],
            'is_nonprofit': [False, True, True],
            'org_type': ['halfway_house', 'nonprofit_general', 'recovery_center'],
            'data_quality_score': [0.8, 0.9, 0.85],
            'has_donation_page': [False, True, True]
        })
        self.config = {
            'product_thresholds': {
                'compass': {'qualified': 6, 'high_priority': 8},
                'upcurve': {'qualified': 6, 'high_priority': 8}
            }
        }

    def test_generate_executive_summary(self):
        summary = self.reporter.generate_executive_summary(self.test_df, {}, self.config)

        # Check for key sections
        self.assertIn('CLICKUP LEAD OPTIMIZER - EXECUTIVE SUMMARY', summary)
        self.assertIn('COMPASS - Residential Program Management', summary)
        self.assertIn('UPCURVE - Nonprofit Fundraising Platform', summary)

        # Check for correct metrics
        self.assertIn('Total Leads Processed:          3', summary)
        self.assertIn('Verified Nonprofits:                               2', summary)
        self.assertIn('Qualified Leads (score ≥ 6):    3 leads', summary) # Compass
        self.assertIn('High Priority (score ≥ 8):            2 leads', summary) # Compass
        self.assertIn('Qualified Leads (score ≥ 6):    2 leads', summary) # Upcurve
        self.assertIn('High Priority (score ≥ 8):            1 leads', summary) # Upcurve

if __name__ == '__main__':
    unittest.main()
