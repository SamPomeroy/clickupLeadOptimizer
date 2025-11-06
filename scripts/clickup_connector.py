#!/usr/bin/env python3
"""
ClickUp Integration for Lead Optimizer
Handles export from and import to ClickUp CRM
"""

import requests
import pandas as pd
import json
import time
from typing import Dict, List, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ClickUpConnector:
    """Manages all ClickUp CRM operations"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            'Authorization': api_key,
            'Content-Type': 'application/json'
        }
        self.base_url = 'https://api.clickup.com/api/v2'
        logger.info("ClickUp connector initialized")
    
    def test_connection(self) -> bool:
        """Test if API key works"""
        try:
            url = f'{self.base_url}/user'
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                user = response.json()['user']
                logger.info(f"Connected as: {user['username']}")
                return True
            else:
                logger.error(f"Connection failed: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def get_list_info(self, list_id: str) -> Dict:
        """Get information about a list"""
        url = f'{self.base_url}/list/{list_id}'
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to get list info: {response.text}")
            return {}
    
    def export_leads(self, list_id: str) -> pd.DataFrame:
        """Export all tasks (leads) from a ClickUp list"""
        
        logger.info(f"Exporting leads from list {list_id}")
        
        url = f'{self.base_url}/list/{list_id}/task'
        params = {
            'include_closed': True,
            'page': 0,
            'include_custom_fields': True
        }
        
        all_tasks = []
        
        while True:
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code != 200:
                logger.error(f"Error fetching tasks: {response.status_code}")
                break
            
            data = response.json()
            tasks = data.get('tasks', [])
            
            if not tasks:
                break
            
            all_tasks.extend(tasks)
            logger.info(f"Fetched {len(all_tasks)} tasks so far...")
            
            if len(tasks) < 100:  # ClickUp max is 100 per page
                break
            
            params['page'] += 1
            time.sleep(0.5)  # Rate limiting
        
        logger.info(f"Total tasks fetched: {len(all_tasks)}")
        
        # Convert to structured format
        leads = []
        for task in all_tasks:
            lead = self.parse_task_to_lead(task)
            leads.append(lead)
        
        df = pd.DataFrame(leads)
        logger.info(f"Created DataFrame with {len(df)} leads and {len(df.columns)} columns")
        
        return df
    
    def parse_task_to_lead(self, task: Dict) -> Dict:
        """Parse ClickUp task into lead format"""
        
        # Extract custom fields
        custom_fields = {}
        for cf in task.get('custom_fields', []):
            name = cf.get('name', '').strip()
            
            # Clean emoji from field names
            import re
            clean_name = re.sub(r'[^\w\s-]', '', name).strip()
            if not clean_name:
                clean_name = name
            
            # Get value based on type
            field_type = cf.get('type')
            
            if field_type == 'drop_down':
                options = cf.get('type_config', {}).get('options', [])
                selected = cf.get('value')
                if selected is not None and options:
                    for opt in options:
                        if opt.get('orderindex') == selected:
                            custom_fields[clean_name] = opt.get('name')
                            break
            elif field_type == 'checkbox':
                custom_fields[clean_name] = cf.get('value', {}).get('checked', False)
            elif field_type == 'number':
                custom_fields[clean_name] = cf.get('value')
            elif field_type == 'currency':
                custom_fields[clean_name] = cf.get('value')
            elif field_type == 'text' or field_type == 'short_text':
                custom_fields[clean_name] = cf.get('value')
            elif field_type == 'email':
                custom_fields[clean_name] = cf.get('value')
            elif field_type == 'phone':
                custom_fields[clean_name] = cf.get('value')
            elif field_type == 'url':
                custom_fields[clean_name] = cf.get('value')
            elif field_type == 'date':
                date_val = cf.get('value')
                if date_val:
                    # Convert milliseconds to datetime
                    from datetime import datetime
                    custom_fields[clean_name] = datetime.fromtimestamp(int(date_val)/1000).isoformat()
            else:
                # Default to string value
                custom_fields[clean_name] = cf.get('value') or cf.get('string')
        
        # Build lead record
        lead = {
            'task_id': task.get('id'),
            'name': task.get('name'),  # Usually the contact name
            'status': task.get('status', {}).get('status'),
            'created_date': task.get('date_created'),
            'updated_date': task.get('date_updated'),
            'description': task.get('description', ''),
            
            # Try to map common fields
            'company': custom_fields.get('Company', custom_fields.get('Organization', '')),
            'first_name': custom_fields.get('First Name', ''),
            'last_name': custom_fields.get('Last Name', ''),
            'title': custom_fields.get('Title', custom_fields.get('Position', '')),
            'email': custom_fields.get('Email', ''),
            'phone': custom_fields.get('Phone', ''),
            'website': custom_fields.get('Website', ''),
            'linkedin': custom_fields.get('LinkedIn', ''),
            'location': custom_fields.get('Location', ''),
            'revenue': custom_fields.get('Revenue', ''),
            'ein': custom_fields.get('EIN', ''),
            'business_mission': custom_fields.get('Business Mission Statement', ''),
            'business_context': custom_fields.get('Business Context', ''),
            
            # Include all custom fields
            **custom_fields
        }
        
        return lead
    
    def create_enrichment_fields(self, list_id: str) -> Dict[str, str]:
        """Create custom fields for enrichment data"""
        
        logger.info("Creating custom fields for enrichment data...")
        
        url = f'{self.base_url}/list/{list_id}/field'
        
        fields = [
            {
                'name': '🏢 Organization Type',
                'type': 'drop_down',
                'type_config': {
                    'options': [
                        {'name': 'Halfway House', 'color': 0},
                        {'name': 'Recovery Center', 'color': 1},
                        {'name': 'Sober Living', 'color': 2},
                        {'name': 'Group Home', 'color': 3},
                        {'name': 'Transitional Housing', 'color': 4},
                        {'name': 'Shelter', 'color': 5},
                        {'name': 'Mental Health', 'color': 6},
                        {'name': 'Faith Based', 'color': 7},
                        {'name': 'Community Service', 'color': 8},
                        {'name': 'Nonprofit General', 'color': 9},
                        {'name': 'Unknown', 'color': 10}
                    ]
                }
            },
            {
                'name': '✅ Nonprofit Verified',
                'type': 'checkbox'
            },
            {
                'name': '📊 Compass Score',
                'type': 'number'
            },
            {
                'name': '💰 Upcurve Score',
                'type': 'number'
            },
            {
                'name': '🎯 Best Product Fit',
                'type': 'drop_down',
                'type_config': {
                    'options': [
                        {'name': 'Compass', 'color': 0},
                        {'name': 'Upcurve', 'color': 1},
                        {'name': 'Both High', 'color': 2},
                        {'name': 'Neither', 'color': 3}
                    ]
                }
            },
            {
                'name': '📈 Data Quality',
                'type': 'number'
            },
            {
                'name': '🔍 Enrichment Notes',
                'type': 'text'
            },
            {
                'name': '📅 Last Enriched',
                'type': 'date'
            },
            {
                'name': '💵 Has Donation Page',
                'type': 'checkbox'
            },
            {
                'name': '🏛️ EIN Number',
                'type': 'short_text'
            }
        ]
        
        field_mapping = {}
        
        for field in fields:
            try:
                response = requests.post(url, headers=self.headers, json=field)
                
                if response.status_code == 200:
                    field_id = response.json()['id']
                    field_mapping[field['name']] = field_id
                    logger.info(f"Created field: {field['name']}")
                    
                elif 'already exists' in response.text.lower():
                    logger.info(f"Field already exists: {field['name']}")
                    # We'd need to fetch existing field ID here
                    
                else:
                    logger.error(f"Failed to create {field['name']}: {response.text}")
                    
            except Exception as e:
                logger.error(f"Error creating field {field['name']}: {e}")
            
            time.sleep(0.5)  # Rate limiting
        
        return field_mapping
    
    def update_lead(self, task_id: str, enrichment_data: Dict, field_mapping: Dict) -> bool:
        """Update a single lead with enrichment data"""
        
        url = f'{self.base_url}/task/{task_id}'
        
        custom_fields = []
        
        # Map enrichment data to custom field updates
        field_map = {
            'org_type': '🏢 Organization Type',
            'is_nonprofit': '✅ Nonprofit Verified',
            'compass_score': '📊 Compass Score',
            'upcurve_score': '💰 Upcurve Score',
            'best_product': '🎯 Best Product Fit',
            'data_quality_score': '📈 Data Quality',
            'has_donation_page': '💵 Has Donation Page',
            'ein': '🏛️ EIN Number'
        }
        
        for data_key, field_name in field_map.items():
            if data_key in enrichment_data and field_name in field_mapping:
                value = enrichment_data[data_key]
                
                # Format value based on field type
                if data_key == 'org_type':
                    # Map to dropdown option
                    type_map = {
                        'halfway_house': 'Halfway House',
                        'recovery_center': 'Recovery Center',
                        'sober_living': 'Sober Living',
                        'group_home': 'Group Home',
                        'transitional_housing': 'Transitional Housing',
                        'shelter': 'Shelter',
                        'mental_health': 'Mental Health',
                        'faith_based': 'Faith Based',
                        'community_service': 'Community Service',
                        'nonprofit_general': 'Nonprofit General',
                        'unknown': 'Unknown'
                    }
                    value = type_map.get(value, 'Unknown')
                
                elif data_key == 'best_product':
                    # Map to dropdown option
                    if enrichment_data.get('compass_score', 0) > 7 and enrichment_data.get('upcurve_score', 0) > 7:
                        value = 'Both High'
                    elif value == 'compass':
                        value = 'Compass'
                    elif value == 'upcurve':
                        value = 'Upcurve'
                    else:
                        value = 'Neither'
                
                custom_fields.append({
                    'id': field_mapping[field_name],
                    'value': value
                })
        
        # Add enrichment notes
        if '🔍 Enrichment Notes' in field_mapping:
            notes = f"Enriched on {datetime.now().strftime('%Y-%m-%d')}\n"
            notes += f"Compass: {enrichment_data.get('compass_reason', 'N/A')}\n"
            notes += f"Upcurve: {enrichment_data.get('upcurve_reason', 'N/A')}"
            
            custom_fields.append({
                'id': field_mapping['🔍 Enrichment Notes'],
                'value': notes
            })
        
        # Add last enriched date
        if '📅 Last Enriched' in field_mapping:
            custom_fields.append({
                'id': field_mapping['📅 Last Enriched'],
                'value': int(time.time() * 1000)  # ClickUp wants milliseconds
            })
        
        # Update the task
        if custom_fields:
            data = {'custom_fields': custom_fields}
            
            try:
                response = requests.put(url, headers=self.headers, json=data)
                
                if response.status_code == 200:
                    return True
                else:
                    logger.error(f"Failed to update task {task_id}: {response.text}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error updating task {task_id}: {e}")
                return False
        
        return True
    
    def import_enriched_data(self, enriched_df: pd.DataFrame, list_id: str) -> Dict:
        """Import enriched data back to ClickUp"""
        
        # First, ensure custom fields exist
        field_mapping = self.create_enrichment_fields(list_id)
        
        if not field_mapping:
            logger.error("Failed to create custom fields")
            return {'success': False, 'message': 'Failed to create custom fields'}
        
        total = len(enriched_df)
        success_count = 0
        failed_ids = []
        
        logger.info(f"Starting import of {total} enriched leads...")
        
        for idx, row in enriched_df.iterrows():
            task_id = row.get('task_id')
            
            if not task_id:
                logger.warning(f"No task ID for row {idx}")
                failed_ids.append(f"row_{idx}")
                continue
            
            # Update the task
            if self.update_lead(task_id, row.to_dict(), field_mapping):
                success_count += 1
            else:
                failed_ids.append(task_id)
            
            # Progress update
            if (idx + 1) % 10 == 0:
                logger.info(f"Import progress: {idx + 1}/{total} ({(idx + 1) * 100 // total}%)")
            
            time.sleep(0.5)  # Rate limiting
        
        logger.info(f"Import complete: {success_count}/{total} successful")
        
        return {
            'success': True,
            'total': total,
            'successful': success_count,
            'failed': len(failed_ids),
            'failed_ids': failed_ids
        }

# Test function
if __name__ == "__main__":
    # Test connection
    API_KEY = "pk_YOUR_API_KEY"
    connector = ClickUpConnector(API_KEY)
    
    if connector.test_connection():
        print("Connection successful!")
