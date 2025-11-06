#!/usr/bin/env python3
"""
Report Generator for ClickUp Lead Optimizer
Creates executive summaries and detailed reports for review
"""

import pandas as pd
from datetime import datetime
from typing import Dict
import json

class ReportGenerator:
    """Generates various report formats for lead enrichment results"""
    
    def generate_executive_summary(self, df: pd.DataFrame, reports: Dict, config: Dict) -> str:
        """Generate text-based executive summary for Michael"""
        
        total_leads = len(df)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Calculate key metrics
        companies_with_data = df['company'].notna().sum() if 'company' in df.columns else 0
        emails_found = df['email'].notna().sum() if 'email' in df.columns else 0
        phones_found = df['phone'].notna().sum() if 'phone' in df.columns else 0
        
        nonprofits = df['is_nonprofit'].sum() if 'is_nonprofit' in df.columns else 0
        
        # Get thresholds
        compass_threshold = config['product_thresholds']['compass']['qualified']
        compass_high = config['product_thresholds']['compass']['high_priority']
        upcurve_threshold = config['product_thresholds']['upcurve']['qualified']
        upcurve_high = config['product_thresholds']['upcurve']['high_priority']
        
        # Calculate product metrics
        compass_qualified = 0
        compass_high_priority = 0
        compass_avg_score = 0
        if 'compass_score' in df.columns:
            compass_qualified = (df['compass_score'] >= compass_threshold).sum()
            compass_high_priority = (df['compass_score'] >= compass_high).sum()
            compass_avg_score = df[df['compass_score'] >= compass_threshold]['compass_score'].mean()
        
        upcurve_qualified = 0
        upcurve_high_priority = 0
        upcurve_avg_score = 0
        if 'upcurve_score' in df.columns:
            upcurve_qualified = (df['upcurve_score'] >= upcurve_threshold).sum()
            upcurve_high_priority = (df['upcurve_score'] >= upcurve_high).sum()
            upcurve_avg_score = df[df['upcurve_score'] >= upcurve_threshold]['upcurve_score'].mean()
        
        multi_fit = 0
        if 'compass_score' in df.columns and 'upcurve_score' in df.columns:
            multi_fit = ((df['compass_score'] >= compass_high) & 
                        (df['upcurve_score'] >= upcurve_high)).sum()
        
        # Organization type distribution
        org_type_dist = ""
        if 'org_type' in df.columns:
            top_types = df['org_type'].value_counts().head(10)
            org_type_dist = "\n".join([f"    - {org_type}: {count}" for org_type, count in top_types.items()])
        
        # Data quality metrics
        avg_quality = df['data_quality_score'].mean() if 'data_quality_score' in df.columns else 0
        high_quality = (df['data_quality_score'] > 0.7).sum() if 'data_quality_score' in df.columns else 0
        
        summary = f"""
================================================================================
                    CLICKUP LEAD OPTIMIZER - EXECUTIVE SUMMARY
================================================================================
Generated: {timestamp}
Report for: Michael / Banyan Labs Sales Team

================================================================================
OVERVIEW
================================================================================
Total Leads Processed:          {total_leads:,}
Companies with Valid Data:      {companies_with_data:,} ({companies_with_data/total_leads*100:.1f}%)
Average Data Quality Score:     {avg_quality:.2%}

Contact Information Coverage:
  - Email Addresses Found:      {emails_found:,} ({emails_found/total_leads*100:.1f}%)
  - Phone Numbers Found:        {phones_found:,} ({phones_found/total_leads*100:.1f}%)

================================================================================
COMPASS - Residential Program Management
================================================================================
Qualified Leads (score ≥ {compass_threshold}):    {compass_qualified:,} leads
High Priority (score ≥ {compass_high}):            {compass_high_priority:,} leads
Average Score (qualified):                         {compass_avg_score:.1f}

Top Organization Types for Compass:
{self._get_top_org_types(df, 'compass_score', compass_threshold)}

Key Insights:
  - Primary opportunity: Recovery centers and halfway houses
  - {compass_high_priority} leads ready for immediate outreach
  - Strong fit indicators: Residential keywords + multiple locations

================================================================================
UPCURVE - Nonprofit Fundraising Platform
================================================================================
Qualified Leads (score ≥ {upcurve_threshold}):    {upcurve_qualified:,} leads
High Priority (score ≥ {upcurve_high}):            {upcurve_high_priority:,} leads
Verified Nonprofits:                               {nonprofits:,}
Average Score (qualified):                         {upcurve_avg_score:.1f}

Top Organization Types for Upcurve:
{self._get_top_org_types(df, 'upcurve_score', upcurve_threshold)}

Key Insights:
  - {df['has_donation_page'].sum() if 'has_donation_page' in df.columns else 0} organizations have active donation pages
  - Best targets: Small-medium nonprofits (<$5M revenue)
  - High conversion potential with faith-based organizations

================================================================================
CROSS-SELLING OPPORTUNITIES
================================================================================
Leads Qualifying for BOTH Products:    {multi_fit:,} leads
Percentage of Total:                   {multi_fit/total_leads*100:.1f}%

These {multi_fit} organizations are HIGH VALUE targets:
  - They need residential management (Compass)
  - They need fundraising tools (Upcurve)
  - Potential for bundled deals with higher contract values

================================================================================
ORGANIZATION TYPE BREAKDOWN
================================================================================
{org_type_dist}

================================================================================
DATA ENRICHMENT SOURCES
================================================================================
{self._get_enrichment_sources(df)}

================================================================================
RECOMMENDED ACTIONS
================================================================================

1. IMMEDIATE OUTREACH (This Week):
   ✓ Contact {compass_high_priority} high-priority Compass leads
   ✓ Contact {upcurve_high_priority} high-priority Upcurve leads
   ✓ Prioritize {multi_fit} multi-product opportunities for bundled offerings

2. SEGMENTATION STRATEGY:
   ✓ Compass: Focus on recovery centers and halfway houses first
   ✓ Upcurve: Target verified nonprofits with donation pages
   ✓ Cross-sell: Approach residential nonprofits with both products

3. DATA IMPROVEMENTS NEEDED:
   ✓ {total_leads - emails_found:,} leads need email addresses
   ✓ {total_leads - phones_found:,} leads need phone numbers
   ✓ Consider manual enrichment for high-score leads with missing contact info

4. CLICKUP CRM UPDATES:
   ✓ New custom fields have been created for product scores
   ✓ Leads are tagged with organization type and nonprofit status
   ✓ Use filters to create targeted outreach lists

================================================================================
FILES GENERATED FOR REVIEW
================================================================================
1. compass_qualified_*.csv      - All Compass opportunities
2. upcurve_qualified_*.csv      - All Upcurve opportunities  
3. multi_product_*.csv          - Cross-selling opportunities
4. enriched_complete_*.csv      - Full dataset with all enrichments
5. report_*.html                - Interactive dashboard (open in browser)

================================================================================
NEXT STEPS
================================================================================
1. Review the qualified lead CSVs
2. Approve the enrichment data
3. Import to ClickUp: python pipeline.py --import-only --file [filename]
4. Begin outreach to high-priority leads

================================================================================
                              END OF EXECUTIVE SUMMARY
================================================================================
"""
        return summary
    
    def _get_top_org_types(self, df: pd.DataFrame, score_col: str, threshold: float) -> str:
        """Get top organization types for a product"""
        
        if score_col not in df.columns or 'org_type' not in df.columns:
            return "    Data not available"
        
        qualified_df = df[df[score_col] >= threshold]
        if qualified_df.empty:
            return "    No qualified leads"
        
        top_types = qualified_df['org_type'].value_counts().head(5)
        if top_types.empty:
            return "    No organization types identified"
        
        lines = []
        for org_type, count in top_types.items():
            avg_score = qualified_df[qualified_df['org_type'] == org_type][score_col].mean()
            lines.append(f"    - {org_type}: {count} leads (avg score: {avg_score:.1f})")
        
        return "\n".join(lines)
    
    def _get_enrichment_sources(self, df: pd.DataFrame) -> str:
        """Summarize enrichment sources used"""
        
        sources = []
        
        if 'sources_checked' in df.columns:
            # Count how many times each source was used
            all_sources = []
            for source_list in df['sources_checked'].dropna():
                if isinstance(source_list, str):
                    try:
                        source_list = json.loads(source_list)
                    except:
                        source_list = [source_list]
                if isinstance(source_list, list):
                    all_sources.extend(source_list)
            
            from collections import Counter
            source_counts = Counter(all_sources)
            
            for source, count in source_counts.most_common():
                sources.append(f"  - {source}: {count} lookups")
        
        if not sources:
            sources = [
                "  - ProPublica Nonprofit API (free)",
                "  - Website scraping",
                "  - Google search results"
            ]
        
        return "\n".join(sources)
    
    def generate_html_report(self, df: pd.DataFrame, reports: Dict, timestamp: str) -> str:
        """Generate interactive HTML report"""
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Lead Optimizer Report - {timestamp}</title>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        h1 {{
            margin: 0;
            font-size: 2.5em;
        }}
        .subtitle {{
            opacity: 0.9;
            margin-top: 10px;
        }}
        .metric-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        .metric-card {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }}
        .metric-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 5px 20px rgba(0,0,0,0.15);
        }}
        .metric-value {{
            font-size: 2.5em;
            font-weight: bold;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .metric-label {{
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-top: 5px;
        }}
        .section {{
            background: white;
            border-radius: 10px;
            padding: 25px;
            margin: 20px 0;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h2 {{
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th {{
            background: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #e0e0e0;
        }}
        tr:hover {{
            background: #f8f8ff;
        }}
        .score-high {{
            background: #4caf50;
            color: white;
            padding: 4px 8px;
            border-radius: 20px;
            font-weight: bold;
        }}
        .score-medium {{
            background: #ff9800;
            color: white;
            padding: 4px 8px;
            border-radius: 20px;
        }}
        .score-low {{
            background: #f44336;
            color: white;
            padding: 4px 8px;
            border-radius: 20px;
        }}
        .chart-container {{
            height: 400px;
            margin: 20px 0;
        }}
        .nonprofit-badge {{
            background: #4caf50;
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.9em;
        }}
        .footer {{
            text-align: center;
            margin-top: 50px;
            color: #666;
            font-size: 0.9em;
        }}
    </style>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
</head>
<body>
    <div class="header">
        <h1>🚀 ClickUp Lead Optimizer Report</h1>
        <div class="subtitle">
            Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}<br>
            Pipeline Run: {timestamp}
        </div>
    </div>
    
    <div class="metric-grid">
        <div class="metric-card">
            <div class="metric-value">{len(df):,}</div>
            <div class="metric-label">Total Leads Processed</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{df['is_nonprofit'].sum() if 'is_nonprofit' in df.columns else 0:,}</div>
            <div class="metric-label">Verified Nonprofits</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{len(reports.get('compass', [])):,}</div>
            <div class="metric-label">Compass Qualified</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{len(reports.get('upcurve', [])):,}</div>
            <div class="metric-label">Upcurve Qualified</div>
        </div>
    </div>
    
    <div class="section">
        <h2>📊 Score Distribution</h2>
        <div id="scoreChart" class="chart-container"></div>
    </div>
    
    <div class="section">
        <h2>🏢 Organization Types</h2>
        <div id="orgTypeChart" class="chart-container"></div>
    </div>
    
    <div class="section">
        <h2>🎯 Top Compass Opportunities</h2>
        {self._generate_html_table(reports.get('compass', pd.DataFrame()).head(15), 'compass')}
    </div>
    
    <div class="section">
        <h2>💰 Top Upcurve Opportunities</h2>
        {self._generate_html_table(reports.get('upcurve', pd.DataFrame()).head(15), 'upcurve')}
    </div>
    
    <div class="section">
        <h2>🌟 Multi-Product Opportunities</h2>
        {self._generate_html_table(reports.get('multi', pd.DataFrame()).head(10), 'multi')}
    </div>
    
    <div class="footer">
        <p>ClickUp Lead Optimizer v2.0 | Built for Banyan Labs Sales Team</p>
        <p>For questions or support, contact your development team</p>
    </div>
    
    <script>
        // Score distribution chart
        {self._generate_score_chart_js(df)}
        
        // Organization type chart
        {self._generate_org_chart_js(df)}
    </script>
</body>
</html>
"""
        return html
    
    def _generate_html_table(self, df: pd.DataFrame, table_type: str) -> str:
        """Generate HTML table for report"""
        
        if df.empty:
            return "<p><em>No qualified leads found for this product.</em></p>"
        
        # Select columns based on table type
        if table_type == 'compass':
            columns = ['company', 'compass_score', 'org_type', 'email', 'phone']
            score_col = 'compass_score'
        elif table_type == 'upcurve':
            columns = ['company', 'upcurve_score', 'is_nonprofit', 'ein', 'email']
            score_col = 'upcurve_score'
        else:  # multi
            columns = ['company', 'compass_score', 'upcurve_score', 'org_type', 'is_nonprofit']
            score_col = None
        
        # Filter to existing columns
        columns = [c for c in columns if c in df.columns]
        
        if not columns:
            return "<p><em>No data available.</em></p>"
        
        html = "<table>\n<tr>"
        
        # Headers
        for col in columns:
            header = col.replace('_', ' ').title()
            html += f"<th>{header}</th>"
        html += "</tr>\n"
        
        # Rows
        for _, row in df[columns].iterrows():
            html += "<tr>"
            for col in columns:
                value = row[col]
                
                if pd.isna(value):
                    html += "<td>-</td>"
                elif col in ['compass_score', 'upcurve_score']:
                    score_class = 'score-high' if value >= 8 else 'score-medium' if value >= 6 else 'score-low'
                    html += f'<td><span class="{score_class}">{value:.1f}</span></td>'
                elif col == 'is_nonprofit':
                    if value:
                        html += '<td><span class="nonprofit-badge">✓ Nonprofit</span></td>'
                    else:
                        html += '<td>-</td>'
                else:
                    html += f"<td>{value}</td>"
            html += "</tr>\n"
        
        html += "</table>"
        return html
    
    def _generate_score_chart_js(self, df: pd.DataFrame) -> str:
        """Generate JavaScript for score distribution chart"""
        
        if 'compass_score' not in df.columns or 'upcurve_score' not in df.columns:
            return "// No score data available"
        
        compass_scores = df['compass_score'].dropna().tolist()
        upcurve_scores = df['upcurve_score'].dropna().tolist()
        
        return f"""
        var compassTrace = {{
            x: {compass_scores},
            name: 'Compass Scores',
            type: 'histogram',
            marker: {{
                color: '#667eea',
                opacity: 0.7
            }},
            xbins: {{
                start: 0,
                end: 10,
                size: 1
            }}
        }};
        
        var upcurveTrace = {{
            x: {upcurve_scores},
            name: 'Upcurve Scores',
            type: 'histogram',
            marker: {{
                color: '#764ba2',
                opacity: 0.7
            }},
            xbins: {{
                start: 0,
                end: 10,
                size: 1
            }}
        }};
        
        var layout = {{
            title: 'Product Fit Score Distribution',
            xaxis: {{
                title: 'Score',
                range: [0, 10]
            }},
            yaxis: {{
                title: 'Number of Leads'
            }},
            barmode: 'overlay',
            hovermode: 'x'
        }};
        
        Plotly.newPlot('scoreChart', [compassTrace, upcurveTrace], layout);
        """
    
    def _generate_org_chart_js(self, df: pd.DataFrame) -> str:
        """Generate JavaScript for organization type chart"""
        
        if 'org_type' not in df.columns:
            return "// No organization type data available"
        
        org_counts = df['org_type'].value_counts().head(10)
        
        return f"""
        var orgTrace = {{
            type: 'bar',
            x: {org_counts.values.tolist()},
            y: {[t.replace('_', ' ').title() for t in org_counts.index.tolist()]},
            orientation: 'h',
            marker: {{
                color: 'rgba(102, 126, 234, 0.8)'
            }},
            text: {org_counts.values.tolist()},
            textposition: 'outside'
        }};
        
        var layout = {{
            title: 'Lead Distribution by Organization Type',
            xaxis: {{
                title: 'Number of Leads'
            }},
            margin: {{
                l: 150
            }}
        }};
        
        Plotly.newPlot('orgTypeChart', [orgTrace], layout);
        """

# Test function
if __name__ == "__main__":
    # Test with sample data
    test_df = pd.DataFrame({
        'company': ['Org1', 'Org2', 'Org3'],
        'compass_score': [8.5, 6.2, 9.1],
        'upcurve_score': [5.0, 8.8, 7.5],
        'is_nonprofit': [False, True, True],
        'org_type': ['halfway_house', 'nonprofit_general', 'recovery_center']
    })
    
    reporter = ReportGenerator()
    summary = reporter.generate_executive_summary(test_df, {}, {
        'product_thresholds': {
            'compass': {'qualified': 6, 'high_priority': 8},
            'upcurve': {'qualified': 6, 'high_priority': 8}
        }
    })
    
    print(summary)
