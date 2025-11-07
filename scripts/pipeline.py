#!/usr/bin/env python3
"""
ClickUp Lead Optimizer - Main Pipeline
Orchestrates the complete lead enrichment and scoring process
"""

import sys
import os
import pandas as pd
import json
import argparse
import logging
from datetime import datetime
from typing import Dict, List

# Import our modules
from lead_optimizer import LeadOptimizer
from clickup_connector import ClickUpConnector
from report_generator import ReportGenerator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class Pipeline:
    """Main pipeline orchestrator"""
    
    def __init__(self, config_file: str = 'config.json'):
        """Initialize pipeline with configuration"""
        
        # Load configuration
        if not os.path.exists(config_file):
            self.create_default_config(config_file)
            logger.error(f"Created default config at {config_file}")
            logger.error("Please edit the config file with your ClickUp API key and list ID")
            sys.exit(1)
        
        with open(config_file, 'r') as f:
            self.config = json.load(f)
        
        # Validate config
        if self.config['clickup_api_key'] == 'pk_YOUR_CLICKUP_API_KEY':
            logger.error("Please edit config.json with your actual ClickUp API key!")
            sys.exit(1)
        
        # Initialize components
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.clickup = ClickUpConnector(self.config['clickup_api_key'])
        self.optimizer = LeadOptimizer('api_keys.json')
        self.reporter = ReportGenerator()
        
        logger.info(f"Pipeline initialized - Run ID: {self.timestamp}")
    
    def create_default_config(self, config_file: str):
        """Create default configuration file"""
        
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        
        default_config = {
            "clickup_api_key": "pk_YOUR_CLICKUP_API_KEY",
            "list_id": "YOUR_LIST_ID",
            "enrichment_settings": {
                "max_workers": 5,
                "batch_size": 50,
                "sample_size": None
            },
            "product_thresholds": {
                "compass": {
                    "qualified": 6.0,
                    "high_priority": 8.0
                },
                "upcurve": {
                    "qualified": 6.0,
                    "high_priority": 8.0
                }
            }
        }
        
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=2)
    
    def step1_export(self) -> pd.DataFrame:
        """Step 1: Export leads from ClickUp"""
        
        logger.info("=" * 60)
        logger.info("STEP 1: EXPORTING FROM CLICKUP")
        logger.info("=" * 60)
        
        # Test connection first
        if not self.clickup.test_connection():
            logger.error("Failed to connect to ClickUp. Check your API key.")
            sys.exit(1)
        
        # Export leads
        df = self.clickup.export_leads(self.config['list_id'])
        
        if df.empty:
            logger.error("No leads exported from ClickUp")
            sys.exit(1)
        
        # Save raw export
        export_file = f'data/raw_export_{self.timestamp}.csv'
        os.makedirs('data', exist_ok=True)
        df.to_csv(export_file, index=False)
        
        logger.info(f"✅ Exported {len(df)} leads")
        logger.info(f"📊 Unique companies: {df['company'].nunique() if 'company' in df.columns else 0}")
        logger.info(f"💾 Saved to: {export_file}")
        
        # Group by company
        if 'company' in df.columns:
            company_df = df[df['company'].notna()].copy()
            company_df = company_df.groupby('company').first().reset_index()
            company_file = f'data/by_company_{self.timestamp}.csv'
            company_df.to_csv(company_file, index=False)
            logger.info(f"📁 Company-grouped version: {company_file} ({len(company_df)} unique)")
            
            return company_df
        
        return df
    
    def step2_enrich(self, df: pd.DataFrame, sample_size: int = None) -> pd.DataFrame:
        """Step 2: Enrich leads with web data"""
        
        logger.info("=" * 60)
        logger.info("STEP 2: ENRICHING LEADS")
        logger.info("=" * 60)
        
        # Apply sampling if requested
        if sample_size and sample_size < len(df):
            logger.info(f"📌 Using sample of {sample_size} leads for testing")
            df = df.sample(n=sample_size, random_state=42)
        
        # Process in batches
        batch_size = self.config.get('enrichment_settings', {}).get('batch_size', 50)
        max_workers = self.config.get('enrichment_settings', {}).get('max_workers', 5)
        
        all_enriched = []
        leads_list = df.to_dict('records')
        total_batches = (len(leads_list) + batch_size - 1) // batch_size
        
        for i in range(0, len(leads_list), batch_size):
            batch = leads_list[i:i+batch_size]
            batch_num = i // batch_size + 1
            
            logger.info(f"Processing batch {batch_num}/{total_batches} "
                       f"(leads {i+1}-{min(i+batch_size, len(leads_list))})")
            
            # Enrich batch
            enriched_batch = self.optimizer.process_batch(batch, max_workers)
            all_enriched.extend(enriched_batch)
            
            # Save checkpoint
            if (batch_num % 2 == 0) or (batch_num == total_batches):
                checkpoint_df = pd.DataFrame(all_enriched)
                checkpoint_file = f'data/enriched_checkpoint_{self.timestamp}.csv'
                checkpoint_df.to_csv(checkpoint_file, index=False)
                logger.info(f"💾 Checkpoint saved: {len(all_enriched)} leads enriched")
        
        # Create final dataframe
        enriched_df = pd.DataFrame(all_enriched)
        
        # Save enriched data
        enriched_file = f'data/enriched_complete_{self.timestamp}.csv'
        enriched_df.to_csv(enriched_file, index=False)
        
        # Print summary stats
        logger.info(f"\n✅ Enrichment complete!")
        logger.info(f"📊 Summary:")
        logger.info(f"  - Total leads: {len(enriched_df)}")
        
        if 'is_nonprofit' in enriched_df.columns:
            logger.info(f"  - Nonprofits found: {enriched_df['is_nonprofit'].sum()}")
        
        if 'compass_score' in enriched_df.columns:
            compass_qualified = (enriched_df['compass_score'] >= 
                               self.config['product_thresholds']['compass']['qualified']).sum()
            logger.info(f"  - Compass qualified: {compass_qualified}")
        
        if 'upcurve_score' in enriched_df.columns:
            upcurve_qualified = (enriched_df['upcurve_score'] >= 
                               self.config['product_thresholds']['upcurve']['qualified']).sum()
            logger.info(f"  - Upcurve qualified: {upcurve_qualified}")
        
        logger.info(f"💾 Full data saved to: {enriched_file}")
        
        return enriched_df
    
    def step3_generate_reports(self, enriched_df: pd.DataFrame) -> Dict:
        """Step 3: Generate reports for review"""
        
        logger.info("=" * 60)
        logger.info("STEP 3: GENERATING REPORTS FOR REVIEW")
        logger.info("=" * 60)
        
        os.makedirs('exports', exist_ok=True)
        
        reports = {}
        
        # Get thresholds from config
        compass_threshold = self.config['product_thresholds']['compass']['qualified']
        compass_high = self.config['product_thresholds']['compass']['high_priority']
        upcurve_threshold = self.config['product_thresholds']['upcurve']['qualified']
        upcurve_high = self.config['product_thresholds']['upcurve']['high_priority']
        
        # COMPASS REPORT
        if 'compass_score' in enriched_df.columns:
            compass_df = enriched_df[enriched_df['compass_score'] >= compass_threshold].copy()
            compass_df = compass_df.sort_values('compass_score', ascending=False)
            
            # Select relevant columns
            compass_cols = ['company', 'compass_score', 'compass_reason', 'org_type', 
                          'email', 'phone', 'location', 'is_nonprofit', 'task_id']
            compass_cols = [c for c in compass_cols if c in compass_df.columns]
            
            compass_report = compass_df[compass_cols]
            compass_file = f'exports/compass_qualified_{self.timestamp}.csv'
            compass_report.to_csv(compass_file, index=False)
            reports['compass'] = compass_report
            
            logger.info(f"📊 Compass Report:")
            logger.info(f"   - Qualified leads (>{compass_threshold}): {len(compass_report)}")
            logger.info(f"   - High priority (>{compass_high}): {(compass_df['compass_score'] >= compass_high).sum()}")
            logger.info(f"   - Saved to: {compass_file}")
        
        # UPCURVE REPORT
        if 'upcurve_score' in enriched_df.columns:
            upcurve_df = enriched_df[enriched_df['upcurve_score'] >= upcurve_threshold].copy()
            upcurve_df = upcurve_df.sort_values('upcurve_score', ascending=False)
            
            # Select relevant columns
            upcurve_cols = ['company', 'upcurve_score', 'upcurve_reason', 'is_nonprofit',
                          'ein', 'has_donation_page', 'email', 'phone', 'task_id']
            upcurve_cols = [c for c in upcurve_cols if c in upcurve_df.columns]
            
            upcurve_report = upcurve_df[upcurve_cols]
            upcurve_file = f'exports/upcurve_qualified_{self.timestamp}.csv'
            upcurve_report.to_csv(upcurve_file, index=False)
            reports['upcurve'] = upcurve_report
            
            logger.info(f"📊 Upcurve Report:")
            logger.info(f"   - Qualified leads (>{upcurve_threshold}): {len(upcurve_report)}")
            logger.info(f"   - Verified nonprofits: {upcurve_df['is_nonprofit'].sum() if 'is_nonprofit' in upcurve_df.columns else 0}")
            logger.info(f"   - Saved to: {upcurve_file}")
        
        # MULTI-PRODUCT OPPORTUNITIES
        if 'compass_score' in enriched_df.columns and 'upcurve_score' in enriched_df.columns:
            multi_df = enriched_df[
                (enriched_df['compass_score'] >= compass_high) & 
                (enriched_df['upcurve_score'] >= upcurve_high)
            ].copy()
            
            if not multi_df.empty:
                multi_df = multi_df.sort_values(['compass_score', 'upcurve_score'], ascending=False)
                multi_file = f'exports/multi_product_opportunities_{self.timestamp}.csv'
                multi_df.to_csv(multi_file, index=False)
                reports['multi'] = multi_df
                
                logger.info(f"🌟 Multi-Product Opportunities:")
                logger.info(f"   - High score for both products: {len(multi_df)}")
                logger.info(f"   - Saved to: {multi_file}")
        
        # EXECUTIVE SUMMARY
        summary = self.reporter.generate_executive_summary(enriched_df, reports, self.config)
        summary_file = f'exports/executive_summary_{self.timestamp}.txt'
        with open(summary_file, 'w') as f:
            f.write(summary)
        
        logger.info(f"📄 Executive summary: {summary_file}")
        
        # HTML REPORT
        html_report = self.reporter.generate_html_report(enriched_df, reports, self.timestamp)
        html_file = f'exports/report_{self.timestamp}.html'
        with open(html_file, 'w') as f:
            f.write(html_report)
        
        logger.info(f"🌐 Interactive report: {html_file}")
        
        return reports
    
    def step4_import(self, enriched_df: pd.DataFrame, auto_import: bool = False):
        """Step 4: Import enriched data back to ClickUp (after approval)"""
        
        if not auto_import:
            logger.info("=" * 60)
            logger.info("STEP 4: READY FOR IMPORT")
            logger.info("=" * 60)
            logger.info("📝 Review the reports in exports/")
            logger.info("After Michael's approval, run:")
            logger.info(f"   python scripts/pipeline.py --import-only --file enriched_complete_{self.timestamp}.csv")
            return
        
        logger.info("=" * 60)
        logger.info("STEP 4: IMPORTING TO CLICKUP")
        logger.info("=" * 60)
        
        result = self.clickup.import_enriched_data(enriched_df, self.config['list_id'])
        
        if result['success']:
            logger.info(f"✅ Import complete!")
            logger.info(f"   - Total: {result['total']}")
            logger.info(f"   - Successful: {result['successful']}")
            logger.info(f"   - Failed: {result['failed']}")
        else:
            logger.error(f"Import failed: {result.get('message', 'Unknown error')}")
    
    def run_full_pipeline(self, sample_size: int = None, auto_import: bool = False):
        """Run the complete pipeline"""
        
        logger.info("🚀 STARTING CLICKUP LEAD OPTIMIZER PIPELINE")
        logger.info(f"⏰ Run ID: {self.timestamp}")
        
        try:
            # Step 1: Export
            df = self.step1_export()
            
            # Step 2: Enrich
            enriched_df = self.step2_enrich(df, sample_size)
            
            # Step 3: Generate reports
            reports = self.step3_generate_reports(enriched_df)
            
            # Step 4: Import (optional)
            self.step4_import(enriched_df, auto_import)
            
            logger.info("=" * 60)
            logger.info("🎉 PIPELINE COMPLETE!")
            logger.info("=" * 60)
            
            # Print final summary
            self.print_summary(enriched_df, reports)
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            raise
    
    def print_summary(self, enriched_df: pd.DataFrame, reports: Dict):
        """Print final summary for user"""
        
        print("\n" + "="*60)
        print("FINAL SUMMARY FOR MICHAEL'S REVIEW")
        print("="*60)
        
        print(f"\n📊 OVERALL STATS:")
        print(f"  - Total leads processed: {len(enriched_df)}")
        
        if 'compass' in reports:
            print(f"\n🏢 COMPASS (Residential Program Management):")
            print(f"  - Qualified leads: {len(reports['compass'])}")
            if not reports['compass'].empty:
                print(f"  - Average score: {reports['compass']['compass_score'].mean():.1f}")
                print(f"  - Top 3 leads:")
                for _, row in reports['compass'].head(3).iterrows():
                    print(f"    • {row['company']}: {row['compass_score']:.1f}")
        
        if 'upcurve' in reports:
            print(f"\n💰 UPCURVE (Nonprofit Fundraising):")
            print(f"  - Qualified leads: {len(reports['upcurve'])}")
            if not reports['upcurve'].empty:
                print(f"  - Average score: {reports['upcurve']['upcurve_score'].mean():.1f}")
                print(f"  - Top 3 leads:")
                for _, row in reports['upcurve'].head(3).iterrows():
                    print(f"    • {row['company']}: {row['upcurve_score']:.1f}")
        
        if 'multi' in reports:
            print(f"\n🌟 MULTI-PRODUCT OPPORTUNITIES: {len(reports['multi'])}")
        
        print(f"\n📁 All reports saved to: exports/")
        print(f"   Review these files before importing to ClickUp!")
        print("="*60)

def main():
    """Main entry point"""
    
    parser = argparse.ArgumentParser(description='ClickUp Lead Optimizer Pipeline')
    parser.add_argument('--sample', type=int, help='Process only a sample of leads for testing')
    parser.add_argument('--auto-import', action='store_true', 
                       help='Automatically import to ClickUp after enrichment (skip review)')
    parser.add_argument('--import-only', action='store_true', 
                       help='Only run the import step with existing enriched data')
    parser.add_argument('--file', help='Enriched CSV file to import (for --import-only)')
    
    args = parser.parse_args()
    
    # Create necessary directories
    for dir_name in ['data', 'exports', 'logs', 'config']:
        os.makedirs(dir_name, exist_ok=True)
    
    # Initialize pipeline
    pipeline = Pipeline()
    
    if args.import_only:
        # Just import existing enriched data
        if not args.file:
            logger.error("--file argument required with --import-only")
            logger.error("Example: python scripts/pipeline.py --import-only --file enriched_complete_20240101_120000.csv")
            return
        
        file_path = f'data/{args.file}'
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return
        
        logger.info(f"Importing {file_path} to ClickUp...")
        enriched_df = pd.read_csv(file_path)
        pipeline.step4_import(enriched_df, auto_import=True)
    
    else:
        # Run full pipeline
        pipeline.run_full_pipeline(
            sample_size=args.sample,
            auto_import=args.auto_import
        )

if __name__ == "__main__":
    main()
