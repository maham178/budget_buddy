"""
LLM Handler - Supports Ollama (local) and vLLM (production)
"""

import requests
import json
import re
from datetime import datetime
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LLMHandler:
    """Multi-backend LLM Handler"""
    
    def __init__(self, backend: str = "ollama", **kwargs):
        self.backend = backend
        self.max_tokens = kwargs.get("max_tokens", 500)
        self.temperature = kwargs.get("temperature", 0.1)
        self.timeout = kwargs.get("timeout", 60)
        
        if backend == "ollama":
            self.api_url = kwargs.get("api_url", "http://localhost:11434/api/generate")
            self.model = kwargs.get("model", "phi3:mini")
            logger.info(f"Using Ollama backend with model: {self.model}")
        elif backend == "vllm":
            self.api_url = kwargs.get("api_url", "http://localhost:8000/v1/completions")
            self.api_key = kwargs.get("api_key", "dummy")
            logger.info(f"Using vLLM backend at {self.api_url}")
        else:
            logger.warning(f"Unknown backend: {backend}, using mock")
            self.backend = "mock"
    
    def extract_expenses(self, user_text: str) -> List[Dict]:
        """Extract expenses using configured backend"""
        
        if self.backend == "ollama":
            return self._extract_with_ollama(user_text)
        elif self.backend == "vllm":
            return self._extract_with_vllm(user_text)
        else:
            return self._extract_with_mock(user_text)
    
    def _extract_with_ollama(self, user_text: str) -> List[Dict]:
        """Extract expenses using Ollama"""
        
        prompt = f"""Extract expenses from this text: "{user_text}"

Return ONLY a JSON array. Each expense must have: 
- amount (number in rupees)
- category (groceries/transport/utilities/healthcare/dining/entertainment/shopping/other)
- date (YYYY-MM-DD format, use today {datetime.now().strftime('%Y-%m-%d')} if not specified)
- description (short text, max 30 chars)

Example: [{{"amount": 1500, "category": "groceries", "date": "2024-01-15", "description": "groceries"}}]

JSON array:"""

        try:
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": self.temperature,
                        "num_predict": self.max_tokens
                    }
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                text = result.get("response", "")
                
                # Extract JSON
                json_match = re.search(r'\[.*\]', text, re.DOTALL)
                if json_match:
                    expenses = json.loads(json_match.group())
                    for expense in expenses:
                        expense['raw_text'] = user_text
                        if 'description' not in expense:
                            expense['description'] = user_text[:30]
                    logger.info(f"Ollama extracted {len(expenses)} expense(s)")
                    return expenses
                else:
                    logger.warning(f"No JSON found in Ollama response")
                    return []
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return []
    
    def _extract_with_vllm(self, user_text: str) -> List[Dict]:
        """Extract expenses using vLLM"""
        
        prompt = f"""Extract expenses from this text: "{user_text}"

Return ONLY a JSON array. Each expense must have: 
- amount (number), category (groceries/transport/utilities/healthcare/dining/entertainment/shopping/other), 
- date (YYYY-MM-DD, use today {datetime.now().strftime('%Y-%m-%d')}), 
- description (short text)

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
                
                json_match = re.search(r'\[.*\]', text, re.DOTALL)
                if json_match:
                    expenses = json.loads(json_match.group())
                    for expense in expenses:
                        expense['raw_text'] = user_text
                        if 'description' not in expense:
                            expense['description'] = user_text[:30]
                    logger.info(f"vLLM extracted {len(expenses)} expense(s)")
                    return expenses
                else:
                    logger.warning(f"No JSON found in vLLM response")
                    return []
            else:
                logger.error(f"vLLM API error: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"vLLM error: {e}")
            return []
    
    def _extract_with_mock(self, user_text: str) -> List[Dict]:
        """Mock extraction for testing without LLM"""
        
        import re
        # Simple regex to extract numbers
        amounts = re.findall(r'(\d+)', user_text)
        
        if amounts:
            expenses = []
            for amount in amounts[:3]:  # Max 3 expenses
                # Guess category from text
                text_lower = user_text.lower()
                if any(word in text_lower for word in ['grocery', 'doodh', 'sabzi']):
                    category = 'groceries'
                elif any(word in text_lower for word in ['petrol', 'taxi', 'transport']):
                    category = 'transport'
                elif any(word in text_lower for word in ['bijli', 'electricity', 'gas']):
                    category = 'utilities'
                elif any(word in text_lower for word in ['dawa', 'medicine', 'doctor']):
                    category = 'healthcare'
                elif any(word in text_lower for word in ['dinner', 'lunch', 'food']):
                    category = 'dining'
                else:
                    category = 'other'
                
                expenses.append({
                    "amount": int(amount),
                    "category": category,
                    "date": datetime.now().strftime('%Y-%m-%d'),
                    "description": user_text[:30],
                    "raw_text": user_text
                })
            return expenses
        return []