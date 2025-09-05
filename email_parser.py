import re
import html
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup
import streamlit as st

class OrderEmailParser:
    """Parser for extracting order information from emails"""
    
    def __init__(self):
        # Common order-related patterns
        self.order_patterns = {
            'order_id': [
                # Order number patterns
                r'order\s*(?:#|number|id)?\s*:?\s*([a-zA-Z0-9\-_]{4,20})',
                r'order\s+([a-zA-Z0-9\-_]{6,20})',
                r'order\s*#\s*([a-zA-Z0-9\-_]{4,20})',
                
                # Tracking patterns
                r'tracking\s*(?:number|id)?\s*:?\s*([a-zA-Z0-9\-_]{6,25})',
                r'track\s*(?:number|id)?\s*:?\s*([a-zA-Z0-9\-_]{6,25})',
                
                # Confirmation patterns
                r'confirmation\s*(?:number|id)?\s*:?\s*([a-zA-Z0-9\-_]{4,20})',
                r'reference\s*(?:number|id)?\s*:?\s*([a-zA-Z0-9\-_]{4,20})',
                
                # Purchase patterns
                r'purchase\s*(?:number|id)?\s*:?\s*([a-zA-Z0-9\-_]{4,20})',
                r'transaction\s*(?:id|number)?\s*:?\s*([a-zA-Z0-9\-_]{4,20})',
                
                # Hash patterns
                r'#([a-zA-Z0-9\-_]{6,20})',
                
                # Long numeric sequences (common for order IDs)
                r'([0-9]{8,15})',
                
                # Amazon specific patterns
                r'([0-9]{3}-[0-9]{7}-[0-9]{7})',  # Standard Amazon format
                r'([A-Z][0-9]{2}-[0-9]{7}-[0-9]{7})',  # Amazon with letter prefix
                r'(D[0-9]{2}-[0-9]{7}-[0-9]{7})',  # Amazon D01 format
                r'([0-9]{14})',  # Amazon 14-digit format
                
                # Myntra specific patterns
                r'(MYN[0-9]{8,12})',  # Myntra order format
                r'([0-9]{10,12})',  # Myntra numeric orders
                
                # Generic patterns with common separators
                r'([A-Z]{2,4}[0-9]{6,12})',
                r'([0-9]{6,10}-[0-9]{6,10})',
                r'([A-Z0-9]{8,15})',
            ],
            'status': [
                r'(shipped|delivered|out for delivery|in transit|processing|confirmed|cancelled|pending)',
                r'status:\s*([^<>\n]+)',
                r'order\s+status:\s*([^<>\n]+)',
            ],
            'delivery_date': [
                r'delivery\s+(?:date|by):\s*([^<>\n]+)',
                r'expected\s+(?:delivery|arrival):\s*([^<>\n]+)',
                r'estimated\s+(?:delivery|arrival):\s*([^<>\n]+)',
                r'will\s+(?:arrive|be delivered)\s+(?:by|on)?\s*([^<>\n]+)',
            ]
        }
        
        # Common seller identifiers
        self.seller_patterns = [
            r'from\s+(.+?)(?:\s+<|$)',
            r'@([a-zA-Z0-9\-_.]+)',
        ]
        
        # Date parsing patterns
        self.date_patterns = [
            r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
            r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
            r'([a-zA-Z]+ \d{1,2}, \d{4})',
            r'(\d{1,2} [a-zA-Z]+ \d{4})',
        ]
    
    def parse_email(self, email_data: Dict) -> Optional[Dict]:
        """Parse an email for order information"""
        try:
            # Check if email is order-related
            if not self._is_order_email(email_data):
                # Debug: Log why email was rejected
                subject = email_data.get('subject', '')[:100]
                return None
            
            # Extract information
            seller = self._extract_seller(email_data)
            order_id = self._extract_order_id(email_data)
            status = self._extract_status(email_data)
            delivery_date = self._extract_delivery_date(email_data)
            
            # Generate order ID if none found using email metadata
            if not order_id:
                email_date = email_data.get('date', datetime.now())
                subject = email_data.get('subject', '')[:20].replace(' ', '')
                date_str = email_date.strftime('%Y%m%d') if hasattr(email_date, 'strftime') else '20240101'
                order_id = f"ORD-{date_str}-{abs(hash(subject)) % 10000:04d}"
            
            # Return order if we have meaningful information
            # Must have either seller info or identifiable order content
            has_seller = seller and seller != 'Unknown'
            has_status = status and status.lower() not in ['', 'unknown']
            
            if has_seller or has_status or order_id:
                return {
                    'seller': seller or 'Unknown',
                    'order_id': order_id,
                    'status': status or 'Confirmed',
                    'delivery_date': delivery_date,
                    'email_subject': email_data.get('subject', ''),
                    'email_date': email_data.get('date', datetime.now())
                }
            
            return None
            
        except Exception as e:
            st.warning(f"Error parsing email: {str(e)}")
            return None
    
    def _is_order_email(self, email_data: Dict) -> bool:
        """Check if email is an actual order confirmation (not promotional)"""
        subject = email_data.get('subject', '').lower()
        body = email_data.get('body', '').lower()
        sender = email_data.get('sender', '').lower()
        
        # Strong indicators of actual order confirmations
        order_confirmation_keywords = [
            'order confirmation', 'purchase confirmation', 'your order',
            'order number', 'tracking number', 'shipment confirmation',
            'delivery confirmation', 'order receipt', 'thank you for your order',
            'order placed', 'order summary', 'order details'
        ]
        
        # Promotional/marketing indicators to exclude
        promotional_keywords = [
            'unsubscribe', 'promotional', 'sale', 'deal', 'offer', 
            'discount', 'newsletter', 'marketing', 'advertisement',
            'limited time', 'save now', 'special offer', 'free shipping',
            'browse our', 'check out our', 'new arrivals'
        ]
        
        text_to_check = f"{subject} {body} {sender}"
        
        # Must have order confirmation keywords
        has_order_keywords = any(keyword in text_to_check for keyword in order_confirmation_keywords)
        
        # Must not have promotional keywords
        has_promotional = any(keyword in text_to_check for keyword in promotional_keywords)
        
        # Additional check: look for actual order/tracking numbers
        has_order_numbers = bool(re.search(r'order\s*(?:#|number|id)?\s*:?\s*[a-zA-Z0-9\-_]{4,}', text_to_check))
        has_tracking_numbers = bool(re.search(r'tracking\s*(?:number|id)?\s*:?\s*[a-zA-Z0-9\-_]{6,}', text_to_check))
        
        # Return true only if it looks like a real order confirmation
        return (has_order_keywords and not has_promotional) or has_order_numbers or has_tracking_numbers
    
    def _extract_seller(self, email_data: Dict) -> str:
        """Extract seller information from email"""
        sender = email_data.get('sender', '')
        
        # Clean up sender email
        if '<' in sender and '>' in sender:
            # Extract name before email
            name_match = re.search(r'^([^<]+)', sender)
            if name_match:
                seller_name = name_match.group(1).strip().strip('"')
                if seller_name and not seller_name.startswith('=?'):
                    return seller_name
            
            # Extract domain from email
            email_match = re.search(r'<([^@]+@([^>]+))>', sender)
            if email_match:
                domain = email_match.group(2)
                return self._clean_domain(domain)
        
        # Extract domain from plain email
        if '@' in sender:
            domain = sender.split('@')[-1].strip('>')
            return self._clean_domain(domain)
        
        return sender or 'Unknown'
    
    def _clean_domain(self, domain: str) -> str:
        """Clean and format domain name"""
        # Remove common prefixes and suffixes
        domain = re.sub(r'^(www\.|mail\.|noreply\.|no-reply\.)', '', domain)
        domain = re.sub(r'\.(com|org|net|co\.uk|in)$', '', domain)
        
        # Capitalize first letter
        return domain.title() if domain else 'Unknown'
    
    def _extract_order_id(self, email_data: Dict) -> Optional[str]:
        """Extract order ID from email with comprehensive fallback methods"""
        subject = email_data.get('subject', '')
        body = email_data.get('body', '')
        sender = email_data.get('sender', '').lower()
        text = f"{subject} {body}"
        
        # Clean HTML if present
        if '<' in text and '>' in text:
            soup = BeautifulSoup(text, 'html.parser')
            text = soup.get_text()
        
        # Retailer-specific extraction
        if 'amazon' in sender:
            return self._extract_amazon_order_id(text)
        elif 'myntra' in sender:
            return self._extract_myntra_order_id(text)
        
        # Try primary patterns first
        for pattern in self.order_patterns['order_id']:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Filter out common false positives
                if (len(match) >= 4 and 
                    not match.lower() in ['order', 'number', 'confirmation', 'tracking', 'purchase'] and
                    (not match.isdigit() or len(match) >= 8)):  # Allow long numeric sequences
                    return match.strip()
        
        # Fallback 1: Look for any sequence that looks like an identifier
        fallback_patterns = [
            r'([A-Z0-9]{6,})',  # Any uppercase/number combo
            r'([0-9]{6,})',     # Any 6+ digit number
            r'([A-Z]{2,}[0-9]{3,})',  # Letters followed by numbers
            r'([0-9]{3,}[A-Z]{2,})',  # Numbers followed by letters
        ]
        
        for pattern in fallback_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if len(match) >= 6:
                    return match.strip()
        
        # Fallback 2: Extract from subject line specifically
        subject_match = re.search(r'#([A-Z0-9\-_]{4,})', subject)
        if subject_match:
            return subject_match.group(1)
        
        # Fallback 3: Look for numbers in subject
        subject_numbers = re.findall(r'([0-9]{4,})', subject)
        if subject_numbers:
            return subject_numbers[0]
        
        # Fallback 4: Generate ID from email metadata
        sender = email_data.get('sender', '')
        email_date = email_data.get('date')
        if sender and email_date:
            # Extract domain
            domain_match = re.search(r'@([^>\s]+)', sender)
            if domain_match:
                domain = domain_match.group(1).split('.')[0].upper()[:4]
                date_str = email_date.strftime('%m%d') if hasattr(email_date, 'strftime') else '0000'
                return f"{domain}{date_str}"
        
        return None
    
    def _extract_amazon_order_id(self, text: str) -> Optional[str]:
        """Extract Amazon-specific order IDs"""
        amazon_patterns = [
            r'order\s*#?\s*([0-9]{3}-[0-9]{7}-[0-9]{7})',  # Standard Amazon
            r'order\s*#?\s*([A-Z][0-9]{2}-[0-9]{7}-[0-9]{7})',  # Amazon with prefix
            r'order\s*#?\s*([D][0-9]{2}-[0-9]{7}-[0-9]{7})',  # Amazon D01 format
            r'([0-9]{3}-[0-9]{7}-[0-9]{7})',  # Standalone format
            r'([A-Z][0-9]{2}-[0-9]{7}-[0-9]{7})',
            r'([D][0-9]{2}-[0-9]{7}-[0-9]{7})',
            r'order\s*#?\s*([0-9]{14})',  # 14-digit Amazon orders
            r'([0-9]{14})',  # Standalone 14-digit
        ]
        
        for pattern in amazon_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                return matches[0].strip()
        return None
    
    def _extract_myntra_order_id(self, text: str) -> Optional[str]:
        """Extract Myntra-specific order IDs"""
        myntra_patterns = [
            r'order\s*(?:id|number|#)?\s*:?\s*([0-9]{10,12})',  # Myntra order numbers
            r'order\s*(?:id|number|#)?\s*:?\s*(MYN[0-9]{8,12})',  # Myntra MYN format
            r'([0-9]{10,12})',  # Standalone 10-12 digit numbers
            r'(MYN[0-9]{8,12})',  # Standalone MYN format
        ]
        
        for pattern in myntra_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Validate it's likely a Myntra order (10+ digits)
                order_id = matches[0].strip()
                if len(order_id) >= 10:
                    return order_id
        return None
    
    def _extract_status(self, email_data: Dict) -> Optional[str]:
        """Extract order status from email"""
        text = f"{email_data.get('subject', '')} {email_data.get('body', '')}"
        
        # Clean HTML if present
        if '<' in text and '>' in text:
            soup = BeautifulSoup(text, 'html.parser')
            text = soup.get_text()
        
        # Try each pattern
        for pattern in self.order_patterns['status']:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                status = matches[0].strip()
                if isinstance(status, tuple):
                    status = status[0]
                return status.title()
        
        # Check subject for status keywords
        subject = email_data.get('subject', '').lower()
        status_keywords = {
            'shipped': 'Shipped',
            'delivered': 'Delivered',
            'confirmed': 'Confirmed',
            'processing': 'Processing',
            'cancelled': 'Cancelled',
            'dispatched': 'Shipped',
            'out for delivery': 'Out for Delivery'
        }
        
        for keyword, status in status_keywords.items():
            if keyword in subject:
                return status
        
        return None
    
    def _extract_delivery_date(self, email_data: Dict) -> Optional[datetime]:
        """Extract delivery date from email"""
        text = f"{email_data.get('subject', '')} {email_data.get('body', '')}"
        
        # Clean HTML if present
        if '<' in text and '>' in text:
            soup = BeautifulSoup(text, 'html.parser')
            text = soup.get_text()
        
        # Try delivery date patterns
        for pattern in self.order_patterns['delivery_date']:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                date_str = match.strip()
                parsed_date = self._parse_date_string(date_str)
                if parsed_date:
                    return parsed_date
        
        # Look for any dates in the email
        for pattern in self.date_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                parsed_date = self._parse_date_string(match)
                if parsed_date and parsed_date > datetime.now():
                    return parsed_date
        
        return None
    
    def _parse_date_string(self, date_str: str) -> Optional[datetime]:
        """Parse various date string formats"""
        if not date_str:
            return None
        
        # Clean the date string
        date_str = re.sub(r'[^\w\s\-/,:]', '', date_str).strip()
        
        # Common date formats to try
        formats = [
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%Y-%m-%d',
            '%m-%d-%Y',
            '%d-%m-%Y',
            '%B %d, %Y',
            '%b %d, %Y',
            '%d %B %Y',
            '%d %b %Y',
            '%Y/%m/%d',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        # Try to parse relative dates
        today = datetime.now()
        if 'today' in date_str.lower():
            return today
        elif 'tomorrow' in date_str.lower():
            return today + timedelta(days=1)
        elif 'monday' in date_str.lower():
            days_ahead = 0 - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return today + timedelta(days=days_ahead)
        # Add more weekday parsing as needed
        
        return None
