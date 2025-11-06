#!/usr/bin/env python3
"""
ClickUp Lead Optimizer - Comprehensive Enrichment Engine
Scrapes web, checks nonprofits, scores for any product
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup
import json
import time
import re
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
from urllib.parse import urlparse, quote
import os

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LeadOptimizer:
    """Universal lead enrichment for any Banyan product"""
    
    def __init__(self, config_path: str = None):
        """Initialize with optional API keys"""
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Load API keys if available
        self.api_keys = {}
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    self.api_keys = json.load(f)
                logger.info(f"Loaded API keys: {list(self.api_keys.keys())}")
            except:
                logger.warning("No API keys loaded - using free sources only")
        
        # Cache to avoid duplicate lookups
        self.cache = {}
        
        # Product-specific scoring rules (easily extensible!)
        self.product_rules = {
            'compass': {
                'name': 'Compass - Residential Program Management',
                'target_keywords': [
                    'halfway house', 'recovery', 'sober living', 'residential',
                    'group home', 'transitional', 'reentry', 'treatment center',
                    'therapeutic community', 'oxford house'
                ],
                'high_value_types': ['halfway_house', 'recovery_center', 'sober_living', 'group_home'],
                'medium_value_types': ['transitional_housing', 'shelter', 'mental_health'],
                'boost_if_nonprofit': 1.2,
                'min_score': 3.0,
                'max_score': 10.0
            },
            'upcurve': {
                'name': 'Upcurve - Nonprofit Fundraising',
                'target_keywords': [
                    'nonprofit', '501c3', 'charity', 'foundation', 'fundraising',
                    'donation', 'giving', 'philanthropic', 'tax-exempt', 'ngo'
                ],
                'requires_nonprofit': True,
                'boost_if_has_donation_page': 1.5,
                'boost_if_small_org': 1.3,  # Under $5M revenue
                'min_score': 2.0,
                'max_score': 10.0
            },
            # Add more products here as needed!
            # 'jona': { ... },
            # 'harper': { ... },
        }
        
        # Organization type patterns
        self.org_patterns = {
            'halfway_house': ['halfway house', 'reentry', 're-entry', 'transitional living', 'second chance'],
            'recovery_center': ['recovery', 'rehab', 'addiction', 'substance abuse', 'detox', 'treatment'],
            'sober_living': ['sober living', 'sober house', 'recovery residence', 'oxford house'],
            'transitional_housing': ['transitional housing', 'temporary housing', 'bridge housing'],
            'shelter': ['shelter', 'safe house', 'emergency housing', 'crisis housing'],
            'group_home': ['group home', 'residential care', 'assisted living', 'adult family home'],
            'mental_health': ['mental health', 'psychiatric', 'behavioral health', 'psych'],
            'faith_based': ['church', 'ministry', 'christian', 'catholic', 'baptist', 'methodist'],
            'community_service': ['community', 'ymca', 'ywca', 'boys girls club', 'community center'],
            'nonprofit_general': ['nonprofit', 'non-profit', '501c3', 'charity', 'foundation']
        }
    
    # ========== NONPROFIT VERIFICATION ==========
    
    def check_nonprofit_status(self, org_name: str, ein: str = None) -> Dict:
        """Check multiple sources for nonprofit status"""
        
        result = {'is_nonprofit': False, 'sources_checked': []}
        
        # 1. ProPublica API (FREE!)
        propublica = self.check_propublica(org_name)
        result['sources_checked'].append('ProPublica')
        if propublica.get('is_nonprofit'):
            result.update(propublica)
            return result  # Found it!
        
        # 2. Try IRS if we have an EIN
        if ein:
            irs = self.check_irs_by_ein(ein)
            result['sources_checked'].append('IRS')
            if irs.get('is_nonprofit'):
                result.update(irs)
                return result
        
        # 3. Check website for nonprofit indicators
        # This happens in website scraping
        
        return result
    
    def check_propublica(self, org_name: str) -> Dict:
        """ProPublica Nonprofit Explorer (FREE, no key needed!)"""
        try:
            url = "https://projects.propublica.org/nonprofits/api/v2/search.json"
            params = {'q': org_name}
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('organizations'):
                org = data['organizations'][0]
                ein = org.get('ein')
                
                # Get detailed info
                if ein:
                    detail_url = f"https://projects.propublica.org/nonprofits/api/v2/organizations/{ein}.json"
                    detail_resp = self.session.get(detail_url, timeout=10)
                    if detail_resp.status_code == 200:
                        details = detail_resp.json()['organization']
                        return {
                            'is_nonprofit': True,
                            'ein': ein,
                            'nonprofit_name': details.get('name'),
                            'city': details.get('city'),
                            'state': details.get('state'),
                            'ntee_code': details.get('ntee_code'),
                            'ruling_year': details.get('ruling_date', '')[:4],
                            'revenue': details.get('revenue_amount'),
                            'asset_amount': details.get('asset_amount')
                        }
                
                return {
                    'is_nonprofit': True,
                    'ein': ein,
                    'nonprofit_name': org.get('name')
                }
            
            return {'is_nonprofit': False}
            
        except Exception as e:
            logger.debug(f"ProPublica check failed for {org_name}: {e}")
            return {'is_nonprofit': False}
    
    def check_irs_by_ein(self, ein: str) -> Dict:
        """Quick IRS check if we have EIN"""
        # IRS has a bulk data file we could download
        # For now, just validate EIN format
        if re.match(r'^\d{2}-\d{7}$', ein) or re.match(r'^\d{9}$', ein):
            return {'ein_valid_format': True}
        return {'ein_valid_format': False}
    
    # ========== WEB SCRAPING ==========
    
    def scrape_organization_website(self, url: str) -> Dict:
        """Comprehensive website scraping for org data"""
        
        if not url:
            return {}
        
        # Ensure proper URL format
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'
        
        try:
            response = self.session.get(url, timeout=10, allow_redirects=True)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            data = {
                'website_url': response.url,  # Final URL after redirects
                'website_title': None,
                'meta_description': None,
                'mission_statement': None,
                'about_text': None,
                'services_offered': [],
                'contact_info': {},
                'social_links': {},
                'nonprofit_indicators': []
            }
            
            # Title and meta
            if soup.find('title'):
                data['website_title'] = soup.find('title').get_text(strip=True)
            
            meta_desc = soup.find('meta', {'name': 'description'}) or soup.find('meta', {'property': 'og:description'})
            if meta_desc:
                data['meta_description'] = meta_desc.get('content', '')
            
            # Look for key sections
            text_content = soup.get_text(separator=' ', strip=True).lower()
            
            # Mission statement detection
            mission_markers = ['our mission', 'mission statement', 'our purpose', 'we believe']
            for marker in mission_markers:
                if marker in text_content:
                    # Try to extract the paragraph containing it
                    for elem in soup.find_all(['p', 'div', 'section']):
                        elem_text = elem.get_text(strip=True)
                        if marker in elem_text.lower():
                            data['mission_statement'] = elem_text[:500]
                            break
                    if data['mission_statement']:
                        break
            
            # About section
            about_section = soup.find(['div', 'section'], {'id': re.compile('about', re.I)})
            if not about_section:
                about_section = soup.find(['div', 'section'], {'class': re.compile('about', re.I)})
            if about_section:
                data['about_text'] = about_section.get_text(separator=' ', strip=True)[:1000]
            
            # Services/Programs
            services_section = soup.find(['div', 'section'], text=re.compile('services|programs|what we do', re.I))
            if services_section:
                services = services_section.find_all(['li', 'p'])[:10]
                data['services_offered'] = [s.get_text(strip=True)[:100] for s in services]
            
            # Contact extraction
            phone_pattern = re.compile(r'[\+\(]?[1-9][0-9 .\-\(\)]{8,}[0-9]')
            email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
            
            phones = phone_pattern.findall(str(soup))[:3]  # Get up to 3 phones
            emails = email_pattern.findall(str(soup))[:5]  # Get up to 5 emails
            
            if phones:
                data['contact_info']['phones'] = list(set(phones))
            
            if emails:
                # Filter out system emails
                valid_emails = [e for e in emails if not any(
                    x in e.lower() for x in ['noreply', 'no-reply', 'donotreply', 'example.com']
                )]
                if valid_emails:
                    data['contact_info']['emails'] = list(set(valid_emails))[:3]
            
            # Address extraction (basic)
            address_pattern = re.compile(r'\d{1,5}\s+[\w\s]+(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|way|court|ct)', re.I)
            addresses = address_pattern.findall(str(soup))
            if addresses:
                data['contact_info']['address'] = addresses[0]
            
            # Social media
            social_patterns = {
                'facebook': r'(?:https?:)?//(?:www\.)?facebook\.com/[\w\-\.]+',
                'twitter': r'(?:https?:)?//(?:www\.)?twitter\.com/[\w\-\.]+',
                'linkedin': r'(?:https?:)?//(?:www\.)?linkedin\.com/(?:company|in)/[\w\-\.]+',
                'instagram': r'(?:https?:)?//(?:www\.)?instagram\.com/[\w\-\.]+',
                'youtube': r'(?:https?:)?//(?:www\.)?youtube\.com/(?:c|channel|user)/[\w\-\.]+'
            }
            
            for platform, pattern in social_patterns.items():
                matches = re.findall(pattern, str(soup), re.I)
                if matches:
                    data['social_links'][platform] = matches[0]
            
            # Nonprofit indicators
            nonprofit_keywords = [
                '501(c)(3)', '501c3', 'tax-exempt', 'tax deductible',
                'nonprofit', 'non-profit', 'not-for-profit', 'charitable',
                'donate', 'donation', 'give now', 'support us',
                'volunteer', 'foundation', 'charity'
            ]
            
            for keyword in nonprofit_keywords:
                if keyword in text_content:
                    data['nonprofit_indicators'].append(keyword)
            
            # Donation page check
            donate_links = soup.find_all('a', href=re.compile('donate|giving|support|contribution', re.I))
            if donate_links:
                data['has_donation_page'] = True
                data['donation_url'] = donate_links[0].get('href', '')
            
            return data
            
        except requests.RequestException as e:
            logger.debug(f"Website scraping failed for {url}: {e}")
            return {'website_error': str(e)}
        except Exception as e:
            logger.error(f"Unexpected error scraping {url}: {e}")
            return {}
    
    def google_search(self, query: str, num_results: int = 5) -> List[Dict]:
        """Basic Google search scraping (no API needed)"""
        try:
            search_url = f"https://www.google.com/search?q={quote(query)}&num={num_results}"
            
            response = self.session.get(search_url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            results = []
            for g in soup.find_all('div', class_='g')[:num_results]:
                result = {}
                
                # Title and link
                link_elem = g.find('a')
                if link_elem:
                    result['url'] = link_elem.get('href', '')
                
                title_elem = g.find('h3')
                if title_elem:
                    result['title'] = title_elem.get_text(strip=True)
                
                # Snippet
                snippet_elem = g.find('span', class_='aCOpRe') or g.find('div', class_='IsZvec')
                if snippet_elem:
                    result['snippet'] = snippet_elem.get_text(strip=True)
                
                if result.get('url') and result.get('title'):
                    results.append(result)
            
            return results
            
        except Exception as e:
            logger.debug(f"Google search failed for '{query}': {e}")
            return []
    
    # ========== ORGANIZATION CLASSIFICATION ==========
    
    def classify_organization(self, org_data: Dict) -> Dict:
        """Classify organization type based on all available data"""
        
        # Combine all text for analysis
        text_parts = [
            str(org_data.get('company', '')),
            str(org_data.get('website_title', '')),
            str(org_data.get('meta_description', '')),
            str(org_data.get('mission_statement', '')),
            str(org_data.get('about_text', '')),
            str(org_data.get('business_mission', '')),
            ' '.join(org_data.get('services_offered', [])),
            ' '.join(org_data.get('search_snippets', []))
        ]
        
        combined_text = ' '.join(text_parts).lower()
        
        # Score each organization type
        type_scores = {}
        keywords_found = {}
        
        for org_type, patterns in self.org_patterns.items():
            score = 0
            found = []
            
            for pattern in patterns:
                if pattern.lower() in combined_text:
                    score += 1
                    found.append(pattern)
            
            if score > 0:
                type_scores[org_type] = score
                keywords_found[org_type] = found
        
        # Determine primary type
        if type_scores:
            primary_type = max(type_scores, key=type_scores.get)
            confidence = min(type_scores[primary_type] / 3.0, 1.0)  # Normalize
        else:
            primary_type = 'unknown'
            confidence = 0.0
        
        return {
            'org_type': primary_type,
            'org_type_confidence': confidence,
            'org_type_keywords': keywords_found.get(primary_type, []),
            'all_type_scores': type_scores
        }
    
    # ========== PRODUCT SCORING ==========
    
    def score_for_product(self, org_data: Dict, product: str) -> Dict:
        """Score a lead for a specific product"""
        
        if product not in self.product_rules:
            return {'score': 0, 'reason': 'Product not configured'}
        
        rules = self.product_rules[product]
        score = rules['min_score']
        factors = []
        
        # Check if nonprofit (for products that care)
        is_nonprofit = org_data.get('is_nonprofit', False)
        
        if rules.get('requires_nonprofit') and not is_nonprofit:
            return {
                'score': 2.0,
                'reason': 'Not a nonprofit (required for this product)'
            }
        
        # Keyword matching
        text_content = ' '.join([
            str(org_data.get('company', '')),
            str(org_data.get('mission_statement', '')),
            str(org_data.get('about_text', '')),
            str(org_data.get('meta_description', ''))
        ]).lower()
        
        keyword_matches = 0
        for keyword in rules.get('target_keywords', []):
            if keyword.lower() in text_content:
                keyword_matches += 1
        
        if keyword_matches > 0:
            score += min(keyword_matches * 0.5, 3.0)  # Cap at +3
            factors.append(f"{keyword_matches} relevant keywords")
        
        # Organization type bonus
        org_type = org_data.get('org_type', 'unknown')
        
        if org_type in rules.get('high_value_types', []):
            score += 3.0
            factors.append(f"High-value org type: {org_type}")
        elif org_type in rules.get('medium_value_types', []):
            score += 1.5
            factors.append(f"Medium-value org type: {org_type}")
        
        # Product-specific bonuses
        if product == 'compass':
            # Residential programs need Compass
            if any(word in text_content for word in ['resident', 'housing', 'beds', 'capacity']):
                score += 1.0
                factors.append("Has residential component")
            
            # Multiple locations = higher need
            if org_data.get('multiple_locations'):
                score += 0.5
                factors.append("Multiple locations")
        
        elif product == 'upcurve':
            # Active fundraising = higher need
            if org_data.get('has_donation_page'):
                score += 1.5
                factors.append("Has donation page")
            
            # Small nonprofits need help more
            revenue = org_data.get('revenue', 0)
            if revenue and revenue < 5000000:
                score += 1.0
                factors.append("Small nonprofit (<$5M)")
            
            # New nonprofits especially
            ruling_year = org_data.get('ruling_year', '')
            if ruling_year and int(ruling_year) > 2018:
                score += 0.5
                factors.append("Newer nonprofit")
        
        # Apply multipliers
        if is_nonprofit and rules.get('boost_if_nonprofit'):
            score *= rules['boost_if_nonprofit']
            factors.append("Nonprofit bonus applied")
        
        # Cap at max score
        final_score = min(score, rules['max_score'])
        
        return {
            'score': round(final_score, 1),
            'reason': '; '.join(factors) if factors else 'Low match'
        }
    
    def score_all_products(self, org_data: Dict) -> Dict:
        """Score a lead for all configured products"""
        
        scores = {}
        
        for product in self.product_rules.keys():
            result = self.score_for_product(org_data, product)
            scores[f'{product}_score'] = result['score']
            scores[f'{product}_reason'] = result['reason']
        
        # Determine best fit
        product_scores = {p: scores[f'{p}_score'] for p in self.product_rules.keys()}
        
        if product_scores:
            best_product = max(product_scores, key=product_scores.get)
            scores['best_product'] = best_product
            scores['best_score'] = product_scores[best_product]
        else:
            scores['best_product'] = 'none'
            scores['best_score'] = 0
        
        return scores
    
    # ========== MAIN ENRICHMENT ==========
    
    def enrich_lead(self, lead: Dict) -> Dict:
        """Complete enrichment pipeline for a single lead"""
        
        org_name = lead.get('company', '').strip()
        
        if not org_name:
            logger.warning(f"No company name for lead {lead.get('id', 'unknown')}")
            return lead
        
        logger.info(f"Enriching: {org_name}")
        
        # Start with original lead data
        enriched = lead.copy()
        
        # Check cache
        cache_key = hashlib.md5(org_name.encode()).hexdigest()
        if cache_key in self.cache:
            logger.debug(f"Using cached data for {org_name}")
            cached = self.cache[cache_key]
            enriched.update(cached)
            return enriched
        
        # 1. Check nonprofit status
        nonprofit_data = self.check_nonprofit_status(org_name, lead.get('ein'))
        enriched.update(nonprofit_data)
        
        # 2. Find and scrape website
        website_url = lead.get('website')
        if not website_url and lead.get('email'):
            # Try to derive from email domain
            email_domain = lead['email'].split('@')[-1]
            website_url = f"https://{email_domain}"
        
        if not website_url:
            # Try to find via Google
            search_results = self.google_search(f'"{org_name}" website')
            if search_results:
                website_url = search_results[0]['url']
        
        if website_url:
            website_data = self.scrape_organization_website(website_url)
            enriched.update(website_data)
        
        # 3. Google search for additional context
        search_results = self.google_search(f'"{org_name}" {lead.get("location", "")}')
        if search_results:
            enriched['search_results'] = search_results
            enriched['search_snippets'] = [r['snippet'] for r in search_results[:3]]
        
        # 4. Classify organization
        classification = self.classify_organization(enriched)
        enriched.update(classification)
        
        # 5. Score for all products
        scores = self.score_all_products(enriched)
        enriched.update(scores)
        
        # 6. Data quality assessment
        quality_score = 0
        quality_checks = {
            'has_company': bool(enriched.get('company')),
            'has_email': bool(enriched.get('email')),
            'has_phone': bool(enriched.get('phone') or enriched.get('phones')),
            'has_website': bool(enriched.get('website_url')),
            'has_mission': bool(enriched.get('mission_statement')),
            'nonprofit_verified': enriched.get('is_nonprofit') is not None,
            'org_classified': enriched.get('org_type') != 'unknown'
        }
        
        quality_score = sum(quality_checks.values()) / len(quality_checks)
        enriched['data_quality_score'] = round(quality_score, 2)
        enriched['data_quality_checks'] = quality_checks
        
        # 7. Add enrichment metadata
        enriched['enriched_at'] = datetime.now().isoformat()
        enriched['enrichment_version'] = '2.0'
        
        # Cache the enrichment (exclude original lead data)
        cache_data = {k: v for k, v in enriched.items() if k not in lead}
        self.cache[cache_key] = cache_data
        
        return enriched
    
    def process_batch(self, leads: List[Dict], max_workers: int = 5) -> List[Dict]:
        """Process multiple leads in parallel"""
        
        results = []
        total = len(leads)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_lead = {
                executor.submit(self.enrich_lead, lead): i 
                for i, lead in enumerate(leads)
            }
            
            for future in as_completed(future_to_lead):
                idx = future_to_lead[future]
                try:
                    result = future.result(timeout=30)
                    results.append(result)
                    
                    if (idx + 1) % 10 == 0:
                        logger.info(f"Progress: {idx + 1}/{total} leads enriched")
                        
                except Exception as e:
                    logger.error(f"Failed to enrich lead {idx}: {e}")
                    results.append(leads[idx])  # Keep original if enrichment fails
        
        return results


# Test function
if __name__ == "__main__":
    # Test with sample lead
    optimizer = LeadOptimizer()
    
    test_lead = {
        'company': 'Salvation Army',
        'email': 'info@salvationarmy.org',
        'location': 'Phoenix, AZ'
    }
    
    result = optimizer.enrich_lead(test_lead)
    print(json.dumps(result, indent=2))
