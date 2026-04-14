import requests
import json
import re
from datetime import datetime
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LLMHandler:
    """LLM Handler for vLLM API"""
    
    def __init__(self, api_url: str, api_key: str = "dummy", timeout: int = 60):
        self.api_url = api_url
        self.api_key = api_key
        self.timeout = timeout
        self.max_tokens = 500
        self.temperature = 0.1
        logger.info(f"LLM Handler initialized with vLLM at {api_url}")
    
    def extract_expenses(self, user_text: str) -> List[Dict]:
        """Extract expenses using vLLM API"""
        
        prompt = f"""Extract expenses from this text: "{user_text}"

Return ONLY a JSON array. Each expense must have: amount (number), category (groceries/transport/utilities/healthcare/dining/entertainment/shopping/other), date (YYYY-MM-DD format, use today {datetime.now().strftime('%Y-%m-%d')} if not specified), description (short text)

Example: [{{"amount": 1500, "category": "groceries", "date": "2024-01-15", "description": "groceries"}}]

JSON array:"""

        try:
            response = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "prompt": prompt,
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature,
                    "stop": ["```", "\n\n"]
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                text = result.get('choices', [{}])[0].get('text', '')
                
                # Extract JSON array
                json_match = re.search(r'\[.*\]', text, re.DOTALL)
                if json_match:
                    expenses = json.loads(json_match.group())
                    for expense in expenses:
                        expense['raw_text'] = user_text
                        if 'description' not in expense:
                            expense['description'] = user_text[:50]
                    logger.info(f"Extracted {len(expenses)} expense(s)")
                    return expenses
                else:
                    logger.warning(f"No JSON found in response")
                    return []
            else:
                logger.error(f"vLLM API error: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"LLM API Error: {e}")
            return []